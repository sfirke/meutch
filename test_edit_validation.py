#!/usr/bin/env python3
"""
Test form validation for ListItemForm, specifically testing scenarios that occur during item editing.

This test ensures that the form properly validates when:
1. Required fields are provided
2. Image field is empty (user doesn't upload a new image during edit)
3. Valid category UUID is provided
4. Optional fields are handled correctly
"""

import sys
import os
sys.path.insert(0, '/home/sam/git/meutch')
import pytest
from app import create_app, db
from app.forms import ListItemForm
from app.models import Category, User, Item
from tests.factories import CategoryFactory, UserFactory, ItemFactory
from config import TestingConfig
from werkzeug.datastructures import FileStorage
from io import BytesIO

def test_edit_form_validation_with_real_category():
    """Test form validation for edit item scenario with real database fixtures"""
    
    app = create_app()
    app.config.from_object(TestingConfig)
    
    with app.app_context():
        # Setup test database
        db.create_all()
        
        try:
            # Create a real category using factory
            category = CategoryFactory()
            db.session.commit()
            
            with app.test_request_context():
                print(f"Testing ListItemForm validation with category UUID: {category.id}")
                
                # Create a form similar to what edit_item would use
                form = ListItemForm()
                
                # Simulate form data that would come from editing an item
                form.name.data = "Updated Test Item"
                form.description.data = "Updated description"
                form.category.data = str(category.id)  # Use real UUID
                form.tags.data = "tag1, tag2"
                form.delete_image.data = False
                
                # Simulate empty image field (what happens when user doesn't select a file)
                form.image.data = FileStorage()  # Empty FileStorage object
                
                # Test validation
                is_valid = form.validate()
                print(f"Form validates: {is_valid}")
                print(f"Form errors: {form.errors}")
                
                # This should pass - empty image is allowed for editing
                assert is_valid, f"Form should validate with empty image field. Errors: {form.errors}"
                
                # Test with None image data
                print("\nTesting with None image data...")
                form.image.data = None
                is_valid2 = form.validate()
                print(f"Form validates: {is_valid2}")
                print(f"Form errors: {form.errors}")
                
                # This should also pass
                assert is_valid2, f"Form should validate with None image field. Errors: {form.errors}"
                
                print("✅ All form validation tests passed!")
                
        finally:
            # Cleanup
            db.session.rollback()
            db.drop_all()

def test_edit_form_validation_missing_required_fields():
    """Test form validation fails when required fields are missing"""
    
    app = create_app()
    app.config.from_object(TestingConfig)
    
    with app.app_context():
        # Setup test database
        db.create_all()
        
        try:
            # Create a real category using factory
            category = CategoryFactory()
            db.session.commit()
            
            with app.test_request_context():
                print("Testing ListItemForm validation with missing required fields...")
                
                # Create a form with missing name (required field)
                form = ListItemForm()
                form.name.data = ""  # Missing required field
                form.description.data = "Updated description"
                form.category.data = str(category.id)
                form.tags.data = "tag1, tag2"
                form.delete_image.data = False
                form.image.data = None
                
                # Test validation
                is_valid = form.validate()
                print(f"Form validates: {is_valid}")
                print(f"Form errors: {form.errors}")
                
                # This should fail - name is required
                assert not is_valid, "Form should not validate when required name field is empty"
                assert 'name' in form.errors, "Name field should have validation errors"
                
                print("✅ Required field validation test passed!")
                
        finally:
            # Cleanup
            db.session.rollback()
            db.drop_all()

def test_edit_form_validation_invalid_category():
    """Test form validation fails when invalid category is provided"""
    
    app = create_app()
    app.config.from_object(TestingConfig)
    
    with app.app_context():
        # Setup test database
        db.create_all()
        
        try:
            with app.test_request_context():
                print("Testing ListItemForm validation with invalid category...")
                
                # Create a form with invalid category
                form = ListItemForm()
                form.name.data = "Updated Test Item"
                form.description.data = "Updated description"
                form.category.data = "invalid-uuid"  # Invalid category
                form.tags.data = "tag1, tag2"
                form.delete_image.data = False
                form.image.data = None
                
                # Test validation
                is_valid = form.validate()
                print(f"Form validates: {is_valid}")
                print(f"Form errors: {form.errors}")
                
                # This should fail - invalid category
                assert not is_valid, "Form should not validate with invalid category"
                assert 'category' in form.errors, "Category field should have validation errors"
                
                print("✅ Invalid category validation test passed!")
                
        finally:
            # Cleanup
            db.session.rollback()
            db.drop_all()

def test_edit_form_validation():
    """Run all tests in sequence"""
    test_edit_form_validation_with_real_category()
    test_edit_form_validation_missing_required_fields()
    test_edit_form_validation_invalid_category()
    print("✅ All form validation tests completed successfully!")

if __name__ == '__main__':
    test_edit_form_validation()
