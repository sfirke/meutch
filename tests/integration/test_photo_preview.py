"""
Tests for photo preview functionality in item forms
"""
import io
from app.utils.storage import MAX_SOURCE_IMAGE_PIXELS, MAX_UPLOAD_FILE_SIZE_BYTES, MAX_UPLOAD_FILE_SIZE_LABEL
from tests.factories import UserFactory, CategoryFactory
from conftest import login_user


class TestPhotoPreview:
    """Test photo preview functionality"""
    
    def test_list_item_form_includes_photo_preview_classes(self, client, app, auth_user):
        """Test that list item form includes photo-preview class for image input"""
        with app.app_context():
            user = auth_user()
            login_user(client, user.email)
            
            response = client.get('/list-item')
            assert response.status_code == 200
            
            # Check that multi-image upload component is included
            assert b'multi-image-upload' in response.data
            assert b'multi-image-container' in response.data
            
            # Check that Cropper.js library is included
            assert b'cropperjs' in response.data
            assert b'cropper.min.css' in response.data
            assert b'cropper.min.js' in response.data
            
            # Check that photo-preview.js and multi-image-upload.js are included
            assert b'photo-preview.js' in response.data
            assert b'multi-image-upload.js' in response.data
            assert f'data-max-file-size-bytes="{MAX_UPLOAD_FILE_SIZE_BYTES}"'.encode() in response.data
            assert f'data-max-source-image-pixels="{MAX_SOURCE_IMAGE_PIXELS}"'.encode() in response.data
            assert f'Up to {MAX_UPLOAD_FILE_SIZE_LABEL} per photo before compression.'.encode() in response.data
    
    def test_edit_item_form_includes_photo_preview_classes(self, client, app, auth_user):
        """Test that edit item form includes multi-image upload component"""
        with app.app_context():
            user = auth_user()
            login_user(client, user.email)
            
            # Create an item owned by the user
            category = CategoryFactory()
            from app.models import Item
            from app import db
            
            item = Item(
                name='Test Item',
                description='Test description',
                owner=user,
                category_id=category.id
            )
            db.session.add(item)
            db.session.commit()
            
            response = client.get(f'/item/{item.id}/edit')
            assert response.status_code == 200
            
            # Check that multi-image upload component is included
            assert b'multi-image-upload' in response.data
            assert b'multi-image-container' in response.data
            
            # Check that Cropper.js library is included
            assert b'cropperjs' in response.data
            assert b'cropper.min.css' in response.data
            assert b'cropper.min.js' in response.data
            
            # Check that photo-preview.js and multi-image-upload.js are included
            assert b'photo-preview.js' in response.data
            assert b'multi-image-upload.js' in response.data
            assert f'data-max-file-size-bytes="{MAX_UPLOAD_FILE_SIZE_BYTES}"'.encode() in response.data
            assert f'data-max-source-image-pixels="{MAX_SOURCE_IMAGE_PIXELS}"'.encode() in response.data
            assert f'Up to {MAX_UPLOAD_FILE_SIZE_LABEL} per photo before compression.'.encode() in response.data
    
    def test_form_accepts_image_file(self, client, app, auth_user):
        """Test that the form accepts and processes image files (verifies form still works)"""
        with app.app_context():
            user = auth_user()
            category = CategoryFactory()
            login_user(client, user.email)
            
            # Create a fake image file
            image_data = io.BytesIO(b'fake image data')
            image_data.name = 'test.jpg'
            
            # Mock the upload function to avoid actual file operations
            from unittest.mock import patch
            with patch('app.main.routes.upload_item_images', return_value=['https://example.com/test.jpg']):
                response = client.post('/list-item', data={
                    'name': 'Item with Photo',
                    'description': 'An item with a photo',
                    'category': str(category.id),
                    'image': (image_data, 'test.jpg')
                }, follow_redirects=True, content_type='multipart/form-data')
                
                assert response.status_code == 200
                assert b'has been listed successfully!' in response.data
                
                # Verify item was created
                from app.models import Item
                item = Item.query.filter_by(name='Item with Photo').first()
                assert item is not None
                assert item.images[0].url == 'https://example.com/test.jpg'
