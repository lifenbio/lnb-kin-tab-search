FROM python:3.9-alpine

ENV PYTHONUNBUFFERED=1

# 빌드 의존성: postgres + 컴파일러 + cmake/make (pandas/numpy musllinux wheel 미지원 시 source build 대비)
RUN apk add --no-cache \
    postgresql-dev \
    gcc \
    g++ \
    python3-dev \
    musl-dev \
    cmake \
    make \
    linux-headers \
    openblas-dev \
    gfortran \
    tzdata
ENV TZ=Asia/Seoul

# 최신 pip + wheel 도구로 prebuilt wheel 활용 극대화
RUN pip install --upgrade pip setuptools wheel

COPY requirements.txt /requirements.txt
RUN pip install -r /requirements.txt

WORKDIR /app
COPY . /app
