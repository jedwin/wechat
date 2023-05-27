from django.test import TestCase
from .models import *
from .location_game import *

class TestModel(TestCase):

    def test_login(self):
        # check if user test is exist
        try:
            user = User.objects.get(username='test')
            user.delete()
        except User.DoesNotExist:
            pass
        user = User.objects.create_user(username='test', password='test')
        self.client.login(username='test', password='test')
        response = self.client.get('/game/')
        self.assertEqual(response.status_code, 200)

