import boto3
from flask import current_app
from werkzeug.utils import secure_filename
import uuid
import io
from PIL import Image, ImageOps
import os

def get_s3_client():
    return boto3.client('s3',
        region_name=current_app.config['DO_SPACES_REGION'],
        endpoint_url=current_app.config['DO_SPACES_ENDPOINT'],
        aws_access_key_id=current_app.config['DO_SPACES_KEY'],
        aws_secret_access_key=current_app.config['DO_SPACES_SECRET']
    )

def process_image(file, max_width=800, max_height=600, quality=85):
    """
    Process and resize an image while maintaining aspect ratio
    
    Args:
        file: Uploaded file object
        max_width: Maximum width in pixels (default: 800)
        max_height: Maximum height in pixels (default: 600)
        quality: JPEG quality 1-100 (default: 85)
    
    Returns:
        BytesIO object containing the processed image
    """
    try:
        # Open the image
        image = Image.open(file)
        
        # Convert to RGB if necessary (handles RGBA, P, etc.)
        if image.mode in ('RGBA', 'LA', 'P'):
            # Create a white background
            background = Image.new('RGB', image.size, (255, 255, 255))
            if image.mode == 'P':
                image = image.convert('RGBA')
            background.paste(image, mask=image.split()[-1] if image.mode in ('RGBA', 'LA') else None)
            image = background
        elif image.mode != 'RGB':
            image = image.convert('RGB')
        
        # Auto-rotate based on EXIF data
        image = ImageOps.exif_transpose(image)
        
        # Calculate new dimensions while maintaining aspect ratio
        width, height = image.size
        ratio = min(max_width / width, max_height / height)
        
        # Only resize if the image is larger than our maximum dimensions
        if ratio < 1:
            new_width = int(width * ratio)
            new_height = int(height * ratio)
            image = image.resize((new_width, new_height), Image.Resampling.LANCZOS)
        
        # Save to BytesIO
        output = io.BytesIO()
        image.save(output, format='JPEG', quality=quality, optimize=True)
        output.seek(0)
        
        return output
        
    except Exception as e:
        current_app.logger.error(f"Image processing error: {str(e)}")
        # Return original file if processing fails
        file.seek(0)
        return file

def upload_file(file, folder='items', max_width=800, max_height=600, quality=85):
    """
    Upload a file to DigitalOcean Spaces with optional image processing
    
    Args:
        file: Uploaded file object
        folder: Folder in the bucket to upload to (default: 'items')
        max_width: Maximum width for image processing (default: 800)
        max_height: Maximum height for image processing (default: 600)
        quality: JPEG quality for image processing (default: 85)
    
    Returns:
        URL of the uploaded file or None if upload failed
    """
    if not file:
        return None
        
    try:
        filename = secure_filename(file.filename)
        file_ext = os.path.splitext(filename)[1].lower()
        
        # Check if it's an image file
        image_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp'}
        is_image = file_ext in image_extensions
        
        # Generate unique filename
        base_name = os.path.splitext(filename)[0]
        if is_image:
            # Always use .jpg for processed images to ensure consistency
            unique_filename = f"{uuid.uuid4()}-{base_name}.jpg"
        else:
            unique_filename = f"{uuid.uuid4()}-{filename}"
        
        # Process the file
        if is_image:
            processed_file = process_image(file, max_width, max_height, quality)
            content_type = 'image/jpeg'
        else:
            file.seek(0)
            processed_file = file
            content_type = 'application/octet-stream'
        
        # Upload to DigitalOcean Spaces
        s3_client = get_s3_client()
        s3_client.upload_fileobj(
            processed_file,
            current_app.config['DO_SPACES_BUCKET'],
            f'{folder}/{unique_filename}',
            ExtraArgs={
                'ACL': 'public-read',
                'ContentType': content_type
            }
        )
        
        return f"{current_app.config['DO_SPACES_ENDPOINT']}/{current_app.config['DO_SPACES_BUCKET']}/{folder}/{unique_filename}"
    except Exception as e:
        current_app.logger.error(f"Upload error: {str(e)}")
        return None

def upload_profile_image(file):
    """
    Upload a profile image with optimized dimensions for avatars
    
    Args:
        file: Uploaded file object
    
    Returns:
        URL of the uploaded profile image or None if upload failed
    """
    return upload_file(file, folder='profiles', max_width=400, max_height=400, quality=90)

def upload_item_image(file):
    """
    Upload an item image with optimized dimensions for item listings
    
    Args:
        file: Uploaded file object
    
    Returns:
        URL of the uploaded item image or None if upload failed
    """
    return upload_file(file, folder='items', max_width=800, max_height=600, quality=85)

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