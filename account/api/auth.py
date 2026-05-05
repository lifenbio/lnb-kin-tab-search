import requests
from ninja import Router
from django.contrib.auth.hashers import check_password, make_password
from common.package.schema import (
    NotFoundSchema,
    TokenSchema,
    Message
)
from account.models import (
    Account
)
from account.schema.auth import (
    LoginSchema,
    FindIdSchema,
    FindPWDSchema
)
from common.package.jwt import create_token
from common.package.password import get_random_pwd


auth_router = Router()


@auth_router.post(
    "/login",
    response={
        200: TokenSchema,
        404: NotFoundSchema
    },
    auth=None
)
def login(request, account: LoginSchema):
    try:
        user = Account.objects.get(username=account.dict().get('username'))
        print(user.password)
        print(account.dict().get('password'))
        if not check_password(account.dict().get('password'), user.password):
            return 404, {"message": "비밀번호를 확인해주세요."}
        if not user.is_active:
            return 404, {"message": "탈퇴 계정입니다."}
    except Account.DoesNotExist:
        return 404, {"message": "아이디가 존재하지 않습니다."}

    return 200, {
        "token": create_token(user),
        "id": user.id,
        "username": user.username,
        "name": user.name,
        "type": user.type
    }


@auth_router.post(
    "/find-id",
    response={
        200: Message,
        404: NotFoundSchema
    },
    auth=None
)
def find_id(request, account: FindIdSchema):
    try:
        user = Account.objects.get(
            name=account.dict().get('name'),
            phone_number=account.dict().get('phone_number')
        )

        send_url = 'https://apis.aligo.in/send/'
        sms_data = {
            'key': 'vfctiet3ri9bo368e4qpjmzd32g3fkcd',
            'userid': 'smartfactoria',
            'sender': '01026342202',
            'receiver': account.dict().get('phone_number'),
            "msg": f"서비스 아이디: {user.username}"
        }

        requests.post(send_url, data=sms_data)

        return 200, {
            "message": "입력하신 번호로 아이디를 전송하였습니다."
        }
    except Account.DoesNotExist:
        return 404, {"message": "존재하지 않는 계정 정보 입니다."}


@auth_router.post(
    "/find-pwd",
    response={
        200: Message,
        404: NotFoundSchema
    },
    auth=None
)
def find_pwd(request, account: FindPWDSchema):
    try:
        user = Account.objects.get(
            username=account.dict().get('username'),
            name=account.dict().get('name'),
            phone_number=account.dict().get('phone_number')
        )
        make_pwd = get_random_pwd()
        user.password = make_password(make_pwd)
        user.save()

        send_url = 'https://apis.aligo.in/send/'
        sms_data = {
            'key': 'vfctiet3ri9bo368e4qpjmzd32g3fkcd',
            'userid': 'smartfactoria',
            'sender': '01026342202',
            'receiver': account.dict().get('phone_number'),
            "msg": f"임시 비밀번호: {make_pwd}"
        }

        requests.post(send_url, data=sms_data)

        return 200, {
            "message": "임시 비밀번호를 전송하였습니다."
        }
    except Account.DoesNotExist:
        return 404, {"message": "존재하지 않는 계정 정보 입니다."}
