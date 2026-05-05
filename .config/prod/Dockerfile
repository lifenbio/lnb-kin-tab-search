FROM python:3.9.0-alpine

ENV PYTHONUNBUFFERED 1

RUN apk add --no-cache postgresql-dev gcc python3-dev musl-dev
RUN apk add --no-cache tzdata
ENV TZ Asia/Seoul

COPY requirements.txt /requirements.txt

RUN pip install --upgrade pip && pip install -r /requirements.txt

WORKDIR /app

COPY . /app