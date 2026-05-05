import jwt
from typing import Optional
from datetime import datetime, timedelta
from ninja.security import HttpBearer
from django.contrib.auth import get_user_model


SECRET_KEY = '0m-%p7jel*ft3%u5kt1^_dulf_&%78j$=_01w1ik&vb@%x%f93'
ALGORITHM = 'HS256'
User = get_user_model()


class JWTAuth(HttpBearer):
    def authenticate(self, request, token: str):
        try:
            # 토큰에서 payload를 디코딩하고 확인합니다.
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])

            # 페이로드에서 사용자 ID를 가져와 사용자를 검색합니다.
            user_id = payload.get('user_id')
            user = User.objects.get(id=user_id)

            return user
        except (jwt.PyJWTError, User.DoesNotExist):
            # 인증 실패 시 None을 반환합니다.
            return None


def create_token(user):
    # 사용자 ID를 포함한 페이로드를 생성합니다.
    payload = {
        'user_id': user.id,
        'exp': datetime.utcnow() + timedelta(days=1)  # 예: 토큰 만료는 1일 후
    }

    # JWT를 생성하고 반환합니다.
    token = jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)
    return token


def get_authenticated_user(request):
    auth_header = request.headers.get('Authorization')
    user = None
    if auth_header:
        if auth_header.startswith('Bearer '):
            token = auth_header.split('Bearer ')[1]
            custom_auth = JWTAuth()
            user = custom_auth.authenticate(request, token)
    return user
