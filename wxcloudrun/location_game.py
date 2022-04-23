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
from django.db import models
from django.db.models import F, Q, When, Count
from django.http import HttpResponse
import logging
from wxcloudrun import reply
from wxcloudrun.models import *
from wxcloudrun.coordinate_converter import *
from wxcloudrun.user_manage import gen_passwd

WAITING_FOR_PASSWORD = 'w_password'             # 等待用户输入认证密码
WAITING_FOR_POI_KEYWORD = 'w_keyword'           # 等待用户输入POI关键词
WAITING_FOR_POI_DISTANCE = 'w_dist'             # 等待用户输入POI搜索范围（米）
ASK_FOR_PASSWORD = '请先输入从客服处获得的密码'
AUDIT_SUCCESS = '验证成功，请重新点击菜单开始游戏'
AUDIT_FAILED = '密码错误，请查证后再输入'
GAME_IS_NOT_ACTIVE = '对不起，游戏未启动或时间已过'

CHECK_CLEAR_CODE = '查看通关密码'
CHECK_PROGRESS = '查看当前进度'
FIELD_CLEAR_CODE = 'clear_code'                 # 存放通过码的字典key
FIELD_REWARD_LIST = 'reward_list'               # 存放已获取奖励的字典key
FIELD_COMMAND_DICT = 'cmd_dict'                 # 存放已行动命令的字典key
FIELD_IS_AUDIT = 'is_audit'                     # 存在当前用户在当前游戏是否已认证的key
FIELD_WAIT_STATUS = 'wait_status'               # 保存当前游戏的当前任务
OPTION_ENABLE = 'weui-cell weui-cell_access'    # 提供可选选项的样式
OPTION_DISABLE = 'weui-cell weui-cell_disable'  # 提供不可选选项的样式
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
            my_medias = WechatMedia.objects.filter(name=image_name)
            if len(my_medias) > 0:
                my_media = my_medias[0]
                img_url = my_media.info['url']
                img_string = f'<p style="text-align: center;"><img src="{img_url}" alt="{image_name}"></p>'
                return img_string
            else:
                return image_name
        except ObjectDoesNotExist:
            return matched
    if len(in_content) > 0:
        ret_content = '<p>'
        ret_content += in_content.replace('\n', '</p><p>')
        ret_content += '</p>'
        re_pattern = '「(?P<keyword>[^」]+)」'
        return re.sub(pattern=re_pattern, repl=replace_media, string=ret_content)
        # matches = re.findall(pattern=re_pattern, string=ret_content)
        # if len(matches) > 0:
        #     ret_result = re.sub(pattern=re_pattern, repl=replace_media, string=ret_content)
        #     return ret_result
        # else:
        #     # 如果文本中没有需要插入图片，就按原样返回
        #     return ret_content
    else:
        # 如果in_content为空，则原样返回
        return in_content


class ExploreGame(models.Model):
    app = models.ForeignKey(WechatApp, on_delete=models.CASCADE, null=True)
    name = models.CharField(max_length=100)
    opening = models.TextField(max_length=1000, default='', verbose_name='游戏启动内容', blank=True)
    settings_file = models.CharField(max_length=300, blank=True, verbose_name='游戏配置文件')
    is_active = models.BooleanField(default=False)
    clear_requirement = models.CharField(max_length=100, default='', blank=True, 
                                         verbose_name='本游戏通关条件，以｜分隔')
    clear_notice = models.TextField(max_length=1000, default='', verbose_name='本游戏通关提示内容', blank=True)
    passwd_init = models.CharField(max_length=5, default='0', verbose_name='本游戏密码的开头字符', blank=True)
    entry = models.CharField(max_length=100, default='', verbose_name='游戏入口任务，留空表示直接显示所有可以挑战任务', blank=True)
    
    def __str__(self):
        return f'{self.app}_{self.name}'

    def show_opening(self):
        return replace_content_with_html(self.opening)

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
            f = open(self.settings_file, 'w', encoding='utf-8')
            f.writelines('任务, 前置条件, 地点要求, 用户位置搜索关键词, 谜面类型,谜面,')
            f.writelines('提示类型,提示内容,答案列表,选项列表,奖励类型,奖励内容,奖励id,')
            f.writelines('下一步选项列表,是否显示下一步,返回任务名称,未满足条件时是否显示,')
            f.writelines('未满足条件时显示的提示,满足条件时显示的提示,已完成时显示的提示,音频文件链接\n')
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
            export_list.append(quest.next_list.replace(',', '，'))
            export_list.append(str(quest.show_next))
            export_list.append(quest.back_quest.replace(',', '，'))
            export_list.append(str(quest.show_if_unavailable))
            export_list.append(quest.comment_when_unavailable.replace(',', '，'))
            export_list.append(quest.comment_when_available.replace(',', '，'))
            export_list.append(quest.comment_when_clear.replace('\n', ''))
            export_list.append(str(quest.audio_link))
            f.writelines(','.join(export_list))
            f.writelines('\n')
            count += 1

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
            f = open(self.settings_file, 'r', encoding='utf-8')
        except:
            ret_dict['errmsg'] = f'can not open setting file: {self.settings_file}'
            return ret_dict

        all_rows = f.readlines()
        for i in range(1, len(all_rows)):
            quest = all_rows[i].replace('\n','').split(',')
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
            next_list = quest[13]
            show_next = quest[14].upper()
            back_quest = quest[15]
            show_if_unavailable = quest[16].upper()
            comment_when_unavailable = quest[17]
            comment_when_available = quest[18]
            comment_when_clear = quest[19]
            audio_link = quest[20]
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
                    my_quest.next_list = next_list
                    if show_next == 'TRUE':
                        my_quest.show_next = True
                    else:
                        my_quest.show_next = False
                    my_quest.back_quest = back_quest
                    if show_if_unavailable == 'TRUE':
                        my_quest.show_if_unavailable = True
                    else:
                        my_quest.show_if_unavailable = False
                    my_quest.comment_when_unavailable = comment_when_unavailable
                    my_quest.comment_when_available = comment_when_available
                    my_quest.comment_when_clear = comment_when_clear
                    my_quest.audio_link = audio_link
                    my_quest.save()
                    update_count += 1
                except ObjectDoesNotExist:
                    my_quest = ExploreGameQuest(game=self, quest_trigger=quest_trigger, prequire_list=prequire_list,
                                                location_list=location_list, poi_keyword=poi_keyword,
                                                question_type=question_type, question_data=question_data,
                                                hint_type=hint_type, hint_data=hint_data, answer_list=answer_list,
                                                options_list=options_list, reward_type=reward_type, reward=reward,
                                                reward_id=reward_id, next_list=next_list, show_next=show_next,
                                                back_quest=back_quest, show_if_unavailable=show_if_unavailable,
                                                comment_when_unavailable=comment_when_unavailable,
                                                comment_when_available=comment_when_available,
                                                comment_when_clear=comment_when_clear, audio_link=audio_link)
                    new_count += 1
                my_quest.save()
        ret_dict['result'] = True
        ret_dict['errmsg'] = f'update {update_count} quests, create {new_count} quests'
        return ret_dict

    def gen_passwords(self, how_many=20):
        if how_many > 100:
            # 因为托管的mysql按业务次数收费，所以每次不能生成太多
            how_many = 100
        count = 0
        for i in range(how_many):
            try:
                new_passwd_str = gen_passwd(initial=self.passwd_init, length=6, use_number=True,
                                            use_upper=False, use_lower=False)
                new_passwd = WechatGamePasswd(game=self, password=new_passwd_str)
                new_passwd.save()
                logger.info(f'new_passwd_str={new_passwd_str}')
                count += 1
            except Exception as e:
                # 如果新建失败，例如密码重复了，log下来
                logger.error(f'{e}')
        return count

    def check_progress(self, reward_list):
        # 为某个玩家总结进度描述文字
        done_q_name_list = list()
        all_quest = ExploreGameQuest.objects.filter(game=self)
        total_reward = 0
        for q in all_quest:
            if q.reward_id > 0:
                total_reward += 1
            if q.reward_id in reward_list:
                done_q_name_list.append(q.quest_trigger)
        total_done = len(done_q_name_list)
        if total_done == total_reward:
            text_content = f'您已经完成全部{total_reward}个任务！'
        elif total_done > 0:
            text_content = f'您现在完成了{total_reward}个任务中的{total_done}个：{str(done_q_name_list)[1:-1]}。'
        else:
            text_content = f'您一共需要完成{total_reward}个任务，但一个都还没有完成。'
        return text_content

    def export_password(self, available_only=True):
        cur_datetime = time.strftime('%Y%m%d%H%M%S',time.localtime())
        # file_name = f'{self.name}可用密码列表{cur_datetime}.csv'
        file_name = 'passwords.csv'
        response = HttpResponse(
            content_type='text/csv; charset=gbk',
        )
        response.headers['Content-Disposition']= f'attachment; filename="{file_name}"'
        logger.info(f'export game password: {response.headers}')
        passwd_list = list(WechatGamePasswd.objects.filter(game=self, is_assigned=not available_only))
        writer = csv.writer(response)
        writer.writerow(['game name', 'password'])
        for passwd in passwd_list:
            writer.writerow([self.name, passwd.password])

        return response


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
    question_data = models.TextField(max_length=1000, default='', verbose_name='谜面', blank=True)
    hint_type = models.CharField(max_length=10, choices=question_type_choice, default='TEXT', verbose_name='提示类型')
    hint_data = models.TextField(max_length=1000, default='', verbose_name='提示内容', blank=True)
    answer_list = models.CharField(max_length=100, default='', verbose_name='谜底列表，以｜分隔', blank=True)
    options_list = models.CharField(max_length=1000, default='', blank=True,
                                    verbose_name='谜底选项列表，以｜分隔，留空表示填空题')
    reward_type = models.CharField(max_length=10, choices=question_type_choice, default='TEXT', verbose_name='奖励类型')
    reward = models.TextField(max_length=1000, default='', verbose_name='本题奖励内容', blank=True)
    reward_id = models.IntegerField(default=0, verbose_name='本题奖励id')
    next_list = models.CharField(max_length=1000, default='', blank=True,
                                 verbose_name='下一步任务分支选项，以｜分隔，只有在这个列表中的任务才来作为下一步')
    show_next = models.BooleanField(default=True, verbose_name='是否显示下一步分支选项，如果不显示，则以answer_list的答案来跳转下一步')
    back_quest = models.CharField(max_length=100, default='', verbose_name='返回到某个任务的名称，留空表示返回到开始', blank=True)
    show_if_unavailable = models.BooleanField(default=False, verbose_name='未满足挑战条件时是否显示')
    comment_when_unavailable = models.CharField(max_length=100, default='还不能选择', verbose_name='未满足挑战条件时显示的提示')
    comment_when_available = models.CharField(max_length=100, default='可选择', verbose_name='满足挑战条件时显示的提示')
    comment_when_clear = models.CharField(max_length=100, default='已完成', verbose_name='已完成任务时显示的提示')
    audio_link = models.URLField(max_length=1000, default='',  blank=True, verbose_name='音频文件链接')

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

        if content_type in ['TEXT', 'PIC', 'VIDEO']:  # 现在用html格式统一显示，所以不需要区分文字、图片或视频
            text_content = content_data.replace('<br>', '\n').strip()
            if for_text:
                text_content = replace_content_with_hyperlink(text_content)
                replyMsg = reply.TextMsg(toUser, fromUser, text_content)
            else:
                if type in ['question', 'hint', 'reward']:
                    # 只有"问题内容"需要进行html样式更新
                    ret_content = replace_content_with_html(text_content)

                else:
                    # 其余类型无需转换
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
            if len(self.answer_list) > 0:
                content = self.answer_list
            elif len(self.next_list) > 0:
                content = self.next_list
            else:
                content = ''
        elif type == 'next':
            content = self.next_list
        else:
            # 类型错误
            content = ''
        if len(content) > 0:
            return content.replace(alt_sep, sep).split(sep)
        else:
            return list()


class WechatGamePasswd(models.Model):
    # app = models.ForeignKey(WechatApp, on_delete=models.CASCADE, null=True)
    game = models.ForeignKey(ExploreGame, default=None, on_delete=models.CASCADE, blank=True, null=True)
    password = models.CharField(max_length=50, primary_key=True)
    assigned_player = models.ForeignKey(WechatPlayer, default=None, on_delete=models.CASCADE, blank=True, null=True)
    is_assigned = models.BooleanField(default=False, verbose_name='是否已分配')

    def __str__(self):
        return self.password

    def assign_to_player(self, open_id, force=False):
        try:
            my_player = WechatPlayer.objects.get(app=self.game.app, open_id=open_id)
            if not self.is_assigned or force:
                self.assigned_player = my_player
                self.is_assigned = True
                self.save()
                return True
            else:
                print(f'this passwd is already assigned to player')
                return False
        except ObjectDoesNotExist:
            # can't find the open_id player
            print(f'can not find the player with open_id {open_id}')
            return False

        except MultipleObjectsReturned:
            # multiple player with same open_id were found
            print(f'multiple player with open_id {open_id} were found')
            return False

    def export_to_csv(self):
        return f'{self.app.name},{self.password},{self.assigned_player.name}'

    def clear_player(self):
        self.assigned_player = None
        self.is_assigned = False
        self.save()
        return True
