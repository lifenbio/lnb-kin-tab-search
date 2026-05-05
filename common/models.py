from django.db import models


class BaseModel(models.Model):
    created_dt = models.DateTimeField(auto_now_add=True, verbose_name='생성(등록)일시')
    
    class Meta:
        abstract = True


################################################################################################################
# 기준정보 지식인
################################################################################################################
class StandardInformationKeyword(BaseModel):
    product = models.CharField(max_length=256, default='', verbose_name='제품')
    keyword = models.CharField(max_length=256, default='', verbose_name='키워드')
    priority = models.CharField(max_length=256, default='', verbose_name='우선순위')

    class Meta:
        db_table = 'standard_information_keyword'
        verbose_name = '기준정보 키워드'


class StandardInformationURL(BaseModel):
    url = models.CharField(max_length=256, default='', verbose_name='url')
    product = models.CharField(max_length=256, default='', verbose_name='제품')
    conversion_keyword = models.CharField(max_length=256, default='', verbose_name='전환 키워드')
    manuscript_form = models.CharField(max_length=256, default='', verbose_name='원고 형태')
    publication_keyword = models.CharField(max_length=256, default='', verbose_name='발행 키워드')

    class Meta:
        db_table = 'standard_information_url'
        verbose_name = '기준정보 URL'


class DailyResult(BaseModel):
    # 키워드 영역
    keyword_product = models.CharField(max_length=256, default='', verbose_name='제품(키워드 파일)')
    keyword = models.CharField(max_length=256, default='', verbose_name='키워드')
    priority = models.CharField(max_length=256, default='', verbose_name='우선순위')

    # URL 영역
    url = models.CharField(max_length=256, default='', verbose_name='url')
    url_product = models.CharField(max_length=256, default='', verbose_name='제품(URL 파일)')
    conversion_keyword = models.CharField(max_length=256, default='', verbose_name='전환 키워드')
    manuscript_form = models.CharField(max_length=256, default='', verbose_name='원고 형태')
    publication_keyword = models.CharField(max_length=256, default='', verbose_name='발행 키워드')

    transmission_url_date = models.CharField(max_length=256, default='', verbose_name='송출된 URL 상세 작성일')
    transmission_url_views = models.CharField(max_length=256, default='', verbose_name='송출된 URL 상세 조회수')
    transmission_url_comment_cnt = models.CharField(max_length=256, default='', verbose_name='송출된 URL 상세 조회수')

    pc_views = models.CharField(max_length=256, default='', verbose_name='조회수(PC)')
    mobile_views = models.CharField(max_length=256, default='', verbose_name='조회수(Mobile)')

    area_ranking = models.IntegerField(default=0, verbose_name='영역 순위')

    ranking = models.IntegerField(default=0, verbose_name='순위')
    name = models.CharField(max_length=256, default='', verbose_name='ID(답변인 이름)')
    is_transmission = models.BooleanField(default=False, verbose_name='송출 유무')

    #question_date = models.DateTimeField(null=True, blank=True, verbose_name='질문일자')
    question_date = models.CharField(max_length=256, default='', verbose_name='질문일자')
    type = models.CharField(max_length=256, default='', verbose_name='종류')
    is_subkeyword = models.BooleanField(default=False, verbose_name='서브키워드 유무')

    class Meta:
        db_table = 'daily_result'
        verbose_name = '일일 결과'
        indexes = [
            models.Index(fields=['created_dt']),
            models.Index(fields=['question_date']),
        ]


class INURLDetailViewCounter(BaseModel):
    product = models.CharField(max_length=256, default='', verbose_name='제품')
    keyword = models.CharField(max_length=256, default='', verbose_name='키워드')
    url = models.CharField(max_length=256, default='', verbose_name='URL')
    answer_code = models.CharField(max_length=256, default='', verbose_name='답변코드')

    class Meta:
        db_table = 'in_url_detail_view_counter'
        verbose_name = '지식인 조회수'