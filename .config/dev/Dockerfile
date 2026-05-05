FROM python:3.9.0-alpine

ENV PYTHONUNBUFFERED=1

# 필요한 패키지 설치
RUN apk add --no-cache postgresql-dev gcc g++ python3-dev musl-dev
RUN apk add --no-cache tzdata
ENV TZ=Asia/Seoul

# 최신 pip 및 setuptools 설치
RUN pip install --upgrade pip setuptools

# requirements.txt 파일 복사 및 설치
COPY requirements.txt /requirements.txt
RUN pip install -r /requirements.txt

# 작업 디렉토리 설정
WORKDIR /app

# 어플리케이션 파일 복사
COPY . /app