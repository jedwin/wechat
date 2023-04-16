# views.py

from django.shortcuts import HttpResponse
from django.views.decorators.csrf import csrf_exempt
import hashlib
from . import receive
from . import reply
from random import sample
# import opencc
from .common_functions import *
from .resource_manage import *
from .models import *

Pre_Set_Reply = '请先输入从客服处获得的密码，注意区分大小写'
auto_reply_for_non_player_file = 'data/自动回复内容列表.csv'
AUTO_REPLY_KEYWORD_NAME = '邀请加入'  # 对于未输入密码的玩家对应的关键词，通过修改这个关键词的设置，可以改变对为鉴权玩家发送对内容

# django默认开启了csrf防护，@csrf_exempt是去掉防护
# 微信服务器进行参数交互，主要是和微信服务器进行身份的验证

@csrf_exempt
def check_signature(request, app_en_name):
    my_app = WechatApp.objects.get(en_name=app_en_name)
    if request.method == "GET":
        print("request: ", request)
        # 接受微信服务器get请求发过来的参数
        # 将参数list中排序合成字符串，再用sha1加密得到新的字符串与微信发过来的signature对比，
        # 如果相同就返回echostr给服务器，校验通过
        # ISSUES: TypeError: '<' not supported between instances of 'NoneType' and 'str'
        # 解决方法：当获取的参数值为空是传空，而不是传None
        signature = request.GET.get('signature', '')
        timestamp = request.GET.get('timestamp', '')
        nonce = request.GET.get('nonce', '')
        echostr = request.GET.get('echostr', '')
        # 微信公众号处配置的token
        token = my_app.acc_token

        hashlist = [token, timestamp, nonce]
        hashlist.sort()
        print("[token, timestamp, nonce]: ", hashlist)

        hashstr = ''.join([s for s in hashlist]).encode('utf-8')
        print('hashstr before sha1: ', hashstr)

        hashstr = hashlib.sha1(hashstr).hexdigest()
        print('hashstr sha1: ', hashstr)

        if hashstr == signature:
            return HttpResponse(echostr)
        else:
            return HttpResponse("signature not correct")
    elif request.method == "POST":
        # print(request)
        otherContent = autoreply(request, app_en_name)
        return HttpResponse(otherContent)
    else:
        # request方法不正确  print("你的方法不正确....")
        return HttpResponse('seccuss')


def autoreply(request, app_en_name):
    try:
        webData = request.body
        my_app = WechatApp.objects.get(en_name=app_en_name)
        recMsg = receive.parse_xml(webData)
        active_games = [x.name for x in WechatGame.objects.filter(app=my_app, is_active=True)]
        # print(f'active_games: {active_games}')
        if isinstance(recMsg, receive.Msg):
            toUser = recMsg.FromUserName
            open_id = toUser
            fromUser = recMsg.ToUserName
            cur_game, cur_player, cur_gamedata = check_player(my_app=my_app, open_id=open_id)
            cur_keyword = cur_gamedata.cur_keyword
            cmd_list = cur_gamedata.cmd_list()

            if recMsg.MsgType == 'text':
                content = recMsg.Content.decode('utf-8')
                app_keyword_list = [x.keyword for x in AppKeyword.objects.filter(app=my_app)]
                # 首先检查是否输入了APP级关键词
                if content in app_keyword_list:
                    cmd_list.append(content)
                    try:
                        my_app_keyword = AppKeyword.objects.get(app=my_app, keyword=content)
                        replyMsg = my_app_keyword.reply_msg(toUser=toUser, fromUser=fromUser)
                    except ObjectDoesNotExist:
                        text_content = f'APP级关键词{content}出错，请联系管理员'
                        replyMsg = reply.TextMsg(toUser, fromUser, text_content)
                # 然后检查是否已完成鉴权
                elif cur_player.is_audit:
                    # 首先检查是否输入了游戏名称，切换游戏
                    if content in active_games:
                        cur_player.cur_game_name = content
                        cur_player.save()
                        cur_game = WechatGame.objects.get(app=my_app, name=content)
                        check_gamedata = WechatGameData.objects.filter(player=cur_player, game=cur_game)
                        if len(check_gamedata) > 0:
                            cur_gamedata = check_gamedata[0]
                        else:
                            # 这个玩家切换到新游戏，帮ta新建档案
                            cur_keyword = GameKeyword.objects.get(game=cur_game, keyword=keyword_start)
                            cur_gamedata = WechatGameData(player=cur_player, game=cur_game,
                                                          cur_keyword=cur_keyword,
                                                          data_dict=dict(), cmd_str=list())
                            cur_gamedata.save()
                        # cmd_list.append(content)
                        cur_keyword = cur_gamedata.cur_keyword
                        if cur_keyword:
                            cur_process = cur_keyword.keyword
                        else:

                            cur_process = keyword_start

                        replyMsg = update_process_and_reply(app=my_app, cur_game=cur_game,
                                                            cur_process=cur_process,
                                                            cur_gamedata=cur_gamedata, toUser=toUser,
                                                            fromUser=fromUser)
                    # 用户不是切换游戏
                    else:
                        # 判断用户当前所在的游戏
                        user_cur_game_name = cur_player.cur_game_name
                        # print(f'cur_game: {cur_game}')
                        if len(user_cur_game_name) > 0:
                            if user_cur_game_name in active_games:
                                keyword_list = [x.keyword for x in GameKeyword.objects.filter(game=cur_game)]

                                # 输入了【提示】指令，不用更新进度
                                if content == keyword_hint:
                                    cmd_list.append(content)
                                    replyMsg = cur_keyword.reply_msg(type='hint', toUser=toUser, fromUser=fromUser)

                                # 输入了显示当前卡进度指令，不用更新进度
                                elif content == keyword_card:
                                    cmd_list.append(content)
                                    replyMsg = cur_keyword.reply_msg(type='card', toUser=toUser, fromUser=fromUser)

                                # 输入了重新开始游戏指令
                                elif content == keyword_restart:
                                    cmd_list.append(content)
                                    cur_process = keyword_start
                                    replyMsg = update_process_and_reply(app=my_app, cur_game=cur_game,
                                                                        cur_process=cur_process,
                                                                        cur_gamedata=cur_gamedata, toUser=toUser,
                                                                        fromUser=fromUser)
                                # 输入了返回指令
                                elif content == keyword_go_back:
                                    cmd_list.append(content)
                                    # try:
                                    #     cur_keyword = cur_gamedata.backward(keyword_when_fail=keyword_start)
                                    #     cur_process = cur_keyword.keyword
                                    #     replyMsg = update_process_and_reply(app=my_app, cur_game=cur_game,
                                    #                                         cur_process=cur_process,
                                    #                                         cur_gamedata=cur_gamedata, toUser=toUser,
                                    #                                         fromUser=fromUser)
                                    # except KeyError:
                                    #     # 无法返回
                                    text_content = f'世间没有后悔药，现在已经无法返回了，确实要重来的话，请输入【{keyword_restart}】吧'
                                    replyMsg = reply.TextMsg(toUser, fromUser, text_content)

                                # 输入了已配置的关键词
                                elif content in keyword_list:
                                    cmd_list.append(content)
                                    # print(f'cur_keyword: {cur_keyword}')
                                    # print(f'option_list: {option_list}')
                                    # 按顺序答对了
                                    if content in cur_keyword.option_list():
                                        # 更新进度到当前关键词
                                        cur_process = content
                                        replyMsg = update_process_and_reply(app=my_app, cur_game=cur_game,
                                                                            cur_process=cur_process,
                                                                            cur_gamedata=cur_gamedata, toUser=toUser,
                                                                            fromUser=fromUser)
                                    # 答对了关键词，但没按顺序来
                                    else:
                                        text_content = f'不要着急，解题要一步步来哦，请按题目内容回答。'
                                        replyMsg = reply.TextMsg(toUser, fromUser, text_content)

                                # 输入了不相关的词语
                                else:
                                    cmd_list.append(content)
                                    my_error_auto_replys = list(ErrorAutoReply.objects.filter(is_active=True))
                                    if len(my_error_auto_replys) > 0:
                                        choose_reply = sample(my_error_auto_replys, 1)[0]
                                        replyMsg = choose_reply.reply_msg(toUser=toUser, fromUser=fromUser)
                                    else:
                                        text_content = f'{error_reply_default}'
                                        replyMsg = reply.TextMsg(toUser, fromUser, text_content)
                            else:
                                text_content = f'你曾经玩的游戏当前已不再进行，请选择新的游戏：【{"】、【".join(active_games)}】'
                                replyMsg = reply.TextMsg(toUser, fromUser, text_content)
                        else:
                            # cur_game_name is blank
                            print('cur_game_name is blank')
                            text_content = f'请选择需要进行的游戏：【{"】、【".join(active_games)}】'
                            replyMsg = reply.TextMsg(toUser, fromUser, text_content)
                else:
                    # 还没有通过鉴权
                    user_id = auth_user(password=content)
                    if user_id:
                        cur_player.name = user_id
                        cur_player.is_audit = True
                        cur_player.cur_game_name = my_app.cur_game_name
                        cur_player.save()
                        text_content = f'''欢迎您进入游戏！\n请输入【{keyword_start}】，在游戏过程中可以随时输入【{keyword_hint}】获得下一步的指引'''

                        replyMsg = reply.TextMsg(toUser, fromUser, text_content)
                    else:
                        # 没有输对密码
                        # auto_reply_dict = load_auto_reply_settings(auto_reply_for_non_player_file)
                        # auto_reply_dict {编号: [回复类型, 回复文件名称或内容, 视频描述]}
                        check_keyword = GameKeyword.objects.filter(game=cur_game, keyword=AUTO_REPLY_KEYWORD_NAME)
                        if len(check_keyword) > 0:
                            cur_keyword = check_keyword[0]
                            replyMsg = cur_keyword.reply_msg(type='content', toUser=toUser, fromUser=fromUser)
                        else:
                            # 没有配置回复文件，按默认设置回复
                            text_content = Pre_Set_Reply
                            replyMsg = reply.TextMsg(toUser, fromUser, text_content)
                cur_gamedata.cmd_str = '|'.join(cmd_list)
                cur_gamedata.save()
                return replyMsg.send()
            else:
                # 用户发过来的不是text
                mediaId = recMsg.MediaId
                replyMsg = reply.ShortVideoMsg(toUser, fromUser, mediaId)
                return replyMsg.send()

        else:
            print("暂不处理")
            return reply.Msg().send()
    except Exception as e:
        print(e)


def update_process_and_reply(app, cur_game, cur_process, cur_gamedata, toUser, fromUser):
    cur_keyword = GameKeyword.objects.get(keyword=cur_process, game=cur_game)
    process_data_dict = {'cur_process': cur_process, 'cur_card': cur_keyword.cur_pic}
    cur_gamedata.data_dict = json.dumps(process_data_dict, ensure_ascii=False)
    cur_gamedata.cur_keyword = cur_keyword
    cur_gamedata.save()
    replyMsg = cur_keyword.reply_msg(type='content', toUser=toUser, fromUser=fromUser)
    return replyMsg


def check_player(my_app, open_id):
    """
    根据open_id查询玩家信息，如果是旧玩家，就返回已有的GameData对象，如果是新玩家，就新建一个并返回
    :param open_id:
    :return: WechatGame, WechatPlayer, WechatGameData对象
    """
    # 首先找到这个player对象
    check_player = WechatPlayer.objects.filter(app=my_app, open_id=open_id)

    if len(check_player) > 0:
        # 如果这是个旧玩家
        cur_player = check_player[0]
        # 判断这个玩家的当前游戏
        check_game = WechatGame.objects.filter(app=my_app, name=cur_player.cur_game_name)
        if len(check_game) > 0:
            # 如果玩家记录中的game对象存在，就取第一个作为cur_game
            cur_game = check_game[0]
            # 尝试寻找这个玩家在当前游戏里的档案
            check_gamedata = WechatGameData.objects.filter(player=cur_player, game=cur_game)
            # 如果游戏档案存在，则载入
            if len(check_gamedata) > 0:
                cur_gamedata = check_gamedata[0]
                # cur_keyword = cur_gamedata.cur_keyword
            # 如果游戏档案不存在，就为这个玩家在这个游戏新建一个
            else:
                cur_keyword = GameKeyword.objects.get(game=cur_game, keyword=keyword_start)
                cur_gamedata = WechatGameData(player=cur_player, game=cur_game, cur_keyword=cur_keyword,
                                              data_dict=dict(), cmd_str=list())
                cur_gamedata.save()
        else:
            # 如果玩家记录中的game对象已不存在
            # 就以当前app的第一个激活游戏，为玩家建立游戏档案
            cur_game = WechatGame.objects.filter(app=my_app, is_active=True)[0]
            cur_keyword = GameKeyword.objects.get(game=cur_game, keyword=keyword_start)
            cur_gamedata = WechatGameData(player=cur_player, game=cur_game, cur_keyword=cur_keyword,
                                          data_dict=dict(), cmd_str=list())
            cur_gamedata.save()

    # 这是个新玩家
    else:
        # 对于新接入的玩家，首先新建玩家档案，再以当前默认游戏新建游戏档案
        print('new player')
        check_games = WechatGame.objects.filter(app=my_app, name=my_app.cur_game_name)
        if check_games.count() > 0:
            # 这个公众号设定的当前默认游戏存在，就取第一个
            cur_game = check_games[0]
        else:
            # 如果这个公众号的当前默认Game对象不存在
            # 需要再想想怎么处理
            cur_game = WechatGame.objects.filter(app=my_app)[0]
        cur_player = WechatPlayer(app=my_app, open_id=open_id, game_hist={'game_list': [dict()]},
                                  cur_game_name=my_app.cur_game_name)
        cur_player.save()
        # 当前进度从keyword_start对应的关键词开始
        cur_keyword = GameKeyword.objects.get(game=cur_game, keyword=keyword_start)
        cur_gamedata = WechatGameData(player=cur_player, game=cur_game,
                                      cur_keyword=cur_keyword,
                                      data_dict=dict(), cmd_str=list())
        cur_gamedata.save()

    return cur_game, cur_player, cur_gamedata