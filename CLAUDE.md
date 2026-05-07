# kin-tab (lifenbio_in 코드) — 운영 가이드

라바 지식인 통검 크롤링 + 일별 결과 메일/엑셀 송출 시스템. 옛 `lifenbio_in` 코드를 2026-05-06 에 lnb-cdk 패턴으로 EC2/인프라 교체 완료. 본 문서는 다음 세션·후임자가 빠르게 컨텍스트 회복하기 위한 운영 핵심.

---

## 인프라 토폴로지

```
[새 EC2  43.201.249.37 (CrawlingKinTabStack/Server0, t3.medium, AL2023)]
  ├─ docker-compose.prod.yml (5 컨테이너)
  │   ├─ web (uvicorn :8000)
  │   ├─ celery_beat (한국 0/14/21시 cron)
  │   ├─ celery_worker
  │   ├─ redis :6379
  │   └─ flower :5555
  ├─ IAM Role: crawl-kin-tab-ec2-role (SSM read + S3 daily-excel-data RW)
  └─ /usr/local/bin/refresh-env (없음 — 첫 부팅 git clone 실패로 대체 스크립트 /tmp/finish-userdata.sh 사용)

[VPC peering pcx-0b7fa0b5cfe4e21a0]
  kin-tab VPC (10.0.0.0/16) ↔ default VPC (172.31.0.0/16)
  양쪽 DNS resolution 활성, 양쪽 route table 5+2 갱신, RDS SG cross-VPC inbound

[운영 RDS database-1.c7s088s44kme.ap-northeast-2.rds.amazonaws.com]
  default VPC, postgres DB, ~20K daily_result row/day, 누적 2.7M+ row
  SG: sg-00a25da86151d7935 (새 EC2 SG sg-0be09a929879edee5 인바운드 5432)

[S3 daily-excel-data]
  YYYY-MM-DD.xlsx 매일 14시 cron 이 PUT
  ⚠️ Versioning 비활성 — 실수로 덮어쓰면 복원 불가. 테스트 전에 다른 버킷 쓸 것

[GitHub]
  코드 repo:        https://github.com/lifenbio/lnb-kin-tab-search (public, main)
  CDK repo:         https://github.com/lifenbio/lnb-cdk (private, CrawlingKinTabStack)
  옛 private repo:  youngmany/lifenbio_in (archive 권장 — git history 에 자격증명 노출)

[SSM Parameter Store /crawling/kin-tab/*]
  SECRET_KEY, SQL_PASSWORD, EMAIL_HOST_USER, EMAIL_HOST_PASSWORD,
  NAVER_AD_API_KEY, NAVER_AD_SECRET_KEY, NAVER_AD_CUSTOMER_ID,
  AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY,
  DAILY_EXCEL_RECIPIENTS, DETAIL_VIEW_RECIPIENTS,
  SQL_HOST_OVERRIDE  ← 컷오버 신호 (있으면 .env.prod 끝에 SQL_HOST=값 append)
```

키페어: `crawling-keypair`. 로컬 키 파일: `~/.ssh/crawling-keypair.pem` (chmod 400)

---

## 자주 쓰는 운영 명령

### SSH 접속
```bash
ssh -i ~/.ssh/crawling-keypair.pem ec2-user@43.201.249.37
```

### 컨테이너 상태 / 로그
```bash
ssh -i ~/.ssh/crawling-keypair.pem ec2-user@43.201.249.37 \
  'cd /app && sudo docker-compose -f docker-compose.prod.yml ps'

# celery_beat 스케줄 발동 로그
sudo docker logs app-celery_beat-1 2>&1 | tail -30

# celery_worker task 실행/에러
sudo docker logs app-celery_worker-1 2>&1 | tail -30
```

### 코드 변경 배포
```bash
# 로컬: lifenbio_in 작업 → /tmp/kin_tab_push 로 sync → push
rsync -a --delete --exclude='.git' --exclude='.env.dev' --exclude='.env.prod' \
  --exclude='__pycache__' --exclude='*.pyc' --exclude='celerybeat-schedule' \
  --exclude='db.sqlite3' \
  /Users/youngmany/LNB/lifenbio_in/ /tmp/kin_tab_push/
cd /tmp/kin_tab_push && git add -A && git commit -m "..." && git push origin main

# EC2: pull + restart
ssh -i ~/.ssh/crawling-keypair.pem ec2-user@43.201.249.37 \
  'cd /app && sudo git pull origin main && sudo docker-compose -f docker-compose.prod.yml restart app celery_worker celery_beat'
```

### SSM 시크릿 변경 + 적용
```bash
aws ssm put-parameter --region ap-northeast-2 --type SecureString --overwrite \
  --name "/crawling/kin-tab/<KEY>" --value "<value>"

# .env.prod 재구성 + docker-compose 재기동
ssh -i ~/.ssh/crawling-keypair.pem ec2-user@43.201.249.37 \
  'sudo bash /tmp/finish-userdata.sh'
```

### 14시 cron 이 시간 안에 못 끝났을 때 — 수동 보충 발사

증상: 14시 자사송출 결과 메일에 row 가 평소보다 적음 / S3 `YYYY-MM-DD.xlsx` 가 2MB 미만.

원인: 0시 cron 의 ~6,700 키워드 처리가 14시간 안에 못 끝남 (새 EC2 IP 가 naver 에서 throttle, VPC peering RTT 등).

해결: `prev_map` 으로 캐시 빌드 + S3 PUT + 운영 4명에게 메일 (build_daily_excel 의 mail 포함 동일 흐름):

```python
ssh -i ~/.ssh/crawling-keypair.pem ec2-user@43.201.249.37
cd /app && sudo docker-compose -f docker-compose.prod.yml exec -T app python manage.py shell << 'PYEOF'
from datetime import date, timedelta
from io import BytesIO
import pandas as pd
from common.models import DailyResult
from common.package.storage import s3_client
from common.package.mail import send

target = date(YYYY, MM, DD)  # ⭐ 보충 대상 일자
prev = target - timedelta(days=1)

prev_map = {}
for r in DailyResult.objects.filter(created_dt__date=prev).only("url","keyword","transmission_url_views"):
    prev_map[(r.url, r.keyword)] = r.transmission_url_views or ""

columns = ["수집월","수집월일","키워드제품명","매칭키워드","검색어","우선순위","조회수P","조회수M",
           "영역순위","순위","ID","송출유무","질문일자","종류","URL제품명","전환키워드",
           "원고형태","발행키워드","서브유무","URL","상세 조회수","댓글수","증가량"]
data = []
qs = DailyResult.objects.filter(created_dt__date=target).values(
    "created_dt__month","created_dt","keyword_product","keyword","priority",
    "pc_views","mobile_views","area_ranking","ranking","name","is_transmission",
    "question_date","type","url_product","conversion_keyword","manuscript_form",
    "publication_keyword","is_subkeyword","url","transmission_url_views","transmission_url_comment_cnt")

for row in qs:
    cm = row["created_dt"].strftime("%Y-%m"); cmd = row["created_dt"].strftime("%Y-%m-%d")
    qd = row["question_date"]
    if "주" in qd:
        try: qd = (row["created_dt"] - timedelta(weeks=int(qd.replace(" ","").replace("주","").replace("전","")))).strftime("%Y-%m-%d")
        except: pass
    elif "일" in qd:
        try: qd = (row["created_dt"] - timedelta(days=int(qd.replace(" ","").replace("일","").replace("전","")))).strftime("%Y-%m-%d")
        except: pass
    diff = 0
    try:
        if row["is_transmission"] and len(row["transmission_url_views"]) >= 1:
            pv = prev_map.get((row["url"], row["keyword"]), "")
            if pv:
                diff = int(row["transmission_url_views"].replace(",","")) - int(pv.replace(",",""))
    except ValueError:
        diff = 0
    data.append([cm, cmd, row["keyword_product"], row["keyword"].replace(" ",""), row["keyword"], row["priority"],
                 row["pc_views"], row["mobile_views"], row["area_ranking"], row["ranking"], row["name"],
                 "1" if row["is_transmission"] else "0", qd, row["type"], row["url_product"],
                 row["conversion_keyword"], row["manuscript_form"], row["publication_keyword"],
                 "1" if row["is_subkeyword"] else "0", row["url"],
                 (row["transmission_url_views"] or "").replace(",",""), row["transmission_url_comment_cnt"], diff])

df = pd.DataFrame(data, columns=columns)
buf = BytesIO(); df.to_excel(buf, index=False); buf.seek(0)
key = f"{target}.xlsx"
s3_client.put(key=key, excel_buffer=buf.getvalue())

send(
    f"[지식인] 자사송출 결과 ({target} 보충)",
    "자사송출 결과 — cron 처리 시간 부족으로 14시 메일이 부분 데이터였던 분 보충",
    to=["sh.hwang@lifenbio.com","jhyjhy@lifenbio.com","chano94@lifenbio.com","min4397@naver.com"],
    cc=[],
    files=[("result.xlsx", buf.getvalue(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")]
)
PYEOF
```

### 부분 검증 (디버그 트리거)

`base_data.py /test-*` 엔드포인트는 운영 cron 과 동일 로직을 부분 실행:

```bash
# limit=N 으로 처음 N개 키워드만 (cron 0시 task 검증)
curl 'http://43.201.249.37:8000/api/common/base/test-collect?limit=10'

# limit=N row 만 (cron 21시 task 검증, 메일 발사)
curl 'http://43.201.249.37:8000/api/common/base/test-detail-page?limit=10'

# 특정 일자 엑셀 + S3 + 메일 (cron 14시 task 동일)
# ⚠️ S3 daily-excel-data/YYYY-MM-DD.xlsx 를 OVERWRITE 함. 운영 일자에는 신중!
curl "http://43.201.249.37:8000/api/common/base/test-result?date=YYYY-MM-DD"
```

⚠️ **`/test-result?date=오늘` 호출 시 prod S3 파일 덮어씀** — 5/6 에 실수로 그렇게 한 사고 있음. 보충 발사가 필요한 경우 위의 수동 inline script 사용 (S3 prod 파일과 RDS 에서 정확한 재생성).

---

## 코드 구조 + 설계 결정

### 주요 파일
- `common/services/naver_in.py` — 운영 cron 의 본체 (collect_daily_kin / build_daily_excel / collect_detail_view)
- `common/tasks.py` — `@shared_task` 3종 wrapper (cron 진입점)
- `common/api/base_data.py` — 업로드 (`/keyword`, `/url`, `/new/url`) + 디버그 (`/test-*`)
- `main/celery.py` — beat schedule (한국 0/14/21시)

### 회귀 안전 기준 (절대 양보 금지)
**`tasks.py` 의 매일 cron 산출물 (메일·S3 엑셀·DailyResult row) 이 리팩토링 전후 동일** 이게 유일한 회귀 기준. 다른 곳 (`/test-*`, admin 화면, 죽은 라우터) 변경은 회귀 아님.

회귀 검증 절차:
1. 직전 일자 daily 엑셀 + DailyResult row 베이스라인
2. 변경 후 같은 입력 재현 → `pandas.testing.assert_frame_equal`
3. prod 배포 후 다음 cron 산출물 24-72h 모니터링

### 시크릿
- `main/settings/base.py` 의 시크릿은 모두 `os.environ['KEY']` (fallback 없음 — env 누락 시 즉시 실패).
- `common/package/naver_view.py` 의 네이버 광고 API 키도 동일.
- `.env.dev`, `.env.prod` 는 git 추적 안 됨 (`.gitignore`).
- 운영 자격증명은 SSM 에서 UserData 가 fetch → `.env.prod` 생성.

### 무한루프 방어
원본의 `while True` 5개를 `_fetch_with_retry(max_attempts=60)` / `_get_view_with_retry(max_attempts=20)` 로 대체. 정상 케이스 동작 동일, 한도 초과 시 `CrawlFailure` → outer try/except 가 잡음.

### find_matching_data 캐싱 (2026-05-07 추가)
0시 cron 처리 속도 개선. `collect_daily_kin` 시작 시 `_build_siu_cache()` 1회 호출 → `(dirId, docId) → SIU row` dict. 매 row 의 LIKE 쿼리 (cross-VPC peering RTT 동반) 제거. 14,807 row 전체에서 DB filter 결과와 mismatch=0 입증. cache build 도 outer try 안에서 호출되어 RDS 일시 문제 시 graceful exit.

### SMS 코드 모두 제거
2026-05-06 사용자 요청. `services/naver_in.py` 의 `send_sms` 호출 제거, `common/package/sms.py` 모듈 삭제, `base_data.py` import 제거.

---

## 알려진 이슈 + 대응

| 이슈 | 증상 | 대응 |
|---|---|---|
| **0시 cron 14시간 초과** | 14시 cron 메일이 부분 데이터로 발사 | 위의 "수동 보충 발사" — 운영 RDS 의 완전 데이터로 재생성 + 메일 |
| **S3 versioning 비활성** | 실수로 PUT 시 prior 버전 복원 불가 | 운영 일자에 `/test-result` 호출 금지. 보충은 inline script. |
| **S3 prod 버킷 = 테스트와 공용** | `s3BucketName: 'daily-excel-data'` 가 prod S3 직접 사용 | 향후 `daily-excel-data-test` 별도 버킷 검토 |
| **새 EC2 IP 가 Naver 에서 throttle** | 503 응답 → retry sleep 누적 → 0시 cron 처리 속도 저하 | 시간 흐르며 자연 개선 기대. 또는 별도 proxy. |
| **옛 EC2 SMTP 비번 거부** | 옛 비번 `WKEHDGHK123` 가 535 거부 (언제부터인지 불명) | 새 비번 `MLTH7F16UC7P` 발급 + SSM 등록 (5/6 완료) |
| **`/usr/local/bin/refresh-env` 미설치** | UserData 가 git clone 실패로 그 단계 못 거침 | `/tmp/finish-userdata.sh` 가 동등 역할. EC2 재기동 시 사용. 향후 정상 UserData 재실행 또는 install 필요. |

---

## 컷오버 history (참고)

- **2026-05-06 12:30 UTC** `cdk deploy CrawlingKinTabStack` — 새 EC2 + fresh test RDS 생성
- **2026-05-06 13:48 UTC** `/test-collect`/`/test-detail-page`/`/test-result` 검증. SMTP 통과. **(주의) S3 5/6 prod 덮어씀** — 8KB 짜리 테스트 데이터로
- **2026-05-06 14:00 UTC** 옛 EC2 14시 cron 정상 시간이지만 SMTP 535 거부로 메일 안 감
- **2026-05-06 ~13-14 UTC** VPC peering 생성 + route + RDS SG inbound. cross-VPC TCP 5432 통과 검증
- **2026-05-06 14:00 UTC** SSM `SQL_HOST_OVERRIDE` = 운영 RDS endpoint 등록 + recipients 운영 명단으로 갱신 + `finish-userdata.sh` 재실행 + 옛 EC2 celery_beat stop
- **2026-05-06 22:?? UTC** 옛 EC2 (`i-0e7b3a36a8601ef6f`) terminated, 테스트 RDS 삭제
- **2026-05-06 08:07 UTC** 보충 발사로 5/6 S3 정상 (1,978,755 bytes) + 메일 4명
- **2026-05-07** 새 EC2 의 첫 cron — 0시 cron 이 18시간 넘어도 진행 중 → 14시 cron 부분 데이터. 보충 발사
- **2026-05-07** `find_matching_data` pre-cache 최적화 push + 적용. 5/8 0시 cron 부터 효과 적용

---

## 주요 식별자 (메모용)

| 자원 | ID/endpoint |
|---|---|
| 새 EC2 | `i-...` (terminate 안 함 — VPC peering 의존) Public IP `43.201.249.37` |
| 운영 RDS | `database-1.c7s088s44kme.ap-northeast-2.rds.amazonaws.com` |
| VPC peering | `pcx-0b7fa0b5cfe4e21a0` |
| kin-tab VPC | `vpc-076e1a8031f010d44` (10.0.0.0/16) |
| default VPC | `vpc-04e2c002dd0881050` (172.31.0.0/16) |
| 새 EC2 SG | `sg-0be09a929879edee5` (crawl-kin-tab-ec2-sg) |
| 운영 RDS SG | `sg-00a25da86151d7935` |
| AWS Account | `211125385464` |
| Region | `ap-northeast-2` |

## 후속 작업 (미해결)

- **자격증명 회전** — AWS IAM 키, 네이버 광고 API, RDS 비번. 옛 git history 에 노출분. 동작 영향 0 이지만 보안 best practice.
- **CDK 의 RDS drift 정리** — 테스트 RDS 가 직접 삭제됐는데 stack 의 RDS 리소스는 남아 있음. `skipRdsCreation: true` 로 토글하면 깨끗.
- **옛 private repo `youngmany/lifenbio_in`** archive 또는 삭제.
