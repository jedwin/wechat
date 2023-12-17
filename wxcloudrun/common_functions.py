# 定义公共函数
import csv
import os
import json
from random import sample
from wxcloudrun.models import *
from wxcloudrun.location_game import *
from django.core.exceptions import *
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives import hashes
import base64

# 加密消息
def encrypt_message(message, public_key):
    message = message.encode('utf-8')
    encrypted = public_key.encrypt(
        message,
        padding.PKCS1v15()
    )
    return base64.b64encode(encrypted).decode('utf-8')

# 解密消息
def decrypt_message(encrypted_message, private_key):
    # encrypt_msg was encoded by base64, so decode it first
    encrypted_message = base64.b64decode(encrypted_message)
    decrypted = private_key.decrypt(
        encrypted_message,
        padding.PKCS1v15()
    )
    return decrypted

# 加载私钥
def load_private_key(file_path):
    with open(file_path, "rb") as key_file:
        private_key = serialization.load_ssh_private_key(
            data=key_file.read(),
            password=None  # 如果私钥被密码保护，替换为相应的密码
        )
    return private_key

# 加载公钥
def load_public_key(file_path):
    with open(file_path, "rb") as key_file:
        public_key = serialization.load_ssh_public_key(
            data=key_file.read()
        )
    return public_key


def load_auto_reply_settings(auto_reply_for_non_player_file):
    """
    读取关键词csv文档，返回keyword_dict对象
    """
    if os.path.exists(auto_reply_for_non_player_file):
        auto_reply_dict = dict()  # {编号: [回复类型, 回复文件名称或内容, 视频描述]}

        with open(auto_reply_for_non_player_file, 'r') as f:
            auto_reply_list = csv.reader(f)  # [编号, 回复类型, 回复文件名称或内容, 视频描述]
            # 为防止csv内容中编号有重复，这里使用自动生成的编号number
            number = 0
            for auto_reply_row in auto_reply_list:
                content_type = auto_reply_row[1]
                content_data = auto_reply_row[2]
                video_desc = auto_reply_row[3]
                if content_type == '图片' and content_data[-4:] != '.jpg':
                    content_data += '.jpg'

                auto_reply_dict[number] = [content_type, content_data, video_desc]
                number += 1
        return auto_reply_dict
    else:
        return False


def load_game_settings_v2(game_settings_file):
    """
    读取关键词csv文档，返回keyword_dict对象
    """
    if os.path.exists(game_settings_file):
        keyword_dict = dict()  # {'keyword': [scene, content_type, content_data, hint_type, hint_data, cur_pic]}
        scene_dict = dict()  # {'scene': [hint_type, hint_data, cur_pic]}
        with open(game_settings_file, 'r') as f:
            keywords_data = csv.reader(f)
            # [ 0   1       2     3     4           5       6               7              8         9        10
            # [关卡,关键词,谜面类型,谜面,文件名称或内容,提示类型,下一关键词提示,当前填字游戏进度图,输入关键词范围,上一关关键词,视频描述]

            for keyword_row in keywords_data:
                scene = keyword_row[0]
                keyword = keyword_row[1]
                content_type = keyword_row[2]
                content_data = keyword_row[4]
                hint_type = keyword_row[5]
                hint_data = keyword_row[6]
                cur_pic = keyword_row[7]
                option_list = keyword_row[8].split('|')
                last_keyword = keyword_row[9]
                video_desc = keyword_row[10]
                if content_type == '图片' and content_data[-4:] != '.jpg':
                    content_data += '.jpg'
                if hint_type == '图片' and hint_data[-4:] != '.jpg':
                    hint_data += '.jpg'
                if len(cur_pic) > 0 and cur_pic[-4:] != '.jpg':
                    cur_pic += '.jpg'
                keyword_dict[keyword] = [scene, content_type, content_data, hint_type,
                                         hint_data, cur_pic, option_list, last_keyword, video_desc]
                scene_dict[scene] = [hint_type, hint_data, cur_pic]
        return keyword_dict, scene_dict
    else:

        return False


def load_images_data(image_json_file):
    """
    从
    """
    if os.path.exists(image_json_file):

        with open(image_json_file, 'r') as f:
            image_dict = json.loads(''.join(f.readlines()))
            return image_dict
    else:
        return False


def gen_reply_html(request):
    keyword_file = '微信公众号关键词.csv'
    # keywords_dict = load_keywords(keyword_file)  # {keyword: [pic_list, text_list, rule_name]}
    # keyword = request.GET.get('keyword', '')
    # if keyword in keywords_dict.keys():
    #     text_list = [text_content.split('<br>') for text_content in keywords_dict[keyword][1]]
    #     pic_list = keywords_dict[keyword][0]
    #     content = {'content': [keyword, pic_list, text_list]}
    #     return render(request, 'auto_reply.html', content)
    # else:
    #     return HttpResponse('Keyword error!')


def load_user_data(user_json_file):
    """
    读取文件查询用户的数据，文件格式为json，返回dict
    :param user_json_file:
    :return:
    """
    user_data_dict = dict()
    if os.path.exists(user_json_file):
        with open(user_json_file, 'r') as f:
            user_data_dict = json.loads(''.join(f.readlines()))
    if len(user_data_dict.keys()) != user_data_keys_count:
        user_data_dict = reset_user_data()
        save_user_data(user_data_dict=user_data_dict, user_json_file=user_json_file)
    return user_data_dict


def reset_user_data():
    """
    返回一个空白的用户数据字典，内容格式：
     {
        current_game:   当前游戏名称,
        transmit_count: 总发送消息数,
        game_process:   dict() # 可以根据不同的游戏设置对应的进度内容
        cmd_list:       用户输入过的命令列表
        user_id:        用户输入的id
    }
    :return:
    """
    user_data_dict = dict()
    user_data_dict['current_game'] = ''
    user_data_dict['transmit_count'] = 0
    user_data_dict['game_process'] = dict()
    user_data_dict['cmd_list'] = list()
    user_data_dict['user_id'] = ''
    return user_data_dict


def save_user_data(user_json_file, user_data_dict):
    """
    保存对应open id用户的当前进度数据，文件格式为json

    :param user_json_file:
    :param user_data_dict:
    :return:
    """
    if len(user_data_dict) > 0:
        result = json.dumps(user_data_dict, ensure_ascii=False)
        with open(user_json_file, 'w') as f:
            f.writelines(result)
            return user_data_dict


def get_summary(user_data_dict, max_length=500):
    """
    根据用户的进度信息，返回总览文字
    :param max_length:
    :param user_data_dict:
    :return:
    """
    if user_data_dict:
        current_game = user_data_dict['current_game']
        transmit_count = user_data_dict['transmit_count']
        process_data_dict = user_data_dict['game_process']
        cmd_list = user_data_dict['cmd_list']
        user_id = user_data_dict['user_id']
        return_string = f'''你好，{user_id}，
        你已经向我们发送了{transmit_count}条游戏指令
        你当前的游戏是《{current_game}》
        你在这个游戏里的进度是{process_data_dict}
        你输入过的命令是{cmd_list} 
        '''
        # print(return_string)
        return return_string[:max_length]


def auth_user(game, password, user_id=''):
    """
    根据密码对用户进行鉴权
    :param add:         进行鉴权的app
    :param user_id:     要鉴权的open id
    :param password:    提供的密码字符串
    :return: 鉴权通过则返回True，不通过则返回False
    """
    if len(password) > 0:
        available_passwd = WechatGamePasswd.objects.filter(game=game, password=password, is_assigned=False)
        if len(available_passwd) > 0:
            # password is valid
            my_passwd = available_passwd[0]
            try:
                my_player = WechatPlayer.objects.get(app=game.app, open_id=user_id)
            except ObjectDoesNotExist:
                # 没有找到user_id对应的用户
                return False
            my_passwd.assigned_player = my_player
            my_passwd.is_assigned = True
            my_passwd.save()
            return True
        else:
            return False  # 没找到对应的密码，也就是密码不对
    else:
        return False  # 没有提供密码


def load_user_passwd_dict():
    """
    返回用户与密码的配对dict
    :param allowed_usesr_list_file:
    :return:
    """
    if os.path.exists(allowed_usesr_list_file):
        user_passwd_dict = dict()
        with open(allowed_usesr_list_file, 'r') as f:
            password_data_rows = csv.reader(f)  # user_id, password
            for password_data_row in password_data_rows:
                user_id = password_data_row[0]
                password = password_data_row[1]
                user_passwd_dict[user_id] = password
        return user_passwd_dict
    else:
        return False


def get_player_summary(appid, game_name):
    """
    统计某个游戏内的玩家信息，通过遍历每个玩家的game_hist来实现
    :param appid:      appid
    :param game_name:  游戏名称
    :return:           返回一个list，每个元素一个dict，代表一个玩家的情况，包含以下内容：
        user_id, open_id: 玩家的id和open_id
        transmit_count: 玩家共计发出过多少个指令，例如回答问题, 
        cur_process: 玩家当前所处的任务关卡, 
        quests_num: 玩家进入过的关卡数,
        rewards_num: 玩家获得过的奖励数,
        is_passed: 玩家是否通关
            
    """
    summary_list = list()
    # player_count = 0
    try:
        my_app = WechatApp.objects.get(appid=appid)
        my_game = ExploreGame.objects.get(app=my_app, name=game_name)
        all_players = WechatPlayer.objects.filter(game_hist__has_key=my_game.name)
        for player in all_players:
            my_game_data = player.game_hist[my_game.name]
            player_info = dict()
            player_info['user_id'] = player.name
            player_info['open_id'] = player.open_id
            all_command = list()
            x = my_game_data.get('cmd_dict', dict())
            # x = {'关卡1': [指令1, 指令2, ...], '关卡2': [指令1, 指令2, ...]}
            for y in x.values():
                all_command.extend(y) # 所有的指令
            player_info['transmit_count'] = len(all_command)
            player_info['quests_num'] = len(x)  # 进入过的关卡数
            player_info['rewards_num'] = len(my_game_data.get('reward_list', list()))  # 获得过的奖励数
            player_info['cur_process'] = my_game_data.get('wait_status', '')  # 当前所处的任务关卡
            player_info['is_passed'] = len(my_game_data.get('clear_code', ''))>0
            summary_list.append(player_info)
    except ObjectDoesNotExist:
        raise
    except MultipleObjectsReturned:
        raise
    return summary_list


def list_open_id():
    """
    从open_id_file中读取json内容，返回dict
    :return:
    """
    if os.path.exists(open_id_file):
        with open(open_id_file, 'r') as f:
            open_id_dict = json.loads((''.join(f.readlines())))

            return list(open_id_dict.items())
    else:
        print(f'open_id_file not exists: {open_id_file}')
        return False


def gen_passwd(leng=7, use_symbol=False, use_lower=True, use_number=False, use_upper=True):
    """
    密码生成器
    :param leng:
    :param use_symbol:
    :param use_cap:
    :param use_number:
    :param use_uncap:
    :return:
    """
    password_list = list()
    symbol_list = ['!', '@', '#', '$', '%', '^', '&', '*', '(', ')', '_', '+', '-', '=']
    number_list = ['0', '1', '2', '3', '4', '5', '6', '7', '8', '9']
    upper_list = ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J', 'K', 'L', 'M', 'N', 'O', 'P', 'Q', 'R', 'S', 'T',
                  'U', 'V', 'W', 'X', 'Y', 'Z']
    lower_list = ['z', 'y', 'x', 'w', 'v', 'u', 't', 's', 'r', 'q', 'p', 'o', 'n', 'm', 'l', 'k', 'j', 'i', 'h', 'g',
                  'f', 'e', 'd', 'c', 'b', 'a']
    if use_lower:
        password_list.extend(lower_list)
    if use_upper:
        password_list.extend(upper_list)
    if use_number:
        password_list.extend(number_list)
    if use_symbol:
        password_list.extend(symbol_list)
    if len(password_list) > 0 and leng > 0:
        password = ''.join(sample(password_list, leng)).replace(' ', '')
        return password
    else:
        return False