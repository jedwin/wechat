from django.core.exceptions import *
import google_auth_oauthlib.flow
from googleapiclient.discovery import build
import os
from django.shortcuts import HttpResponse, render, HttpResponseRedirect
from django.http import JsonResponse
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
import requests
from requests_oauthlib import OAuth2Session
from django.conf import settings
from wxcloudrun.common_functions import gen_passwd
from wxcloudrun.models import WechatPlayer
from hashlib import sha1
import logging

logger = logging.getLogger('django')

DEFAULT_NEXT_URL = '/game/'

################ for Github OAuth2.0 ################
GITHUB_OAUTH_CLIENT_ID = os.environ.get('GITHUB_CLIENT_ID')
GITHUB_OAUTH_CLIENT_SECRET = os.environ.get('GITHUB_CLIENT_SECRET')
GITHUB_OAUTH_REDIRECT_URI = os.environ.get('GITHUB_REDIRECT_URI')
GITHUB_OAUTH_SCOPE = ['user:email']

def authorize_github(request):
    if request.user.is_authenticated:
        return HttpResponseRedirect('/game/')
    else:
        # 生成一个随机字符串，用于防止跨站请求伪造攻击
        state = gen_passwd(leng=16, use_lower=True, use_upper=True, use_number=True, use_symbol=False)
        # 将state放入当前会话中
        request.session['state'] = state
        logger.info(f'set state: {state}')
        github = OAuth2Session(GITHUB_OAUTH_CLIENT_ID, redirect_uri=GITHUB_OAUTH_REDIRECT_URI, scope=[GITHUB_OAUTH_SCOPE], state=state)
        authorization_url, _ = github.authorization_url('https://github.com/login/oauth/authorize')
        
        return HttpResponseRedirect(authorization_url)

def callback_github(request):
    # check the state
    state = request.GET.get('state', '')
    stored_state = request.session.get('state', '')
    # logger.info(f'returned state: {state}')
    if state == stored_state:
        github = OAuth2Session(GITHUB_OAUTH_CLIENT_ID)
        token = github.fetch_token('https://github.com/login/oauth/access_token', client_secret=GITHUB_OAUTH_CLIENT_SECRET,
                                authorization_response=request.build_absolute_uri())
        if token:
        # 在此处处理GitHub授权成功后的逻辑
            access_token = token['access_token']
            # logger.info(f'access_token: {access_token}')
            # 获取用户信息，使用headers参数将access_token放入请求头中
            
            github_user_info = requests.get('https://api.github.com/user', headers={'Authorization': f'token {access_token}'}).json()
            if 'id' in github_user_info.keys():
                github_id = github_user_info['id']
                user = find_user(id=github_id, auth_user_info=github_user_info, auth_type='github')
                if user:
                    
                    login(request, user)
                    return HttpResponseRedirect('/game/')
                else:
                    return HttpResponse(f'无法找到对应的玩家。github_user_info: {github_user_info}')  
            else:
                # 无法获取用户信息
                return JsonResponse(github_user_info)
        else:
            return HttpResponse('GitHub授权失败，请重试！')
    else:
        return HttpResponse('state验证失败，请重试！')

################ for Google OAuth2.0 ################
GOOGLE_API_CLIENT_SECRET = os.environ.get("GOOGLE_API_CLIENT_SECRET")
GOOGLE_API_CLIENT_id = os.environ.get("GOOGLE_API_CLIENT_ID")
SCOPES = ['https://www.googleapis.com/auth/userinfo.profile']
CLIENT_SECRETS_FILE = "client_secret.json"
API_SERVICE_NAME = 'oauth2'
API_VERSION = 'v2'

def authorize_google(request):
    # 先保存要返回的URL
    next_url = request.GET.get('next', DEFAULT_NEXT_URL)
    
    # 先判断当前用户是否已经登录，如果已经登录，则直接跳转到首页
    if request.user.is_authenticated:
        return HttpResponseRedirect(next_url)
    else:
        request.session['next_url'] = next_url
        # 开始进行Google OAuth2.0认证
        # Create flow instance to manage the OAuth 2.0 Authorization Grant Flow steps.
        flow = google_auth_oauthlib.flow.Flow.from_client_secrets_file(
                CLIENT_SECRETS_FILE, scopes=SCOPES)

        # The URI created here must exactly match one of the authorized redirect URIs
        # for the OAuth 2.0 client, which you configured in the API Console. If this
        # value doesn't match an authorized URI, you will get a 'redirect_uri_mismatch'
        # error.
        # flow.redirect_uri = 'https://www.key2go.top:8443/code'
        flow.redirect_uri = os.environ.get("GOOGLE_API_REDIRECT_URI")

        authorization_url, state = flow.authorization_url(
                # Enable offline access so that you can refresh an access token without
                # re-prompting the user for permission. Recommended for web server apps.
                access_type='offline',
                # Enable incremental authorization. Recommended as a best practice.
                include_granted_scopes='true')
        # 将state放入当前会话中
        request.session['state'] = state

        logger.info(f'state={state}')
        # logger.info(f'authorization_url={authorization_url}')
        return HttpResponseRedirect(authorization_url)


def callback_google(request):
    # Specify the state when creating the flow in the callback so that it can
    # verified in the authorization server response.
    state = request.GET.get('state', '')
    if state != request.session.get('state', ''):
        # The state in the response doesn't match the state in the request.
        # 可能是CSRF攻击
        return HttpResponse('The state is not correct, please try again.')
    else:
        flow = google_auth_oauthlib.flow.Flow.from_client_secrets_file(
                CLIENT_SECRETS_FILE, scopes=SCOPES, state=state)
        flow.redirect_uri = os.environ.get("GOOGLE_API_REDIRECT_URI")

        # Use the authorization server's response to fetch the OAuth 2.0 tokens.
        authorization_response = request.build_absolute_uri()
        flow.fetch_token(authorization_response=authorization_response)

        # Store credentials in the session.
        # ACTION ITEM: In a production app, you likely want to save these
        #                            credentials in a persistent database instead.
        credentials = flow.credentials
        credentials_dict = credentials_to_dict(credentials)
        # token = credentials_dict['token']
        logger.info(credentials_dict)
        user_profile = build('oauth2', 'v2', credentials=credentials)
        google_user_info = user_profile.userinfo().get().execute()
        google_id = google_user_info['id']
        user = find_user(id=google_id, auth_user_info=google_user_info, auth_type='google')
        if user:
            # 取回要返回的URL
            next_url = request.session.get('next_url', DEFAULT_NEXT_URL)
            login(request, user)
            return HttpResponseRedirect(next_url)
        else:
            return HttpResponse(f'无法找到对应的玩家。google_user_info: {google_user_info}')


def credentials_to_dict(credentials):
    return {'token': credentials.token,
            'refresh_token': credentials.refresh_token,
            'token_uri': credentials.token_uri,
            'client_id': credentials.client_id,
            'client_secret': credentials.client_secret,
            'scopes': credentials.scopes}

def find_user(id=None, auth_user_info=None, auth_type=None):
    """
    根据id和auth_type查找玩家，然后通过玩家user_info json对象中的user_id查找对应的User对象
    param: id: 通过OAuth2.0认证后得到的用户id
    param: auth_user_info: 通过OAuth2.0认证后得到的用户信息字典
    param: auth_type: 认证类型，目前支持github和google

    return: None 或 User对象
    
    """
    if id and auth_type:
        players = WechatPlayer.objects.all()
        # 根据player.user_info['github_id']查找是否已经存在该用户
        for player in players:
            if player.user_info:  # 如果玩家的user_info不为空
                user_auth_dict = player.user_info.get(auth_type, {})
                if auth_type in ['github', 'google']:
                    auth_user_id = user_auth_dict.get('id', '')
                else:
                    return HttpResponse(f'不支持的认证类型：{auth_type}')
                
                user_id = player.user_info.get('user_id', '')
                if user_id:
                    if auth_user_id == id:
                        # 找到匹配的用户，先更新对应的user_info
                        player.user_info[auth_type] = auth_user_info
                        player.save()
                        # 再用user_id查找对应的User对象
                        try:
                            user = User.objects.get(id=user_id)
                            return user
                        except ObjectDoesNotExist:
                            return HttpResponse(f'找到user_id，但无法找到对应的用户。user_id: {user_id}')
                    else:
                        continue
                else:
                    # 这个玩家没有user_id，可能是之前的老玩家，需要更新user_id
                    continue
            else:  # 玩家的user_info为空
                open_id = player.open_id
                if open_id:
                    for user in User.objects.all():
                        if open_id == sha1(str(user.id).encode('utf-8')).hexdigest():
                            # 找到匹配的用户，再用user_id查找对应的User对象
                            player.user_info = {'user_id': user.id, auth_type: {}}
                            player.save()
                        else:
                            continue
                else:  # 玩家的openid为空
                    continue