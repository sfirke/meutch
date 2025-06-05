#!/usr/bin/env python3

import sys
import os

# Add the project root to the path
sys.path.insert(0, '/home/sam/git/meutch')

from app import create_app
from app.forms import ListItemForm
from werkzeug.datastructures import FileStorage
from io import BytesIO

def test_empty_file_validation():
    """Test how the form handles empty file uploads"""
    app = create_app()
    
    with app.app_context():
        # Create a form with empty file
        form = ListItemForm()
        
        # Simulate an empty file upload (like when user doesn't select a file)
        empty_file = FileStorage()
        form.image.data = empty_file
        
        # Set other required fields
        form.name.data = "Test Item"
        form.description.data = "Test Description"
        form.category.data = "1"  # Assuming category 1 exists
        form.tags.data = ""
        
        # Test validation
        print("Testing empty file validation...")
        print(f"Form validates: {form.validate()}")
        print(f"Image field errors: {form.image.errors}")
        print(f"All form errors: {form.errors}")
        
        # Test with None file
        form.image.data = None
        print(f"\nWith None file - Form validates: {form.validate()}")
        print(f"Image field errors: {form.image.errors}")

if __name__ == '__main__':
    test_empty_file_validation()
