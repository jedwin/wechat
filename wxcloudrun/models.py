from django.db import models
from django.core.exceptions import *
from hashlib import sha1
from wxcloudrun.coordinate_converter import *
from django.db.models import F, Q, When, Count
import urllib3
import requests
import certifi
import json
import time
import os
import csv
import re
from wxcloudrun import reply
# from django.core.exceptions import ValidationError, ObjectDoesNotExist
from django.utils.translation import gettext_lazy as _
from logging import getLogger

error_code_access_token_expired = 42001
error_code_access_token_missing = 41001
errstring_access_token_expired = 'acc token refreshed, please re-run'
errstring_access_token_refresh_failed = 'acc token refresh failed'
error_code_access_token_refresh_failed = -2
error_code_media_type_incorrect = -3
error_code_unkown_error = -9
SEP_SYM = '|'  # 用于分隔多个内容的符号，后面会被用在split()函数中
keyword_hint = '提示'
keyword_card = '卡'
keyword_restart = '重新开始'
keyword_go_back = '返回'
keyword_start = '开始游戏'
keyword_control = '特殊指令'
keyword_invite = '邀请加入'
keyword_change_process = '改变进度'
error_reply_default = '你输入的答案不对，请再想想'
error_code_file = 'error_code.csv'
default_error_string = 'Unknow error'

logger = getLogger('django')

def get_error_string(in_code, in_file=error_code_file, default_string=default_error_string):
    """
    从腾讯的error_code文档中，找到对应的错误解释
    :param in_code: 腾讯中为正数，为了区分admin.py里面的返回值count，特意将错误码同一换成相反数
    :param in_file: 存储腾讯错误码的csv文件
    :param default_string: 无法找到对应错误码时返回的默认字符串
    :return: 如果能在in_file中找到解释就返回该解释，否则返回default_string
    """
    if os.path.exists(in_file):
        with open(in_file, 'r', encoding='utf-8') as f:
            error_lines = [x.split(',') for x in f.readlines()]
        for err_code, err_string in error_lines:
            if str(in_code) == err_code:
                return err_string
        # 如果整个循环结束仍为找到对应的err_code，就返回默认字符串
        return default_string
    else:
        # 如果没有找到错误码文件
        return f'{in_file} is not exists'


# Create your models here.
class WechatApp(models.Model):
    """
    WechatApp对象表示一个公众号
    """
    appid = models.CharField(max_length=100)
    secret = models.CharField(max_length=100)
    token = models.CharField(max_length=200)
    acc_token = models.CharField(max_length=500)
    name = models.CharField(max_length=100)
    en_name = models.CharField(max_length=100, default='')
    cur_game_name = models.CharField(max_length=100, default='')
    super_user = models.CharField(max_length=200, null=True)
    in_docker = models.BooleanField(default=False, verbose_name='是否在docker中运行') # 是否在docker中运行，会影响api调用的方式

    def __str__(self):
        return self.name

    def super_user_list(self):
        if self.super_user:
            return self.super_user.split(SEP_SYM)
        else:
            return []

    def refresh_access_token(self):
        """
        从腾讯服务器或docker本地更新access_token
        :param in_docker: 是否在docker中运行
        :return: access_token
        """
        if self.in_docker:
            # 如果在docker中运行，就从docker本地获取access_token
            acc_token_file = '/.tencentcloudbase/wx/cloudbase_access_token'
            with open(acc_token_file, 'r') as f:
                self.acc_token = f.readline()
                self.save()
                logger.info(f'access token refreshed: {self.acc_token}')
            return True
        else:
            # 如果不在docker中运行，就从腾讯服务器获取access_token
            http = urllib3.PoolManager(cert_reqs='CERT_REQUIRED', ca_certs=certifi.where())
            request_url = f'https://api.weixin.qq.com/cgi-bin/token?grant_type=client_credential&appid={self.appid}&secret={self.secret}'
            a = http.request('GET', request_url).data.decode('utf-8')
            b = json.loads(a)
            if 'errcode' in b.keys():
                errcode = 0 - int(b['errcode'])
                default_error_string = get_error_string(errcode)
                return False
            else:
                self.acc_token = b['access_token']
                self.save()
                print(f'access_token is refreshed: {self.acc_token}')
                return True

    def get_subscr_players(self, next_openid=None):
        """
        从微信服务器拉取已关注的用户清单，并与已有player清单对比，如果未在数据库的则补齐
        反过来，数据库中有，但拉取中没有，可能是未关注的用户，不需要删除，但要打上标识
        :param next_openid: 从这个id开始拉取，为None时从头开始拉取
        :return: True/False
        """

        http = urllib3.PoolManager(cert_reqs='CERT_REQUIRED', ca_certs=certifi.where())
        total_count = 1  # 所有关注用户数量，预设为1，为了发起第一次拉取
        got_count = 0  # 已获取的用户数量
        succ_count = 0  # 更新用户信息成功个数
        fail_count = 0  # 更新用户信息失败个数
        while got_count < total_count:
            if self.in_docker:
                request_url = f'https://api.weixin.qq.com/cgi-bin/user/get?access_token={self.acc_token}'
                if next_openid:
                    request_url += f'&next_openid={next_openid}'
            else:
                request_url = f'http://api.weixin.qq.com/cgi-bin/user/get'
                if next_openid:
                    request_url += f'?next_openid={next_openid}'

            # a = http.request('GET', request_url).data.decode('utf-8')
            # b = json.loads(a)
            a = requests.get(request_url)
            a.encoding = 'utf-8'
            b = a.json()
            error_code = b.get('error_code', 0)
            if error_code == 0:
                total_count = int(b['total'])
                got_count += int(b['count'])
                next_openid = b['next_openid']
                # data should be like
                # "data":{
                #     "openid":["OPENID1","OPENID2"]},
                openid_list = b['data']['openid']
                for openid in openid_list:
                    try:
                        my_player = WechatPlayer.objects.get(app=self, open_id=openid)  # 应该最多只有1个
                    except ObjectDoesNotExist:
                        my_player = WechatPlayer(app=self, open_id=openid)
                    result, error_code = my_player.get_user_info()
                    if result:
                        succ_count += 1
                    else:
                        fail_count += 1
            elif error_code == error_code_access_token_expired:
                if self.refresh_access_token():
                    return False, errstring_access_token_expired
                else:
                    return False, errstring_access_token_refresh_failed
            else:
                error_code = 0 - int(b['error_code'])
                error_string = get_error_string(error_code)
                return False, error_string
        # 如果成功，返回获取到的关注用户数量
        return True, f'共有{got_count}个关注用户，成功更新{succ_count}个，失败{fail_count}个'

    def get_media_from_tencent(self, media_type):
        """
        从微信公众号服务器上更新图片、视频或语音素材
        同时会删除不在服务器上的条目
        :media_type:
        :return: resource_dict
        """
        # http = urllib3.PoolManager(cert_reqs='CERT_REQUIRED', ca_certs=certifi.where())

        resource_dict = dict()
        offset = 0
        if self.refresh_access_token():
            if self.in_docker:
                request_url = f'https://api.weixin.qq.com/cgi-bin/material/batchget_material?access_token={self.acc_token}'
            else:
                request_url = f'http://api.weixin.qq.com/cgi-bin/material/batchget_material'
            try:
                total_count = self.get_resource_count(media_type=f'{media_type}_count')
                if total_count > 0:
                    logger.info(f'开始更新{media_type}素材，共{total_count}个')
                    # 从数据库中取出现有素材
                    images_in_db = WechatMedia.objects.filter(app=self, media_type=media_type)
                    media_id_in_db_list = [x.media_id for x in images_in_db]
                    # print(f'media_id_in_db_list: {media_id_in_db_list}')
                    # 获得图片总数后，进行全量抓取
                    media_id_in_server_list = list()
                    while offset <= total_count:
                        # form_data = f'''{{
                        #     "type":"{media_type}",
                        #     "offset":{offset},
                        #     "count":20
                        # }}'''
                        # a = http.request('POST', request_url, body=form_data, encode_multipart=False).data.decode(
                        #     'utf-8')
                        # b = json.loads(a)
                        form_data = {'type': media_type, 'offset': offset, 'count': 20}
                        a = requests.post(request_url, data=json.dumps(form_data, ensure_ascii=False).encode('utf-8'))
                        # print(f'a.encoding={a.encoding}')
                        a.encoding = 'utf-8'
                        b = a.json()
                        # print(f'a.encoding={a.encoding}')
                        error_code = b.get('error_code', 0)
                        if error_code == 0:
                            items = b['item']
                            item_count = b['item_count']
                            if item_count == 0:
                                break
                            offset += item_count
                            for item_dict in items:
                                # print(item_dict)
                                media_id = item_dict['media_id']
                                media_name = item_dict['name']
                                media_id_in_server_list.append(media_id)
                                # item_url = item_dict['url']
                                if media_id in media_id_in_db_list:
                                    # 如果数据库已有media_id相同的对象，就先删除
                                    old_medias = WechatMedia.objects.filter(app=self, media_id=media_id,
                                                                            media_type=media_type)
                                    old_medias.delete()
                                my_media = WechatMedia(app=self, media_id=media_id, media_type=media_type,
                                                       name=media_name, info=item_dict)
                                my_media.save()
                        else:
                            logger.error(f'获取{media_type}素材时出错，错误代码：{error_code}')
                            error_code = 0 - error_code
                            error_string = get_error_string(error_code)
                            return False
                        time.sleep(0.1)

                    # 清理数据库中冗余的条目
                    for media_id in media_id_in_db_list:
                        if media_id not in media_id_in_server_list:
                            try:
                                my_image = WechatMedia.objects.get(app=self, media_id=media_id)
                                my_image.delete()
                            except ObjectDoesNotExist:
                                pass
                    return total_count
                else:
                    # if total_count==0 means no resources in wechat server yet
                    # else some other error occured, return total_count directly
                    return total_count
            except:
                return error_code_unkown_error
        else:
            # failed to refresh access_token
            return error_code_access_token_refresh_failed

    def get_resource_count(self, media_type="image_count"):
        """

        :param media_type: "voice_count", "video_count","image_count", "news_count"
        :return:
        """
        if self.in_docker:
            # http = urllib3.PoolManager(cert_reqs='CERT_REQUIRED', ca_certs=certifi.where())
            request_count_url = f'https://api.weixin.qq.com/cgi-bin/material/get_materialcount?access_token={self.acc_token}'
        else:
            request_count_url = f'http://api.weixin.qq.com/cgi-bin/material/get_materialcount'
        # 获取图片总数
        # a = http.request('GET', request_count_url).data.decode('utf-8')
        # b = json.loads(a)
        a = requests.get(request_count_url)
        a.encoding = 'utf-8'
        b = a.json()
        # print(f'b={b}')
        error_code = b.get('error_code', 0)
        logger.console(f'error_code={error_code}')
        if error_code > 0:
            # print(b)
            # returning the negative value for error indicator
            return 0 - error_code
        else:
            if media_type in b.keys():
                total_count = b[media_type]
                print(f'return count: {total_count}')
                return total_count
            else:
                print(f'media_type incorrect: {media_type}')
                return error_code_media_type_incorrect

    def image_count(self):
        return WechatMedia.objects.filter(app=self, media_type='image').count()

    def video_count(self):
        return WechatMedia.objects.filter(app=self, media_type='video').count()

    def subscriber_count(self):
        return WechatPlayer.objects.filter(app=self, subscribe=1).count()

    def add_menu(self, remark='', menu_string=None):
        my_menu = WechatMenu(app=self, remark=remark, menu_string=menu_string)
        my_menu.save()


class WechatMedia(models.Model):
    """
    微信公众号的图片、视频、语音资源
    这种资源的info字段一样
    额外添加media_type来区分
    """
    app = models.ForeignKey(WechatApp, on_delete=models.CASCADE)
    media_id = models.CharField(max_length=100, null=True)
    name = models.CharField(max_length=200, null=True, blank=True)
    info = models.JSONField()
    media_type = models.CharField(max_length=20, null=True)

    def __str__(self):
        my_info = self.info
        return self.name

    def url(self):
        my_info = self.info
        return my_info.get('url', '')

    def update_time(self):
        my_info = self.info
        time_str = time.localtime(my_info['update_time'])
        return time.strftime("%Y-%m-%d %H:%M:%S", time_str)

    def tags(self):
        my_info = self.info
        return my_info.get('tags', '')

    def delete_from_wechat(self):
        """
        根据media id list删除图片素材
        :return: images_dict
        """
        media_count = self.app.get_resource_count()  # 用于确保刷新access_token
        if media_count >= 0:
            http = urllib3.PoolManager(cert_reqs='CERT_REQUIRED', ca_certs=certifi.where())
            request_url = f'https://api.weixin.qq.com/cgi-bin/material/del_material?access_token={self.app.acc_token}'
            my_info = json.loads(self.info)
            media_id = my_info['media_id']
            name = my_info['name']
            print(f'deleting {media_id}')
            form_data = f'''{{
                            "media_id":"{media_id}"
                        }}'''
            a = http.request('POST', request_url, body=form_data, encode_multipart=False).data.decode('utf-8')
            b = json.loads(a)
            error_code = b.get('error_code', 0)

            if error_code > 0:
                error_code = 0 - int(b['error_code'])
                error_string = get_error_string(error_code)
                return False
            else:
                self.delete()
                # print(f'已成功删除{name}')
                return True
        else:
            print(f'Can not get media_count')
            return False


def replace_content_with_hyperlink(my_content):
    """
    通过正则表达式查找文本中带【xx】的关键词，并替换成如下微信回复超链接
    【<a href="weixin://bizmsgmenu?msgmenuid=1&msgmenucontent=xx">xx</a>】
    如果超过1过选项，就在最后列出每个选项的超链接，样式如下：
    你的选择是？
    xxxx
    yyyy
    
    :param my_content:
    :return:
    """

    def insert_hyperlink(matched):
        link_before = '【<a href="weixin://bizmsgmenu?msgmenuid=1&msgmenucontent='
        link_mid = '">'
        link_after = '</a>】'
        keyword = matched.group('keyword')
        return f'{link_before}{keyword}{link_mid}{keyword}{link_after}'

    # 根据Python文档，使用(?P<name>...)语法时，那这个name，可以直接在re.sub()中repl参数指定的函数里引用
    # 例如insert_hyperlink函数中只会带1个参数--matched对象，它的group函数就可以直接调用以name命名的匹配字符串
    re_pattern = '【(?P<keyword>[^】]+)】'
    matches = re.findall(pattern=re_pattern, string=my_content)
    # link_before = '<a href="weixin://bizmsgmenu?msgmenuid=1&msgmenucontent='
    # link_mid = '">'
    # link_after = '</a>'

    if len(matches) > 0:
    #     # 如果超过1过选项，就在最后列出每个选项的超链接
    #     attached_string = f'\n你的选择是?\n\n'
    #     for keyword in matches:
    #         attached_string += f'''{link_before}{keyword}{link_mid}{keyword}{link_after}\n\n'''
    #     return f'{my_content}\n{attached_string}'
    # elif len(matches) == 1:
    #     # 如果只有1个关键词，就直接将关键词替换成超链接
        my_result = re.sub(pattern=re_pattern, repl=insert_hyperlink, string=my_content)
        return my_result
    else:
        # 如果文本中没有关键词，就按原样返回
        return my_content


class WechatPlayer(models.Model):
    app = models.ForeignKey(WechatApp, on_delete=models.CASCADE, null=True)
    name = models.CharField(max_length=100, default='-', blank=True)
    open_id = models.CharField(max_length=100, default='', primary_key=True)
    cur_game_name = models.CharField(max_length=100, default='', blank=True)
    is_audit = models.BooleanField(default=False)
    game_hist = models.JSONField(null=True, blank=True)
    nickname = models.CharField(max_length=100, default='', blank=True)
    remark = models.CharField(max_length=100, default='', blank=True)
    subscribe_scene = models.CharField(max_length=100, default='', blank=True)
    sex = models.IntegerField(null=True, blank=True)
    tagid_list = models.CharField(max_length=200, default='', blank=True)
    user_info = models.JSONField(null=True, blank=True)
    subscribe = models.IntegerField(default=0, blank=True)
    head_image = models.URLField(max_length=500, default='',  blank=True)
    cur_location = models.CharField(max_length=200, default='', blank=True)
    cur_longitude = models.FloatField(null=True, blank=True)
    cur_latitude = models.FloatField(null=True, blank=True)
    cur_Precision = models.FloatField(null=True, blank=True)
    poi_keyword = models.CharField('搜索兴趣点的关键词', max_length=50, default='', blank=True)
    poi_dist = models.IntegerField('搜索兴趣点的距离范围', default=100, blank=True)
    waiting_status_choice = [('', 'not in waiting status'), ('w_keyword', 'waiting for keyword'),
                             ('w_dist', 'waiting for distance'), ('w_password', 'waiting for password')]
    waiting_status = models.CharField(max_length=50, default='', blank=True)
    
    # tag_id = models.IntegerField(default=0, blank=True)
    
    # {'game_list': [WechatGameData]}

    def __str__(self):
        return self.nickname

    def game_data_count(self):
        return len(WechatGameData.objects.filter(player=self))

    def save(self, *args, **kwargs):
        self.poi_dist = max(self.poi_dist, 10)
        super().save(*args, **kwargs)

    def set_remark(self, remark):

        http = urllib3.PoolManager(cert_reqs='CERT_REQUIRED', ca_certs=certifi.where())
        request_url = f'https://api.weixin.qq.com/cgi-bin/user/info/updateremark?access_token={self.app.acc_token}'
        form_data = f'''{{
                        "openid":"{self.open_id}",
                        "remark":"{self.remark}"
                    }}'''
        a = http.request('POST', request_url, body=form_data.encode('utf-8'),
                         encode_multipart=False).data.decode('utf-8')
        b = json.loads(a)
        error_code = b.get('error_code', 0)
        if error_code == error_code_access_token_expired:
            if self.app.refresh_access_token():
                return False, errstring_access_token_expired
            else:
                return False, errstring_access_token_refresh_failed
        elif error_code > 0:
            error_code = 0 - int(b['error_code'])
            error_string = get_error_string(error_code)
            return False, error_string
        else:
            # 如果成功获取信息，就直接返回json文件
            return True, b

    def get_user_info(self):
        """
        从微信服务器获取某个用户的信息
        :param openid: 用户的openid
        :return: 返回用户信息
        """

        request_url = f'http://api.weixin.qq.com/cgi-bin/user/info?openid={self.open_id}&lang=zh_CN'
        # acc_token = self.app.refresh_access_token()
        # request_url = f'http://api.weixin.qq.com/sns/userinfo?access_token={acc_token}&openid={self.open_id}&lang=zh_CN'
        # a = http.request('GET', request_url).data.decode('utf-8')
        # b = json.loads(a)
        a = requests.get(request_url)
        a.encoding = 'utf-8'
        b = a.json()
        print(b)
        error_code = b.get('error_code', 0)
        if error_code == 0:
            self.nickname = b['nickname']
            self.remark = b['remark']
            self.subscribe_scene = b['subscribe_scene']
            self.sex = int(b['sex'])
            self.tagid_list = b['tagid_list']
            self.subscribe = b['subscribe']
            self.user_info = b
            self.save()
            return True, error_code
        elif error_code == error_code_access_token_expired:
            if self.app.refresh_access_token():
                return False, errstring_access_token_expired
            else:
                return False, errstring_access_token_refresh_failed
        else:
            error_code = 0 - int(b['error_code'])
            return False, error_code

    def get_nearby_poi(self):
        if self.cur_longitude is None or self.cur_latitude is None:
            return False, '未能获取用户位置信息'
        elif len(self.poi_keyword) == 0:
            return False, '未设置搜索关键词'
        elif self.poi_dist < 10:
            return False, '搜索范围小与10米最低要求，请重新设置'
        my_map = QqMap.objects.all()[0]
        result, ret_obj = my_map.search_places(longitude=self.cur_longitude, latitude=self.cur_latitude,
                                               dist=self.poi_dist, keyword=self.poi_keyword)
        if result:
            poi_list = ret_obj
            self.cur_location += str(poi_list)
            self.save()
            return result, poi_list
        else:
            errmsg = ret_obj
            return result, errmsg

    def get_location_address(self):
        if self.cur_longitude is None or self.cur_latitude is None:
            return False, '未能获取用户位置信息'
        my_map = QqMap.objects.all()[0]
        result, ret_obj = my_map.get_place_name(longitude=self.cur_longitude, latitude=self.cur_latitude)
        if result:
            self.cur_location = ret_obj
            self.save()
            return result, ret_obj
        else:
            errmsg = ret_obj
            return result, errmsg

    def hash_with_game(self, cur_game_name, len=8):
        temp_string = (self.open_id + cur_game_name).encode('utf-8')
        return sha1(temp_string).hexdigest()[0-len:]


class AppKeyword(models.Model):
    app = models.ForeignKey(WechatApp, on_delete=models.CASCADE, null=True)
    keyword = models.CharField(max_length=100, null=True)
    content_type_choice = [('文字', '文字'), ('视频', '视频'), ('图片', '图片')]
    content_type = models.CharField(max_length=100, choices=content_type_choice, default='文字')
    content_data = models.TextField(max_length=1000, default='')

    def reply_msg(self, toUser, fromUser):
        if self.content_type in ['文字', 'TEXT']:
            text_content = self.content_data.replace('<br>', '\n').strip()
            replyMsg = reply.TextMsg(toUser, fromUser, text_content)
        elif self.content_type in ['图片', 'PIC']:
            my_media = WechatMedia.objects.filter(app=self.app, name=self.content_data)
            if len(my_media) > 0:
                # 如果有重名的图片，就发第一张
                mediaId = my_media[0].media_id
                replyMsg = reply.ImageMsg(toUser, fromUser, mediaId)
            else:
                text_content = f'找不到对应的图片{self.content_data}，请联系管理员'
                replyMsg = reply.TextMsg(toUser, fromUser, text_content)

        elif self.content_type in ['视频', 'VIDEO']:
            my_media = WechatMedia.objects.filter(app=self.app, name=self.content_data)
            if len(my_media) > 0:
                # 如果有重名的视频，就发第一个
                mediaId = my_media[0].media_id
                replyMsg = reply.VideoMsg(toUser, fromUser, mediaId, self.content_data, '')
            else:
                text_content = f'找不到对应的视频{self.content_data}，请联系管理员'
                replyMsg = reply.TextMsg(toUser, fromUser, text_content)
        else:
            text_content = f'app关键词的内容类型{self.content_type}错误，请联系管理员'
            replyMsg = reply.TextMsg(toUser, fromUser, text_content)

        return replyMsg


class ErrorAutoReply(models.Model):
    """
    玩家答错自动回复对象
    """
    reply_type_choice = [('TEXT', '文字'), ('PIC', '图片')]
    reply_type = models.CharField(max_length=10, default='文字', choices=reply_type_choice)
    reply_content = models.TextField(default=error_reply_default)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.reply_content

    def reply_msg(self, toUser, fromUser='', for_text=True):
        content_type = self.reply_type
        content_data = self.reply_content
        if content_type == 'TEXT':
            text_content = content_data.replace('<br>', '\n').strip()
            if for_text:
                text_content = replace_content_with_hyperlink(text_content)
                replyMsg = reply.TextMsg(toUser, fromUser, text_content)
            else:
                ret_content = text_content
        elif content_type == 'PIC':
            my_media = WechatMedia.objects.filter(app=self.game.app, name=content_data)
            if len(my_media) > 0:
                # 如果有重名的图片，就发第一张
                mediaId = my_media[0].media_id
                if for_text:
                    replyMsg = reply.ImageMsg(toUser, fromUser, mediaId)
                else:
                    # return the image url
                    ret_content = my_media[0].info.get('url', '')
            else:
                text_content = f'找不到对应的图片{content_data}，请联系管理员'
                replyMsg = reply.TextMsg(toUser, fromUser, text_content)
                ret_content = text_content
        else:
            text_content = f'答错自动回复内容{content_type}错误，请联系管理员'
            replyMsg = reply.TextMsg(toUser, fromUser, text_content)
            ret_content = text_content

        if for_text:
            return replyMsg
        else:
            return ret_content


class WechatMenu(models.Model):
    """
    公众号自定义菜单
    """
    app = models.ForeignKey(WechatApp, on_delete=models.CASCADE, null=True, blank=True)
    menu_string = models.JSONField(null=True, blank=True)
    remark = models.CharField(max_length=100, default='', blank=True)
    MatchRule = models.BooleanField(default=False)
    match_tag_id = models.CharField(max_length=100, default='', blank=True)
    
    def __str__(self):
        return self.remark

    def save(self):
        result, ret_obj = self.gen_menu_json()
        if result:
            super(WechatMenu, self).save()
            return True, 'OK'
        else:
            return False, ret_obj

    def gen_menu_json(self):
        buttons = MenuButton.objects.filter(menu=self)
        json_dict = dict()
        json_dict['button'] = list()
        for button in buttons:
            result, ret_obj = button.gen_json_dict()
            if result:
                json_dict['button'].append(ret_obj)
            else:
                return False, ret_obj
        if self.MatchRule:
            if len(self.match_tag_id) > 0:
                json_dict['matchrule'] = {'tag_id': self.match_tag_id}
        self.menu_string = json_dict
        return True, 'OK'

    def submit_menu(self):
        acc_token = self.app.acc_token
        # http = urllib3.PoolManager(cert_reqs='CERT_REQUIRED', ca_certs=certifi.where())
        # request_url = f'https://api.weixin.qq.com/cgi-bin/menu/create?access_token={acc_token}'
        request_url = f'http://api.weixin.qq.com/cgi-bin/menu/create'
        try:
            pass
            # my_menu = json.loads(self.menu_string, encoding='utf-8')

        except:
            return False, 'menu_string is not valid'

        else:
            # a = http.request('POST', request_url, body=json.dumps(self.menu_string, ensure_ascii=False).encode('utf-8'),
            #                  encode_multipart=False).data.decode('utf-8')
            # b = json.loads(a)
            a = requests.post(request_url, data=json.dumps(self.menu_string, ensure_ascii=False).encode('utf-8'))
            a.encoding = 'utf-8'
            b = a.json()
            error_code = b.get('error_code', 0)
            errmsg = b.get('errmsg', 'OK')
            if error_code == 0:
                return True, errmsg
            elif error_code == error_code_access_token_expired:
                if self.app.refresh_access_token():
                    return False, errstring_access_token_expired
                else:
                    return False, errstring_access_token_refresh_failed
            else:
                # 如果成功获取信息，就直接返回json文件
                return False, errmsg


class MenuButton(models.Model):
    menu = models.ForeignKey(WechatMenu, on_delete=models.CASCADE, null=True)
    name = models.CharField('菜单标题', max_length=120, default='')
    type_choice = [('sub_button', '二级菜单'), ('click', '按钮'), ('view', '链接'), ('scancode_waitmsg', '扫码带提示'),
                   ('scancode_push', '扫码推事件'), ('pic_sysphoto', '系统拍照发图'),
                   ('pic_photo_or_album', '拍照或者相册发图'),
                   ('pic_weixin', '微信相册发图'), ('location_select', '选择位置'),
                   ('media_id', '图文消息'), ('view_limited', '图文消息（限制）'),
                   ('article_id', '发布后的图文消息'), ('article_view_limited', '发布后的图文消息（限制）')]
    type = models.CharField(max_length=100, default='click', choices=type_choice)
    key = models.CharField(max_length=100, default='', blank=True)
    url = models.TextField(max_length=1000, default='', blank=True)
    media_id = models.CharField(max_length=100, default='', blank=True)
    app_id = models.CharField('小程序id', max_length=300, default='', blank=True)
    pagepath = models.CharField('小程序页面路径', max_length=300, default='', blank=True)
    article_id = models.CharField(max_length=100, default='', blank=True)
    sub_button = models.JSONField(null=True, blank=True)

    def __str__(self):
        return f'{self.menu.remark} {self.name}'

    def gen_json_dict(self):
        ret_dict = dict()
        if len(self.name) == 0:
            return False, 'name is blank'
        else:
            ret_dict['name'] = self.name
            if self.type == 'sub_button':
                sub_buttons = MenuSubButton.objects.filter(parent_button=self)
                if len(sub_buttons) > 0:
                    # check sub buttons
                    ret_dict['sub_button'] = list()
                    for sub_button in sub_buttons:
                        result, ret_obj = sub_button.gen_json_dict()
                        if result:
                            ret_dict['sub_button'].append(ret_obj)

                        else:
                            return False, ret_obj
                    self.sub_button = ret_dict
                    self.save()
            elif self.type in ['view']:
                if len(self.url) == 0:
                    return False, 'url is blank while type=view'
                else:
                    ret_dict['url'] = self.url
                    ret_dict['type'] = self.type
            elif self.type in ['click', 'location_select']:
                if len(self.key) == 0:
                    return False, f'key is blank in {self.name}'
                else:
                    ret_dict['key'] = self.key
                    ret_dict['type'] = self.type

        return True, ret_dict


class MenuSubButton(models.Model):
    parent_button = models.ForeignKey(MenuButton, on_delete=models.DO_NOTHING, null=True)
    name = models.CharField('菜单标题', max_length=120, default='')
    type_choice = [('click', '按钮'), ('view', '链接'), ('scancode_waitmsg', '扫码带提示'),
                   ('scancode_push', '扫码推事件'), ('pic_sysphoto', '系统拍照发图'),
                   ('pic_photo_or_album', '拍照或者相册发图'),
                   ('pic_weixin', '微信相册发图'), ('location_select', '选择位置'),
                   ('media_id', '图文消息'), ('view_limited', '图文消息（限制）'),
                   ('article_id', '发布后的图文消息'), ('article_view_limited', '发布后的图文消息（限制）')]
    type = models.CharField(max_length=100, default='click', choices=type_choice)
    key = models.CharField(max_length=100, default='', blank=True)
    url = models.TextField(max_length=1000, default='', blank=True)
    media_id = models.CharField(max_length=100, default='', blank=True)
    app_id = models.CharField('小程序id', max_length=300, default='', blank=True)
    pagepath = models.CharField('小程序页面路径', max_length=300, default='', blank=True)
    article_id = models.CharField(max_length=100, default='', blank=True)

    def __str__(self):
        return f'{self.parent_button.name} {self.name}'

    def gen_json_dict(self):
        ret_dict = dict()
        if len(self.name) == 0:
            return False, 'name is blank'
        else:
            ret_dict['name'] = self.name
        if self.type in ['click', 'location_select']:
            if len(self.key) == 0:
                return False, 'key is blank while type=click'
            else:
                ret_dict['key'] = self.key
                ret_dict['type'] = self.type
        elif self.type in ['view']:
            if len(self.url) == 0:
                return False, 'url is blank while type=view'
            else:
                ret_dict['url'] = self.url
                ret_dict['type'] = self.type
        else:
            pass
        return True, ret_dict


class QqMap(models.Model):
    name = models.CharField(max_length=100, default='', blank=True)
    key = models.CharField(max_length=100, default='', blank=True)

    def __str__(self):
        return self.name

    def search_places(self, longitude, latitude, dist, keyword):
        longitude, latitude = wgs84_to_gcj02(longitude, latitude)
        http = urllib3.PoolManager(cert_reqs='CERT_REQUIRED', ca_certs=certifi.where())
        request_url = 'https://apis.map.qq.com/ws/place/v1/search?'
        request_url += f'boundary=nearby({latitude},{longitude},{dist},0)'
        request_url += f'&key={self.key}&keyword={keyword}'
        a = http.request('GET', request_url).data.decode('utf-8')
        b = json.loads(a)
        status = b.get('status', -1)
        ret_list = list()
        if status == 0:
            POIs = b.get('data', list())

            for poi_dict in POIs:
                poi_title = poi_dict.get('title', '')
                if len(poi_title) > 0:
                    ret_list.append(poi_title)
            return True, ret_list
        else:
            message = b.get('message', '')
            return False, message

    def get_place_name(self, longitude, latitude):
        longitude, latitude = wgs84_to_gcj02(longitude, latitude)
        http = urllib3.PoolManager(cert_reqs='CERT_REQUIRED', ca_certs=certifi.where())
        request_url = f'https://apis.map.qq.com/ws/geocoder/v1/?location={latitude},{longitude}&key={self.key}'
        a = http.request('GET', request_url).data.decode('utf-8')
        b = json.loads(a)
        status = b.get('status', -1)
        if status == 0:
            result = b.get('result', dict())
            address = result.get('address', '')
            recommend = result.get('formatted_addresses', dict()).get('recommend', '')
            return True, f'{address} {recommend}'
        else:
            message = b.get('message', '')
            return False, message