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
from wxcloudrun import views2 as mpv2

urlpatterns = (
    path('wechat/miaozan/', mpv2.check_signature),      # 淼赞文化专用
    path('<str:filename>', mpv2.download),         # 用于微信公众号域名验证下载文件
    path('admin/', admin.site.urls),
    path('accounts/', include('django.contrib.auth.urls')),
    path('code/', mpv2.get_user_info_with_code),  # 用于微信网页授权获取用户信息
    path('profile/', mpv2.show_profile),  # 显示用户信息（微信风格页面）
)
