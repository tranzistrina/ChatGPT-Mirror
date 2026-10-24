import hashlib
import json
import time

import requests
from requests.exceptions import RequestException
from rest_framework.exceptions import ValidationError

from app.accounts.models import VisitLog
from app.settings import ADMIN_PASSWORD
from app.settings import CHATGPT_GATEWAY_URL


def generate_md5(input_string):
    md5_object = hashlib.md5()
    md5_object.update(input_string.encode('utf-8'))
    return md5_object.hexdigest()

def get_client_ip(request):
    # X-Forwarded-For supplied by an untrusted client is spoofable.
    return request.META.get("REMOTE_ADDR") or "127.0.0.1"

def req_gateway(method, uri, *args, **kwargs):
    url = CHATGPT_GATEWAY_URL + uri
    headers = {
        "Authorization": "Bearer {}".format(ADMIN_PASSWORD),
    }
    try:
        res = requests.request(method, url, headers=headers, *args, timeout=25, **kwargs, allow_redirects=False)
    except RequestException as e:
        raise ValidationError("请求异常, 网关服务未正常启用")

    if res.status_code != 200:
        try:
            err_msg = res.json()
        except:
            err_msg = res.text

        raise ValidationError(err_msg)

    return res.json()


def clean_int_list(data_list):
    if isinstance(data_list, str):
        data_list = json.loads(data_list)

    new_list = []
    for i in data_list:
        if isinstance(i, int):
            new_list.append(i)
        elif isinstance(i, str) and i.isdigit():
            new_list.append(int(i))

    return new_list


def save_visit_log(request, log_type, chatgpt_username=None):

    VisitLog.save_data({
        "ip": get_client_ip(request),
        "log_type": log_type,
        "chatgpt_username": chatgpt_username,
        "username": request.user.username,
        "created_at": int(time.time()),
        "user_agent": request.headers.get('User-Agent'),
    })
