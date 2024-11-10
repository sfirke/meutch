import boto3
from flask import current_app
from werkzeug.utils import secure_filename
import uuid

def get_s3_client():
    return boto3.client('s3',
        region_name=current_app.config['DO_SPACES_REGION'],
        endpoint_url=current_app.config['DO_SPACES_ENDPOINT'],
        aws_access_key_id=current_app.config['DO_SPACES_KEY'],
        aws_secret_access_key=current_app.config['DO_SPACES_SECRET']
    )

# app/utils/storage.py
def upload_file(file):
    if not file:
        return None
        
    try:
        filename = secure_filename(file.filename)
        unique_filename = f"{uuid.uuid4()}-{filename}"
        
        s3_client = get_s3_client()
        s3_client.upload_fileobj(
            file,
            current_app.config['DO_SPACES_BUCKET'],
            f'items/{unique_filename}',
            ExtraArgs={'ACL': 'public-read'}
        )
        
        return f"{current_app.config['DO_SPACES_ENDPOINT']}/{current_app.config['DO_SPACES_BUCKET']}/items/{unique_filename}"
    except Exception as e:
        return None

def delete_file(url):
    if not url:
        return
        
    try:
        key = url.split('/')[-2] + '/' + url.split('/')[-1]
        s3_client = get_s3_client()
        s3_client.delete_object(
            Bucket=current_app.config['DO_SPACES_BUCKET'],
            Key=key
        )
    except Exception as e:
        current_app.logger.error(f"Delete error: {str(e)}")