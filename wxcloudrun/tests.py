from django.test import TestCase, RequestFactory
from django.contrib.auth.models import User, Group
from .models import *
from . import views2
from .location_game import *
import os

TEST_USER_NAME = 'test'
TEST_USER_PASSWORD = 'test'
TEST_APP_NAME = 'test_app'
TEST_GAME_NAME = 'test_game'
TEST_QUEST_TRIGGER = 'test_quest'
TEST_SETTINGS_FILE = 'test.csv'
TEST_ACCOUNT_FILE = f'/settings/{TEST_GAME_NAME}_新账号清单.csv'
TEST_APP_ID = 'wx0a0a0a0a0a0a0a0a'
TEST_GAME_OPENING = 'for test purpose'
TEST_GAME_ENTRY = '游戏入口'

class TestModel(TestCase):

    def setUp(self):
        # create an app
        app = WechatApp.objects.create(en_name=TEST_APP_NAME, name=TEST_GAME_NAME, appid=TEST_APP_ID)
        # app.save()
        # print(f'appid: {app.appid} en_name: {app.en_name}, created!')
        # create a game
        game = ExploreGame.objects.create(app=app, name=TEST_GAME_NAME, opening=TEST_GAME_OPENING, 
                                          is_active=True)
        # game.save()

        # import the quests from csv file
        game.settings_file = TEST_SETTINGS_FILE
        result_dict = game.import_from_csv()
        game.entry = TEST_GAME_ENTRY
        # create a group and a user
        group = Group.objects.create(name=TEST_GAME_NAME)
        # group.save()
        user = User.objects.create(username=TEST_USER_NAME, password=TEST_USER_PASSWORD)
        user.groups.add(group)
        # user.save()
        self.user = user
        return True
    
    def test_login(self):
        
        self.assertIsNotNone(self.user)
        self.factory = RequestFactory()
        request = self.factory.get(f"/game/?app_en_name={TEST_APP_NAME}&game_name={TEST_GAME_NAME}")
        request.user = self.user
        response = views2.game(request)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, f"<p>{TEST_GAME_OPENING}</p>")

    # def test_import_quest(self):
    #     app, game = self.create_app_and_game()
    #     print(f'game: {game.name} app: {game.app.en_name}, created!')
    #     self.assertEqual(game.name, TEST_GAME_NAME)
    #     self.assertEqual(game.app, app)
    #     # set the settings file to test.csv
    #     game.settings_file = TEST_SETTINGS_FILE
    #     result_dict = game.import_from_csv()
    #     print(f'import result: {result_dict["result"]}, msg: {result_dict["errmsg"]}')
    #     # check the quests number is proper
    #     quests = ExploreGameQuest.objects.filter(game=game)
    #     print(f'quests: {len(quests)}, imported!')
    #     i = 0
    #     for q in quests:
    #         i += 1
    #         print(f'任务{i}：{q.quest_trigger}\t谜面：{q.question_data}\t提示：{q.hint_data}\t答案：{q.answer_list}\t奖励：{q.reward}\t奖励id：{q.reward_id}\tm1：{q.comment_when_unavailable}\tm2：{q.comment_when_available}\tm3：{q.comment_when_clear}')
        
       
        

