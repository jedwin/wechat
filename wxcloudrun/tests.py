from random import randint
from django.test import TestCase, RequestFactory
from django.contrib.auth.models import User, Group, AnonymousUser
from .models import *
from . import views2
from .views2 import *
from .ExploerGameHandler import *
from .location_game import *
import os

TEST_USER_NAME = 'test'
TEST_USER_PASSWORD = 'test'
TEST_APP_NAME = 'test_app'
TEST_GAME_NAME = 'test_game'
TEST_SETTINGS_FILE = './test.csv'
# TEST_ACCOUNT_FILE = f'{TEST_GAME_NAME}_新账号清单.csv'
TEST_APP_ID = 'wx0a0a0a0a0a0a0a0a'
TEST_GAME_OPENING = 'for test purpose'
TEST_GAME_ENDING = 'test ending'
TEST_GAME_ENTRY = '游戏入口'
TEST_GAME_CLEAR_REQUIREMENT = '999'  # 默认通关条件
TEST_MAX_STEP = 40  # test_process中最大测试步数
SHOW_PROCESS = False  # 是否显示测试关卡过程
RANDOM_ANSWER_STRING = 'aghiqrsyz01289' # 随机答案字符串

class TestModel(TestCase):
    @classmethod
    def setUpTestData(cls):
        # create an app
        app = WechatApp.objects.create(en_name=TEST_APP_NAME, name=TEST_APP_NAME, appid=TEST_APP_ID)

        # create a game
        game = ExploreGame.objects.create(app=app, name=TEST_GAME_NAME, opening=TEST_GAME_OPENING, clear_notice=TEST_GAME_ENDING,
                                          is_active=True, entry=TEST_GAME_ENTRY, settings_file=TEST_SETTINGS_FILE, 
                                          clear_requirement=TEST_GAME_CLEAR_REQUIREMENT)
        
        # create a group and a user
        group = Group.objects.create(name=game.name)
        user = User.objects.create(username=TEST_USER_NAME, password=TEST_USER_PASSWORD)
        
        # create a wechat player
        open_id = sha1(str(user.id).encode('utf-8')).hexdigest()
        player = WechatPlayer.objects.create(app=app, open_id=open_id, name=TEST_USER_NAME, game_hist={game.name: dict()})
    
    def setUp(self) -> None:
        self.user = User.objects.get(id=1)
        self.app = WechatApp.objects.get(id=1)
        self.game = ExploreGame.objects.get(id=1)
        self.group = Group.objects.get(id=1)
        self.player = WechatPlayer.objects.get(name=TEST_USER_NAME)
        self.factory = RequestFactory()

    def test_login(self):
        print(f'开始测试\033[34m【系统权限逻辑】\033[0m')
        request = self.factory.get(f"/game/?app_en_name={TEST_APP_NAME}&game_name={self.game.name}")

        # 测试未登录时的返回
        request.user = AnonymousUser()
        response = views2.game(request)
        self.assertEqual(type(response), HttpResponseRedirect)
        print('\033[32m用户未登录时，重定向登录页面正常\033[0m')

        # 测试无权限时的返回
        request.user = self.user
        response = views2.game(request)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, f"无权限进入本游戏")
        print('\033[32m对无权限玩家，页面内容显示正常\033[0m')

        # 测试有权限时的返回
        # group = Group.objects.get(name=TEST_GAME_NAME)
        self.user.groups.add(self.group)
        response = views2.game(request)
        self.assertContains(response, self.game.show_opening())
        print('\033[32m对有权限玩家，游戏开场画面显示正常\033[0m')

        # 游戏未激活时的返回
        self.game.is_active = False
        self.game.save()
        response = views2.game(request)
        # print(response.content.decode('utf-8'))
        self.assertContains(response, views2.GAME_IS_NOT_ACTIVE)
        print('\033[32m对已分配权限，但游戏未激活时，提示内容显示正常\033[0m')
        self.game.is_active = True
        self.game.save()
        
        # 测试不指定游戏时的返回
        request = self.factory.get(f"/game/?app_en_name={TEST_APP_NAME}")
        request.user = self.user
        response = views2.game(request)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, f"请选择你要进行的游戏")
        print('\033[32m对有权限玩家不指定游戏名时，游戏选择画面返回正常\033[0m')

        # 设置为直接进入游戏时的返回
        self.app.auto_enter_game = True
        self.app.save()
        response = views2.game(request)
        self.assertContains(response, self.game.show_opening())
        print('\033[32m对有权限玩家不指定游戏，但打开直接进入游戏开关时，游戏开场内容显示正常\033[0m')
        
    def test_process(self):
        print(f'开始测试游戏\033[34m【{self.game.name}】\033[0m流程')
        content_is_ok = True  # 内容是否正常
        content_count = 0  # 内容显示次数
        hint_is_ok = True  # 提示是否正常
        hint_count = 0
        option_is_ok = True # 选项是否正常
        option_count = 0
        answer_is_ok = True # 答题框是否正常
        answer_count = 0
        error_tips_is_ok = True # 错误提示是否正常
        error_tips_count = 0
        clear_notice_is_ok = True # 通关提示是否正常

        # 导入游戏数据
        if TEST_SETTINGS_FILE.endswith('.csv'):
            result_dict = self.game.import_from_csv()
        elif TEST_SETTINGS_FILE.endswith('.json'):
            result_dict = self.game.import_from_json()
        else:
            raise ValueError(f'Unsupported file format: {TEST_SETTINGS_FILE}')
        if result_dict['result']:
            print(f'\033[32m{result_dict["errmsg"]}\033[0m')
        else:
            print(f'\033[31m{result_dict["errmsg"]}\033[0m')

        # 开始测试游戏流程
        entry_quest = ExploreGameQuest.objects.get(game=self.game, quest_trigger=self.game.entry)
        open_id = sha1(str(self.user.id).encode('utf-8')).hexdigest()
        is_cleared = False  # 是否已通关
        request = self.factory.get(f"/game/?app_en_name={TEST_APP_NAME}&game_name={self.game.name}")
        request.user = self.user
        self.user.groups.add(self.group)
        clear_requirement_list = self.game.get_content_list(type='clear_requirement')
        
        # 测试玩家首次进入游戏的返回
        response = views2.game(request)
        # print(response.content.decode('utf-8'))
        self.assertContains(response, self.game.show_opening())
        print(f'\033[32m【游戏开场】\033[0m内容显示正常')

        # 初始化玩家状态
        reward_list = list()
        cur_quest = entry_quest
        answer = cur_quest.quest_trigger
        num_of_step = 0
        # 开始逐个关卡测试
        while num_of_step < TEST_MAX_STEP:
            num_of_step += 1
            test_result = False
            request = self.factory.post(f"/game/", {'app_en_name': TEST_APP_NAME,'game_name': self.game.name, 'cmd': answer})
            request.user = self.user
            response = views2.game(request)
            
            # 检查回答正确时的正文内容
            content = cur_quest.reply_msg(type='question', toUser=open_id, fromUser='', for_text=False)
            # print(response.content.decode('utf-8'))
            self.assertContains(response, content)
            content_count += 1
            
            # 检查是否正确显示提示按钮和内容
            if cur_quest.hint_data != '':
                self.assertContains(response, "id='showIOSDialog_hint'")
                self.assertContains(response, cur_quest.reply_msg(type='hint', toUser=open_id, fromUser='', for_text=False))
                hint_count += 1
                if SHOW_PROCESS: print(f'本关卡有提示内容，显示正常')
            else:
                self.assertNotContains(response, "id='showIOSDialog_hint'")

            # 未通关时不应该出现通关码按钮
            self.assertNotContains(response, 'id="showClearCode"')

            # 检查选择题和问答题的呈现逻辑
            if cur_quest.show_next:
                # 检查选择题的选项显示
                next_list = cur_quest.next_list.replace('｜', '|').split('|')
                available_answers_list = list()
                not_available_answers_list = list()
                num_of_next = 0
                for item in next_list:
                    try:
                        option_quest = ExploreGameQuest.objects.get(game=self.game, quest_trigger=item)
                        prequire_list = option_quest.get_content_list(type='prequire')
                        if len(prequire_list) == 0 or set(prequire_list).issubset(set(reward_list)):
                            # 如果没有前置条件，或者前置条件已满足，才显示
                            if option_quest.reward_id == 0 or option_quest.reward_id not in reward_list:
                                # 没有奖励id，或奖励未获得过，才显示
                                num_of_next += 1
                                self.assertContains(response, f"option_click('{item}');")
                                available_answers_list.append(item)
                    except ExploreGameQuest.DoesNotExist:
                        # 如果对应下一关不存在，则不应该显示
                        self.assertNotContains(response, f"option_click('{item}');")
                        not_available_answers_list.append(item)
                if len(available_answers_list) == 0:
                    if SHOW_PROCESS: print(f'\033[31m【注意】\033[0m：关卡\033[34m【{cur_quest.quest_trigger}】\033[0m是\033[32m选择题\033[0m，但没有可用选项，无法继续测试。可能是前置条件设置有误或关卡缺失')
                    break
                # 至少有一个可用选项
                if SHOW_PROCESS: print(f'关卡\033[34m【{cur_quest.quest_trigger}】\033[0m是\033[32m选择题\033[0m，{num_of_next}个可选项都显示正常：{available_answers_list}')
                option_count += 1
                if len(not_available_answers_list) > 0:
                    if SHOW_PROCESS: print(f'\033[31m【注意】\033[0m：本关卡关联了{len(not_available_answers_list)}个缺失关卡 {not_available_answers_list}')
                # 随机选择一个选项作为答案
                answer = available_answers_list[randint(0, num_of_next-1)]
                if SHOW_PROCESS: print(f'随机选择的答案是：\033[43m【{answer}】\033[0m')
                next_quest_trigger = answer
            else:
                # 检查选择题的答案框显示
                self.assertContains(response, 'placeholder="请把你的答案写在这里"')
                if SHOW_PROCESS: print(f'关卡\033[34m【{cur_quest.quest_trigger}】\033[0m是\033[34m问答题\033[0m，答案框显示正常。正确答案是：{cur_quest.answer_list}')
                answer_count += 1
                answer_list = cur_quest.answer_list.replace('｜', '|').split('|')
                num_of_answer = len(answer_list)
                # 随机选择一个作为答案
                answer = answer_list[randint(0, num_of_answer-1)]
                if SHOW_PROCESS: print(f'随机选择的答案是：\033[43m【{answer}】\033[0m')
                next_quest_trigger = cur_quest.next_list.replace('｜', '|').split('|')[0]
            try:
                next_quest = ExploreGameQuest.objects.get(game=self.game, quest_trigger=next_quest_trigger)
            except ExploreGameQuest.DoesNotExist:
                print(f'\033[31m【注意】\033[0m：下一个关卡\033[31m【{next_quest_trigger}】\033[0m不存在，无法继续测试')
                break
            # 更新奖励列表
            if cur_quest.reward_id > 0 and cur_quest.reward_id not in reward_list:
                reward_list.append(cur_quest.reward_id)
                if SHOW_PROCESS: print(f'正常进入关卡\033[34m【{cur_quest.quest_trigger}】\033[0m，并获得奖励ID：\033[45m【{cur_quest.reward_id}】\033[0m')
                # 判断是否已满足通关条件，如果是就跳出循环
                if set(clear_requirement_list).issubset(set(reward_list)):
                    is_cleared = True
                    # print(f'已满足通关条件：{clear_requirement_list}')
                    break
            else:
                if SHOW_PROCESS: print(f'正常进入关卡\033[34m【{cur_quest.quest_trigger}】\033[0m')
            
            # 检查玩家等待状态是否正确
            self.player = WechatPlayer.objects.get(name=TEST_USER_NAME)
            cur_player_game_dict = get_cur_player_game_dict(player=self.player, game_name=self.game.name)
            wait_status = cur_player_game_dict.get(FIELD_WAIT_STATUS, '')
            self.assertEqual(wait_status, cur_quest.quest_trigger)

            # 准备进入下一个关卡
            cur_quest = next_quest
            if cur_quest.next_list == '':
                print(f'\033[31m【注意】\033[0m：关卡\033[31m【{cur_quest.quest_trigger}】\033[0m的\033[31m下一步为空\033[0m，无法继续测试')
                break
            if SHOW_PROCESS: print(f'目前获得奖励列表：\033[35m{reward_list}\033[0m')

            # 在mod 4 = 2时测试回答错误时的返回
            if num_of_step % 4 == 2:
                request = self.factory.post(f"/game/", {'app_en_name': TEST_APP_NAME,'game_name': self.game.name, 'cmd': RANDOM_ANSWER_STRING})
                request.user = self.user
                response = views2.game(request)
                self.assertContains(response, 'id="errorTips"')
                if SHOW_PROCESS: print(f'\033[34m第{num_of_step}步回答错误时，错误提示显示正常\033[0m')
                error_tips_count += 1


        # 如果已满足通关条件，就再一次进入游戏，看看是否正确显示通关画面
        if is_cleared:
            # 把获得通关奖励id的答案发出去之后，检查是否正确显示通关内容和通关码按钮
            request = self.factory.post(f"/game/", {'app_en_name': TEST_APP_NAME,'game_name': self.game.name, 'cmd': answer})
            request.user = self.user
            response = views2.game(request)
            self.assertContains(response, self.game.show_clear_notice())
            self.assertContains(response, 'id="showClearCode"')
            print(f'\033[32m第一次通关时，内容显示正常\033[0m')

            # 再检查一次进入游戏，是否正确显示通关内容和通关码按钮
            answer = 'jfdaealrtflg'  # 随便一个答案
            request = self.factory.post(f"/game/", {'app_en_name': TEST_APP_NAME,'game_name': self.game.name, 'cmd': answer})
            request.user = self.user
            response = views2.game(request)
            self.assertContains(response, self.game.show_clear_notice())
            self.assertContains(response, 'id="showClearCode"')
            print(f'\033[32m已通关后再次进入游戏时，通关画面显示正常\033[0m')
            test_result = True
        
        # 判断是否完成了测试步骤
        if content_is_ok: print(f'\033[32m{content_count}次进入关卡，内容显示正常\033[0m')
        if hint_is_ok: print(f'\033[32m{hint_count}个关卡中配置有提示，内容显示正常\033[0m')
        if option_is_ok: print(f'\033[32m{option_count}条选择题，选项显示正常\033[0m')
        if answer_is_ok: print(f'\033[32m{answer_count}条问答题，答题框显示正常\033[0m')
        if error_tips_is_ok: print(f'\033[32m{error_tips_count}次故意回答错误时，错误提示显示正常\033[0m')
        if len(reward_list) > 0: 
            print(f'\033[32m获得奖励ID：{reward_list}\033[0m') 
        else: 
            print(f'\033[32m未获得任何奖励\033[0m')
        if test_result:
            print(f'\033[32m流程测试完成，顺利达到通关条件\033[0m')
        elif num_of_step >= TEST_MAX_STEP:
            print(f'\033[31m流程测试未完成\033[0m, 已达到最大测试步数{TEST_MAX_STEP}仍未能通关')
        else:
            print(f'\033[31m流程测试未完成\033[0m, 共进行{num_of_step}步')

    def test_ExplorerGame_and_Quest(self):
        # 测试ExploreGame类
        my_quest = ExploreGameQuest.objects.create(game=self.game, quest_trigger=self.game.entry)
        next_quest_1 = ExploreGameQuest.objects.create(game=self.game, quest_trigger='next1')
        next_quest_2 = ExploreGameQuest.objects.create(game=self.game, quest_trigger='next2')
        my_quest.question_data = 'test question'
        my_quest.hint_data = 'test hint'
        my_quest.show_next = True
        my_quest.next_list = 'next1|next2'
        # self.assertEqual(self.game.show_opening(), replace_content_with_html(TEST_GAME_OPENING))
        # self.assertEqual(self.game.show_clear_notice(), replace_content_with_html(TEST_GAME_ENDING))
        self.user.groups.add(self.group)
        
        # 不带app名调用
        ret_dict = handle_player_command(game_name=self.game.name, 
                                         open_id=self.user.id, cmd='test', user_name=self.user.username)
        self.assertEqual(ret_dict['error_msg'], 'app_en_name is blank')
        print(f'\033[32m不带app名调用，返回正常\033[0m')

        # 乱写app名调用
        wrong_app = 'wrong_app'
        ret_dict = handle_player_command(app_en_name=wrong_app, game_name=self.game.name, 
                                         open_id=self.user.id, cmd='test', user_name=self.user.username)
        self.assertEqual(ret_dict['error_msg'], f'app_en_name:{wrong_app} 不存在')
        print(f'\033[32m乱写app名调用，返回正常\033[0m')

        # 不带游戏名调用
        ret_dict = handle_player_command(app_en_name=self.app.en_name, 
                                         open_id=self.user.id, cmd='test', user_name=self.user.username)
        self.assertEqual(ret_dict['error_msg'], 'game_name is blank')
        print(f'\033[32m不带游戏名调用，返回正常\033[0m')

        # 乱写游戏名调用
        wrong_game = 'wrong_game'
        ret_dict = handle_player_command(app_en_name=self.app.en_name, game_name=wrong_game, 
                                         open_id=self.user.id, cmd='test', user_name=self.user.username)
        self.assertEqual(ret_dict['error_msg'], f'游戏{wrong_game}不存在')
        print(f'\033[32m乱写游戏名调用，返回正常\033[0m')

        # 不带用户名调用
        ret_dict = handle_player_command(app_en_name=self.app.en_name, game_name=self.game.name, 
                                         open_id=self.user.id, cmd='test')
        self.assertEqual(ret_dict['error_msg'], 'user_name is blank')
        print(f'\033[32m不带用户名调用，返回正常\033[0m')

        # 乱写用户名调用，可以正常使用
        wrong_user = 'wrong_user'
        ret_dict = handle_player_command(app_en_name=self.app.en_name, game_name=self.game.name, 
                                         open_id=self.user.id, cmd='test', user_name=wrong_user)
        self.assertEqual(ret_dict['error_msg'], '')
        print(f'\033[32m乱写用户名调用，返回正常\033[0m')

