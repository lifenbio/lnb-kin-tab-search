## 사용방법

### 로컬 개발환경

```
도커 설치
https://hub.docker.com/editions/community/docker-ce-desktop-mac
(M1이면 apple chip, 아니면 intel chip)

컴포즈 실행 및 migration, create superuser
docker-compose up -d --build
docker-compose exec web python manage.py makemigrations
docker-compose exec web python manage.py migrate
docker-compose -f docker-compose.prod.yml exec web python manage.py createsuperuser
```

### 배포 환경

도커 설치 (추후 하기 작성 명령어 스크립트 처리 예정)

```
오래된 도커 버전이 있을시 삭제
sudo apt-get remove docker docker-engine docker.io

설치에 필요한 패키지 설치
sudo apt-get update && sudo apt-get install \
    apt-transport-https \
    ca-certificates \
    curl \
    software-properties-common

패키지 저장소 추가
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo apt-key add -
sudo add-apt-repository \
   "deb [arch=amd64] https://download.docker.com/linux/ubuntu \
   $(lsb_release -cs) \
   stable"

아래 명령어를 통해 docker 패키지 검색 되는지 확인
sudo apt-get update && sudo apt-cache search docker-ce

도커 CE 설치
sudo apt-get update && sudo apt-get install docker-ce

도커 컴포즈 설치
sudo apt-get install docker-compose
```

컴포즈 실행 및 마이그레이션, collectstatic, create superuser

```
docker-compose -f docker-compose.prod.yml up -d --build
docker-compose -f docker-compose.prod.yml exec web python manage.py makemigrations
docker-compose -f docker-compose.prod.yml exec web python manage.py migrate
docker-compose -f docker-compose.prod.yml exec web python manage.py collectstatic
docker-compose -f docker-compose.prod.yml exec web python manage.py createsuperuser
```

## 설정방법

`settings` 폴더에는 `base.py`, `dev.py`, `prod.py` 이렇게 세 가지의 파일이 있습니다.  
`base.py` 는 기본 설정 파일입니다.  
`dev.py` 에는 로컬 환경 혹은 개발 시 환경에 대한 설정을 추가하시면 됩니다. 가령, `DEBUG=True` 같은 설정들은 `dev.py` 에서만 활성화되어야 합니다.  
`prod.py` 에는 실제 서비스 환경에서의 설정을 추가하시면 됩니다. 가령, 데이터베이스 설정값이 담긴 환경변수들을 여기서 포함하시면 됩니다.


## License
MIT