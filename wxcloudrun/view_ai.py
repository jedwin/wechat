import json
from django.shortcuts import HttpResponse, render, HttpResponseRedirect
import requests
import os
from logging import getLogger
from wxcloudrun.common_functions import *
from cryptography.hazmat.primitives.serialization import PublicFormat, Encoding

import base64

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
    if request.method == 'POST':
        question = request.POST.get('question', '')
        character = request.POST.get('character', '')
        encrypted_msg = request.POST.get('encrypted_msg', '')
        csrf_token = request.POST.get('csrfmiddlewaretoken')
        encrypted_key = request.POST.get('encrypted_key', '')
        encrypted_iv = request.POST.get('encrypted_iv', '')
    elif request.method == 'GET':
        question = ''
        character = ''
        encrypted_msg = ''
        encrypted_key = ''
        encrypted_iv = ''

    else:
        return HttpResponse('request method error!')
    public_key = load_public_key('public_key.pem')
    ret_dict = dict()
    ret_dict['home_server'] = HOME_SERVER
    ret_dict['chosen_character'] = ''
    # ret_dict['public_key'] = public_key.public_bytes(encoding=Encoding.PEM, format=PublicFormat.SubjectPublicKeyInfo).decode('utf-8')
    if user.is_authenticated:
        if 'GPT' in user.groups.values_list('name', flat=True):
            template = 'wechat_chat.html'
            
            if encrypted_msg != '':
                reply_string = ''
                # try:
                private_key = load_private_key('private_key.pem')
                # reply_string += f'加载私钥成功！<br>'
                decrypted_key_dict = json.loads(decrypt_message(private_key=private_key, encrypted_message=encrypted_key))
                decrypted_key = decode_base64url(decrypted_key_dict['k'])
                # reply_string += f'解密key成功！{decrypted_key.hex()}<br>'
                decrypted_iv = decrypt_message(private_key=private_key, encrypted_message=encrypted_iv)
                decrypted_iv = base64_to_bytes(decrypted_iv)
                # reply_string += f'解密iv成功！{decrypted_iv.hex()}<br>'
                encrypted_msg = base64.b64decode(encrypted_msg)
                # reply_string += f'收到的加密信息：{encrypted_msg.hex()}<br>'
                question = decrypt_aes_gcm(encrypted_data=encrypted_msg, key=decrypted_key, iv=decrypted_iv)
                # ret_dict = get_gpt3_response(question=question, character=character)

                ciphertext, tag = encrypt_aes(plaintext='测试', key=decrypted_key, iv=decrypted_iv)
                ret_dict['encrypted_msg'] = base64.b64encode(ciphertext+tag).decode('utf-8')
                ret_dict['reply_obj'] = ''
                return render(request, template, ret_dict)
                # except Exception as e:
                #     reply_string += f'解密失败！{e}'
                #     ret_dict['reply_obj'] = reply_string
                #     return render(request, template, ret_dict)
            else:
                
                return render(request, template, ret_dict)
        else:
            return HttpResponse('您没有访问权限！')
    else:
        return HttpResponseRedirect('/admin/login/?next=/chat/')