import certifi
import csv
import io
import json
import os
import re
import sys
import time
import urllib3
from django.core.exceptions import *
from django.core.exceptions import ValidationError, ObjectDoesNotExist
from django.db import models
from django.db.models import F, Q, When, Count
import logging
from wxcloudrun import reply
from wxcloudrun.models import *
from wxcloudrun.coordinate_converter import *


sep = '|'           # 分隔符
alt_sep = '｜'      # 在分隔前会将此字符替换成sep，因此两者等效
sys.stdout = io.TextIOWrapper(sys.stdout.buffer,encoding='utf-8')  # 改变标准输出的默认编码
logger = logging.getLogger('log')


def replace_content_with_html(in_content):
    """
    将内容换成适合html的图文格式
    1、将换行\n替换为</p><p>，并在头尾分别加上<p>和</p>
    2、将里面< >包含的图片名称，换成media url <img src="xxxx" alt="yyy">
    """
    def replace_media(matched):
        image_name = matched.group('keyword')
        try:
            my_media = WechatMedia.objects.get(name=image_name)
            img_url = my_media.info['url']
            img_string = f'<p><img src="{img_url}" alt="{image_name}"></p>'
            return img_string
        except ObjectDoesNotExist:
            return matched

    ret_content = '<p>'
    ret_content += in_content.replace('\n', '</p><p>')
    ret_content += '</p>'
    re_pattern = '「(?P<keyword>[^」]+)」'
    matches = re.findall(pattern=re_pattern, string=ret_content)
    if len(matches) > 0:
        ret_result = re.sub(pattern=re_pattern, repl=replace_media, string=ret_content)
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

    def export_to_csv(self):
        """
        将本游戏下面所有quest保存为csv
        返回json对象
        {'result': True表示成功，False表示有异常
        'errmsg': string, 异常时开查看这个信息
        }
        """
        ret_dict = dict()
        ret_dict['result'] = False
        ret_dict['errmsg'] = 'Initial'
        find_string = '\r\n'
        replace_string = '</p><p>'
        try:
            f = open(self.settings_file, 'w', encoding='gbk')
            f.writelines('任务, 前置条件, 地点要求, 用户位置搜索关键词, 谜面类型,谜面,')
            f.writelines('提示类型,提示内容,答案列表,选项列表,奖励类型,奖励内容,奖励id\n')
        except:
            ret_dict['errmsg'] = f'setting file can not be created'
            return ret_dict
        all_quests = ExploreGameQuest.objects.filter(game=self)
        count = 0
        for quest in all_quests:
            export_list = list()
            export_list.append(quest.quest_trigger.replace(',', '，'))
            export_list.append(quest.prequire_list.replace(',', '，'))
            export_list.append(quest.location_list.replace(',', '，'))
            export_list.append(quest.poi_keyword.replace(',', '，'))
            export_list.append(quest.question_type)
            export_list.append(quest.question_data.replace(find_string, replace_string).replace(',', '，'))   #
            export_list.append(quest.hint_type)
            export_list.append(quest.hint_data.replace(find_string, replace_string).replace(',', '，'))
            export_list.append(quest.answer_list.replace(',', '，'))
            export_list.append(quest.options_list.replace(',', '，'))
            export_list.append(quest.reward_type)
            export_list.append(quest.reward.replace(',', '，'))
            export_list.append(str(quest.reward_id))
            f.writelines(','.join(export_list))
            f.writelines('\n')
            count += 1
            # logger.info(export_list)
        ret_dict['result'] = True
        ret_dict['errmsg'] = f'export {count} quests'
        return ret_dict

    def import_from_csv(self):
        ret_dict = dict()
        ret_dict['result'] = False
        ret_dict['errmsg'] = 'Initial'
        replace_string = '\r\n'
        find_string = '</p><p>'
        new_count = 0
        update_count = 0
        try:
            f = open(self.settings_file, 'r', encoding='gbk')
        except:
            ret_dict['errmsg'] = f'can not open setting file: {self.settings_file}'
            return ret_dict

        all_rows = f.readlines()
        for i in range(1, len(all_rows)):
            quest = all_rows[i].split(',')
            quest_trigger = quest[0]
            prequire_list = quest[1]
            location_list = quest[2]
            poi_keyword = quest[3]
            question_type = quest[4]
            question_data = quest[5].replace(find_string, replace_string)
            hint_type = quest[6]
            hint_data = quest[7].replace(find_string, replace_string)
            answer_list = quest[8]
            options_list = quest[9]
            reward_type = quest[10]
            reward = quest[11]
            reward_id = quest[12]
            if len(reward_id) > 0:
                reward_id = int(reward_id)
            else:
                reward_id = 0
            if len(quest_trigger) > 0:
                try:
                    my_quest = ExploreGameQuest.objects.get(game=self, quest_trigger=quest_trigger)
                    my_quest.quest_trigger = quest_trigger
                    my_quest.prequire_list = prequire_list
                    my_quest.location_list = location_list
                    my_quest.poi_keyword = poi_keyword
                    my_quest.question_type = question_type
                    my_quest.question_data = question_data
                    my_quest.hint_type = hint_type
                    my_quest.hint_data = hint_data
                    my_quest.answer_list = answer_list
                    my_quest.options_list = options_list
                    my_quest.reward = reward
                    my_quest.reward_type = reward_type
                    my_quest.reward_id = reward_id
                    my_quest.save()
                    update_count += 1
                except ObjectDoesNotExist:
                    my_quest = ExploreGameQuest(game=self, quest_trigger=quest_trigger, prequire_list=prequire_list,
                                                location_list=location_list, poi_keyword=poi_keyword,
                                                question_type=question_type, question_data=question_data,
                                                hint_type=hint_type, hint_data=hint_data, answer_list=answer_list,
                                                options_list=options_list, reward_type=reward_type, reward=reward,
                                                reward_id=reward_id)
                    new_count += 1
                my_quest.save()
        ret_dict['result'] = True
        ret_dict['errmsg'] = f'update {update_count} quests, create {new_count} quests'
        return ret_dict


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
                if type in ['question', 'hint']:
                    # 只有"问题内容"需要进行html样式更新
                    ret_content = replace_content_with_html(text_content)

                else:
                    # 其余类型无需转换
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