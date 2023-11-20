
import io
import os
import re
import sys
import time
from django.core.exceptions import *
from django.db import models
from django.db.models import F, Q, When, Count
from django.http import HttpResponse
from django.contrib.auth.models import User, Group
import logging
from wxcloudrun import reply
from wxcloudrun.models import *
from wxcloudrun.coordinate_converter import *
from wxcloudrun.user_manage import gen_passwd
from sqlalchemy import create_engine, text

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
INITIAL_COMMAND = 'init'                        # 初始化命令
ENDING_COMMAND = 'ending'                          # 已通关标记
# home_server = 'https://www.key2go.top:8443'
HOME_SERVER = os.environ.get('HOME_SERVER', '')  # 存放静态文件的服务器地址，留空则使用本地
if len(HOME_SERVER) > 0:
    if HOME_SERVER[-1] != '/':
        HOME_SERVER += '/'
else:
    HOME_SERVER = '/'
domain_name = 'miao2022.com'                    # 用于创建新账号的邮件地址域名

SETTING_PATH = '/settings/'      # 游戏设置文件存放路径
sep = '|'           # 分隔符
alt_sep = '｜'      # 在分隔前会将此字符替换成sep，因此两者等效
sys.stdout = io.TextIOWrapper(sys.stdout.buffer,encoding='utf-8')  # 改变标准输出的默认编码

################# 内部数据库信息，用于游戏数据统计 #################
db_name = os.environ.get("database")
db_user = os.environ.get("user")
db_password = os.environ.get("password")
db_host = '172.17.0.1'
db_port = '2345'
to_table = 'game_statisitc_data'
sslmode = 'require'
engine_str = f'postgresql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}'
pg_engine_miao = create_engine(engine_str, connect_args={'sslmode': sslmode}, echo=False)
###################### 数据库信息结束 ########################

logger = logging.getLogger('django')

def replace_content_with_html(in_content):
    """
    将内容换成适合html的图文格式
    1、将换行\n替换为</p><p>，并在头尾分别加上<p>和</p>
    2、将里面< >包含的图片名称，换成media url <img src="xxxx" alt="yyy">
    """
    def replace_media(matched):
        """
        将匹配到的图片名称替换成media url
        由于改用本地服务器，因此不再需要进行WechatMedia的查询
        """
        file_name = matched.group('keyword')
        # 根据file_name后缀名，判断是图片、音频还是视频，从而生成不同的html代码
        if file_name.endswith('.jpg') or file_name.endswith('.png'):
            img_url = f'images/' + file_name
            ret_string = f'<p style="text-align: center;"><img src="{HOME_SERVER}{img_url}" alt="{file_name}"></p>'
        elif file_name.endswith('.mp3') or file_name.endswith('.m4a'):
            audio_url = f'mp3/' + file_name
            ret_string = f'<p style="text-align: center;"><audio autoplay controls><source src="{HOME_SERVER}{audio_url}" type="audio/mpeg"></audio></p>'
        elif file_name.endswith('.mp4') or file_name.endswith('.m4v') or file_name.endswith('.mov'):
            video_url = f'video/' + file_name
            ret_string = f'<p style="text-align: center;"><video src="{HOME_SERVER}{video_url}" controls="controls"></video></p>'
        else:
            # 如果不是图片、音频、视频，则直接返回空字符串
            ret_string = ''
        return ret_string
        # try:
        #     # my_medias = WechatMedia.objects.filter(name=image_name)
        #     if len(my_medias) > 0:
        #         my_media = my_medias[0]
        #         img_url = my_media.info['url']
        #         img_string = f'<p style="text-align: center;"><img src="{img_url}" alt="{image_name}"></p>'
        #         return img_string
        #     else:
        #         return image_name
        # except ObjectDoesNotExist:
        #     return matched
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
    account_file = models.CharField(max_length=300, default='', verbose_name='用户名列表文件，用于创建用户', blank=True)

    class Meta:
        verbose_name = '游戏'
        verbose_name_plural = '游戏'

    def __str__(self):
        return f'{self.app}_{self.name}'

    def show_opening(self):
        return replace_content_with_html(self.opening)
    
    def show_clear_notice(self):
        return replace_content_with_html(self.clear_notice)

    def get_content_list(self, type='clear_requirement'):
        """
        将配置的列表类配置，返回为list对象
        """
        try:
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
        except Exception as e:
            # log the error
            logger.error(f'get_content_list error: {e}')
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
            f = open(f'{SETTING_PATH}{self.settings_file}', 'w', encoding='utf_8_sig')
            f.writelines('任务, 前置条件, 地点要求, 用户位置搜索关键词, 谜面类型,谜面,')
            f.writelines('提示类型,提示内容,答案列表,选项列表(已废弃),奖励类型,奖励内容,奖励id,')
            f.writelines('下一步选项列表,是否显示下一步,返回任务名称,未满足条件时是否显示,')
            f.writelines('未满足条件时显示的提示,满足条件时显示的提示,已完成时显示的提示,音频文件链接\n')
        except Exception as e:
            ret_dict['errmsg'] = f'setting file can not be created: {e}'
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
            f.writelines(','.join(export_list))
            f.writelines('\n')
            count += 1

        ret_dict['result'] = True
        ret_dict['errmsg'] = f'export {count} quests'
        return ret_dict

    def export_to_obsidian(self):
        """
        将本游戏下面所有quest保存为obsidian的多markdown文件格式
        保存路径为self.settings_file对应的文件名
        例如settings_file=game1.csv，那么保存的文件夹路径是f'{SETTING_PATH}game1'
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
            if self.settings_file[-4:] == '.csv':
                folder_name = self.settings_file[:-4]   # 去掉.csv
            else:
                folder_name = self.settings_file
            if not os.path.exists(f'{SETTING_PATH}{folder_name}'):
                os.mkdir(f'{SETTING_PATH}{folder_name}')
            md_flow_chart_file = f'{SETTING_PATH}{folder_name}/flow_chart.md'
            self.save_to_mermaid(md_file=md_flow_chart_file)
        except Exception as e:
            ret_dict['errmsg'] = f'obsidian folder can not be created: {e}'
            return ret_dict
        all_quests = ExploreGameQuest.objects.filter(game=self)
        count = 0
        for quest in all_quests:
            quest_md_file = f'{SETTING_PATH}{folder_name}/{quest.quest_trigger}.md'
            try:
                f = open(quest_md_file, 'w', encoding='utf_8_sig')
                f.writelines(f'# {quest.quest_trigger}\n\n')
                f.writelines(f'### 前置条件\n\n')
                f.writelines(f'{quest.prequire_list}\n\n')
                f.writelines(f'### 地点要求\n\n')
                f.writelines(f'{quest.location_list}\n\n')
                f.writelines(f'### 用户位置搜索关键词\n\n')
                f.writelines(f'{quest.poi_keyword}\n\n')
                f.writelines(f'### 谜面类型\n\n')
                f.writelines(f'{quest.question_type}\n\n')
                f.writelines(f'### 谜面\n\n')
                f.writelines(f'{quest.question_data}\n\n')
                f.writelines(f'### 提示类型\n\n')
                f.writelines(f'{quest.hint_type}\n\n')
                f.writelines(f'### 提示内容\n\n')
                f.writelines(f'{quest.hint_data}\n\n')
                f.writelines(f'### 答案列表\n\n')
                f.writelines(f'{quest.answer_list}\n\n')
                f.writelines(f'### 选项列表\n\n')
                f.writelines(f'{quest.options_list}\n\n')
                f.writelines(f'### 奖励类型\n\n')
                f.writelines(f'{quest.reward_type}\n\n')
                f.writelines(f'### 奖励内容\n\n')
                f.writelines(f'{quest.reward}\n\n')
                f.writelines(f'### 奖励id\n\n')
                f.writelines(f'{quest.reward_id}\n\n')
                f.writelines(f'### 下一步选项列表\n\n')
                f.writelines(f'[[{quest.next_list.replace("|","]], [[")}]]\n\n')
                f.writelines(f'### 是否显示下一步\n\n')
                f.writelines(f'{quest.show_next}\n\n')
                f.writelines(f'### 返回任务名称\n\n')
                f.writelines(f'{quest.back_quest}\n\n')
                f.writelines(f'### 未满足条件时是否显示\n\n')
                f.writelines(f'{quest.show_if_unavailable}\n\n')
                f.writelines(f'### 未满足条件时显示的提示\n\n')
                f.writelines(f'{quest.comment_when_unavailable}\n\n')
                f.writelines(f'### 满足条件时显示的提示\n\n')
                f.writelines(f'{quest.comment_when_available}\n\n')
                f.writelines(f'### 已完成时显示的提示\n\n')
                f.writelines(f'{quest.comment_when_clear}\n\n')

                f.close()

            except Exception as e:
                ret_dict['errmsg'] = f'obsidian file {quest_md_file} can not be created: {e}'
                return ret_dict
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
        delete_count = 0
        try:
            f = open(f'{SETTING_PATH}{self.settings_file}', 'r', encoding='utf_8_sig')
        except:
            ret_dict['errmsg'] = f'can not open setting file: {self.settings_file}'
            return ret_dict

        try:
            all_rows = f.readlines()
            lines_number = len(all_rows)
            quest_list = list()
            for i in range(1, lines_number):
                quest = all_rows[i].replace('\n','').split(',')
                quest_trigger = quest[0]
                prequire_list = quest[1]
                location_list = quest[2]
                poi_keyword = quest[3]
                question_type = 'TEXT'  # quest[4]
                question_data = quest[5].replace(find_string, replace_string)
                hint_type = 'TEXT'  # quest[6]
                hint_data = quest[7].replace(find_string, replace_string)
                answer_list = quest[8]
                options_list = quest[9]
                reward_type = 'TEXT'  # quest[10]
                reward = quest[11]
                reward_id = quest[12]
                if len(reward_id) > 0:
                    reward_id = int(reward_id)
                else:
                    reward_id = 0
                next_list = quest[13]
                if quest[14].upper() == 'TRUE':
                    show_next = True
                else:
                    show_next = False
                back_quest = quest[15]
                if quest[16].upper() == 'TRUE':
                    show_if_unavailable = True
                else:
                    show_if_unavailable = False
                comment_when_unavailable = quest[17]
                comment_when_available = quest[18]
                comment_when_clear = quest[19]

                # 下面做一些数据的修正
                if len(answer_list) == 0:
                    # 如果没有配置答案列表，则默认是选择题
                    show_next = True

                # 开始导入关卡数据
                
                if len(quest_trigger) > 0:
                    try:
                        # 如果尝试匹配现有的关卡进行更新
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
                        my_quest.show_next = show_next
                        my_quest.back_quest = back_quest
                        my_quest.show_if_unavailable = show_if_unavailable
                        my_quest.comment_when_unavailable = comment_when_unavailable
                        my_quest.comment_when_available = comment_when_available
                        my_quest.comment_when_clear = comment_when_clear

                        my_quest.save()
                        update_count += 1
                        quest_list.append(quest_trigger)
                    except ObjectDoesNotExist:
                        # 如果没有找到关卡，则创建一个新的关卡
                        my_quest = ExploreGameQuest(game=self, quest_trigger=quest_trigger, prequire_list=prequire_list,
                                                    location_list=location_list, poi_keyword=poi_keyword,
                                                    question_type=question_type, question_data=question_data,
                                                    hint_type=hint_type, hint_data=hint_data, answer_list=answer_list,
                                                    options_list=options_list, reward_type=reward_type, reward=reward,
                                                    reward_id=reward_id, next_list=next_list, show_next=show_next,
                                                    back_quest=back_quest, show_if_unavailable=show_if_unavailable,
                                                    comment_when_unavailable=comment_when_unavailable,
                                                    comment_when_available=comment_when_available,
                                                    comment_when_clear=comment_when_clear)
                        quest_list.append(quest_trigger)
                    new_count += 1
                    my_quest.save()
            
            # 删除没有在csv文件中出现的关卡
            all_quests = ExploreGameQuest.objects.filter(game=self)
            for quest in all_quests:
                if quest.quest_trigger not in quest_list:
                    quest.delete()
                    delete_count += 1
            ret_dict['result'] = True
            ret_dict['errmsg'] = f'删除了 {delete_count} 个旧关卡, 导入 {new_count} 个新关卡，更新了 {update_count} 个已有关卡。'
            return ret_dict
        except IndexError as e:
            ret_dict['errmsg'] = f'csv文件 {self.settings_file} 的第{i}行存在问题: {e}'
            return ret_dict
        except UnicodeDecodeError as e:
            ret_dict['errmsg'] = f'csv文件 {self.settings_file} 无法解码，请检查是否使用了UTF-8编码保存: {e}'
            return ret_dict
        except Exception as e:
            ret_dict['errmsg'] = f'导入csv文件 {self.settings_file} 时出错。 {e}'
            return ret_dict

    def gen_passwords(self, how_many=20):
        """
        用于生成密码对象，已废弃
        """
        if how_many > 100:
            # 未免误操作，此处做一个限制
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

    def gen_users(self, how_many=20, from_file=False, passwd_length=3, user_name_length=3):
        """
        为本游戏生成新的用户
        :param how_many: 生成多少个用户, 默认20个, 最多100个
        :param from_file: 是否从文件中读取用户信息，如果设为True，则忽略how_many参数，且self.account_file必须不为空
                            如果设为False，则从how_many参数指定的数量生成用户，并会将生成的用户信息写入文件f'{SETTING_PATH}{self.name}_新账号清单.csv'
        :param file_name: 从文件中读取用户信息的文件名
        :return: 成功生成的用户数量
        
        """
        output_file = f'{SETTING_PATH}{self.name}_新账号清单.csv'
        if how_many > 100:
            # 未免误操作，此处做一个限制
            how_many = 100
        count = 0
        delect_count = 0
        # 检查是否存在游戏名称对应的组
        try:
            group = Group.objects.get(name=self.name)
            logger.info(f'group {self.name} exists')
        except ObjectDoesNotExist:
            group = Group.objects.create(name=self.name)
            logger.info(f'group {self.name} created')
        
        if from_file:
            if not self.account_file:
                logger.error(f'请先设置self.account_file')
                return 0
            try:
                # open a file to read
                f = open(f'{SETTING_PATH}{self.account_file}', 'r', encoding='utf_8_sig')
                input_data = f.readlines()
                how_many = len(input_data)
                f.close()
            except Exception as e:
                logger.error(f'读取文件 {self.account_file} 出错: {e}')
                return 0
        # open a file to append, if not exists, create it
        if os.path.exists(output_file):
            fi = open(output_file, 'r', encoding='utf_8_sig')
            existing_users_data = [x.replace('\n', '').split(',') for x in fi.readlines()]
            fi.close()
        else:
            existing_users_data = []
        fo = open(output_file, 'w', encoding='utf_8_sig')
        created_user_list = []
        for i in range(how_many):
            try:
                if from_file:
                    # 从文件中读取用户名和密码
                    user_data_list = input_data[i].replace('\n', '').split(',')
                    if len(user_data_list) == 2:
                        # 如果该行有两列，第一列作为用户名，第二列作为密码
                        new_user_name, new_passwd_str = user_data_list
                        new_passwd_str = new_passwd_str.strip()
                    else:
                        # 否则，只是使用第一列做用户名，密码自动生成
                        new_user_name = user_data_list[0]
                        new_passwd_str = gen_passwd(initial=self.passwd_init, length=passwd_length, use_number=True,
                                                    use_upper=False, use_lower=False)
                else:
                    # 生成随机的账号和密码
                    new_user_name = gen_passwd(initial=self.passwd_init, length=user_name_length, use_number=False,
                                            use_upper=True, use_lower=False)
                    new_passwd_str = gen_passwd(initial=self.passwd_init, length=passwd_length, use_number=True,
                                                    use_upper=False, use_lower=False)
                
                try: # 检查用户名是否已经存在，如果存在，就先删除
                    cur_user = User.objects.get(username=new_user_name)
                    cur_user.delete()
                    delect_count += 1
                    # logger.error(f'用户名 {new_user_name} 已经存在，已删除')
                except ObjectDoesNotExist:
                    pass

                new_user = User.objects.create_user(new_user_name, f'{new_user_name}@{domain_name}', new_passwd_str)
                new_user.groups.add(group)
                marked = False
                for x in existing_users_data:
                    if x[0] == new_user_name:
                        x[1] = new_passwd_str
                        marked = True
                        break
                if not marked:
                    existing_users_data.append([new_user_name, new_passwd_str])
                # created_user_list.append(f'{new_user_name},{new_passwd_str}')
                count += 1
            except Exception as e:
                logger.error(f'{e}')
                continue
        existing_users_str_list = list()
        for x in existing_users_data:
            existing_users_str_list.append(','.join(x))

        fo.writelines('\n'.join(existing_users_str_list))
        fo.writelines('\n')
        fo.close()
        return count

    def check_progress(self, reward_list):
        # 为某个玩家总结进度描述文字
        done_q_name_list = list()
        all_quest = ExploreGameQuest.objects.filter(game=self)
        total_reward_list = list()
        for q in all_quest:
            if q.reward_id > 0:
                total_reward_list.append(q.reward_id)
            if q.reward_id in reward_list:
                done_q_name_list.append(q.quest_trigger)
        total_done = len(set(reward_list))
        total_reward = len(set(total_reward_list))
        if total_done >= total_reward:
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

    def md_file(self):
        return f'{SETTING_PATH}{self.settings_file.replace(".csv", ".md")}'

    def md_file_url(self):
        return f'{SETTING_PATH}{self.md_file()}'

    def save_to_mermaid(self, graph_type='TD', md_file=None):
        """
        生成mermaid的流程图
        """
        if md_file:
            game_md_file = md_file
        else:
            game_md_file = self.md_file()
        logger.info(f'start to generate mermaid file for {self.name}, game_md_file={game_md_file}')
        NEW_LINE = '\n'
        with open(game_md_file, 'w', encoding='utf_8_sig') as f:
            my_keywords = ExploreGameQuest.objects.filter(game=self)
            logger.info(f'game {self.name} has {len(my_keywords)} keywords')
            f.writelines(f'```mermaid\n')
            if graph_type == 'TD':
                f.writelines(f'graph {graph_type}\n')
                f.writelines(f'classDef picclass fill:#f9f,stroke:#333,stroke-width:2px;\n')
                f.writelines(f'classDef videoclass fill:#bbf,stroke:#f66,color:#fff,stroke-dasharray: 5 5;\n')
            elif graph_type == 'state':
                f.writelines(f'stateDiagram-v2\n')
            else:
                logger.error(f'graph_type={graph_type} not supported')
                f.writelines(f'```\n')
                return False

            for my_keyword in my_keywords:
                try:
                    from_word = my_keyword.question_data[:20].replace("-", "").replace(NEW_LINE, "<br>").replace("，", "<br>")
                    from_word = from_word.replace("【", "").replace("】", "").replace("「", "").replace("」", "")
                    if graph_type == 'TD':
                        f.writelines(f'id_{my_keyword.pk}["{my_keyword.quest_trigger}-{from_word}"]\n')
                        # if my_keyword.question_type == '图片':
                        #     f.writelines(f'style id_{my_keyword.pk}\n')
                        # elif my_keyword.question_type == '视频':
                        #     f.writelines(f'style id_{my_keyword.pk} fill:#bbf,stroke:#f66,'
                        #                  f'stroke-width:2px,color:#fff,stroke-dasharray: 5 5\n')
                    elif graph_type == 'state':
                        f.writelines(f'{my_keyword.quest_trigger} : {my_keyword.quest_trigger}-{from_word}...{NEW_LINE}')
                    else:
                        # should not happen
                        pass
                except Exception as e:
                    logger.error(f'error when generate mermaid file for {self.name}, {e}')
                    f.writelines(f'```\n')
                    return False

            for my_keyword in my_keywords:
                for next_keyword in my_keyword.next_list.split(sep):
                    try:
                        # remove the space in the next_keyword
                        next_keyword = next_keyword.strip()
                        next_kw = ExploreGameQuest.objects.get(game=self, quest_trigger=next_keyword)
                        if graph_type == 'TD':
                            if my_keyword.question_type == '图片':
                                f.writelines(f'id_{my_keyword.pk}:::picclass --> |{next_keyword}| id_{next_kw.pk}\n')
                            else:
                                f.writelines(f'id_{my_keyword.pk} --> |{next_keyword}| id_{next_kw.pk}\n')
                        elif graph_type == 'state':

                            from_word = f'{my_keyword.quest_trigger}'

                            to_word = f'{next_kw.quest_trigger}'
                            f.writelines(f'{from_word} --> {to_word} : {next_kw.quest_trigger}\n')
                        else:
                            # should not happen
                            pass
                    except ObjectDoesNotExist:
                        logger.error(f'next_keyword {next_keyword} for {my_keyword} is not found in game {self.name}')
                    except MultipleObjectsReturned:
                        logger.error(f'next_keyword {next_keyword} for {my_keyword} is not unique in game {self.name}')
                    except Exception as e:
                        logger.error(f'error when generate mermaid file for {self.name}, {e}')
                        f.writelines(f'```\n')
                        return False

            f.writelines(f'```\n')

        return True

    def statistic_player(self):
        """
        统计本游戏下面的用户情况
        """
        ret_dict = dict()
        ret_dict['result'] = False
        ret_dict['errmsg'] = 'Initial'
        output_file = self.settings_file.replace('.csv', '_玩家统计.csv')
        try:
            
            # 从WechatPlayer过滤game_hist字典存在self.name的用户
            all_players = WechatPlayer.objects.filter(game_hist__has_key=self.name)
            passed_players = WechatPlayer.objects.filter(game_hist__has_key=self.name, waiting_status=ENDING_COMMAND)
            all_quests = ExploreGameQuest.objects.filter(game=self)
            # 逐个检查每个玩家对每个关卡的完成情况
            with open(f'{SETTING_PATH}{output_file}', 'w', encoding='utf_8_sig') as f:
                f.writelines('游戏,玩家,关卡名称,关卡类型,完成状态,输入答案数量,答案列表\n')
                for player in all_players:
                    # logger.info(f'checking player {player.name}')
                    reward_list = player.game_hist[self.name].get('reward_list', list())
                    for quest in all_quests:
                        str_lines_list = []
                        str_lines_list.append(self.name)
                        str_lines_list.append(player.name)
                        if quest.reward_id > 0:  # 有奖励id的关卡
                            # logger.info(f'checking quest {quest.quest_trigger}')
                            str_lines_list.append(quest.quest_trigger)
                            if quest.show_next:
                                str_lines_list.append('选择题')
                            else:
                                str_lines_list.append('填空题')
                            cmd_dict = player.game_hist[self.name].get('cmd_dict', dict())
                            cmd_list = cmd_dict.get(quest.quest_trigger, list())
                            command_quantity = str(len(cmd_list))
                            if quest.reward_id in reward_list:
                                str_lines_list.append('已完成')
                                str_lines_list.append(command_quantity)
                                str_lines_list.append(f'{";".join(cmd_list)}')
                            elif quest.quest_trigger in cmd_dict.keys():
                                str_lines_list.append('进行中')
                                str_lines_list.append(command_quantity)
                                str_lines_list.append(f'{";".join(cmd_list)}')
                            else:
                                str_lines_list.append('未开始')
                                str_lines_list.append('0')
                                str_lines_list.append('')
                        else:  # 无需答题的关卡
                            str_lines_list.append(quest.quest_trigger)
                            str_lines_list.append('普通关卡')
                            str_lines_list.append('-')
                            str_lines_list.append('0')
                            str_lines_list.append('')
                        f.writelines(f'{",".join(str_lines_list)}\n')
            # df = pd.read_csv(f'{SETTING_PATH}{output_file}', encoding='utf_8_sig')
            # # check if the table exists
            # if pg_engine_miao.has_table(to_table):
            #     # delete the existing data in to_table if the table exists
            #     conn = pg_engine_miao.connect()
            #     sql = f'delete from public.{to_table} where "游戏"='
            #     sql += f"'{self.name}'"
            #     conn.execute(text(sql))
            #     conn.close()
            # df.to_sql(name=to_table, con=pg_engine_miao, schema='public', if_exists='append', index=False)
            ret_dict['result'] = True
            ret_dict['errmsg'] = (f'本游戏共有{len(all_players)}个玩家登录了游戏，其中{len(passed_players)}个已经通关。'
                                  f'统计结果已输出到{SETTING_PATH}{output_file}库')
            return ret_dict
        except Exception as e:
            ret_dict['errmsg'] = f'统计玩家时出错: {e}'
            return ret_dict

    def check_media_availability(self):
        """
        检查本游戏下面的所有关卡的媒体文件是否存在
        param:
            无
        return:
            missing_media_dict: dict, key为关卡名称，value为缺失的媒体文件列表
        
        """
        missing_media_dict = dict()
        all_quests = ExploreGameQuest.objects.filter(game=self)
        missing_media_list = list()
        for quest in all_quests:
            quest_content = quest.question_data + quest.hint_data
            re_pattern = '「(?P<keyword>[^」]+)」'
            re_result = re.findall(re_pattern, quest_content)
            
            for keyword in re_result:
                try:
                    media = WechatMedia.objects.get(game=self, keyword=keyword)
                except ObjectDoesNotExist:
                    missing_media_list.append(keyword)
            # if len(missing_media_list) > 0:
            #     missing_media_dict[quest.quest_trigger] = missing_media_list
        return missing_media_list

class ExploreGameQuest(models.Model):
    game = models.ForeignKey(ExploreGame, on_delete=models.CASCADE)
    quest_trigger = models.CharField(max_length=100, default='', verbose_name='本关名字')
    prequire_list = models.CharField(max_length=1000, default='', blank=True,
                                     verbose_name='本题前置条件，以｜分隔，留空表示无需额外条件')
    location_list = models.CharField(max_length=1000, default='', blank=True,
                                     verbose_name='限定位置关键词，以｜分隔，留空表示不限定位置')
    poi_keyword = models.CharField(max_length=10, default='', blank=True,
                                   verbose_name='地点POI关键词，用于搜索用户周边')
    question_type_choice = [('TEXT', '文字'), ('VIDEO', '视频'), ('PIC', '图片')]
    question_type = models.CharField(max_length=10, choices=question_type_choice,
                                     default='TEXT', verbose_name='谜面类型（已废弃，无需设置）')
    question_data = models.TextField(max_length=1000, default='', verbose_name='谜面', blank=True)
    hint_type = models.CharField(max_length=10, choices=question_type_choice,
                                 default='TEXT', verbose_name='提示类型（已废弃，无需设置）')
    hint_data = models.TextField(max_length=1000, default='', verbose_name='提示内容', blank=True)
    answer_list = models.CharField(max_length=100, default='', verbose_name='谜底列表，以｜分隔，仅在填空题时生效。可以设置多个正确答案，答对任意一个都会跳转到分支选项列的第一个对应的关卡', blank=True)
    options_list = models.CharField(max_length=1000, default='', blank=True,
                                    verbose_name='选项列表（已废弃，无需设置）')
    reward_type = models.CharField(max_length=10, choices=question_type_choice, default='TEXT',
                                   verbose_name='奖励类型')
    reward = models.TextField(max_length=1000, default='', verbose_name='答对本关问题将获得的道具或奖励内容', blank=True)
    reward_id = models.IntegerField(default=0, verbose_name='答对本关问题将获得的道具或奖励id')
    next_list = models.CharField(max_length=1000, default='', blank=True,
                                 verbose_name='分支选项，以｜分隔，在选择题时作为选项，填空题时仅第一个选项有效')
    show_next = models.BooleanField(default=True,
                                    verbose_name='选中表示选择题，未选中表示填空题')
    back_quest = models.CharField(max_length=100, default='', verbose_name='用于回答之后跳回到某个任务的名称，留空表示不生效', blank=True)
    show_if_unavailable = models.BooleanField(default=False, verbose_name='未满足挑战条件时是否显示')
    comment_when_unavailable = models.CharField(max_length=100, default='还不能选择', verbose_name='未满足挑战条件时显示的提示', blank=True)
    comment_when_available = models.CharField(max_length=100, default='可选择', verbose_name='满足挑战条件时显示的提示', blank=True)
    comment_when_clear = models.CharField(max_length=100, default='已完成', verbose_name='已完成任务时显示的提示', blank=True)

    class Meta:
        verbose_name = '任务关卡'
        verbose_name_plural = '任务关卡'

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
            # 发送关卡奖励内容
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
                    # 只有 问题内容、提示、奖励 的内容需要进行html样式更新
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
        type:
        - prequire：获取前置条件list,
        - answer：获取answer_list,
        - next：获取next_list，
        - option：获取option_list
        - location：获取location_list
        """
        if type == 'prequire':
            content = self.prequire_list
            # 对于前置条件，由于是数字id，所以需要转换为int
            if len(content) > 0:
                ret_list = list()
                prequire_list = content.replace(alt_sep, sep).split(sep)
                for x in prequire_list:
                    x = x.strip()
                    if len(x) > 0:
                        ret_list.append(int(x))
                # print(f'prequire_list of {self.quest_trigger} = {ret_list}')
                return ret_list
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
            return [x.strip() for x in content.replace(alt_sep, sep).split(sep)]
        else:
            return list()


class WechatGamePasswd(models.Model):
    # app = models.ForeignKey(WechatApp, on_delete=models.CASCADE, null=True)
    game = models.ForeignKey(ExploreGame, default=None, on_delete=models.CASCADE, blank=True, null=True)
    password = models.CharField(max_length=50, primary_key=True)
    assigned_player = models.ForeignKey(WechatPlayer, default=None, on_delete=models.CASCADE, blank=True, null=True)
    is_assigned = models.BooleanField(default=False, verbose_name='是否已分配')

    class Meta:
        verbose_name = '游戏密码(已废弃)'
        verbose_name_plural = '游戏密码(已废弃)'

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
