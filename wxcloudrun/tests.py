from django.test import TestCase, RequestFactory
from django.contrib.auth.models import User, Group
from .models import *
from .views2 import *
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


class TestModel(TestCase):

    def create_app_and_game(self):
        try:
            app = WechatApp.objects.get(en_name=TEST_APP_NAME)
            
        except WechatApp.DoesNotExist:
            app = WechatApp.objects.create(en_name=TEST_APP_NAME, name=TEST_GAME_NAME, appid=TEST_APP_ID)
            print(f'appid: {app.appid} en_name: {app.en_name}, created!')

        try:
            game = ExploreGame.objects.get(app=app, name=TEST_GAME_NAME)
        except ExploreGame.DoesNotExist:
            game = ExploreGame.objects.create(app=app, name=TEST_GAME_NAME, opening='for test purpose', is_active=True)
        return app, game
    
    def test_login(self):
        app, game = self.create_app_and_game()
        if os.path.exists(TEST_ACCOUNT_FILE):
            os.remove(TEST_ACCOUNT_FILE)
        result_count = game.gen_users(how_many=10)
        self.assertGreater(result_count, 0)
        # 打开已生成的账号文件，获取第一个用户的用户名和密码
        
        with open(game.account_file, 'r') as f:
            lines = f.readlines()
            line = lines[0]
            username, password, clear_code = line.split(',')
            print(f'username: {username}, password: {password}')
        self.user = User.objects.get(username=username)
        self.assertIsNotNone(self.user)
        self.factory = RequestFactory()
        request = self.factory.get("/game/")
        response = game(request)
        self.assertEqual(response.status_code, 200)

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
        
       
        

