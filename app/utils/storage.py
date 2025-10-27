import boto3
from flask import current_app, url_for
from werkzeug.utils import secure_filename
import uuid
import io
from PIL import Image, ImageOps
import os
from abc import ABC, abstractmethod


class StorageBackend(ABC):
    """Abstract base class for file storage backends."""
    
    @abstractmethod
    def upload(self, file_obj, folder, filename):
        """
        Upload a file to storage.
        
        Args:
            file_obj: File-like object to upload
            folder: Folder/prefix to store the file in
            filename: Name of the file
            
        Returns:
            URL of the uploaded file or None on failure
        """
        pass
    
    @abstractmethod
    def delete(self, url):
        """
        Delete a file from storage.
        
        Args:
            url: URL of the file to delete
        """
        pass


class LocalFileStorage(StorageBackend):
    """Local file storage backend for development."""
    
    def __init__(self, upload_folder='app/static/uploads'):
        self.upload_folder = upload_folder
        # Ensure the base upload folder exists
        os.makedirs(upload_folder, exist_ok=True)
    
    def upload(self, file_obj, folder, filename):
        """Upload a file to local storage."""
        try:
            # Create folder if it doesn't exist
            folder_path = os.path.join(self.upload_folder, folder)
            os.makedirs(folder_path, exist_ok=True)
            
            # Save the file
            file_path = os.path.join(folder_path, filename)
            file_obj.seek(0)
            with open(file_path, 'wb') as f:
                f.write(file_obj.read())
            
            # Return URL path (relative to static folder)
            return url_for('static', filename=f'uploads/{folder}/{filename}', _external=True)
        except Exception as e:
            current_app.logger.error(f"Local storage upload error: {str(e)}")
            return None
    
    def delete(self, url):
        """Delete a file from local storage."""
        try:
            # Extract the path from the URL
            # URL format: http://localhost:5000/static/uploads/folder/filename.jpg
            if '/static/uploads/' in url:
                rel_path = url.split('/static/uploads/')[-1]
                file_path = os.path.join(self.upload_folder, rel_path)
                
                if os.path.exists(file_path):
                    os.remove(file_path)
                    current_app.logger.info(f"Deleted file: {file_path}")
        except Exception as e:
            current_app.logger.error(f"Local storage delete error: {str(e)}")


class DOSpacesStorage(StorageBackend):
    """DigitalOcean Spaces storage backend for production."""
    
    def __init__(self, region, key, secret, bucket):
        self.region = region
        self.endpoint = f'https://{region}.cdn.digitaloceanspaces.com'
        self.key = key
        self.secret = secret
        self.bucket = bucket
    
    def _get_client(self):
        """Get boto3 S3 client configured for DigitalOcean Spaces."""
        return boto3.client('s3',
            region_name=self.region,
            endpoint_url=self.endpoint,
            aws_access_key_id=self.key,
            aws_secret_access_key=self.secret
        )
    
    def upload(self, file_obj, folder, filename):
        """Upload a file to DigitalOcean Spaces."""
        try:
            s3_client = self._get_client()
            s3_client.upload_fileobj(
                file_obj,
                self.bucket,
                f'{folder}/{filename}',
                ExtraArgs={
                    'ACL': 'public-read',
                    # All uploads are images converted to JPEG by process_image()
                    'ContentType': 'image/jpeg'
                }
            )
            return f"{self.endpoint}/{self.bucket}/{folder}/{filename}"
        except Exception as e:
            current_app.logger.error(f"DO Spaces upload error: {str(e)}")
            return None
    
    def delete(self, url):
        """Delete a file from DigitalOcean Spaces."""
        if not url:
            return
        
        try:
            key = url.split('/')[-2] + '/' + url.split('/')[-1]
            s3_client = self._get_client()
            s3_client.delete_object(
                Bucket=self.bucket,
                Key=key
            )
        except Exception as e:
            current_app.logger.error(f"DO Spaces delete error: {str(e)}")


def get_storage_backend():
    """
    Get the appropriate storage backend based on configuration.
    
    Returns LocalFileStorage for development or when DO Spaces credentials
    are not configured. Returns DOSpacesStorage for production.
    """
    # Check if we should use local storage
    use_local = current_app.config.get('USE_LOCAL_STORAGE', False)
    
    # If not explicitly set to use local storage, check if DO Spaces is configured
    if not use_local:
        region = current_app.config.get('DO_SPACES_REGION')
        key = current_app.config.get('DO_SPACES_KEY')
        secret = current_app.config.get('DO_SPACES_SECRET')
        bucket = current_app.config.get('DO_SPACES_BUCKET')
        
        # Use DO Spaces if all credentials are present
        if all([region, key, secret, bucket]):
            return DOSpacesStorage(region, key, secret, bucket)
    
    # Default to local storage
    return LocalFileStorage()


def is_valid_file_upload(file):
    """
    Check if a file upload is valid and contains actual content
    
    Args:
        file: File object from form upload
        
    Returns:
        bool: True if file is valid and has content, False otherwise
    """
    if not file:
        return False
    
    # Check if filename exists and is not empty
    if not hasattr(file, 'filename') or not file.filename:
        return False
    
    # Check if filename is not just whitespace
    if not file.filename.strip():
        return False
    
    # Check if file has content by trying to read and reset
    try:
        current_position = file.tell()
        file.seek(0, 2)  # Seek to end
        file_size = file.tell()
        file.seek(current_position)  # Reset to original position
        return file_size > 0
    except (AttributeError, OSError):
        return False


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
    Upload an image file to storage with processing
    
    Args:
        file: Uploaded file object
        folder: Folder in storage to upload to (default: 'items')
        max_width: Maximum width for image processing (default: 800)
        max_height: Maximum height for image processing (default: 600)
        quality: JPEG quality for image processing (default: 85)
    
    Returns:
        URL of the uploaded image or None if upload failed
    """
    if not file:
        return None
    
    # Check if the file upload is valid and has content
    if not is_valid_file_upload(file):
        return None
        
    try:
        filename = secure_filename(file.filename)
        file_ext = os.path.splitext(filename)[1].lower()
        
        # Check if it's an image file
        image_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp'}
        if file_ext not in image_extensions:
            # Reject non-image files (app only supports image uploads)
            current_app.logger.warning(f"Rejected non-image file upload: {filename}")
            return None
        
        # Generate unique filename (always JPEG since we process all uploads as images)
        base_name = os.path.splitext(filename)[0]
        unique_filename = f"{uuid.uuid4()}-{base_name}.jpg"
        
        # Process the image
        processed_file = process_image(file, max_width, max_height, quality)
        
        # Get storage backend and upload
        storage = get_storage_backend()
        return storage.upload(processed_file, folder, unique_filename)
        
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

def upload_circle_image(file):
    """
    Upload a circle image with optimized dimensions for circle avatars/banners
    
    Args:
        file: Uploaded file object
    
    Returns:
        URL of the uploaded circle image or None if upload failed
    """
    return upload_file(file, folder='circles', max_width=600, max_height=600, quality=85)

def delete_file(url):
    """
    Delete a file from storage.
    
    Args:
        url: URL of the file to delete
    """
    if not url:
        return
    
    try:
        storage = get_storage_backend()
        storage.delete(url)
    except Exception as e:
        current_app.logger.error(f"Delete error: {str(e)}")