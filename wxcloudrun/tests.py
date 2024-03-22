from random import randint
from django.test import TestCase, RequestFactory
from django.contrib.auth.models import User, Group
from .models import *
from . import views2
from .views2 import *
from .location_game import *
import os

TEST_USER_NAME = 'test'
TEST_USER_PASSWORD = 'test'
TEST_APP_NAME = 'test_app'
TEST_GAME_NAME = 'test_game'
TEST_SETTINGS_FILE = './test2.csv'
# TEST_ACCOUNT_FILE = f'{TEST_GAME_NAME}_新账号清单.csv'
TEST_APP_ID = 'wx0a0a0a0a0a0a0a0a'
TEST_GAME_OPENING = 'for test purpose'
TEST_GAME_ENDING = 'test ending'
TEST_GAME_ENTRY = '游戏入口'


class TestModel(TestCase):

    def setUp(self):
        # create an app
        app = WechatApp.objects.create(en_name=TEST_APP_NAME, name=TEST_APP_NAME, appid=TEST_APP_ID)

        # create a game
        game = ExploreGame.objects.create(app=app, name=TEST_GAME_NAME, opening=TEST_GAME_OPENING, clear_notice=TEST_GAME_ENDING,
                                          is_active=True, entry=TEST_GAME_ENTRY, settings_file=TEST_SETTINGS_FILE)

        # import the quests from csv file
        # result_dict = game.import_from_csv()
        result_dict = game.import_from_json()
        print(f'import result: {result_dict["result"]}, msg: {result_dict["errmsg"]}')
        
        # create a group and a user
        group = Group.objects.create(name=TEST_GAME_NAME)
        user = User.objects.create(username=TEST_USER_NAME, password=TEST_USER_PASSWORD)
        
        # create a wechat player
        open_id = sha1(str(user.id).encode('utf-8')).hexdigest()
        player = WechatPlayer.objects.create(app=app, open_id=open_id, name=TEST_USER_NAME)
        self.app = app
        self.game = game
        self.group = group
        self.user = user
        self.player = player
        return True
    
    # def test_login(self):

    #     self.factory = RequestFactory()
    #     request = self.factory.get(f"/game/?app_en_name={TEST_APP_NAME}&game_name={TEST_GAME_NAME}")
    #     request.user = self.user

    #     # 测试无权限时的返回
    #     response = views2.game(request)
    #     self.assertEqual(response.status_code, 200)
    #     self.assertContains(response, f"无权限进入本游戏")
    #     print('无权限时返回正常')

    #     # 测试有权限时的返回
    #     # group = Group.objects.get(name=TEST_GAME_NAME)
    #     self.user.groups.add(self.group)
    #     response = views2.game(request)
    #     self.assertContains(response, f"<p>{TEST_GAME_OPENING}</p>")
    #     print('有权限时返回正常')

    #     # 测试不指定游戏时的返回
    #     request = self.factory.get(f"/game/?app_en_name={TEST_APP_NAME}")
    #     request.user = self.user
    #     response = views2.game(request)
    #     self.assertEqual(response.status_code, 200)
    #     self.assertContains(response, f"请选择你要进行的游戏")
    #     print('不指定游戏时返回正常')

    #     # 设置为直接进入游戏时的返回
    #     self.app.auto_enter_game = True
    #     self.app.save()
    #     response = views2.game(request)
    #     self.assertContains(response, f"<p>{TEST_GAME_OPENING}</p>")
    #     print('不指定游戏，但打开直接进入游戏开关，返回正常')

    #     # 还原配置，取消权限，防止影响其他测试
    #     self.user.groups.remove(self.group)
    #     self.app.auto_enter_game = False
    #     self.app.save()
        
    def test_process(self):
        entry_quest = ExploreGameQuest.objects.get(game=self.game, quest_trigger=self.game.entry)
        open_id = sha1(str(self.user.id).encode('utf-8')).hexdigest()
        
        self.factory = RequestFactory()
        request = self.factory.get(f"/game/?app_en_name={TEST_APP_NAME}&game_name={self.game.name}")
        request.user = self.user
        self.user.groups.add(self.group)
        clear_requirement_list = self.game.get_content_list(type='clear_requirement')
        # 测试玩家首次进入游戏的返回
        response = views2.game(request)
        self.assertContains(response, self.game.entry)
        # self.assertEqual(player.waiting_status, '')
        player = WechatPlayer.objects.get(open_id=open_id)
        print(f'首次\033[31m【进入游戏】\033[0m时内容显示正常')
        reward_list = list()
        # 测试玩家进入第一关的返回
        answer = entry_quest.quest_trigger
        request = self.factory.post(f"/game/", {'app_en_name': TEST_APP_NAME,'game_name': self.game.name, 'cmd': entry_quest.quest_trigger})
        request.user = self.user
        response = views2.game(request)
        # self.assertContains(response, entry_quest.question_data)
        # print(f'进入关卡\033[31m【{entry_quest.quest_trigger}】\033[0m时内容显示正常')
        cur_quest = entry_quest
        # 开始逐个关卡测试
        while cur_quest.next_list != '':
            if cur_quest.show_next:
                # 检查选择题的选项显示
                next_list = cur_quest.next_list.replace('｜', '|').split('|')
                available_answers_list = list()
                num_of_next = 0
                for item in next_list:
                    option_quest = ExploreGameQuest.objects.get(game=self.game, quest_trigger=item)
                    prequire_list = option_quest.get_content_list(type='prequire')
                    if len(prequire_list) == 0 or set(prequire_list).issubset(set(reward_list)):
                        # 如果没有前置条件，或者前置条件已满足，才显示
                        if option_quest.reward_id == 0 or option_quest.reward_id not in reward_list:
                            # 没有奖励id，或奖励未获得过，才显示
                            num_of_next += 1
                            self.assertContains(response, f"option_click('{item}');")
                            available_answers_list.append(item)
                    # self.assertContains(response, f"option_click('{item}');")
                print(f'关卡\033[31m【{cur_quest.quest_trigger}】\033[0m是\033[32m选择题\033[0m，{num_of_next}个可选项都显示正常：{available_answers_list}')
                # 随机选择一个选项作为答案
                answer = available_answers_list[randint(0, num_of_next-1)]
                print(f'随机选择的答案是：\033[43m【{answer}】\033[0m')
                next_quest_trigger = answer
            else:
                # 检查选择题的答案框显示
                self.assertContains(response, 'placeholder="请把你的答案写在这里"')
                print(f'关卡\033[31m【{cur_quest.quest_trigger}】\033[0m是\033[34m问答题\033[0m，答案框显示正常。正确答案是：{cur_quest.answer_list}')
                answer_list = cur_quest.answer_list.replace('｜', '|').split('|')
                num_of_answer = len(answer_list)
                # 随机选择一个作为答案
                answer = answer_list[randint(0, num_of_answer-1)]
                print(f'随机选择的答案是：\033[43m【{answer}】\033[0m')
                next_quest_trigger = cur_quest.next_list.replace('｜', '|').split('|')[0]
            next_quest = ExploreGameQuest.objects.get(game=self.game, quest_trigger=next_quest_trigger)
            request = self.factory.post(f"/game/", {'app_en_name': TEST_APP_NAME,'game_name': self.game.name, 'cmd': answer})
            request.user = self.user
            response = views2.game(request)
            if cur_quest.reward_id > 0 and cur_quest.reward_id not in reward_list:
                    reward_list.append(cur_quest.reward_id)
                    print(f'回答关卡\033[31m【{cur_quest.quest_trigger}】\033[0m正确，获得奖励ID：\033[45m【{cur_quest.reward_id}】\033[0m')
            
            if set(clear_requirement_list).issubset(set(reward_list)):
                print(f'已满足通关条件：{clear_requirement_list}')
                break
            cur_quest = next_quest
            print(f'目前获得奖励列表：\033[35m{reward_list}\033[0m')
