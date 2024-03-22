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
TEST_QUEST_TRIGGER = 'test_quest'
TEST_SETTINGS_FILE = './test.csv'
TEST_ACCOUNT_FILE = f'{TEST_GAME_NAME}_新账号清单.csv'
TEST_APP_ID = 'wx0a0a0a0a0a0a0a0a'
TEST_GAME_OPENING = 'for test purpose'
TEST_GAME_ENDING = 'test ending'
TEST_GAME_ENTRY = '游戏入口'


class TestModel(TestCase):

    def setUp(self):
        # create an app
        app = WechatApp.objects.create(en_name=TEST_APP_NAME, name=TEST_GAME_NAME, appid=TEST_APP_ID)

        # create a game
        game = ExploreGame.objects.create(app=app, name=TEST_GAME_NAME, opening=TEST_GAME_OPENING, clear_notice=TEST_GAME_ENDING,
                                          clear_requirement='99', is_active=True, entry=TEST_GAME_ENTRY, settings_file=TEST_SETTINGS_FILE)

        # import the quests from csv file
        result_dict = game.import_from_csv()
        # print(f'import result: {result_dict["result"]}, msg: {result_dict["errmsg"]}')
        
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
        entry_quest = ExploreGameQuest.objects.get(game=self.game, quest_trigger=TEST_GAME_ENTRY)
        open_id = sha1(str(self.user.id).encode('utf-8')).hexdigest()
        
        self.factory = RequestFactory()
        request = self.factory.get(f"/game/?app_en_name={TEST_APP_NAME}&game_name={TEST_GAME_NAME}")
        request.user = self.user
        self.user.groups.add(self.group)
        # 测试玩家首次进入游戏的返回
        response = views2.game(request)
        self.assertContains(response, self.game.opening)
        # self.assertEqual(player.waiting_status, '')
        player = WechatPlayer.objects.get(open_id=open_id)
        print(f'首次进入时返回正常，玩家等待状态：{player.waiting_status}')

        # 测试玩家进入第一关的返回
        answer = entry_quest.quest_trigger
        request = self.factory.post(f"/game/", 
                                    {'app_en_name': TEST_APP_NAME,'game_name': TEST_GAME_NAME, 'cmd': answer})
        request.user = self.user
        response = views2.game(request)
        self.assertContains(response, entry_quest.question_data)
        player = WechatPlayer.objects.get(open_id=open_id)
        # self.assertEqual(player.waiting_status, entry_quest.quest_trigger)
        print(f'玩家进入第一关时返回正常，玩家等待状态：{player.waiting_status}')

        # 测试玩家回答第一个问题（填空题）的返回
        answer = entry_quest.answer_list.split('|')[0]
        next_quest_trigger = entry_quest.next_list.split('|')[0]
        next_quest = ExploreGameQuest.objects.get(game=self.game, quest_trigger=next_quest_trigger)
        request = self.factory.post(f"/game/", 
                                    {'app_en_name': TEST_APP_NAME,'game_name': TEST_GAME_NAME, 'cmd': answer})
        request.user = self.user
        response = views2.game(request)
        self.assertContains(response, next_quest.question_data)
        player = WechatPlayer.objects.get(open_id=open_id)
        # self.assertEqual(player.waiting_status, next_quest.quest_trigger)
        print(f'回答第一个问题（填空题）时返回正常，玩家等待状态：{player.waiting_status}')
    
        # 测试玩家回答第二个问题（选择题）的返回
        cur_quest = next_quest
        answer = cur_quest.next_list.split('|')[0]
        next_quest = ExploreGameQuest.objects.get(game=self.game, quest_trigger=answer)
        request = self.factory.post(f"/game/", 
                                    {'app_en_name': TEST_APP_NAME,'game_name': TEST_GAME_NAME, 'cmd': answer})
        request.user = self.user
        response = views2.game(request)
        self.assertContains(response, next_quest.question_data)
        player = WechatPlayer.objects.get(open_id=open_id)
        print(f'回答第二个问题（选择题）时返回正常，玩家等待状态：{player.waiting_status}')
