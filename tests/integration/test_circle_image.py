import io
import pytest
from unittest.mock import patch
from app.models import Circle, db
from tests.factories import UserFactory, CircleFactory
from sqlalchemy import text
from flask import url_for
from conftest import TEST_PASSWORD

def login_user(client, user):
    client.post('/auth/login', data={'email': user.email, 'password': TEST_PASSWORD}, follow_redirects=True)

def login_admin(client, user, circle):
    db.session.execute(
        text(f"""
        INSERT INTO circle_members (user_id, circle_id, joined_at, is_admin)
        VALUES ('{user.id}', '{circle.id}', NOW(), TRUE)
        ON CONFLICT DO NOTHING
        """
        )
    )
    db.session.commit()
    client.post('/auth/login', data={'email': user.email, 'password': TEST_PASSWORD}, follow_redirects=True)


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

@patch('app.circles.routes.is_valid_file_upload', return_value=True)
@patch('app.circles.routes.upload_circle_image', return_value='https://example.com/new-circle.jpg')
def test_edit_circle_image(mock_upload, mock_valid, client, app):
    with app.app_context():
        user = UserFactory()
        circle = CircleFactory(image_url=None)
        login_admin(client, user, circle)
        image_data = (io.BytesIO(b"new image data"), 'circle2.jpg')
        response = client.post(url_for('circles.edit_circle', circle_id=circle.id), data={
            'name': circle.name,
            'description': circle.description,
            'requires_approval': circle.requires_approval,
            'image': image_data
        }, content_type='multipart/form-data', follow_redirects=True)
        assert response.status_code == 200
        db.session.refresh(circle)
        assert circle.image_url == 'https://example.com/new-circle.jpg'
        assert b'Circle image updated.' in response.data

@patch('app.circles.routes.delete_file')
def test_remove_circle_image(mock_delete, client, app):
    with app.app_context():
        user = UserFactory()
        circle = CircleFactory(image_url='https://example.com/old.jpg')
        login_admin(client, user, circle)
        response = client.post(url_for('circles.edit_circle', circle_id=circle.id), data={
            'name': circle.name,
            'description': circle.description,
            'requires_approval': circle.requires_approval,
            'delete_image': True
        }, follow_redirects=True)
        assert response.status_code == 200
        db.session.refresh(circle)
        assert circle.image_url is None
        assert b'Circle image has been removed.' in response.data
        mock_delete.assert_called_once_with('https://example.com/old.jpg')
