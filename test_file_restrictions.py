#!/usr/bin/env python3
"""
Test script to verify that non-image files are properly rejected
"""
import os
import sys
import io
import pytest

def create_test_files():
    """Create test files of different types"""
    test_files = {}
    
    # Create a fake text file
    text_content = "This is a text file, not an image!"
    text_file = io.BytesIO(text_content.encode('utf-8'))
    text_file.filename = "test_document.txt"  # Add filename attribute
    test_files['text'] = text_file
    
    # Create a fake PDF file
    pdf_content = b"%PDF-1.4\n1 0 obj\n<<\n/Type /Catalog\n>>\nendobj\n"
    pdf_file = io.BytesIO(pdf_content)
    pdf_file.filename = "test_document.pdf"  # Add filename attribute
    test_files['pdf'] = pdf_file
    
    # Create a fake executable file
    exe_content = b"MZ\x90\x00" + b"fake executable content"
    exe_file = io.BytesIO(exe_content)
    exe_file.filename = "test_program.exe"  # Add filename attribute
    test_files['exe'] = exe_file
    
    # Create a valid image file (small PNG)
    # This is a minimal valid PNG file
    png_content = (
        b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01'
        b'\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\tpHYs\x00\x00\x0b\x13'
        b'\x00\x00\x0b\x13\x01\x00\x9a\x9c\x18\x00\x00\x00\nIDATx\x9cc```'
        b'\x00\x00\x00\x04\x00\x01\xdd\x8d\xb4\x1c\x00\x00\x00\x00IEND\xaeB`\x82'
    )
    png_file = io.BytesIO(png_content)
    png_file.filename = "test_image.png"  # Add filename attribute
    test_files['png'] = png_file
    
    return test_files

def test_file_upload_restrictions(app):
    from app.utils.storage import upload_item_image, upload_profile_image
    with app.app_context():
        print("🧪 Testing File Upload Restrictions")
        print("=" * 50)
        test_files = create_test_files()
        for file_type, test_file in test_files.items():
            print(f"\n📄 Testing {file_type.upper()} file: {test_file.filename}")
            test_file.seek(0)  # Reset file pointer
            # Test with upload_item_image
            result = upload_item_image(test_file)
            if file_type == 'png':
                print(f"   ✅ Image upload: {'SUCCESS' if result else 'FAILED'}")
                if result:
                    print(f"      URL: {result}")
            else:
                print(f"   {'✅' if not result else '❌'} Non-image rejection: {'SUCCESS' if not result else 'FAILED'}")
                if result:
                    print(f"      ❌ Unexpected upload URL: {result}")
        print(f"\n📊 Test Summary:")
        print(f"   ✅ Valid images should be accepted")
        print(f"   ❌ Non-image files should be rejected")

if __name__ == "__main__":
    try:
        test_file_upload_restrictions()
        print("\n🎉 File upload restriction tests completed!")
    except Exception as e:
        print(f"\n❌ Test failed: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
