"""Unit tests for storage utilities."""
import pytest
from unittest.mock import Mock, patch, MagicMock
from io import BytesIO
from PIL import Image
from app.utils.storage import (
    is_valid_file_upload, process_image, upload_file,
    upload_item_image, upload_profile_image
)

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
    
    @patch('app.utils.storage.get_s3_client')
    def test_upload_file_success(self, mock_s3_client, app):
        """Test successful file upload."""
        with app.app_context():
            # Setup mocks
            mock_s3 = Mock()
            mock_s3_client.return_value = mock_s3
            
            # Create test file with proper mock behavior
            mock_file = Mock()
            mock_file.filename = 'test.jpg'
            mock_file.read.return_value = b'fake image data'
            mock_file.seek.return_value = None
            mock_file.tell.side_effect = [0, 1000, 0]  # current pos, file size, reset pos
            
            with patch('app.utils.storage.process_image') as mock_process:
                mock_processed_file = BytesIO(b'processed image data')
                mock_process.return_value = mock_processed_file
                
                result = upload_file(mock_file, folder='test', require_image=True)
                
                # Verify S3 upload was called
                mock_s3.upload_fileobj.assert_called_once()
                
                # Verify return URL format
                assert result is not None
                assert '/test/' in result
    
    @patch('app.utils.storage.get_s3_client')
    def test_upload_file_failure(self, mock_s3_client, app):
        """Test file upload failure."""
        with app.app_context():
            # Setup mocks
            mock_s3 = Mock()
            mock_s3.upload_fileobj.side_effect = Exception("Upload failed")
            mock_s3_client.return_value = mock_s3
            
            # Create test file with proper mock behavior
            mock_file = Mock()
            mock_file.filename = 'test.jpg'
            mock_file.read.return_value = b'fake image data'
            mock_file.seek.return_value = None
            mock_file.tell.side_effect = [0, 1000, 0]  # current pos, file size, reset pos
            
            with patch('app.utils.storage.process_image') as mock_process:
                mock_processed_file = BytesIO(b'processed image data')
                mock_process.return_value = mock_processed_file
                
                result = upload_file(mock_file, folder='test', require_image=True)
                
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
