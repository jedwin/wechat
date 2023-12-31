import urllib3
import certifi
import json
import time
import os



errcode_token_expired = 42001
errstring_token_expired = 'access_token expired'

def del_image_data(token, mediaid_list):
    """
    根据media id list删除图片素材
    :return: True/False
    """
    http = urllib3.PoolManager(cert_reqs='CERT_REQUIRED', ca_certs=certifi.where())
    request_url = f'https://api.weixin.qq.com/cgi-bin/material/del_material?access_token={token}'

    # 循环
    for media_id in mediaid_list:
        print(f'deleting {media_id}')
        form_data = f'''{{
                    "media_id":"{media_id}"
                }}'''
        a = http.request('POST', request_url, body=form_data, encode_multipart=False).data.decode('utf-8')
        b = json.loads(a)
        time.sleep(0.5)
        if 'errcode' in b.keys():
            errcode = int(b['errcode'])
            if errcode > 0:
                print(f'删除{media_id}时返回错误: {b}')
        else:
            print(f'返回格式错误: {b}')
            return False
    return True


def get_resource_data(token, media_type):
    """

    :return: resource_dict
    """
    http = urllib3.PoolManager(cert_reqs='CERT_REQUIRED', ca_certs=certifi.where())
    request_url = f'https://api.weixin.qq.com/cgi-bin/material/batchget_material?access_token={token}'
    resource_dict = dict()
    offset = 0

    total_count = get_resource_count(token=token, media_type=f'{media_type}_count')
    if total_count == errstring_token_expired:
        return errstring_token_expired
    elif total_count > 0:
        # 获得图片总数后，进行全量抓取
        while offset <= total_count:
            form_data = f'''{{
                "type":"{media_type}",
                "offset":{offset},
                "count":20
            }}'''
            a = http.request('POST', request_url, body=form_data, encode_multipart=False).data.decode('utf-8')
            b = json.loads(a)
            if 'errcode' in b.keys():
                print(b)
                return False
            else:
                items = b['item']
                item_count = b['item_count']
                if item_count == 0:
                    break
                # print(f'item_count: {item_count}')
                offset += item_count
                # offset += 20
                for item_dict in items:
                    # print(item_dict)
                    media_id = item_dict['media_id']
                    resource_name = item_dict['name']
                    if media_type == 'image':
                        item_url = item_dict['url']
                    elif media_type == 'video':
                        item_url = item_dict['cover_url']
                    if resource_name in resource_dict.keys():
                        # print(f'发现重复名称{resource_name}')
                        pass
                    else:
                        resource_dict[resource_name] = [media_id, item_url]
                time.sleep(0.5)
                print(f'offset: {offset}, len of list:{len(resource_dict)}')
        return resource_dict
    else:
        print(f'failed to get resource list')


def refresh_token(appid, secret, token_file):
    """
    根据appid获取新的access_token
    :return: token
    """

    http = urllib3.PoolManager(cert_reqs='CERT_REQUIRED', ca_certs=certifi.where())
    request_url = f'https://api.weixin.qq.com/cgi-bin/token?grant_type=client_credential&appid={appid}&secret={secret}'
    a = http.request('GET', request_url).data.decode('utf-8')
    b = json.loads(a)
    if 'errcode' in b.keys():
        print(b)
        return False
    else:
        token = b['access_token']
        with open(token_file, 'w') as f:
            f.writelines(token)
        return token


def save_resource_to_json(json_file, resource_dict):
    """
    把获取的图片素材信息存入json文件
    :param json_file:
    :param images_dict:
    :return:
    """
    result = json.dumps(resource_dict, ensure_ascii=False)
    with open(json_file, 'w') as f:
        f.writelines(result)
    return True


def load_resource_from_json(json_file):
    """
    从文件中读取已有的图片素材信息
    :param json_file:
    :return:
    """
    if os.path.exists(json_file):
        with open(json_file, 'r') as f:
            resource_dict = json.loads(''.join(f.readline()))
        if resource_dict:
            return resource_dict
        else:
            print(f'resource_dict is empty after loaded')
    else:
        print(f'json file {json_file} not exists')
        return False


def load_delete_list(delete_list_file, images_dict):
    """
    从文件中读取准备删除的文件名，返回对应的media id列表
    :param images_dict: 
    :param delete_list_file:
    :return:
    """
    media_id_list = list()
    if not images_dict:
        print('image_list is empty')
        return False
    if os.path.exists(delete_list_file):
        with open(delete_list_file, 'r') as f:
            delete_list = [filename.replace('\n', '.jpg') for filename in f.readlines()]
        if delete_list:
            for delete_file in delete_list:
                if delete_file in images_dict.keys():
                    media_id_list.append(images_dict[delete_file][0])
            return media_id_list
        else:
            print('delete_list is empty')
            return False
    else:
        print(f'delete_list_file {delete_list_file} not exists')
        return False


def load_token(token_file):
    """
    从文件中读取已有的token
    :param token_file:
    :return:
    """
    if os.path.exists(token_file):
        with open(token_file, 'r') as f:
            token = f.readline()
        if token:
            return token
    else:
        print(f'token file {token_file} not exists')
        return False


def get_resource_count(token, media_type="image_count"):
    """

    :param token:
    :param meida_type: "voice_count", "video_count","image_count", "news_count"
    :return:
    """
    http = urllib3.PoolManager(cert_reqs='CERT_REQUIRED', ca_certs=certifi.where())
    request_count_url = f'https://api.weixin.qq.com/cgi-bin/material/get_materialcount?access_token={token}'

    # 获取图片总数
    a = http.request('GET', request_count_url).data.decode('utf-8')
    b = json.loads(a)
    if 'errcode' in b.keys():
        if b['errcode'] == errcode_token_expired:   # access_token expired
            return 'access_token expired'
        else:
            print(b)
            return False
    else:
        if media_type in b.keys():
            total_count = b[media_type]
            return total_count
        else:
            print(f'media_type incorrect: {media_type}')
            return False


def update_resource_file(appid, update_image=False, update_video=False):
    """

    :param appid:
    :param update_image:
    :param update_video:
    :return:
    """
    if appid == 'wx1716c53d902498f1':                  # 小瑛看世界
        secret = 'b6d881fce0186db07041d6a7bd3ab7fb'  # 小瑛看世界
    elif appid == 'wxda71a0c759ab5bf9':                    # 小滢同学
        secret = '673c46a8235fd7e4a8604abb130eb792'     # 小滢同学
    elif appid == 'wx4598e8d0ec793d9a':  # 城宝图
        secret = '3f4da0716fc1221e812390e5d5c1905c'  # 城宝图
    else:
        return f'appid {appid} is not correct'

    token_file = f'token_{appid}.txt'
    image_json_file = f'images_{appid}.json'
    video_json_file = f'video_{appid}.json'
    token = load_token(token_file=token_file)
    if not token:
        token = refresh_token(token_file=token_file, appid=appid, secret=secret)
        if not token:
            exit(1)
        else:
            print(f'token refreshed')
    return_string = ''
    if update_image:
        image_dict = get_resource_data(token=token, media_type='image')  # 从网站上更新图片素材
        if image_dict == errstring_token_expired:
            token = refresh_token(token_file=token_file, appid=appid, secret=secret)
            if token:
                # token 文件已更新，直接返回
                return f'token expired, refreshed, please retry\n'
            else:
                return f'!!token refreshed failed!!'
        elif image_dict:
            save_resource_to_json(json_file=image_json_file, resource_dict=image_dict)
            return_string += f'image resource updated: {len(image_dict)}\n'
        else:
            return_string += f'failed to update image resource\n'

    if update_video:
        video_dict = get_resource_data(token=token, media_type='video')  # 从网站上更新视频素材
        if video_dict == errstring_token_expired:
            token = refresh_token(token_file=token_file, appid=appid, secret=secret)
            if token:
                # token 文件已更新，直接返回
                return f'token expired, refreshed, please retry\n'
            else:
                return f'!!token refreshed failed!!'
        elif video_dict:
            save_resource_to_json(json_file=video_json_file, resource_dict=video_dict)
            return_string += f'video resource updated: {len(video_dict)}\n'
        else:
            return_string += f'failed to update image resource\n'
    return return_string


if __name__ == '__main__':
    delete_list_file = 'delete_image.list'
    # appid = 'wx1716c53d902498f1'                  # 小瑛看世界
    # secret = 'b6d881fce0186db07041d6a7bd3ab7fb'   # 小瑛看世界
    appid = 'wxda71a0c759ab5bf9'                    # 小滢同学
    secret = '673c46a8235fd7e4a8604abb130eb792'     # 小滢同学
    # appid = 'wx4598e8d0ec793d9a'                  # 城宝图
    # secret = '3f4da0716fc1221e812390e5d5c1905c'   # 城宝图
    # result = update_resource_file(appid=appid,update_video=True)
    # print(result)
    # resource_types = ['video', 'image']
    token_file = f'token_{appid}.txt'
    image_json_file = f'../images_{appid}.json'
    # video_json_file = f'../video_{appid}.json'
    token = load_token(token_file=token_file)
    if not token:
        token = refresh_token(token_file=token_file, appid=appid, secret=secret)
        if not token:
            exit(1)
        else:
            print(f'token refreshed')
    image_dict = get_resource_data(token=token, media_type='image')     # 从网站上更新图片素材
    # video_dict = get_resource_data(token=token, media_type='video')     # 从网站上更新视频素材
    # # images_dict = load_resource_from_json(json_file=image_json_file)
    # # video_dict = load_resource_from_json(json_file=video_json_file)
    #
    if image_dict == errstring_token_expired:
        print('token expired, refresh')
        token = refresh_token(token_file=token_file, appid=appid, secret=secret)
    elif image_dict:
        # print(f'resource_dict is loaded. {image_dict}')
        save_resource_to_json(json_file=image_json_file, resource_dict=image_dict)
    else:
        print('failed to get_resource_data')
    #
    # if video_dict == errstring_token_expired:
    #     print('token expired, refresh')
    #     token = refresh_token(token_file=token_file, appid=appid, secret=secret)
    # elif video_dict:
    #     # print(f'resource_dict is loaded. {video_dict}')
    #     save_resource_to_json(json_file=video_json_file, resource_dict=video_dict)
    # else:
    #     print('failed to get_resource_data')
    # to_delete_list = load_delete_list(delete_list_file=delete_list_file, images_dict=images_dict)
    # if to_delete_list:
    #     print(f'mediaid_list is loaded. {len(to_delete_list)}')
    #     del_image_data(token=token, mediaid_list=to_delete_list)
