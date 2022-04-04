# 用于处理explore game的相关流程
# 对于文字版和网页版都通用

from django.core.exceptions import *
from wxcloudrun.common_functions import *
import datetime
from wxcloudrun.models import *
from wxcloudrun.location_game import *

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
FIELD_COMMAND_LIST = 'cmd_list'                 # 存放已行动命令的字典key
FIELD_IS_AUDIT = 'is_audit'                     # 存在当前用户在当前游戏是否已认证的key

OPTION_ENABLE = 'weui-cell weui-cell_access'    # 提供可选选项的样式
OPTION_DISABLE = 'weui-cell weui-cell_disable'  # 提供不可选选项的样式

def handle_player_command(app_en_name='', open_id='', game_name='', cmd='', for_text=True):
    """
    用于处理某个玩家对某个游戏发出了某个指令
    所有参数都是字符串
    返回字典对象
    {'game_is_valid': true/false,
    'game_is_active': true/false,
    'player_is_audit': true/false,
    'player_info': player_info_dict,        该玩家的基本信息，昵称、头像等
    'player_game_info': player_game_info_dict, 该玩家在处理完这个指令后的存档
    'reply_obj': object,        用于回复的主要内容, 如果for_text==True，就以旧版格式返回replyMsg，否则返回字符串
    'reply_options': [reply_opt_dict1, reply_opt_dict2],  用于显示下一步的选项及额外内容
    'hint_string': string,      当前任务的提示信息，放在前端随时显示
    'clear_code': string,       通关密码，放在前端显示，未通关时为空
    'progress': string,         当前进度，放在前端随时显示
    'notify_msg': string,       绿色的提醒
    'error_msg': string,        红色的提醒
    }
    """
    # 初始化返回对象
    ret_dict = dict()
    ret_dict['game_is_valid'] = False
    ret_dict['game_is_active'] = False
    ret_dict['player_is_audit'] = False
    ret_dict['player_info'] = dict()
    ret_dict['player_game_info'] = dict()
    ret_dict['reply_obj'] = ''
    ret_dict['reply_options'] = list()
    ret_dict['hint_string'] = ''
    ret_dict['clear_code'] = ''
    ret_dict['progress'] = ''
    ret_dict['notify_msg'] = ''
    ret_dict['error_msg'] = ''

    # 为了和文字版统一处理，增加fromUser空变量
    fromUser = ''
    # 首先获取app信息，my_app
    if len(app_en_name) > 0:
        try:
            my_app = WechatApp.objects.get(en_name=app_en_name)
            app_keyword_list = [x.keyword for x in AppKeyword.objects.filter(app=my_app)]
        except ObjectDoesNotExist:
            # en_name not valid
            ret_dict['error_msg'] = f'app_en_name:{app_en_name} 不存在'
            return ret_dict
    else:
        # app_en_name not valid
        ret_dict['error_msg'] = f'app_en_name is blank'
        return ret_dict

    #  检查这个openid对应的用户对象，cur_player
    if len(open_id) > 0:
        try:
            cur_player = WechatPlayer.objects.get(app=my_app, open_id=open_id)
        except ObjectDoesNotExist:
            # 如果这个openid是第一次出现，就先创新对应用户
            cur_player = WechatPlayer(app=my_app, open_id=open_id)
            cur_player.save()
    else:
        # open_id not valid
        ret_dict['error_msg'] = f'open_id is blank'
        return ret_dict

    # 如果参数中带了game_name内容，就用game_name获取游戏
    # 如果game_name为空，就以用户的cur_game_name属性获取游戏
    # 如果cur_player.cur_game_name也为空，就返回失败信息
    if len(game_name) > 0:
        cur_game_name = game_name
    elif len(cur_player.cur_game_name) > 0:
        cur_game_name = cur_player.cur_game_name
    else:
        # game_name not valid
        ret_dict['error_msg'] = f'game_name is blank'
        return ret_dict

    # 获取游戏对象，cur_game
    try:
        cur_game = ExploreGame.objects.get(app=my_app, name=cur_game_name)
        ret_dict['game_is_valid'] = True
    except ObjectDoesNotExist:
        # 如果配置的游戏名称已经不存在，就清空已配置的名称
        # 触发词列表置空
        cur_player.cur_game_name = ''
        cur_player.save()
        cur_game = None
        ret_dict['error_msg'] = f'游戏{cur_game_name}不存在'
        return ret_dict

    # 检查游戏激活状态
    # 如果当前游戏处于激活状态，初始化游戏对应的对象
    # 触发词列表、当前玩家游戏存档、已获成就、历史命令列表、通关码、鉴权信息
    if cur_game.is_active:
        ret_dict['game_is_active'] = True
        trigger_list = [x.quest_trigger for x in ExploreGameQuest.objects.filter(game=cur_game)]
        cur_player_game_dict = get_cur_player_game_dict(player=cur_player, game_name=cur_game_name)
        reward_list = cur_player_game_dict.get(FIELD_REWARD_LIST, list())
        cmd_list = cur_player_game_dict.get(FIELD_COMMAND_LIST, list())
        clear_code = cur_player_game_dict.get(FIELD_CLEAR_CODE, '')
        player_is_audit = cur_player_game_dict.get(FIELD_IS_AUDIT, False)
        ret_dict['player_is_audit'] = player_is_audit
        ret_dict['player_game_info'] = cur_player_game_dict
        ret_dict['player_info'] = cur_player.user_info
        ret_dict['clear_code'] = clear_code
        ret_dict['progress'] = check_progress(cur_game=cur_game, reward_list=reward_list)
    else:
        # 如果游戏不是激活状态
        ret_dict['error_msg'] = f'游戏{cur_game_name}未启动或已过活动时间'
        return ret_dict

    # 但需要检查用户是否鉴权
    if player_is_audit:
        # 开始检查cmd指令
        if len(cmd) > 0:
            content = cmd
            if content in trigger_list:
                # 如果用户尝试触发新任务
                cur_quest = ExploreGameQuest.objects.get(game=cur_game, quest_trigger=content)
                prequire_list = cur_quest.get_content_list(type='prequire')
                if set(prequire_list).issubset(set(reward_list)) or len(prequire_list) == 0:
                    # 如果这个Quest没有前置要求，或前置要求都达到了
                    cur_player.waiting_status = content
                    cur_player.save()
                    ret_dict = set_quest(cur_game=cur_game, trigger=content, open_id=open_id, ret_dict=ret_dict)
                else:
                    # 前置要求还没做全
                    done_id_list = set(reward_list).intersection(set(prequire_list))
                    all_quest = ExploreGameQuest.objects.filter(game=cur_game)
                    done_q_name_list = list()
                    for q in all_quest:
                        if q.reward_id in done_id_list:
                            done_q_name_list.append(q.quest_trigger)
                    text_content = f'要回答这个问题，需要先完成{len(prequire_list)}个任务，'
                    text_content += f'而{ret_dict["progress"]}。'
                    ret_dict['error_msg'] = text_content

            elif len(cur_player.waiting_status) > 0:  # 如果用户已经处于等待输入状态

                # 用户已处于某个Quest中，等待输入答案
                if cur_player.waiting_status in trigger_list:
                    # 如果用户已经处于某个quest的任务中
                    try:
                        cur_quest = ExploreGameQuest.objects.get(game=cur_game, quest_trigger=cur_player.waiting_status)
                        answer_list = cur_quest.get_content_list(type='answer')
                    except ObjectDoesNotExist:
                        # 玩家等待状态设置错误，可能是游戏配置已更改
                        # 清空等待状态，将answer_list置为空列表
                        cur_player.waiting_status = ''
                        cur_player.save()
                        answer_list = list()
                        cur_quest = None
                        ret_dict = new_game(cur_game=cur_game, reward_list=reward_list, ret_dict=ret_dict)
                        text_content = f'任务已取消，请重新开始另一个任务'
                        ret_dict['error_msg'] = text_content
                        return ret_dict
                    if content in answer_list:
                        # 答对了当前问题
                        reward_id = cur_quest.reward_id
                        # 如果玩家是新获得的奖励，就增加1个步数，保存奖励记录
                        # 如果玩家之前已经获得过奖励，就忽略
                        if reward_id not in reward_list:
                            cmd_list.append(content)
                            reward_list.append(reward_id)
                            cur_player_game_dict[FIELD_REWARD_LIST] = reward_list
                            cur_player_game_dict[FIELD_COMMAND_LIST] = cmd_list
                            cur_player.game_hist[cur_game_name] = cur_player_game_dict
                            ret_dict['notify_msg'] = cur_quest.reward

                        # 重置玩家当前等待状态，并保存
                        cur_player.waiting_status = ''
                        cur_player.save()
                        # 确认玩家是否已通关
                        clear_requirement_list = cur_game.get_content_list()
                        if set(clear_requirement_list).issubset(set(reward_list)):
                            # 玩家已达到通关要求
                            clear_code = cur_player.hash_with_game()
                            cur_player_game_dict[FIELD_CLEAR_CODE] = clear_code
                            cur_player.game_hist[cur_game_name] = cur_player_game_dict
                            cur_player.save()
                            text_content = f'{cur_game.clear_notice}'
                            text_content += '\n'
                            text_content += f'您的通关密码是：{clear_code}'
                            ret_dict['notify_msg'] = text_content
                            ret_dict['clear_code'] = clear_code
                        else:
                            # 玩家还没通关
                            replyMsg = cur_quest.reply_msg(type='reward', toUser=open_id, fromUser=fromUser,
                                                           for_text=for_text)
                            ret_dict['reply_obj'] = replyMsg
                        # 重置游戏界面
                        ret_dict = new_game(cur_game=cur_game, reward_list=reward_list, ret_dict=ret_dict)
                    else:
                        # 输入了不相关的内容
                        cmd_list.append(content)
                        cur_player_game_dict[FIELD_COMMAND_LIST] = cmd_list
                        cur_player.game_hist[cur_game_name] = cur_player_game_dict
                        cur_player.save()
                        my_error_auto_replys = list(ErrorAutoReply.objects.filter(is_active=True))
                        ret_dict = set_quest(cur_game=cur_game, trigger=cur_player.waiting_status,
                                             ret_dict=ret_dict, open_id=open_id)
                        if len(my_error_auto_replys) > 0:
                            choose_reply = sample(my_error_auto_replys, 1)[0]
                            ret_dict['error_msg'] = choose_reply.reply_msg(toUser=open_id, fromUser=fromUser,
                                                                           for_text=for_text)
                        else:
                            ret_dict['error_msg'] = f'{error_reply_default}'
        else:  # 如果cmd为空，就显示游戏的初始化内容
            ret_dict = new_game(cur_game=cur_game, reward_list=reward_list, ret_dict=ret_dict)
    else:
        # user is not audit
        # 等待用户输入密码
        content = cmd
        if cur_player.waiting_status == WAITING_FOR_PASSWORD:
            # 玩家正在输入密码
            result = auth_user(app=my_app, password=content, user_id=open_id)
            if result:
                player_is_audit = True
                cur_player.waiting_status = ''
                cur_player_game_dict[FIELD_IS_AUDIT] = player_is_audit
                cur_player.game_hist[cur_game_name] = cur_player_game_dict
                cur_player.save()
                ret_dict = new_game(cur_game=cur_game, reward_list=reward_list, ret_dict=ret_dict)
                ret_dict['player_is_audit'] = True
                ret_dict['notify_msg'] = AUDIT_SUCCESS
                ret_dict['cmd'] = ''
            else:
                # 没有输对密码
                ret_dict['error_msg'] = AUDIT_FAILED
        else:
            cur_player.waiting_status = WAITING_FOR_PASSWORD
            cur_player.save()
            ret_dict['error_msg'] = ASK_FOR_PASSWORD

    return ret_dict


def get_cur_player_game_dict(player, game_name):
    """
    返回玩家游戏存档字典
    """
    player_game_dict = player.game_hist  # json object
    # player_game_dict should be like this
    # {'cur_game_name': {setting1: xxx, setting2: xxx}}
    if len(game_name) > 0:
        # 如果游戏名不为空
        if not player_game_dict:
            # 如果这个玩家还没有游戏存档，就用输入的游戏名初始化一个
            cur_player_game_dict = {FIELD_IS_AUDIT: False,
                                    FIELD_COMMAND_LIST: list(),
                                    FIELD_CLEAR_CODE: '',
                                    FIELD_REWARD_LIST: list()}
            player_game_dict = {game_name: cur_player_game_dict}
            player.game_hist = player_game_dict
            player.save()
        else:
            # 如果玩家已经有游戏存档
            cur_player_game_dict = player_game_dict.get(game_name, dict())
    else:
        # 如果输入的游戏名为空，返回空字典
        cur_player_game_dict = dict()
    return cur_player_game_dict


def check_progress(cur_game, reward_list):
    # 按玩家当前成就生成游戏进度描述语句
    if cur_game:
        all_quest = ExploreGameQuest.objects.filter(game=cur_game)
        done_q_name_list = list()
        for q in all_quest:
            if q.reward_id in reward_list:
                done_q_name_list.append(q.quest_trigger)
        if len(done_q_name_list) > 0:
            text_content = f'您现在完成了{str(done_q_name_list)[1:-1]} {len(done_q_name_list)}个任务。'
        else:
            text_content = f'您现在还没有完成任何任务。'
    else:
        text_content = f'您没有参与游戏。'
    return text_content


def new_game(cur_game, reward_list, ret_dict):
    ret_dict['reply_obj'] = replace_content_with_html(cur_game.opening)
    qeusts = ExploreGameQuest.objects.filter(game=cur_game)
    for my_quest in qeusts:
        # 将可以挑战的任务放在选项中
        prequire_list = my_quest.get_content_list(type='prequire')
        if my_quest.reward_id in reward_list:
            # 如果这个Quest已经通关
            ret_dict['reply_options'].append({'trigger': my_quest.quest_trigger,
                                              'comment': '已通关',
                                              'enable': False,
                                              'style': OPTION_ENABLE})
        elif set(prequire_list).issubset(set(reward_list)) or len(prequire_list) == 0:
            # 如果这个Quest没有前置要求，或前置要求都达到了
            ret_dict['reply_options'].append({'trigger': my_quest.quest_trigger,
                                              'comment': '可挑战',
                                              'enable': True,
                                              'style': OPTION_ENABLE})
        else:
            # 其他情况，还不能挑战这个任务
            ret_dict['reply_options'].append({'trigger': my_quest.quest_trigger,
                                              'comment': '未具备挑战条件',
                                              'enable': False,
                                              'style': OPTION_DISABLE})
    ret_dict['progress'] = check_progress(cur_game=cur_game, reward_list=reward_list)
    return ret_dict


def set_quest(cur_game, trigger, ret_dict, open_id):
    cur_quest = ExploreGameQuest.objects.get(game=cur_game, quest_trigger=trigger)
    fromUser = ''
    for_text = False
    ret_dict['reply_obj'] = cur_quest.reply_msg(type='question', toUser=open_id,
                                                fromUser=fromUser, for_text=for_text)
    option_list = cur_quest.get_content_list(type='option')
    for option in option_list:
        ret_dict['reply_options'].append({'trigger': option,
                                          'comment': '',
                                          'enable': True,
                                          'style': OPTION_ENABLE})
    ret_dict['hint_string'] = cur_quest.reply_msg(type='hint', toUser=open_id,
                                                  fromUser=fromUser, for_text=for_text)
    return ret_dict
