"""Unit tests for storage utilities."""
import pytest
from unittest.mock import Mock, patch, MagicMock
from io import BytesIO
from PIL import Image
from app.utils.storage import (
    is_valid_file_upload, process_image, upload_file,
    upload_item_image, upload_profile_image,
    get_storage_backend, LocalFileStorage, DOSpacesStorage
)
import os
import tempfile

class TestFileValidation:
    """Test file validation utilities."""
    
    def test_is_valid_file_upload_with_valid_file(self):
        """Test is_valid_file_upload with valid file."""
        mock_file = Mock()
        mock_file.filename = 'test.jpg'
        mock_file.tell.return_value = 0
        mock_file.seek.return_value = None
        
        # Mock file size check
        def mock_tell_sequence(*args):
            if len(args) == 0:
                return 0  # Current position
            elif args[0] == 0 and len(args) == 2 and args[1] == 2:
                return 1000  # File size when seeking to end
            return 0
        
        mock_file.tell = Mock(side_effect=[0, 1000])
        
        result = is_valid_file_upload(mock_file)
        assert result is True
    
    def test_is_valid_file_upload_with_empty_file(self):
        """Test is_valid_file_upload with empty file."""
        mock_file = Mock()
        mock_file.filename = 'test.jpg'
        mock_file.tell.return_value = 0
        mock_file.seek.return_value = None
        
        # Mock empty file (size 0)
        mock_file.tell = Mock(side_effect=[0, 0])
        
        result = is_valid_file_upload(mock_file)
        assert result is False
    
    def test_is_valid_file_upload_with_no_filename(self):
        """Test is_valid_file_upload with no filename."""
        mock_file = Mock()
        mock_file.filename = ''
        
        result = is_valid_file_upload(mock_file)
        assert result is False
    
    def test_is_valid_file_upload_with_none(self):
        """Test is_valid_file_upload with None."""
        result = is_valid_file_upload(None)
        assert result is False

class TestImageProcessing:
    """Test image processing utilities."""
    
    @patch('app.utils.storage.Image.open')
    @patch('app.utils.storage.ImageOps.exif_transpose')
    def test_process_image_jpeg(self, mock_transpose, mock_open, app):
        """Test processing a JPEG image."""
        with app.app_context():
            # Mock the image processing chain
            mock_img = Mock()
            mock_img.mode = 'RGB'
            mock_img.size = (1000, 800)
            mock_img.resize.return_value = mock_img
            mock_img.save = Mock()
            
            mock_open.return_value = mock_img
            mock_transpose.return_value = mock_img
            
            mock_file = Mock()
            mock_file.seek = Mock()
            
            result = process_image(mock_file, max_width=500, max_height=400)
            
            # Verify the processing chain was called
            mock_open.assert_called_once_with(mock_file)
            mock_transpose.assert_called_once_with(mock_img)
            assert result is not None
    
    @patch('app.utils.storage.Image.open')
    @patch('app.utils.storage.ImageOps.exif_transpose')
    @patch('app.utils.storage.Image.new')
    def test_process_image_png_to_jpeg(self, mock_new, mock_transpose, mock_open, app):
        """Test converting PNG to JPEG."""
        with app.app_context():
            # Mock RGBA image that needs conversion
            mock_img = Mock()
            mock_img.mode = 'RGBA'
            mock_img.size = (800, 600)
            mock_img.split.return_value = [Mock(), Mock(), Mock(), Mock()]  # RGBA channels
            mock_img.convert.return_value = mock_img
            
            # Mock background creation
            mock_background = Mock()
            mock_background.paste = Mock()
            mock_new.return_value = mock_background
            
            mock_open.return_value = mock_img
            mock_transpose.return_value = mock_background
            
            mock_file = Mock()
            mock_file.seek = Mock()
            
            result = process_image(mock_file, max_width=400, max_height=300)
            
            # Verify the conversion process
            mock_open.assert_called_once_with(mock_file)
            mock_new.assert_called_once_with('RGB', (800, 600), (255, 255, 255))
            assert result is not None
    
    @patch('app.utils.storage.Image.open')
    @patch('app.utils.storage.ImageOps.exif_transpose')
    def test_process_image_with_exif_rotation(self, mock_transpose, mock_open, app):
        """Test processing image with EXIF rotation."""
        with app.app_context():
            # Mock image
            mock_img = Mock()
            mock_img.mode = 'RGB'
            mock_img.size = (100, 50)
            mock_img.save = Mock()
            
            mock_open.return_value = mock_img
            mock_transpose.return_value = mock_img
            
            mock_file = Mock()
            mock_file.seek = Mock()
            
            result = process_image(mock_file, max_width=200, max_height=200)
            
            # Verify EXIF transpose was called
            mock_transpose.assert_called_once_with(mock_img)
            assert result is not None

class TestUploadFunctions:
    """Test upload functions."""
    
    @patch('app.utils.storage.get_storage_backend')
    def test_upload_file_success(self, mock_get_backend, app):
        """Test successful file upload."""
        with app.app_context():
            # Setup mock backend
            mock_backend = Mock()
            mock_backend.upload.return_value = 'http://example.com/test/file.jpg'
            mock_get_backend.return_value = mock_backend
            
            # Create test file with proper mock behavior
            mock_file = Mock()
            mock_file.filename = 'test.jpg'
            mock_file.read.return_value = b'fake image data'
            mock_file.seek.return_value = None
            mock_file.tell.side_effect = [0, 1000, 0]  # current pos, file size, reset pos
            
            with patch('app.utils.storage.process_image') as mock_process:
                mock_processed_file = BytesIO(b'processed image data')
                mock_process.return_value = mock_processed_file
                
                result = upload_file(mock_file, folder='test')
                
                # Verify backend upload was called
                mock_backend.upload.assert_called_once()
                
                # Verify return URL
                assert result == 'http://example.com/test/file.jpg'
    
    @patch('app.utils.storage.get_storage_backend')
    def test_upload_file_failure(self, mock_get_backend, app):
        """Test file upload failure."""
        with app.app_context():
            # Setup mock backend that fails
            mock_backend = Mock()
            mock_backend.upload.return_value = None
            mock_get_backend.return_value = mock_backend
            
            # Create test file with proper mock behavior
            mock_file = Mock()
            mock_file.filename = 'test.jpg'
            mock_file.read.return_value = b'fake image data'
            mock_file.seek.return_value = None
            mock_file.tell.side_effect = [0, 1000, 0]  # current pos, file size, reset pos
            
            with patch('app.utils.storage.process_image') as mock_process:
                mock_processed_file = BytesIO(b'processed image data')
                mock_process.return_value = mock_processed_file
                
                result = upload_file(mock_file, folder='test')
                
                # Verify upload failed
                assert result is None
    
    @patch('app.utils.storage.upload_file')
    def test_upload_item_image(self, mock_upload):
        """Test upload_item_image calls upload_file with correct parameters."""
        mock_file = Mock()
        mock_upload.return_value = 'https://example.com/image.jpg'
        
        result = upload_item_image(mock_file)
        
        mock_upload.assert_called_once_with(
            mock_file, 
            folder='items', 
            max_width=800, 
            max_height=600, 
            quality=85
        )
        assert result == 'https://example.com/image.jpg'
    
    @patch('app.utils.storage.upload_file')
    def test_upload_profile_image(self, mock_upload):
        """Test upload_profile_image calls upload_file with correct parameters."""
        mock_file = Mock()
        mock_upload.return_value = 'https://example.com/profile.jpg'
        
        result = upload_profile_image(mock_file)
        
        mock_upload.assert_called_once_with(
            mock_file, 
            folder='profiles', 
            max_width=400, 
            max_height=400, 
            quality=90
        )
        assert result == 'https://example.com/profile.jpg'


class TestStorageBackends:
    """Test storage backend implementations."""
    
    def test_get_storage_backend_local_by_default(self, app):
        """Test get_storage_backend returns LocalFileStorage by default (no DO Spaces config)."""
        with app.app_context():
            # Don't configure any DO Spaces credentials
            backend = get_storage_backend()
            assert isinstance(backend, LocalFileStorage)
    
    def test_get_storage_backend_do_spaces_when_configured(self, app):
        """Test get_storage_backend returns DOSpacesStorage when all credentials provided."""
        with app.app_context():
            app.config['STORAGE_BACKEND'] = 'digitalocean'
            app.config['DO_SPACES_REGION'] = 'nyc3'
            app.config['DO_SPACES_KEY'] = 'test-key'
            app.config['DO_SPACES_SECRET'] = 'test-secret'
            app.config['DO_SPACES_BUCKET'] = 'test-bucket'
            backend = get_storage_backend()
            assert isinstance(backend, DOSpacesStorage)
            # Verify CDN endpoint is used
            assert backend.endpoint == 'https://nyc3.cdn.digitaloceanspaces.com'
    
    def test_local_storage_upload(self, app):
        """Test LocalFileStorage upload functionality."""
        with app.app_context():
            with tempfile.TemporaryDirectory() as tmpdir:
                storage = LocalFileStorage(upload_folder=tmpdir)
                
                # Create a test file
                test_data = b'test image data'
                file_obj = BytesIO(test_data)
                
                # Upload the file
                url = storage.upload(file_obj, 'test-folder', 'test-file.jpg')
                
                # Verify file was created
                file_path = os.path.join(tmpdir, 'test-folder', 'test-file.jpg')
                assert os.path.exists(file_path)
                
                # Verify content
                with open(file_path, 'rb') as f:
                    assert f.read() == test_data
                
                # Verify URL contains the expected path
                assert 'uploads/test-folder/test-file.jpg' in url
    
    def test_local_storage_delete(self, app):
        """Test LocalFileStorage delete functionality."""
        with app.app_context():
            with tempfile.TemporaryDirectory() as tmpdir:
                storage = LocalFileStorage(upload_folder=tmpdir)
                
                # Create a test file
                test_folder = os.path.join(tmpdir, 'test-folder')
                os.makedirs(test_folder, exist_ok=True)
                test_file = os.path.join(test_folder, 'test-file.jpg')
                with open(test_file, 'wb') as f:
                    f.write(b'test data')
                
                # Verify file exists
                assert os.path.exists(test_file)
                
                # Delete the file
                url = 'http://localhost:5000/static/uploads/test-folder/test-file.jpg'
                storage.delete(url)
                
                # Verify file was deleted
                assert not os.path.exists(test_file)
    
    @patch('app.utils.storage.boto3.client')
    def test_do_spaces_upload(self, mock_boto_client, app):
        """Test DOSpacesStorage upload functionality."""
        with app.app_context():
            # Setup mock S3 client
            mock_s3 = Mock()
            mock_boto_client.return_value = mock_s3
            
            storage = DOSpacesStorage(
                region='nyc3',
                key='test-key',
                secret='test-secret',
                bucket='test-bucket'
            )
            
            # Upload a file
            file_obj = BytesIO(b'test data')
            url = storage.upload(file_obj, 'test-folder', 'test-file.jpg')
            
            # Verify S3 upload was called
            mock_s3.upload_fileobj.assert_called_once()
            
            # Verify URL format uses CDN endpoint
            assert url == 'https://nyc3.cdn.digitaloceanspaces.com/test-bucket/test-folder/test-file.jpg'
    
    @patch('app.utils.storage.boto3.client')
    def test_do_spaces_delete(self, mock_boto_client, app):
        """Test DOSpacesStorage delete functionality."""
        with app.app_context():
            # Setup mock S3 client
            mock_s3 = Mock()
            mock_boto_client.return_value = mock_s3
            
            storage = DOSpacesStorage(
                region='nyc3',
                key='test-key',
                secret='test-secret',
                bucket='test-bucket'
            )
            
            # Delete a file
            url = 'https://nyc3.cdn.digitaloceanspaces.com/test-bucket/test-folder/test-file.jpg'
            storage.delete(url)
            
            # Verify S3 delete was called
            mock_s3.delete_object.assert_called_once_with(
                Bucket='test-bucket',
                Key='test-folder/test-file.jpg'
            )
