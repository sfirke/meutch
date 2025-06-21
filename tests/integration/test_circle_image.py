import io
import pytest
from unittest.mock import patch
from app.models import Circle, db
from tests.factories import UserFactory
from flask import url_for

def login_user(client, user):
    client.post('/auth/login', data={'email': user.email, 'password': 'testpassword123'}, follow_redirects=True)


@patch('app.circles.routes.upload_circle_image', return_value='https://example.com/circle.jpg')
def test_create_circle_with_image(mock_upload, client, app):
    with app.app_context():
        user = UserFactory()
        login_user(client, user)
        image_data = (io.BytesIO(b'fake image data'), 'circle.jpg')
        response = client.post(url_for('circles.create_circle'), data={
            'name': 'Circle With Image',
            'description': 'A circle with an image',
            'requires_approval': False,
            'image': image_data
        }, content_type='multipart/form-data', follow_redirects=True)
        assert response.status_code == 200
        circle = Circle.query.filter_by(name='Circle With Image').first()
        assert circle is not None
        assert circle.image_url == 'https://example.com/circle.jpg'
        assert b'has been created successfully' in response.data

@patch('app.circles.routes.upload_circle_image', return_value=None)
def test_create_circle_with_invalid_image(mock_upload, client, app):
    with app.app_context():
        user = UserFactory()
        login_user(client, user)
        # Mock upload failure
        bad_image = (io.BytesIO(b"not an image"), 'circle.jpg')
        response = client.post(url_for('circles.create_circle'), data={
            'name': 'Bad Image Circle',
            'description': 'Should fail',
            'requires_approval': False,
            'image': bad_image
        }, content_type='multipart/form-data', follow_redirects=True)
        assert response.status_code == 200
        circle = Circle.query.filter_by(name='Bad Image Circle').first()
        # Should not create the circle if image upload fails
        assert circle is None
        assert b'Image upload failed' in response.data
