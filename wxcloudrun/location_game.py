from django.db import models
from django.core.exceptions import *
from .coordinate_converter import *
from django.db.models import F, Q, When, Count
import urllib3
import certifi
import json
import time
import os
import csv
import re
from wxcloudrun import reply
from wxcloudrun.models import *
from django.core.exceptions import ValidationError, ObjectDoesNotExist

sep = '|'           # 分隔符
alt_sep = '｜'      # 在分隔前会将此字符替换成sep，因此两者等效


def replace_content_with_html(in_content):
    """
    将内容换成适合html的图文格式
    1、将换行\n替换为</p><p>，并在头尾分别加上<p>和</p>
    2、将里面< >包含的图片名称，换成media url <img src="xxxx" alt="yyy">
    """
    def replace_media(matched):
        try:
            my_media = WechatMedia.objects.get(name=matched)
            img_url = my_media.info['url']
            img_string = f'<img scr="{img_url}" alt="{matched}">'
            return img_string
        except ObjectDoesNotExist:
            return matched

    ret_content = '<p>&nbsp&nbsp'
    ret_content += in_content.replace('\n', '</p><p>&nbsp&nbsp')
    ret_content += '</p>'
    re_pattern = '「(?P<keyword>[^」]+)」'
    matches = re.findall(pattern=re_pattern, string=ret_content)
    if len(matches) > 0:
        ret_result = re.sub(pattern=re_pattern, repl=insert_hyperlink, string=ret_content)
        return ret_result
    else:
        # 如果文本中没有需要插入图片，就按原样返回
        return ret_content


class ExploreGame(models.Model):
    app = models.ForeignKey(WechatApp, on_delete=models.CASCADE, null=True)
    name = models.CharField(max_length=100)
    opening = models.TextField(max_length=1000, default='', verbose_name='游戏启动内容', blank=True)
    settings_file = models.CharField(max_length=300)
    is_active = models.BooleanField(default=False)
    clear_requirement = models.CharField(max_length=100, default='', blank=True, 
                                         verbose_name='本游戏通关条件，以｜分隔')
    clear_notice = models.TextField(max_length=1000, default='', verbose_name='本游戏通关提示内容', blank=True)
    
    def __str__(self):
        return f'{self.app}_{self.name}'

    def get_content_list(self, type='clear_requirement'):
        """
        将配置的列表类配置，返回为list对象
        """
        if type == 'clear_requirement':
            content = self.clear_requirement
            if len(content) > 0:
                return [int(x) for x in content.replace(alt_sep, sep).split(sep)]
            else:
                return list()
        else:
            # 类型错误
            content = ''
        if len(content) > 0:
            return content.replace(alt_sep, sep).split(sep)
        else:
            return list()
        

class ExploreGameQuest(models.Model):
    game = models.ForeignKey(ExploreGame, on_delete=models.CASCADE)
    quest_trigger = models.CharField(max_length=100, default='', verbose_name='本题触发词')
    prequire_list = models.CharField(max_length=1000, default='', blank=True,
                                     verbose_name='本题前置条件，以｜分隔，留空表示无需额外条件')
    location_list = models.CharField(max_length=1000, default='', blank=True,
                                     verbose_name='限定位置关键词，以｜分隔，留空表示不限定位置')
    poi_keyword = models.CharField(max_length=10, default='', blank=True,
                                   verbose_name='地点POI关键词，用于搜索用户周边')
    question_type_choice = [('TEXT', '文字'), ('VIDEO', '视频'), ('PIC', '图片')]
    question_type = models.CharField(max_length=10, choices=question_type_choice, default='TEXT', verbose_name='谜面类型')
    question_data = models.TextField(max_length=1000, default='', verbose_name='谜面')
    hint_type = models.CharField(max_length=10, choices=question_type_choice, default='TEXT', verbose_name='提示类型')
    hint_data = models.TextField(max_length=1000, default='', verbose_name='提示内容', blank=True)
    answer_list = models.CharField(max_length=100, default='', verbose_name='谜底列表，以｜分隔')
    options_list = models.CharField(max_length=1000, default='', blank=True,
                                    verbose_name='谜底选项列表，以｜分隔，留空表示填空题')
    reward_type = models.CharField(max_length=10, choices=question_type_choice, default='TEXT', verbose_name='奖励类型')
    reward = models.TextField(max_length=1000, default='', verbose_name='本题奖励内容')
    reward_id = models.IntegerField(default=0, verbose_name='本题奖励id')

    def __str__(self):
        return f'{self.game}_{self.quest_trigger}'

    def reply_msg(self, type, toUser, fromUser='', for_text=True):
        """
        新增for_text参数，默认情况下，返回的replyMsg对象可以直接送给玩家在微信文字版中使用
        当for_text==False，返回的内容将作在网页版上
        """
        if type == 'question':
            # 发送关键词正文
            content_type = self.question_type
            content_data = self.question_data
        elif type == 'hint':
            # 发送提示内容
            content_type = self.hint_type
            content_data = self.hint_data
        elif type == 'reward':
            # 发送进度卡图片
            content_type = self.reward_type
            content_data = self.reward
        else:
            # 类型错误
            content_type = '文字'
            content_data = f'关键词的内容类型{type}错误，请联系管理员'

        if content_type == 'TEXT':
            text_content = content_data.replace('<br>', '\n').strip()
            if for_text:
                text_content = replace_content_with_hyperlink(text_content)
                replyMsg = reply.TextMsg(toUser, fromUser, text_content)
            else:
                ret_content = replace_content_with_html(text_content)
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

        elif content_type == 'VIDEO':
            my_media = WechatMedia.objects.filter(app=self.game.app, name=content_data)
            if len(my_media) > 0:
                # 如果有重名的视频，就发第一个
                mediaId = my_media[0].media_id
                if for_text:
                    replyMsg = reply.VideoMsg(toUser, fromUser, mediaId, content_data, self.video_desc)
                else:
                    # return the video url
                    ret_content = my_media[0].info.get('url', '')
            else:
                text_content = f'找不到对应的视频{content_data}，请联系管理员'
                replyMsg = reply.TextMsg(toUser, fromUser, text_content)
                ret_content = text_content
        else:
            text_content = f'关键词的内容类型{content_type}错误，请联系管理员'
            replyMsg = reply.TextMsg(toUser, fromUser, text_content)
            ret_content = text_content
        if for_text:
            return replyMsg
        else:
            return ret_content

    def get_content_list(self, type):
        """
        将配置的列表类配置，返回为list对象
        """
        if type == 'prequire':
            content = self.prequire_list
            if len(content) > 0:
                return [int(x) for x in content.replace(alt_sep, sep).split(sep)]
            else:
                return list()
        elif type == 'location':
            content = self.location_list
        elif type == 'option':
            content = self.options_list
        elif type == 'answer':
            content = self.answer_list
        else:
            # 类型错误
            content = ''
        if len(content) > 0:
            return content.replace(alt_sep, sep).split(sep)
        else:
            return list()