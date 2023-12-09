"""wxcloudrun URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/3.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""

from django.contrib import admin
from django.urls import path, include
from wxcloudrun import views2 as mpv2, summary
from wxcloudrun import view_ai as vai
from wxcloudrun import social_django as sd
from django.contrib.auth import views
import os

HOME_SERVER = os.environ.get('HOME_SERVER', '')  # 存放静态文件的服务器地址，留空则使用本地
if len(HOME_SERVER) > 0:
    if HOME_SERVER[-1] != '/':
        HOME_SERVER += '/'
else:
    HOME_SERVER = '/'

urlpatterns = (
    path('admin/', admin.site.urls),
    path('wechat/miaozan/', mpv2.check_signature),      # 淼赞文化专用
    # path('code/callback_google/', sd.callback_google),  # 用于Google OAuth2授权回调，获取用户信息
    # path('code/auth_google/', sd.authorize_google),  # 用于触发Google OAuth2授权
    path('code/callback_github/', sd.callback_github),  # 用于Github OAuth2授权回调，获取用户信息
    path('code/auth_github/', sd.authorize_github),  # 用于触发Github OAuth2授权
    path('code/callback_synology/', sd.callback_synology),  # 用于群晖OAuth2授权回调，获取用户信息
    path('code/auth_synology/', sd.authorize_synology),  # 用于触发群晖OAuth2授权
    path('profile/', mpv2.show_profile),  # 显示用户信息（微信风格页面）
    path('check_answer/', mpv2.check_answer),  # 检查js提交的答案是否正确
    path('game/', mpv2.game),  # 以Django用户管理方式进入游戏
    path('chat/', vai.chat),  # 与GPT对话能力
    path('file/<str:filename>', mpv2.download),         # 用于微信公众号域名验证下载文件
    # path('static/images/layers/<str:filename>', mpv2.redirect),         # 用于将图片重定向到微信云托管域名
    path('accounts/', include("django.contrib.auth.urls")),  # 用于django自带的登录、登出、密码重置等功能
    path('summary/', summary.list_app_view),  # 定制管理页面
    path('summary/<appid>/', summary.list_app_view),  # 定制管理页面
    path('summary/images/<appid>/', summary.list_image_view),  # 图片管理页面
    path('summary/videos/<appid>/', summary.list_video_view),  # 视频管理页面
    path('summary/del_media/<appid>/<media_id>/', summary.del_media),  # 图片管理页面
    path('summary/list_user/<appid>/', summary.list_user_view),  # 用户列表页面
    path('summary/list_user/<appid>/<game_name>/', summary.list_user_view),  # 用户列表页面
    path('summary/user_detail/<appid>/<open_id>/', summary.check_user_view),  # 用户详情页面
    path('summary/list_game/<appid>/', summary.list_game_view),  # 游戏列表页面
    path('summary/game_data/<game_data_id>/', summary.gamed_data_view),  # 玩家游戏档案页面
    path('summary/flow_chart/<appid>/<game_name>/', summary.show_mermaid_chart),  # 游戏流程图页面
    path('summary/reload_keyword/<appid>/<game_name>/', summary.reload_keyword),  # 更新游戏关键词
    path('summary/update_media/<media_type>/<appid>/', summary.update_media),  # 更新公众号图片视频资源
    path('summary/check_media_availability/<appid>/<game_name>/', summary.check_media_availability),  # 检查游戏相关的图片视频缺失情况
)
