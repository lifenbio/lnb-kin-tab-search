import boto3
from django.core.files.storage import default_storage
from main.settings.base import (
    AWS_ACCESS_KEY_ID,
    AWS_SECRET_ACCESS_KEY,
    AWS_STORAGE_BUCKET_NAME
)


def generate_url(file_path):
    return default_storage.url(file_path)


class S3Client():
    def __init__(self):
        self.s3 = boto3.client(
            's3',
            aws_access_key_id=AWS_ACCESS_KEY_ID,
            aws_secret_access_key=AWS_SECRET_ACCESS_KEY
        )
        self.bucket_name = AWS_STORAGE_BUCKET_NAME
    
    def upload(self, file, file_name):
        try:
            extra_args = { 'ContentType': file.content_type }

            self.s3.upload_fileobj(
                file,
                self.bucket_name,
                file_name,
                ExtraArgs=extra_args
            )
        except:
            return None
    
    def put(self, key, excel_buffer):
        self.s3.put_object(
            Bucket=AWS_STORAGE_BUCKET_NAME,
            Key=key,
            Body=excel_buffer
        )

    def delete(self, file_name):
        self.s3.delete_object(
            Bucket=self.bucket_name,
            Key=file_name
        )
    
    def get_s3_url(self, key):
        return f"https://{AWS_STORAGE_BUCKET_NAME}.s3.amazonaws.com/{key}"

    

s3_client = S3Client()
