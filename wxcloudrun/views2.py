# views.py

import io
import sys
from django.shortcuts import HttpResponse, render, HttpResponseRedirect
from django.http import JsonResponse
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
from wxcloudrun.ExploerGameHandler import *
import logging

logger = logging.getLogger('log')
WAITING_FOR_PASSWORD = 'w_password'             # 等待用户输入认证密码
WAITING_FOR_POI_KEYWORD = 'w_keyword'           # 等待用户输入POI关键词
WAITING_FOR_POI_DISTANCE = 'w_dist'             # 等待用户输入POI搜索范围（米）
KEYWORD_CONTACT_US = 'key_contact_us'           # 联系我们
DEFAULT_APP_KEYWORD = '管家'                     # 默认app关键词
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
    try:
        my_app = WechatApp.objects.get(en_name=app_en_name)
    except ObjectDoesNotExist:
        logger.error(f'can not find the app of {app_en_name}')
        return None
    # 获取APP级关键词
    app_keyword_list = [x.keyword for x in AppKeyword.objects.filter(app=my_app)]
    recMsg = receive.parse_xml(webData)
    toUser = recMsg.FromUserName
    open_id = toUser
    fromUser = recMsg.ToUserName

    #  检查这个openid对应的用户情况
    try:
        cur_player = WechatPlayer.objects.get(app=my_app, open_id=open_id)
    except ObjectDoesNotExist:
        # 如果这个openid是第一次出现，就先创新对应用户
        cur_player = WechatPlayer(app=my_app, open_id=open_id)
        cur_player.save()
    content = recMsg.Content.decode('utf-8')
    # 如果用户输入了APP级关键词
    if content in app_keyword_list:
        # cmd_list.append(content)
        try:
            my_app_keyword = AppKeyword.objects.get(app=my_app, keyword=content)
            replyMsg = my_app_keyword.reply_msg(toUser=toUser, fromUser=fromUser)
            return replyMsg.send()
        except ObjectDoesNotExist:
            text_content = f'APP级关键词{content}出错，请联系管理员'
            logger.error(text_content)
            return None
    # 其他情况，暂时不做回应
    # 以后可以返回联系管家之类的文字，或者做其他指引性应答
    else:
        return None


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
        elif event_key.lower() == KEYWORD_CONTACT_US:
            try:
                app_keyword = AppKeyword.objects.get(app=my_app, keyword=DEFAULT_APP_KEYWORD)
                replyMsg = app_keyword.reply_msg(toUser=toUser, fromUser=fromUser)
                return replyMsg.send()
            except ObjectDoesNotExist:
                text_content = f'APP关键词{DEFAULT_APP_KEYWORD}不存在，请联系管理员'
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
    # 微信会通过state参数携带自定义变量，我们在这里放入app_en_name和游戏名
    app_en_name, game_name = request.GET.get('state', '').split('_')
    openid = ''
    appid = ''
    errmsg = ''
    try:
        my_app = WechatApp.objects.get(en_name=app_en_name)
        appid = my_app.appid
    except ObjectDoesNotExist:
        # app_en_name参数传递错误
        errmsg = f'app_en_name参数传递错误: {app_en_name}'
        return HttpResponseRedirect()

    if len(code) > 0:
        request_url = f'http://api.weixin.qq.com/sns/oauth2/access_token?appid={my_app.appid}'
        request_url += f'&secret={my_app.secret}&code={code}&grant_type=authorization_code'
        # http = urllib3.PoolManager(cert_reqs='CERT_REQUIRED', ca_certs=certifi.where())
        # a = http.request('GET', request_url).data.decode('utf-8')
        a = requests.get(request_url)
        a.encoding = 'utf-8'
        b = a.json()
        logger.info(f'b={b}')
        error_code = b.get('error_code', 0)
        if error_code > 0:
            # 获取用户open id时出错
            errmsg = b.get('errmsg', '')
            return HttpResponse(errmsg)

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
            logger.info(f'd={d}')
            error_code = d.get('error_code', 0)
            if error_code > 0:
                # 获取用户信息时出错
                errmsg = d.get('errmsg', '')
                return HttpResponse(errmsg)
            else:
                try:
                    my_user = WechatPlayer.objects.get(app=my_app, open_id=openid)
                except ObjectDoesNotExist:
                    # 这是个新访问的用户
                    my_user = WechatPlayer(app=my_app, open_id=openid)
                nickname = d.get('nickname', '')
                sex = d.get('sex', '')
                headimgurl = d.get('headimgurl', '')
                privilege = d.get('privilege', '')
                my_user.nickname = nickname
                my_user.sex = sex
                my_user.user_info = d
                my_user.head_image = headimgurl
                my_user.save()
                if len(game_name) > 0:
                    cur_game_name = game_name
                    redirect_url = f'/profile/?app_en_name={app_en_name}&cur_game_name={cur_game_name}&openid={openid}&errmsg={errmsg}#wechat_redirect'
                    return HttpResponseRedirect(redirect_url)
                else:
                    errmsg = '重定向链接中的游戏名称为空，可能是菜单设置错误'
                    return HttpResponse(errmsg)
    else:
        errmsg = 'code为空'
        return HttpResponse(errmsg)


def show_profile(request):
    """
    从网页授权后，得到用户open id，会传过来
    如果openid为空，表示授权失败，要查看errmsg内容
    如果openid不为空，但errmsg也不为空，表示获取用户信息失败，同样要查看errmsg内容

    """
    # sys.stdout = io.TextIOWrapper(sys.stdout.buffer,encoding='utf-8') # 改变标准输出的默认编码
    template = 'wechat_main.html'
    app_en_name = request.GET.get('app_en_name', '')
    cur_game_name = request.GET.get('cur_game_name', '')
    open_id = request.GET.get('openid', '')
    cmd = request.GET.get('cmd', '')
    errmsg = request.GET.get('errmsg', '')
    ret_dict = dict()

    if len(errmsg) > 0:
        print(f'errmsg= {errmsg}')
        ret_dict['error_msg'] = errmsg
        logger.error(f'error_msg={error_msg}')
    else:
        if len(open_id) > 0:
            ret_dict = handle_player_command(app_en_name=app_en_name, open_id=open_id, game_name=cur_game_name,
                                             cmd=cmd, for_text=False)
            # logger.info(ret_dict)
        else:
            print(f'openid is blank')
            ret_dict['error_msg'] = '异常调用'
            logger.error(f'openid is blank')
    return render(request, template, ret_dict)


def download(request, filename):
    if os.path.exists(f'/app/{filename}'):
        file = open(f'/app/{filename}', 'rb')
        response = HttpResponse(file)
        response['Content-Type'] = 'application/octet-stream'  # 设置头信息，告诉浏览器这是个文件
        response['Content-Disposition'] = f'attachment;filename="{filename}"'
        return response
    else:
        return None


def check_answer(request):
    app_en_name = request.GET.get('app_en_name', '')
    cur_game_name = request.GET.get('cur_game_name', '')
    open_id = request.GET.get('openid', '')
    cmd = request.GET.get('cmd', '')
    ret_dict = handle_player_command(app_en_name=app_en_name, open_id=open_id, game_name=cur_game_name,
                                     cmd=cmd, for_text=False)
    # logger.info(ret_dict)
    if ret_dict['answer_is_correct']:
        return JsonResponse({'answer_is_correct': True, 'msg': ret_dict['notify_msg']})
    else:
        return JsonResponse({'answer_is_correct': False, 'msg': ret_dict['error_msg']})
