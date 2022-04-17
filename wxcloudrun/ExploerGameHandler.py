# 用于处理explore game的相关流程
# 对于文字版和网页版都通用

from django.core.exceptions import *
from wxcloudrun.common_functions import *
import datetime
from wxcloudrun.models import *
from wxcloudrun.location_game import *


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
    'app_en_name': string,
    'open_id': string,
    'quest_trigger': string,    用来做页面的title
    'page_type': string,             目前分为reward和quest两种，分别对应问题页面和成就页面
    'answer_is_correct': bool   如果用户提交的是答案，而且答对了，就返回True，否则一律返回False
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
    ret_dict['cur_game_name'] = ''
    ret_dict['app_en_name'] = ''
    ret_dict['open_id'] = ''
    ret_dict['quest_trigger'] = ''
    ret_dict['page_type'] = ''
    ret_dict['answer_is_correct'] = False

    # 为了和文字版统一处理，增加fromUser空变量
    fromUser = ''
    # 首先获取app信息，my_app
    if len(app_en_name) > 0:
        try:
            my_app = WechatApp.objects.get(en_name=app_en_name)
            app_keyword_list = [x.keyword for x in AppKeyword.objects.filter(app=my_app)]
            ret_dict['app_en_name'] = app_en_name
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
            # 如果这个openid没有在数据库中，则表明不是从微信进入，需要返回错误信息
            ret_dict['error_msg'] = '用户id异常，请从公众号进入游戏'
            return ret_dict
        ret_dict['open_id'] = open_id
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
        ret_dict['cur_game_name'] = cur_game_name
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
        cur_player_game_dict = get_cur_player_game_dict(player=cur_player, game_name=cur_game_name)
        reward_list = cur_player_game_dict.get(FIELD_REWARD_LIST, list())
        cmd_dict = cur_player_game_dict.get(FIELD_COMMAND_DICT, dict())
        clear_code = cur_player_game_dict.get(FIELD_CLEAR_CODE, '')
        player_is_audit = cur_player_game_dict.get(FIELD_IS_AUDIT, False)
        wait_status = cur_player_game_dict.get(FIELD_WAIT_STATUS, '')
        if len(wait_status) > 0:
            try:
                cur_quest = ExploreGameQuest.objects.get(game=cur_game, quest_trigger=wait_status)
                next_list = cur_quest.get_content_list(type='next')
                if len(next_list) > 0:
                    trigger_list = next_list
                    trigger_list.append(wait_status)
                    if len(cur_quest.back_quest) > 0:
                        trigger_list.append(cur_quest.back_quest)
            except ObjectDoesNotExist:
                next_list = list()
        else:
            next_list = list()
        if len(next_list) == 0:
            trigger_list = [x.quest_trigger for x in ExploreGameQuest.objects.filter(game=cur_game)]
        ret_dict['player_is_audit'] = player_is_audit
        ret_dict['player_game_info'] = cur_player_game_dict
        ret_dict['player_info'] = cur_player.user_info
        ret_dict['clear_code'] = clear_code
        ret_dict['progress'] = cur_game.check_progress(reward_list=reward_list)
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
                ret_dict['answer_is_correct'] = True
                cur_quest = ExploreGameQuest.objects.get(game=cur_game, quest_trigger=content)
                prequire_list = cur_quest.get_content_list(type='prequire')
                if set(prequire_list).issubset(set(reward_list)) or len(prequire_list) == 0:
                    # 如果这个Quest没有前置要求，或前置要求都达到了
                    if cur_quest.reward_id in reward_list:
                        # 如果玩家已经通关这个任务，就显示对应的成就页面
                        ret_dict = set_reward(quest=cur_quest, ret_dict=ret_dict)
                    else:
                        # 如果玩家还没通过这个任务，就显示问题页面
                        wait_status = content
                        cur_player_game_dict[FIELD_WAIT_STATUS] = wait_status
                        cur_player.game_hist[cur_game_name] = cur_player_game_dict
                        cur_player.save()
                        ret_dict = set_quest(cur_game=cur_game, trigger=content, open_id=open_id,
                                             ret_dict=ret_dict, reward_list=reward_list)
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

            elif len(wait_status) > 0:  # 如果用户已经处于等待输入状态

                # 用户已处于某个Quest中，等待输入答案
                if wait_status in trigger_list:
                    # 如果用户已经处于某个quest的任务中
                    try:
                        cur_quest = ExploreGameQuest.objects.get(game=cur_game, quest_trigger=wait_status)
                        answer_list = cur_quest.get_content_list(type='answer')
                        next_list = cur_quest.get_content_list(type='next')
                        cmd_list = cmd_dict.get(wait_status, list())
                    except ObjectDoesNotExist:
                        # 玩家等待状态设置错误，可能是游戏配置已更改
                        # 清空等待状态，将answer_list置为空列表
                        wait_status = ''
                        cur_player_game_dict[FIELD_WAIT_STATUS] = wait_status
                        cur_player.game_hist[cur_game_name] = cur_player_game_dict
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
                        ret_dict['answer_is_correct'] = True
                        # 如果玩家是新获得的奖励，就增加1个步数，保存奖励记录
                        # 如果玩家之前已经获得过奖励，就忽略
                        if reward_id > 0 and reward_id not in reward_list:
                            cmd_list.append(content)
                            cmd_dict[wait_status] = cmd_list
                            reward_list.append(reward_id)
                            cur_player_game_dict[FIELD_REWARD_LIST] = reward_list
                            cur_player_game_dict[FIELD_COMMAND_DICT] = cmd_dict
                            cur_player.game_hist[cur_game_name] = cur_player_game_dict
                            # ret_dict['notify_msg'] = cur_quest.reward

                        if len(next_list) == 0:  # 没有下一步，即简单的游戏模式
                            # 重置玩家当前等待状态，并保存
                            wait_status = ''
                            cur_player_game_dict[FIELD_WAIT_STATUS] = wait_status
                            cur_player.game_hist[cur_game_name] = cur_player_game_dict
                            cur_player.save()
                            # 确认玩家是否已通关
                            clear_requirement_list = cur_game.get_content_list()
                            if set(clear_requirement_list).issubset(set(reward_list)):
                                # 玩家已达到通关要求
                                clear_code = cur_player.hash_with_game(cur_game_name)
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
                            # ret_dict = new_game(cur_game=cur_game, reward_list=reward_list, ret_dict=ret_dict)
                            # 进入显示成就页面
                            ret_dict = set_reward(quest=cur_quest, ret_dict=ret_dict)
                        else: # 有next_list，就生成下一步的页面
                            ret_dict['answer_is_correct'] = True
                            wait_status = next_list[0]
                            cur_player_game_dict[FIELD_WAIT_STATUS] = wait_status
                            cur_player.game_hist[cur_game_name] = cur_player_game_dict
                            cur_player.save()
                            ret_dict = set_quest(cur_game=cur_game, open_id=open_id, ret_dict=ret_dict,
                                                 reward_list=reward_list)
                    else:
                        # 输入了不相关的内容
                        cmd_list.append(content)
                        cmd_dict[wait_status] = cmd_list
                        cur_player_game_dict[FIELD_COMMAND_DICT] = cmd_dict
                        cur_player.game_hist[cur_game_name] = cur_player_game_dict
                        cur_player.save()
                        my_error_auto_replys = list(ErrorAutoReply.objects.filter(is_active=True))
                        ret_dict = set_quest(cur_game=cur_game, trigger=wait_status,
                                             ret_dict=ret_dict, open_id=open_id, reward_list=reward_list)
                        if len(my_error_auto_replys) > 0:
                            choose_reply = sample(my_error_auto_replys, 1)[0]
                            ret_dict['error_msg'] = choose_reply.reply_msg(toUser=open_id, fromUser=fromUser,
                                                                           for_text=for_text)
                        else:
                            ret_dict['error_msg'] = f'{error_reply_default}'
                elif wait_status == WAITING_FOR_PASSWORD:
                    # 如果用户已经完成鉴权，但状态是等待输入密码，就可能人为修改了鉴权状态，先清空等待状态
                    wait_status = ''
                    cur_player_game_dict[FIELD_WAIT_STATUS] = wait_status
                    cur_player.game_hist[cur_game_name] = cur_player_game_dict
                    cur_player.save()
                    ret_dict = new_game(cur_game=cur_game, reward_list=reward_list, ret_dict=ret_dict)
        else:  # 如果cmd为空，就显示游戏的初始化内容
            wait_status = ''
            cur_player_game_dict[FIELD_WAIT_STATUS] = wait_status
            cur_player.game_hist[cur_game_name] = cur_player_game_dict
            cur_player.save()
            ret_dict = new_game(cur_game=cur_game, reward_list=reward_list, ret_dict=ret_dict)
    else:
        # user is not audit
        # 等待用户输入密码
        content = cmd
        if wait_status == WAITING_FOR_PASSWORD:
            # 玩家正在输入密码
            if len(content) > 0:
                result = auth_user(game=cur_game, password=content, user_id=open_id)
                if result:
                    player_is_audit = True
                    wait_status = ''
                    cur_player_game_dict[FIELD_WAIT_STATUS] = wait_status
                    cur_player_game_dict[FIELD_IS_AUDIT] = player_is_audit
                    cur_player.game_hist[cur_game_name] = cur_player_game_dict
                    cur_player.save()
                    ret_dict = new_game(cur_game=cur_game, reward_list=reward_list, ret_dict=ret_dict)
                    ret_dict['player_is_audit'] = True
                    ret_dict['answer_is_correct'] = True
                    ret_dict['cmd'] = ''
                else:
                    # 没有输对密码
                    ret_dict['error_msg'] = AUDIT_FAILED
                    ret_dict['page_type'] = 'password'  # 因为需要输入密码
            else:  # cmd为空，再次显示请输入密码
                ret_dict['error_msg'] = ASK_FOR_PASSWORD
                ret_dict['page_type'] = 'password'  # 因为需要输入密码
        else:
            wait_status = WAITING_FOR_PASSWORD
            cur_player_game_dict[FIELD_WAIT_STATUS] = wait_status
            cur_player.game_hist[cur_game_name] = cur_player_game_dict
            cur_player.save()
            ret_dict['error_msg'] = ASK_FOR_PASSWORD
            ret_dict['page_type'] = 'password'  # 因为需要输入密码

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
                                    FIELD_COMMAND_DICT: dict(),
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


def set_quest_option(my_quest, reward_list):
    # 判断某个任务的状态（已完成、可挑战或不能挑战），返回显示选项
    # 如果判断为不显示，则返回None
    prequire_list = my_quest.get_content_list(type='prequire')
    if my_quest.reward_id in reward_list:
        # 如果这个Quest已经通关
        return {'trigger': my_quest.quest_trigger, 'comment': my_quest.comment_when_clear,
                'enable': True, 'style': OPTION_ENABLE}
    elif set(prequire_list).issubset(set(reward_list)) or len(prequire_list) == 0:
        # 如果这个Quest没有前置要求，或前置要求都达到了
        return {'trigger': my_quest.quest_trigger, 'comment': my_quest.comment_when_available,
                'enable': True, 'style': OPTION_ENABLE}
    else:
        # 其他情况，还不能挑战这个任务，判断是否要显示
        if my_quest.show_if_unavailable:
            return {'trigger': my_quest.quest_trigger, 'comment': my_quest.comment_when_unavailable,
                    'enable': False, 'style': OPTION_DISABLE}
        else:
            return None


def new_game(cur_game, reward_list, ret_dict):

    ret_dict['reply_obj'] = cur_game.show_opening()
    ret_dict['reply_options'] = list()
    entry_quest = None
    if len(cur_game.entry) > 0:
        try:
            entry_quest = ExploreGameQuest.objects.get(game=cur_game, quest_trigger=cur_game.entry)
        except ObjectDoesNotExist:
            # 游戏入口任务不存在，回退到显示所有可选任务
            pass
    if entry_quest:
        quest_option = set_quest_option(my_quest=entry_quest, reward_list=reward_list)
        if quest_option:
            ret_dict['reply_options'].append(quest_option)
    else:
        qeusts = ExploreGameQuest.objects.filter(game=cur_game).order_by('reward_id')
        for cur_quest in qeusts:
            # 将可以挑战的任务放在选项中
            quest_option = set_quest_option(my_quest=cur_quest, reward_list=reward_list)
            if quest_option:
                ret_dict['reply_options'].append(quest_option)
    ret_dict['progress'] = cur_game.check_progress(reward_list=reward_list)
    ret_dict['quest_trigger'] = cur_game.name
    ret_dict['page_type'] = 'main'
    return ret_dict


def set_quest(cur_game, trigger, ret_dict, open_id, reward_list=list()):
    cur_quest = ExploreGameQuest.objects.get(game=cur_game, quest_trigger=trigger)
    fromUser = ''
    for_text = False
    ret_dict['reply_obj'] = cur_quest.reply_msg(type='question', toUser=open_id,
                                                fromUser=fromUser, for_text=for_text)
    option_list = cur_quest.get_content_list(type='option')
    next_list = cur_quest.get_content_list(type='next')
    if len(next_list) > 0 and cur_quest.show_next:
        for next_trigger in next_list:
            try:
                next_quest = ExploreGameQuest.objects.get(game=cur_game, quest_trigger=next_trigger)
                quest_option = set_quest_option(my_quest=next_quest, reward_list=reward_list)
                if quest_option:
                    ret_dict['reply_options'].append(quest_option)
            except ObjectDoesNotExist:
                logger.error(f'{next_trigger} is not exists')

    else:
        for option in option_list:
            ret_dict['reply_options'].append({'trigger': option,
                                              'comment': '',
                                              'enable': True,
                                              'style': OPTION_ENABLE})
    ret_dict['hint_string'] = cur_quest.reply_msg(type='hint', toUser=open_id,
                                                  fromUser=fromUser, for_text=for_text)
    ret_dict['quest_trigger'] = trigger
    ret_dict['page_type'] = 'quest'
    return ret_dict


def set_reward(quest, ret_dict):
    fromUser = ''
    toUser = ''
    for_text = False
    ret_dict['reply_obj'] = quest.reply_msg(type='reward', toUser=toUser,
                                                fromUser=fromUser, for_text=for_text)

    ret_dict['quest_trigger'] = quest.quest_trigger
    ret_dict['hint_string'] = ''
    ret_dict['page_type'] = 'reward'
    return ret_dict