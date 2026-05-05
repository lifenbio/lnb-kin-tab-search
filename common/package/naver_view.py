import os
import pandas as pd
import requests
import time
import hashlib
import hmac
import base64


NAVER_AD_BASE_URL = os.environ.get('NAVER_AD_BASE_URL', 'https://api.naver.com')  # 시크릿 아님
NAVER_AD_API_KEY = os.environ['NAVER_AD_API_KEY']
NAVER_AD_SECRET_KEY = os.environ['NAVER_AD_SECRET_KEY']
NAVER_AD_CUSTOMER_ID = os.environ['NAVER_AD_CUSTOMER_ID']


class Signature:
    @staticmethod
    def generate(timestamp, method, uri, secret_key):
        message = "{}.{}.{}".format(timestamp, method, uri)
        hash = hmac.new(bytes(secret_key, "utf-8"), bytes(message, "utf-8"), hashlib.sha256)

        hash.hexdigest()
        return base64.b64encode(hash.digest())


def get_header(method, uri, api_key, secret_key, customer_id):
    timestamp = str(round(time.time() * 1000))
    signature = Signature.generate(timestamp, method, uri, secret_key)

    return {'Content-Type': 'application/json; charset=UTF-8', 'X-Timestamp': timestamp,
            'X-API-KEY': api_key, 'X-Customer': str(customer_id), 'X-Signature': signature}


def get_view_data(query):
    uri = '/keywordstool'
    method = 'GET'

    params = {}
    params['hintKeywords'] = query.replace(" ", "")
    params['showDetail'] = '1'

    r = requests.get(
        NAVER_AD_BASE_URL + uri,
        params=params,
        headers=get_header(method, uri, NAVER_AD_API_KEY, NAVER_AD_SECRET_KEY, NAVER_AD_CUSTOMER_ID),
    )

    if r.status_code == 200:
        resultdf = pd.DataFrame(r.json()['keywordList'])
        pc_view = resultdf.loc[0,:]['monthlyPcQcCnt']
        mobile_view = resultdf.loc[0,:]['monthlyMobileQcCnt']

        if isinstance(pc_view, str):
            pc_view = pc_view.replace('<', '')
            pc_view = pc_view.replace(' ', '')
        if isinstance(mobile_view, str):
            mobile_view = mobile_view.replace('<', '')
            mobile_view = mobile_view.replace(' ', '')
        
        return pc_view, mobile_view
    else:
        return 0, 0
