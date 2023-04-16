from django.shortcuts import HttpResponse, HttpResponseRedirect, render
from django.views.decorators.csrf import csrf_exempt
from django.core.exceptions import *
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required

from .common_functions import *
from .resource_manage import *
from .models import *
from .location_game import *
import json


@login_required
def list_app_view(request, appid='', resource_type=''):

    need_logout = request.GET.get('logout', '')
    if need_logout:
        logout(request)
        # print('user logout')
        return HttpResponseRedirect('/summary/')
    if appid:
        try:
            apps = WechatApp.objects.get(appid=appid)
        except ObjectDoesNotExist:
            return HttpResponse(f'App {appid} is not exist')
    else:
        apps = WechatApp.objects.all()
    app_list = list()
    for app in apps:
        app_dict = dict()
        appid = app.appid
        app_pk = app.id
        app_dict['appid'] = appid
        app_dict['app_name'] = app.name
        user_count = WechatPlayer.objects.filter(app=app).count()
        game_count = ExploreGame.objects.filter(app=app).count()
        image_count = WechatMedia.objects.filter(app=app, media_type='image').count()
        video_count = WechatMedia.objects.filter(app=app, media_type='video').count()
        app_keyword_count = AppKeyword.objects.filter(app=app).count()
        app_info_dict = dict()
        app_info_dict['玩家数量'] = [user_count, 'list_user']  # 列表第一个值是对应的value，第二个值对应url的字符串，留空表示不做链接
        app_info_dict['游戏数量'] = [game_count, 'list_game']
        app_info_dict['图片数量'] = [image_count, 'images']
        app_info_dict['视频数量'] = [video_count, 'videos']
        app_info_dict['自动回复'] = [app_keyword_count, f'/admin/mypublic/appkeyword/?app__id__exact={app_pk}']
        app_dict['app_info'] = app_info_dict
        app_list.append(app_dict)
    return render(request, 'summary.html', {'appid_list': app_list})


@login_required
def list_user_view(request, appid, game_name=''):
    groups_count = int(request.GET.get('groups_count', '3'))
    try:
        my_app = WechatApp.objects.get(appid=appid)
        game_name_list = [x.name for x in ExploreGame.objects.filter(app=my_app, is_active=True)]
    except ObjectDoesNotExist:
        return HttpResponse(f'APP ID: {appid} not exists')
    user_summary_list = get_player_summary(appid=appid, game_name=game_name)

    total_count = len(user_summary_list)
    passing_list = list()
    quantity_per_group = int(total_count / groups_count) + 1
    for i in range(groups_count):
        user_list = user_summary_list[(i * quantity_per_group):((i + 1) * quantity_per_group)]
        passing_list.append(user_list)

    return render(request, 'list_user.html', {'all_list': passing_list, 'total_count': total_count,
                                              'width_lg': int(12 / groups_count), 'appid': appid,
                                              'game_name_list': game_name_list})


@login_required
def check_user_view(request, appid, open_id):
    if open_id:
        try:
            my_app = WechatApp.objects.get(appid=appid)
            my_player = WechatPlayer.objects.get(app=my_app, open_id=open_id)
            # my_game_data = ExploreGameData.objects.filter(player=my_player)[0]
            # game_name = my_game_data.game.name
            # cur_process = my_game_data.cur_keyword
            # cmd_list = my_game_data.cmd_list
            user_id = my_player.name
            passing_dict = {'process': cur_process, 'cmd_list': cmd_list, 'user_id': user_id,
                            'open_id': open_id, 'appid': appid}
            print(passing_dict)
            return render(request, 'check_user.html', passing_dict)

        except ObjectDoesNotExist:
            return HttpResponse(f'Failed to load user_data。 APP ID: {appid}, open_id: {open_id}')
    else:
        return HttpResponse('Open Id not valid')


@login_required
def rename_user(request):
    open_id = request.GET.get('open_id', '')
    new_user_id = request.GET.get('new_name', '')
    appid = request.GET.get('appid', '')
    user_json_file = f'data/user_data/user_{appid}_{open_id}.json'
    if os.path.exists(user_json_file):
        user_data_dict = load_user_data(user_json_file=user_json_file)
        old_user_id = user_data_dict['user_id']
        user_data_dict['user_id'] = new_user_id
        if save_user_data(user_json_file=user_json_file, user_data_dict=user_data_dict):
            # print(f'成功将{old_user_id}改为{new_user_id}')
            return HttpResponseRedirect(f'/summary/?appid={appid}&open_id={open_id}&check_user=1')
        else:
            text_content = '用户数据保存失败'
            # print(text_content)
            return HttpResponse(text_content)
    else:
        text_content = f'找不到{user_json_file}'
        
        print(text_content)
        return HttpResponse(text_content)


@login_required
def list_image_view(request, appid):
    image_name = request.GET.get('media_name', None)
    try:
        app = WechatApp.objects.get(appid=appid)
        if image_name:
            image_obj_list = WechatMedia.objects.filter(app=app, media_type='image', name=image_name)
        else:
            image_obj_list = WechatMedia.objects.filter(app=app, media_type='image')
        image_list = list()
        for my_image in image_obj_list:
            image_dict = json.loads(my_image.info)
            # image_dict should be like:
            #  {
            # "media_id": MEDIA_ID,
            # "name": NAME,
            # "update_time": UPDATE_TIME,
            # "url":URL
            #  }
            image_list.append(image_dict)
        return render(request, 'list_image.html', {'media_list': image_list, 'appid': appid, 'type': 'image'})
    except ObjectDoesNotExist:
        return HttpResponse(f'App: {appid} does not exist')


@login_required
def list_video_view(request, appid):
    video_name = request.GET.get('media_name', None)
    try:
        app = WechatApp.objects.get(appid=appid)
        if video_name:
            video_obj_list = WechatMedia.objects.filter(app=app, media_type='video', name=video_name)
        else:
            video_obj_list = WechatMedia.objects.filter(app=app, media_type='video')
        video_list = list()
        for my_video in video_obj_list:
            video_dict = json.loads(my_video.info)
            # image_dict should be like:
            #  {
            # "media_id": MEDIA_ID,
            # "name": NAME,
            # "update_time": UPDATE_TIME,
            # "cover_url":URL
            # "description": ,
            # "newcat": ,
            # "newsubcat": ,
            # "tags": ,
            # "vid":
            #  }
            video_list.append(video_dict)
        return render(request, 'list_image.html', {'media_list': video_list, 'appid': appid, 'type': 'video'})
    except ObjectDoesNotExist:
        return HttpResponse(f'App: {appid} does not exist')


@login_required
def del_media(request, appid, media_id):
    """
    删除对应media id的资源，如果有重复的media id，则在腾讯服务器上删除第一个，然后在内部数据库中删除其他
    :param request:
    :param appid:
    :param media_id:
    :return:
    """
    try:
        app = WechatApp.objects.get(appid=appid)
        my_medias = WechatMedia.objects.filter(app=app, media_id=media_id)
        my_medias_count = len(my_medias)
        if my_medias_count == 0:
            return HttpResponse(f'Media id: {media_id} in app: {appid} is not found')
        else:
            target_media = my_medias[0]
            if my_medias_count > 1:
                # remove the duplicates from local db
                duplicate_medias = my_medias[1:]
                for my_media in duplicate_medias:
                    my_media.delete()

            # delete the 1st media
            if target_media.delete_from_wechat():
                return HttpResponseRedirect(f'/summary/images/{appid}/')
            else:
                return HttpResponse(f'failed to del media: {media_id} in app: {appid}')

    except ObjectDoesNotExist:
        return HttpResponse(f'Media: {media_id} in app: {appid} does not exist')



@login_required
def user_manage(request):
    user_passwd_dict = load_user_passwd_dict()
    if user_passwd_dict:
        return render(request, 'list_user.html', {"user_list": user_passwd_dict})
    else:
        return HttpResponse(f'Failed to load user_passwd_dict')


@login_required
def show_mermaid_chart(request, appid, game_name):
    try:
        my_app = WechatApp.objects.get(appid=appid)
        my_game = ExploreGame.objects.get(app=my_app, name=game_name)
        if my_game.save_to_mermaid(graph_type='TD'):
            with open(my_game.md_file(), 'r', encoding='utf_8_sig') as f:
                md_content = ''.join(f.readlines()[1:-1])  # 去掉第一行和最后一行，即去掉```mermaid的标记
                return render(request, 'mermaid.html', {'content': md_content, 'appid': appid, 'game_name': game_name})
        else:
            return HttpResponse(f'{game_name} 生成流程图失败')
    except ObjectDoesNotExist:
        return HttpResponse(f'Game: {game_name} in app: {appid} does not exist')


@login_required
def check_media_availability(request, appid, game_name):
    try:
        my_app = WechatApp.objects.get(appid=appid)
        my_game = ExploreGame.objects.get(app=my_app, name=game_name)
        list_missing_media = my_game.check_media_availability()
        md_content = '<br>'.join(list_missing_media)
        return render(request, 'media_availability.html', {'content': md_content, 'appid': appid, 'game_name': game_name})
    except ObjectDoesNotExist:
        return HttpResponse(f'Game: {game_name} in app: {appid} does not exist')


@login_required
def list_game_view(request, appid):
    try:
        my_app = WechatApp.objects.get(appid=appid)
        my_games = ExploreGame.objects.filter(app=my_app)
        game_list = list()
        for my_game in my_games:
            game_dict = dict()
            game_dict['appid'] = appid
            game_dict['app_name'] =my_app.name
            game_dict['game_pk'] = my_game.pk
            game_dict['game_name'] = my_game.name
            game_dict['is_active'] = my_game.is_active
            # player_count = ExploreGameData.objects.filter(game=my_game).count()
            keyword_count = ExploreGameQuest.objects.filter(game=my_game).count()
            # game_dict['player_count'] = player_count
            game_dict['keyword_count'] = keyword_count
            game_list.append(game_dict)
        # print(game_list)
        return render(request, 'list_game.html', {'game_list': game_list})
    except ObjectDoesNotExist:
        return HttpResponse(f'App: {appid} does not exist')


@login_required
def reload_keyword(request, appid, game_name):
    try:
        my_app = WechatApp.objects.get(appid=appid)
        my_game = ExploreGame.objects.get(app=my_app, name=game_name)
        if my_game.load_settings():
            return HttpResponseRedirect(f'/summary/list_game/{appid}/')
    except ObjectDoesNotExist:
        return HttpResponse(f'Game: {game_name} in app: {appid} does not exist')


@login_required
def gamed_data_view(request, game_data_id):
    try:
        # my_game_data = ExploreGameData.objects.get(pk=game_data_id)
        my_player = my_game_data.player
        my_game = my_game_data.game
        keyword_list = [x.keyword for x in ExplorerGameQuest.objects.filter(game=my_game)]
        pass_dict = dict()
        pass_dict['user_id'] = my_player.name
        pass_dict['appid'] = my_player.app.appid
        pass_dict['open_id'] = my_player.open_id
        pass_dict['cur_keyword'] = my_game_data.cur_keyword.keyword
        pass_dict['cmd_str'] = my_game_data.cmd_str.strip()
        pass_dict['keyword_list'] =keyword_list
        return render(request, 'game_data.html', pass_dict)
    except ObjectDoesNotExist:
        return HttpResponse(f'Game data id: {game_data_id} does not exist')


@login_required
def update_media(request, media_type, appid):
    try:
        my_app = WechatApp.objects.get(appid=appid)
        if media_type in ['image', 'video']:
            count = my_app.get_media_from_tencent(media_type=media_type)
            if count >= 0:
                return HttpResponseRedirect(f'/summary/')
            else:
                return HttpResponse(f'Failed to update the medias')
        else:
            return HttpResponse(f'media_type is not valid')
    except ObjectDoesNotExist:
        return HttpResponse(f'App: {appid} does not exist')