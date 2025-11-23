"""Unit tests for admin models and decorators"""
import pytest
from app.models import User, AdminAction
from app.auth.decorators import admin_required
from tests.factories import UserFactory, AdminActionFactory
from flask import Flask
from flask_login import login_user, current_user


def test_user_is_admin_default_false(app, db_session):
    """Test that is_admin defaults to False for new users"""
    user = UserFactory()
    db_session.commit()
    
    assert user.is_admin is False


def test_user_can_be_promoted_to_admin(app, db_session):
    """Test that a user can be promoted to admin"""
    user = UserFactory()
    db_session.commit()
    
    user.is_admin = True
    db_session.commit()
    
    assert user.is_admin is True


def test_admin_action_model_creation(app, db_session):
    """Test AdminAction model can be created"""
    admin = UserFactory(is_admin=True)
    target = UserFactory()
    db_session.commit()
    
    action = AdminAction(
        action_type='promote',
        target_user_id=target.id,
        admin_user_id=admin.id,
        details={'target_email': target.email}
    )
    db_session.add(action)
    db_session.commit()
    
    assert action.id is not None
    assert action.action_type == 'promote'
    assert action.target_user_id == target.id
    assert action.admin_user_id == admin.id
    assert action.details['target_email'] == target.email


def test_admin_action_relationships(app, db_session):
    """Test AdminAction relationships to users"""
    action = AdminActionFactory()
    db_session.commit()
    
    assert action.target_user is not None
    assert action.admin_user is not None
    assert action.admin_user.is_admin is True


def test_admin_action_factory(app, db_session):
    """Test AdminActionFactory creates valid actions"""
    action = AdminActionFactory(action_type='delete')
    db_session.commit()
    
    assert action.action_type == 'delete'
    assert action.admin_user.is_admin is True
    assert 'target_email' in action.details
    assert 'target_name' in action.details


def test_admin_required_decorator_blocks_non_admin(app, db_session):
    """Test that admin_required decorator blocks non-admin users"""
    from flask import abort
    
    @admin_required
    def admin_only_view():
        return "admin content"
    
    # Create non-admin user
    user = UserFactory(is_admin=False)
    db_session.commit()
    
    with app.test_request_context():
        login_user(user)
        
        # Should raise 403 Forbidden
        with pytest.raises(Exception) as excinfo:
            admin_only_view()
        
        # Check it's a 403 error (werkzeug raises HTTPException)
        assert '403' in str(excinfo.value) or excinfo.typename == 'Forbidden'


def test_admin_required_decorator_allows_admin(app, db_session):
    """Test that admin_required decorator allows admin users"""
    @admin_required
    def admin_only_view():
        return "admin content"
    
    # Create admin user
    admin = UserFactory(is_admin=True)
    db_session.commit()
    
    with app.test_request_context():
        login_user(admin)
        
        # Should succeed
        result = admin_only_view()
        assert result == "admin content"


def test_user_factory_can_create_admin(app, db_session):
    """Test that UserFactory can create admin users"""
    admin = UserFactory(is_admin=True)
    regular = UserFactory(is_admin=False)
    db_session.commit()
    
    assert admin.is_admin is True
    assert regular.is_admin is False
