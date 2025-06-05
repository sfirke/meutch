#!/usr/bin/env python3

import sys
import os
sys.path.insert(0, '/home/sam/git/meutch')
import pytest
from app import create_app
from app.forms import ListItemForm
from werkzeug.datastructures import FileStorage
from io import BytesIO

def test_edit_form_validation():
    """Test form validation for edit item scenario"""
    app = create_app()
    
    with app.app_context():
        with app.test_request_context():
            print("Testing ListItemForm validation with empty image field...")
            
            # Create a form similar to what edit_item would use
            form = ListItemForm()
            
            # Simulate form data that would come from editing an item
            form.name.data = "Updated Test Item"
            form.description.data = "Updated description"
            form.category.data = "1"  # Assuming category exists
            form.tags.data = "tag1, tag2"
            form.delete_image.data = False
            
            # Simulate empty image field (what happens when user doesn't select a file)
            form.image.data = FileStorage()  # Empty FileStorage object
            
            # Test validation
            is_valid = form.validate()
            print(f"Form validates: {is_valid}")
            print(f"Form errors: {form.errors}")
            
            if not is_valid:
                print("Validation failed!")
                for field, errors in form.errors.items():
                    print(f"  {field}: {errors}")
            else:
                print("✅ Form validation passed!")
                
            # Test with None image data
            print("\nTesting with None image data...")
            form.image.data = None
            is_valid2 = form.validate()
            print(f"Form validates: {is_valid2}")
            print(f"Form errors: {form.errors}")

if __name__ == '__main__':
    test_edit_form_validation()
