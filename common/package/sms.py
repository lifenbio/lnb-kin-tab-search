import requests


def send_sms(receiver, msg):
    send_url = 'https://apis.aligo.in/send/'
    sms_data = {
        'key': 'lo6fcn5vlcv3bx16hjo7wgzm64xpe8er',
        'userid': 'youngmany',
        'sender': '01088876675',
        'receiver': receiver,
        "msg": msg
    }
    
    requests.post(send_url, data=sms_data)
