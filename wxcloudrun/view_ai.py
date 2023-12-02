from openai import OpenAI
import json
from django.shortcuts import HttpResponse, render, HttpResponseRedirect
import requests
import os
from logging import getLogger


HOME_SERVER = os.environ.get('HOME_SERVER', '')

GPT_URL = os.environ.get('GPT_URL', '')
API_KEY = os.environ.get('API_KEY', '')
logger = getLogger('django')

def accounting(model, completion_tokens, prompt_tokens):
    """
    根据openai官网的价格进行费用估算
    """
    if 'gpt-3.5-turbo' in model:
        in_token_price = 0.001
        out_token_price = 0.002
    elif 'gpt-4-' in model:
        in_token_price = 0.01
        out_token_price = 0.03
    return (prompt_tokens * in_token_price + completion_tokens * out_token_price)/125  # 汇率按8计算，费用单位10000token，而费用*8/1000=/125


def chat(request):
    user = request.user
    question = request.GET.get('question', '')
    character = request.GET.get('character', '')
    ret_dict = dict()
    ret_dict['home_server'] = HOME_SERVER
    ret_dict['chosen_character'] = ''
    if user.is_authenticated:
        if 'GPT' in user.groups.values_list('name', flat=True):
            template = 'wechat_chat.html'
            if os.path.exists('characters.json'):
                with open('characters.json', 'r', encoding='utf-8') as f:
                    character_DICT = json.load(f)
                    ret_dict['characters'] = list(character_DICT.keys())
            else:
                return HttpResponse('请先配置角色文件！')
            if os.path.exists('GPT_settings.json'):
                with open('GPT_settings.json', 'r', encoding='utf-8') as f:
                    GPT_settings = json.load(f)
                    model = GPT_settings.get('model', 'gpt-3.5-turbo')
                    max_length = GPT_settings.get('max_length', 150)
                    instructions = GPT_settings.get('instructions', '')
            else:
                return HttpResponse('请先配置GPT设置文件！')
                
            if GPT_URL == '' or API_KEY == '':
                return HttpResponse('请先配置环境变量！')
            if (question != ''):
                form_data = dict()
                header = dict()
                header['Content-Type'] = 'application/json'
                form_data['question'] = question
                if character == '' or character not in character_DICT.keys():
                    return render(request, template, ret_dict)
                else:
                    character_file = character_DICT[character]
                    ret_dict['chosen_character'] = character
                if os.path.exists(character_file):
                    with open(character_file, 'r', encoding='utf-8') as f:
                        assistant = f.read()
                        # replace \n with '\n'
                        assistant = assistant.replace('\n', '')
                form_data['instructions'] = f"你是{character}，" + instructions + assistant
                form_data['assistant'] = ''
                form_data['max_tokens'] = max_length
                form_data['api_key'] = API_KEY
                form_data['model'] = model
                # logger.info(f'form_data: {form_data}')
                r = requests.post(GPT_URL, json=form_data)
                if r.status_code == 200:
                    result_dict = json.loads(r.text)
                    if result_dict.get('status', False):
                        result = result_dict['result']
                        # logger.info(f'result: {result}')
                        finish_reason = result['choices'][0]['finish_reason']
                        answer = result['choices'][0]['message']['content']
                        model = result['model']
                        usage = result['usage']['total_tokens']
                        prompt_tokens = result['usage']['prompt_tokens']
                        completion_tokens = result['usage']['completion_tokens']
                        usage = accounting(model, completion_tokens, prompt_tokens)
                        reply_obj = answer
                        summary = f'<br>应答模型：{model}'
                        summary += f'<br>本次费用估算（人民币）：{usage:.4f}'
                        summary += f'<br>终止状态：{finish_reason}'
                        ret_dict['reply_obj'] = reply_obj
                        ret_dict['summary'] = summary
                        # logger.info(f'reply_obj: {ret_dict}')
                        return render(request, template, ret_dict)
                    else:
                        return HttpResponse(f'服务器返回异常！{result_dict}')
                else:
                    return HttpResponse(f'服务器错误！{r.text}')
                
            else:
                
                return render(request, template, ret_dict)
        else:
            return HttpResponse('您没有访问权限！')
    else:
        return HttpResponseRedirect('/admin/login/?next=/chat/')