from django.db import models

class BaseModel(models.Model):
    created_dt = models.DateTimeField(auto_now_add=True, verbose_name='생성(등록)일시')
    
    class Meta:
        abstract = True
