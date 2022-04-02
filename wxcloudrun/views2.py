# views.py

from django.shortcuts import HttpResponse, render, HttpResponseRedirect
from django.views.decorators.csrf import csrf_exempt
import hashlib
from . import receive
from . import reply
from random import sample
# import opencc
from wxcloudrun.common_functions import *
import datetime
from wxcloudrun.models import *
from wxcloudrun.location_game import *

WAITING_FOR_PASSWORD = 'w_password'             # 等待用户输入认证密码
WAITING_FOR_POI_KEYWORD = 'w_keyword'           # 等待用户输入POI关键词
WAITING_FOR_POI_DISTANCE = 'w_dist'             # 等待用户输入POI搜索范围（米）
ASK_FOR_PASSWORD = '请先输入从客服处获得的密码'
GAME_IS_NOT_ACTIVE = '对不起，游戏未启动或时间已过'
CHECK_CLEAR_CODE = '查看通关密码'
CHECK_PROGRESS = '查看当前进度'
FIELD_CLEAR_CODE = 'clear_code'                 # 存放通过码的字典key
FIELD_REWARD_LIST = 'reward_list'               # 存放已获取奖励的字典key
FIELD_COMMAND_LIST = 'cmd_list'                 # 存放已行动命令的字典key
FIELD_IS_AUDIT = 'is_audit'                     # 存在当前用户在当前游戏是否已认证的key

# django默认开启了csrf防护，@csrf_exempt是去掉防护
# 微信服务器进行参数交互，主要是和微信服务器进行身份的验证
@csrf_exempt
def check_signature(request):
    app_en_name = 'miaozan'
    my_app = WechatApp.objects.get(en_name=app_en_name)
    if request.method == "GET":
        # print("request: ", request)
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
        token = my_app.token

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
    """
    基于腾讯服务器发过来的内容，分配处理程序
    """
    try:
        webData = request.body
        recMsg = receive.parse_xml(webData)
        if isinstance(recMsg, receive.Msg):
            if recMsg.MsgType == 'text':
                # 接收到用户的文本信息
                return handle_text_msg(request, app_en_name)
            elif recMsg.MsgType == 'event':
                # 接收到用户触发了事件类流程
                return handle_event_msg(request, app_en_name)
            elif recMsg.MsgType in ['view_miniprogram']:
                # 用户触发跳转小程序事件
                return None
            else:
                # 用户发过来的不是已知类型，直接回复recMsg.MsgType，以便确认类型
                toUser = recMsg.FromUserName
                fromUser = recMsg.ToUserName
                replyMsg = reply.TextMsg(toUser, fromUser, recMsg.MsgType)
                return replyMsg.send()
        else:
            print("暂不处理")
            return reply.Msg().send()
    except Exception as e:
        print(e)


def handle_text_msg(request, app_en_name):
    """
    处理text信息，用于自动应答、游戏流程等

    """
    webData = request.body
    my_app = WechatApp.objects.get(en_name=app_en_name)
    # 获取APP级关键词
    app_keyword_list = [x.keyword for x in AppKeyword.objects.filter(app=my_app)]
    recMsg = receive.parse_xml(webData)
    toUser = recMsg.FromUserName
    open_id = toUser
    fromUser = recMsg.ToUserName
    # 将关键判断条件重置
    trigger_list = list()
    player_is_audit = False
    cur_player_game_dict = dict()
    reward_list = list()
    cmd_list = list()
    clear_code = ''

    #  检查这个openid对应的用户情况
    try:
        cur_player = WechatPlayer.objects.get(app=my_app, open_id=open_id)
    except ObjectDoesNotExist:
        # 如果这个openid是第一次出现，就先创新对应用户
        cur_player = WechatPlayer(app=my_app, open_id=open_id)
        cur_player.save()

    # 先检查用户的当前游戏名称，是否有配置
    if len(cur_player.cur_game_name) > 0:
        # 如果用户有当前游戏
        cur_game_name = cur_player.cur_game_name
        try:
            cur_game = ExploreGame.objects.get(app=my_app, name=cur_game_name)
        except ObjectDoesNotExist:
            # 如果配置的游戏名称已经不存在，就清空已配置的名称
            # 触发词列表置空
            cur_player.cur_game_name = ''
            cur_player.save()
            cur_game = None


        if cur_game:
            if cur_game.is_active:
                # 如果当前游戏处于激活状态
                trigger_list = [x.quest_trigger for x in ExploreGameQuest.objects.filter(game=cur_game)]
                cur_player_game_dict = get_cur_player_game_dict(player=cur_player, game_name=cur_game_name)
                reward_list = cur_player_game_dict.get(FIELD_REWARD_LIST, list())
                cmd_list = cur_player_game_dict.get(FIELD_COMMAND_LIST, list())
                clear_code = cur_player_game_dict.get(FIELD_CLEAR_CODE, '')
                player_is_audit = cur_player_game_dict.get(FIELD_IS_AUDIT, False)
            else:
                # 如果游戏不是激活状态，由后面的程序处理
                pass
        else:
            # 用户有配置游戏名称，但没找到对应的游戏，可能是游戏已被删除，或改名
            # 相当于一个新用户，由后面的流程来处理
            pass

    else:
        # 没有配置游戏名称，可能是未参与游戏的用户，由后面的流程来处理
        pass

    content = recMsg.Content.decode('utf-8')

    # 如果用户输入了APP级关键词
    if content in app_keyword_list:
        # cmd_list.append(content)
        try:
            my_app_keyword = AppKeyword.objects.get(app=my_app, keyword=content)
            replyMsg = my_app_keyword.reply_msg(toUser=toUser, fromUser=fromUser)
        except ObjectDoesNotExist:
            text_content = f'APP级关键词{content}出错，请联系管理员'
            replyMsg = reply.TextMsg(toUser, fromUser, text_content)
    # 玩家打算触发某个Quest任务
    elif content in trigger_list:
        # 先检查用户是否有权限玩这个游戏
        if player_is_audit:
            if cur_game.is_active:
                cur_quest = ExploreGameQuest.objects.get(game=cur_game, quest_trigger=content)
                prequire_list = cur_quest.get_content_list(type='prequire')
                if set(prequire_list).issubset(set(reward_list)) or len(prequire_list) == 0:
                    # 如果这个Quest没有前置要求，或前置要求都达到了
                    cur_player.waiting_status = content
                    cur_player.save()
                    text_content = cur_quest.question_data
                    replyMsg = reply.TextMsg(toUser, fromUser, text_content)
                else:
                    # 前置要求还没做全
                    done_id_list = set(reward_list).intersection(set(prequire_list))
                    all_quest = ExploreGameQuest.objects.filter(game=cur_game)
                    done_q_name_list = list()
                    for q in all_quest:
                        if q.reward_id in done_id_list:
                            done_q_name_list.append(q.quest_trigger)
                    text_content = f'要回答这个问题，需要先完成{len(prequire_list)}个任务，'
                    text_content += f'而您现在只完成了{str(done_q_name_list)[1:-1]} {len(set(reward_list).intersection(set(prequire_list)))}个。'
                    replyMsg = reply.TextMsg(toUser, fromUser, text_content)
            else:
                # 游戏已经去激活，可能是时间已到
                cur_player.waiting_status = ''
                cur_player.save()
                text_content = f'{GAME_IS_NOT_ACTIVE}'
                replyMsg = reply.TextMsg(toUser, fromUser, text_content)
        else:
            # 还没有通过鉴权
            cur_player.waiting_status = WAITING_FOR_PASSWORD
            cur_player.save()
            text_content = f'{ASK_FOR_PASSWORD}'
            replyMsg = reply.TextMsg(toUser, fromUser, text_content)
    elif content == CHECK_CLEAR_CODE:
        # 玩家重新查看游戏通关密码
        if len(clear_code) > 0:
            text_content = f'您的通关密码是：{clear_code}'
        else:
            text_content = f'您还没通关，请继续努力！'
        replyMsg = reply.TextMsg(toUser, fromUser, text_content)
    elif content == CHECK_PROGRESS:
        # 玩家查看游戏进度
        if cur_game:
            all_quest = ExploreGameQuest.objects.filter(game=cur_game)
            done_q_name_list = list()
            for q in all_quest:
                if q.reward_id in reward_list:
                    done_q_name_list.append(q.quest_trigger)
            if len(done_q_name_list) > 0:
                text_content = f'您现在完成了{str(done_q_name_list)[1:-1]} {len(done_q_name_list)}个任务。'
            else:
                text_content = f'您现在还没有完成任何任务。'
        else:
            text_content = f'您没有参与游戏。'
        replyMsg = reply.TextMsg(toUser, fromUser, text_content)
    # 如果用户是否处于等待输入状态
    elif len(cur_player.waiting_status) > 0:
        # 等待用户输入POI搜索关键词
        if cur_player.waiting_status == WAITING_FOR_POI_KEYWORD:
            poi_keyword = content[:50]
            cur_player.poi_keyword = poi_keyword
            cur_player.waiting_status = ''
            cur_player.save()
            text_content = f'兴趣点关键词已设为：{poi_keyword}'
            replyMsg = reply.TextMsg(toUser, fromUser, text_content)
        # 等待用户输入POI搜索范围
        elif cur_player.waiting_status == WAITING_FOR_POI_DISTANCE:
            try:
                poi_dist = int(content)
                if poi_dist < 10:
                    poi_dist = 10
                cur_player.poi_dist = poi_dist
                cur_player.waiting_status = ''
                cur_player.save()
                text_content = f'搜查兴趣点范围已设为：{poi_dist}'
                replyMsg = reply.TextMsg(toUser, fromUser, text_content)
            except:
                text_content = f'你输入的距离不正确：{content}'
                replyMsg = reply.TextMsg(toUser, fromUser, text_content)
        # 等待用户输入认证密码
        elif cur_player.waiting_status == WAITING_FOR_PASSWORD:
            # 玩家正在输入密码
            result = auth_user(app=my_app, password=content, user_id=open_id)
            if result:
                # cur_player.name = user_id  # 鉴权后不再返回user id
                player_is_audit = True
                cur_player.waiting_status = ''
                player_game_dict = cur_player.game_hist
                cur_player_game_dict[FIELD_IS_AUDIT] = True
                cur_player.game_hist[cur_game_name] = cur_player_game_dict
                cur_player.save()
                text_content = f'''验证成功，请重新点击菜单开始游戏'''
                replyMsg = reply.TextMsg(toUser, fromUser, text_content)
            else:
                # 没有输对密码
                text_content = f'密码错误，请查证后再输入'
                replyMsg = reply.TextMsg(toUser, fromUser, text_content)
        # 用户已处于某个Quest中，等待输入答案
        elif cur_player.waiting_status in trigger_list:
            # 如果用户已经处于某个quest的任务中
            if cur_game.is_active:
                try:
                    cur_quest = ExploreGameQuest.objects.get(game=cur_game, quest_trigger=cur_player.waiting_status)
                    answer_list = cur_quest.get_content_list(type='answer')
                except ObjectDoesNotExist:
                    # 玩家等待状态设置错误，可能是游戏配置已更改
                    # 清空等待状态，将answer_list置为空列表
                    cur_player.waiting_status = ''
                    cur_player.save()
                    answer_list = list()
                    cur_quest = None
                    text_content += f'任务已取消，请重新开始另一个任务'
                    replyMsg = reply.TextMsg(toUser, fromUser, text_content)
                if content in answer_list:
                    # 答对了当前问题
                    reward_id = cur_quest.reward_id
                    # 如果玩家是新获得的奖励，就增加1个步数，保存奖励记录
                    # 如果玩家之前已经获得过奖励，就忽略
                    if reward_id not in reward_list:
                        cmd_list.append(content)
                        reward_list.append(reward_id)
                        cur_player_game_dict[FIELD_REWARD_LIST] = reward_list
                        cur_player_game_dict[FIELD_COMMAND_LIST] = cmd_list
                        cur_player.game_hist[cur_game_name] = cur_player_game_dict
                    # 重置玩家当前等待状态，并保存
                    cur_player.waiting_status = ''
                    cur_player.save()
                    # 确认玩家是否已通关
                    clear_requirement_list = cur_game.get_content_list()
                    if set(clear_requirement_list).issubset(set(reward_list)):
                        # 玩家已达到通关要求
                        clear_code = cur_player.hash_with_game()
                        cur_player_game_dict[FIELD_CLEAR_CODE] = clear_code
                        cur_player.game_hist[cur_game_name] = cur_player_game_dict
                        cur_player.save()
                        text_content = f'{cur_game.clear_notice}'
                        text_content += '\n'
                        text_content += f'您的通过密码是：{clear_code}'
                        replyMsg = reply.TextMsg(toUser, fromUser, text_content)
                    else:
                        # 玩家还没通关
                        replyMsg = cur_quest.reply_msg(type='reward', toUser=toUser, fromUser=fromUser)
                elif content == keyword_hint:
                    # 输入了【提示】
                    if cur_quest:
                        replyMsg = cur_quest.reply_msg(type='hint', toUser=toUser, fromUser=fromUser)
                    else:
                        text_content = '您正在进行的任务已经取消，请重新开始另一个吧：）'
                        replyMsg = reply.TextMsg(toUser, fromUser, text_content)
                else:
                    # 输入了不相关的内容
                    cmd_list.append(content)
                    cur_player_game_dict[FIELD_COMMAND_LIST] = cmd_list
                    cur_player.game_hist[cur_game_name] = cur_player_game_dict
                    cur_player.save()
                    my_error_auto_replys = list(ErrorAutoReply.objects.filter(is_active=True))
                    if len(my_error_auto_replys) > 0:
                        choose_reply = sample(my_error_auto_replys, 1)[0]
                        replyMsg = choose_reply.reply_msg(toUser=toUser, fromUser=fromUser)
                    else:
                        text_content = f'{error_reply_default}'
                        replyMsg = reply.TextMsg(toUser, fromUser, text_content)
                    # 注意：这里不能放最后的else部分
                    # 如果存在else，则不会判断下面的其他elif部分
            else:
                # 游戏已经去激活，可能是时间已到
                cur_player.waiting_status = ''
                cur_player.save()
                text_content = f'{GAME_IS_NOT_ACTIVE}'
                replyMsg = reply.TextMsg(toUser, fromUser, text_content)


    # 用户未正式开始游戏，而且未输入正确的触发关键词，可能是新用户
    # 可以返回联系管家之类的文字，或者做其他指引性应答
    else:
        try:
            temp_keyword = '管家'
            my_app_keyword = AppKeyword.objects.get(app=my_app, keyword=temp_keyword)
            replyMsg = my_app_keyword.reply_msg(toUser=toUser, fromUser=fromUser)
        except ObjectDoesNotExist:
            text_content = f'APP级关键词{temp_keyword}出错，请联系管理员'
            replyMsg = reply.TextMsg(toUser, fromUser, text_content)
    return replyMsg.send()

def handle_event_msg(request, app_en_name):
    """
    处理事件类流程

    """
    webData = request.body
    recMsg = receive.parse_xml(webData)
    toUser = recMsg.FromUserName
    fromUser = recMsg.ToUserName
    try:
        my_app = WechatApp.objects.get(en_name=app_en_name)
        my_player = WechatPlayer.objects.get(app=my_app, open_id=toUser)
    except ObjectDoesNotExist:
        my_player = WechatPlayer(app=my_app, open_id=toUser)
        my_player.save()

    # 用户点击了菜单
    if recMsg.Event in ('CLICK'):
        # 用户点击了按钮
        # 需要确保返回replyMsg.send()，或者None
        event_key = recMsg.EventKey
        if event_key == 'set_keyword':
            text_content = f'''请输入你想找的地点关键词'''
            my_player.waiting_status = WAITING_FOR_PASSWORD
            my_player.save()
            replyMsg = reply.TextMsg(toUser, fromUser, text_content)
            return replyMsg.send()
        elif event_key == 'set_distance':
            text_content = f'''请输入你想找的距离范围（米）'''
            my_player.waiting_status = 'w_dist'
            my_player.save()
            replyMsg = reply.TextMsg(toUser, fromUser, text_content)
            return replyMsg.send()
        elif event_key.lower() == 'show_parameters':
            text_content = f'当前你的搜索关键词：{my_player.poi_keyword}，搜索范围：{my_player.poi_dist}米'
            replyMsg = reply.TextMsg(toUser, fromUser, text_content)
            return replyMsg.send()
        elif event_key.lower() == 'show_my_location':
            _, my_location = my_player.get_location_address()
            text_content = my_location
            my_player.cur_location = text_content
            replyMsg = reply.TextMsg(toUser, fromUser, text_content)
            return replyMsg.send()
        elif event_key.lower() == 'show_my_nearby':
            result, poi_list = my_player.get_nearby_poi()
            if result:
                poi_string = "\n".join(poi_list)
                text_content = f'在你{my_player.poi_dist}米内找到{len(poi_list)}个'
                text_content += f'与【{my_player.poi_keyword}】相关的地点：'
                text_content += '\n' + poi_string
            else:
                text_content = str(poi_list)
            replyMsg = reply.TextMsg(toUser, fromUser, text_content)
            return replyMsg.send()
        elif event_key.lower() == 'key_game_1':
            # 开始老广新痕游戏
            cur_game_name = '老广新痕（4月版）'
            try:
                my_game = ExploreGame.objects.get(app=my_app, name=cur_game_name)
            except ObjectDoesNotExist:
                text_content = '游戏不存在'
                replyMsg = reply.TextMsg(toUser, fromUser, text_content)
                return replyMsg.send()
            # 获取用户游戏档案，检查用户是否已鉴权
            cur_player_game_dict = get_cur_player_game_dict(player=my_player, game_name=cur_game_name)
            player_is_audit = cur_player_game_dict.get(FIELD_IS_AUDIT, False)
            if my_game.is_active:

                if player_is_audit:
                    my_player.cur_game_name = my_game.name
                    my_player.waiting_status = ''
                    my_player.save()
                    if len(my_game.opening) > 0:
                        text_content = replace_content_with_hyperlink(my_game.opening)
                    else:
                        text_content = f'{my_game}未设置开场白'
                else:
                    text_content = f'{ASK_FOR_PASSWORD}'
                    my_player.cur_game_name = cur_game_name
                    my_player.waiting_status = WAITING_FOR_PASSWORD
                    my_player.save()
            else:
                #  游戏未激活
                text_content = f'{GAME_IS_NOT_ACTIVE}'
            replyMsg = reply.TextMsg(toUser, fromUser, text_content)
            return replyMsg.send()
        else:  # 未知的点击key
            text_content = f'''event_key:{event_key}'''
            replyMsg = reply.TextMsg(toUser, fromUser, text_content)
            return replyMsg.send()
    elif recMsg.Event == 'VIEW':
        # 用户点击了菜单上的链接
        event_url = recMsg.EventKey
    elif recMsg.Event in ['scancode_push', 'scancode_waitmsg']:
        # 扫码事件
        pass
    elif recMsg.Event in ['pic_sysphoto', 'pic_photo_or_album', 'pic_weixin']:
        # 用户触发拍照或提交照片事件
        pass
    elif recMsg.Event in ['location_select']:
        # 用户上报了某个地理位置，无需回复，因此返回None

        try:
            my_player.cur_longitude = recMsg.Location_Y
            my_player.cur_latitude = recMsg.Location_X
            my_player.cur_Precision = recMsg.Scale
            my_player.cur_location = recMsg.Poiname
            my_player.save()
            # 上报内容还包括recMsg.Label和recMsg.Poiname
            return None
        except ObjectDoesNotExist:
            return None
    elif recMsg.Event in ['LOCATION']:
        # 用户上报了定位信息，无需回复，因此返回None
        # text_content = f'''经度={recMsg.Longitude},纬度={recMsg.Latitude},精度={recMsg.Precision}'''
        try:
            my_player.cur_longitude = recMsg.Longitude
            my_player.cur_latitude = recMsg.Latitude
            my_player.cur_Precision = recMsg.Precision
            # _, my_location = my_player.get_location_address()
            # my_player.cur_location = my_location
            my_player.save()
        except ObjectDoesNotExist:
            pass
        return None

    return replyMsg.send()

def get_user_info_with_code(request):
    """
    基于微信网页授权流程第二步，获取用户信息
    """
    code = request.GET.get('code', '')
    app_en_name, game_name = request.GET.get('state', '').split('_')  # 微信会通过state参数携带自定义变量，我们在这里放入app_en_name
    openid = ''
    appid = ''
    errmsg = ''
    try:
        my_app = WechatApp.objects.get(en_name=app_en_name)
        appid = my_app.appid
        if len(code) > 0:
            request_url = f'http://api.weixin.qq.com/sns/oauth2/access_token?appid={my_app.appid}'
            request_url += f'&secret={my_app.secret}&code={code}&grant_type=authorization_code'
            # http = urllib3.PoolManager(cert_reqs='CERT_REQUIRED', ca_certs=certifi.where())
            # a = http.request('GET', request_url).data.decode('utf-8')
            a = requests.get(request_url)
            a.encoding = 'utf-8'
            b = a.json()
            errcode = b.get('errcode', 0)
            if errcode > 0:
                errmsg = b.get('errmsg', '')
                return HttpResponseRedirect()
                # return HttpResponse(errmsg)
            else:
                temp_acc_token = b.get('access_token', '')
                refresh_token = b.get('refresh_token', '')
                openid = b.get('openid', '')
                scope = b.get('scope', '')
                request_url = 'http://api.weixin.qq.com/sns/userinfo'
                request_url += f'?access_token={temp_acc_token}&openid={openid}&lang=zh_CN'
                # c = http.request('GET', request_url).data.decode('utf-8')
                c = requests.get(request_url)
                c.encoding = 'utf-8'
                d = c.json()
                errcode = d.get('errcode', 0)
                if errcode > 0:
                    errmsg = d.get('errmsg', '')

                else:
                    my_user = WechatPlayer.objects.get(app=my_app, open_id=openid)
                    nickname = d.get('nickname', '')
                    sex = d.get('sex', '')
                    headimgurl = d.get('headimgurl', '')
                    privilege = d.get('privilege', '')
                    my_user.nickname = nickname
                    my_user.sex = sex
                    my_user.user_info = d
                    my_user.head_image = headimgurl
                    my_user.save()

        else:
            errmsg = 'code为空'
    except ObjectDoesNotExist:
        # app_en_name参数传递错误
        errmsg = f'app_en_name参数传递错误: {app_en_name}，或者没有找到对应的用户{openid}'

    if game_name == 'game1':
        cur_game_name = ''
    redirect_url = f'/profile/?app_en_name={app_en_name}&openid={openid}&errmsg={errmsg}#wechat_redirect'
    return HttpResponseRedirect(redirect_url)

def show_profile(request):
    """
    从网页授权后，得到用户open id，会传过来
    如果openid为空，表示授权失败，要查看errmsg内容
    如果openid不为空，但errmsg也不为空，表示获取用户信息失败，同样要查看errmsg内容
    """
    template = 'wechat_main.html'
    app_en_name = request.GET.get('app_en_name', '')
    cur_game_name = request.GET.get('cur_game_name', '')
    openid = request.GET.get('openid', '')
    cmd = request.GET.get('cmd', '')
    errmsg = request.GET.get('errmsg', '')
    ret_dict = dict()
    if len(app_en_name) > 0:
        try:
            my_app = WechatApp.objects.get(en_name=app_en_name)
            ret_dict['app_en_name'] = app_en_name
            ret_dict['openid'] = openid
        except ObjectDoesNotExist:
            ret_dict['title'] = 'app_en_name is not valid'
            ret_dict['app_en_name'] = app_en_name
            ret_dict['openid'] = openid
        if len(openid) > 0:
            if len(errmsg) == 0:
                # 成功
                try:
                    my_user = WechatPlayer.objects.get(app=my_app, open_id=openid)
                    if cur_game_name == '':
                        cur_game_name = my_user.cur_game_name
                    my_game = ExploreGame.objects.get(app=my_app, name=cur_game_name)
                    game_quests = ExploreGameQuest.objects.filter(game=my_game)
                    ret_dict['opening'] = my_game.opening
                    ret_dict['quest_triggers'] = [x.quest_trigger for x in game_quests]
                    ret_dict['app_en_name'] = app_en_name
                    ret_dict['cur_game_name'] = cur_game_name
                    ret_dict['head_image'] = str(my_user.head_image)
                    ret_dict['nickname'] = my_user.nickname
                    ret_dict['title'] = f'欢迎参加{cur_game_name}'
                except ObjectDoesNotExist:
                    ret_dict['title'] = 'player not found'

            else:
                ret_dict['app_en_name'] = app_en_name
                ret_dict['title'] = errmsg

        else:  # openid is blank
            if len(errmsg) > 0:
                ret_dict['title'] = errmsg
                ret_dict['app_en_name'] = app_en_name
                ret_dict['openid'] = openid
            else:
                ret_dict['title'] = 'openid is blank'
                ret_dict['app_en_name'] = app_en_name
    else: # app_en_name is blank
        ret_dict['title'] = 'app_en_name is blank'
        ret_dict['app_en_name'] = app_en_name
        ret_dict['openid'] = openid

    return render(request, template, ret_dict)

def get_cur_player_game_dict(player, game_name):
    player_game_dict = player.game_hist  # json object
    # player_game_dict should be like this
    # {'cur_game_name': {setting1: xxx, setting2: xxx}}
    if len(game_name) > 0:
        # 如果游戏名不为空
        if not player_game_dict:
            # 如果这个玩家还没有游戏存档，就用输入的游戏名初始化一个
            cur_player_game_dict = {FIELD_IS_AUDIT: False,
                                    FIELD_COMMAND_LIST: list(),
                                    FIELD_CLEAR_CODE: '',
                                    FIELD_REWARD_LIST: list()}
            player_game_dict = {game_name: cur_player_game_dict}
            player.game_hist = player_game_dict
            player.save()
        else:
            # 如果玩家已经有游戏存档
            cur_player_game_dict = player_game_dict.get(game_name, dict())
    else:
        # 如果输入的游戏名为空，返回空字典
        cur_player_game_dict = dict()
    return cur_player_game_dict

def download(request, filename):
    if os.path.exists(f'/app/{filename}'):
        file = open(f'/app/{filename}', 'rb')
        response = HttpResponse(file)
        response['Content-Type'] = 'application/octet-stream'  # 设置头信息，告诉浏览器这是个文件
        response['Content-Disposition'] = f'attachment;filename="{filename}"'
        return response
    else:
        return None
