from django.test import TestCase
from .models import *
from .location_game import *

TEST_USER_NAME = 'test'
TEST_USER_PASSWORD = 'test'
TEST_APP_NAME = 'test_app'
TEST_GAME_NAME = 'test_game'
TEST_QUEST_TRIGGER = 'test_quest'
TEST_SETTINGS_FILE = 'test.csv'


class TestModel(TestCase):

    def test_login(self):
        # check if user test is exist
        try:
            user = User.objects.get(username=TEST_USER_NAME)
            user.delete()
        except User.DoesNotExist:
            pass
        user = User.objects.create_user(username=TEST_USER_NAME, password=TEST_USER_PASSWORD)
        self.client.login(username=TEST_USER_NAME, password=TEST_USER_PASSWORD)
        response = self.client.get('/game/')
        self.assertEqual(response.status_code, 200)

    def create_game_object(self):
        # check if game "test" is exist
        try:
            game = ExploreGame.objects.get(name=TEST_GAME_NAME)
            game.delete()
        except ExploreGame.DoesNotExist:
            pass
        
        try:
            test_app = WechatApp.objects.get(en_name=TEST_APP_NAME)
        except WechatApp.DoesNotExist:
            # app miaozan not exist, create it
            test_app = WechatApp.objects.create(en_name=TEST_APP_NAME, name='临时测试用', appid='wx0a0a0a0a0a0a0a0a')
        # self.assertEqual(test_app.en_name, TEST_APP_NAME)
        game = ExploreGame.objects.create(app=test_app, name=TEST_GAME_NAME, opening='for test purpose', is_active=True)
        # self.assertEqual(game.name, TEST_GAME_NAME)
        # # create game_quest for game "test_game"
        # game_quest = ExploreGameQuest.objects.create(game=game, quest_trigger=TEST_QUEST_TRIGGER, question_data='for test purpose',
        #                                              hint_data='for test purpose', answer_list='for|test|purpose',)
        # self.assertEqual(game_quest.quest_trigger, TEST_QUEST_TRIGGER)

    def test_import_quest(self):
        # create the game object
        self.create_game_object()
        game = ExploreGame.objects.get(name=TEST_GAME_NAME)
        # set the settings file to test.csv
        game.settings_file = TEST_SETTINGS_FILE
        game.import_from_csv()
        # check the quests number is proper
        quests = ExploreGameQuest.objects.filter(game=game)
        self.assertGreaterEqual(len(quests), 2)
        
       
        

