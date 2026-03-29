/**
 * Drag and Drop File Upload Enhancement
 * Enhances standard file inputs with drag & drop functionality
 */

(function() {
    'use strict';

    /**
     * Initialize drag and drop for a file input element
     * @param {HTMLElement} fileInput - The file input element to enhance
     */
    function initDragDrop(fileInput) {
        if (!fileInput || fileInput.type !== 'file') {
            console.warn('Invalid file input element provided to initDragDrop');
            return;
        }

        // Check if already initialized
        if (fileInput.dataset.dragDropInitialized === 'true') {
            return;
        }
        fileInput.dataset.dragDropInitialized = 'true';

        // Get accepted file types from the input's accept attribute
        const acceptedTypes = fileInput.accept || 'image/*';
        
        // Create drag & drop zone wrapper
        const dropZone = document.createElement('div');
        dropZone.className = 'drag-drop-zone';
        dropZone.setAttribute('role', 'button');
        dropZone.setAttribute('aria-label', 'Drag and drop image file or click to browse');
        dropZone.setAttribute('tabindex', '0');
        dropZone.innerHTML = `
            <div class="drag-drop-content">
                <i class="fas fa-cloud-upload-alt fa-3x mb-3 text-muted"></i>
                <p class="mb-2"><strong>Drag & drop an image here</strong></p>
                <p class="text-muted small mb-2">or</p>
                <button type="button" class="btn btn-sm btn-outline-primary browse-btn">Browse files</button>
                <p class="text-muted small mt-2 mb-0 file-info">No file selected</p>
            </div>
        `;

        // Insert drop zone before the file input
        fileInput.parentNode.insertBefore(dropZone, fileInput);
        
        // Hide the original file input but keep it functional
        fileInput.style.display = 'none';
        
        // Get references to elements
        const browseBtn = dropZone.querySelector('.browse-btn');
        const fileInfo = dropZone.querySelector('.file-info');

        // Browse button click handler
        browseBtn.addEventListener('click', function(e) {
            e.preventDefault();
            fileInput.click();
        });

        // Keyboard accessibility for drop zone
        dropZone.addEventListener('keydown', function(e) {
            if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault();
                fileInput.click();
            }
        });

        // File input change handler
        fileInput.addEventListener('change', function() {
            updateFileInfo(fileInput, fileInfo, dropZone);
        });

        // Drag counter to prevent flickering
        let dragCounter = 0;

        // Drag over handler
        dropZone.addEventListener('dragover', function(e) {
            e.preventDefault();
            e.stopPropagation();
            dropZone.classList.add('drag-over');
        });

        // Drag enter handler
        dropZone.addEventListener('dragenter', function(e) {
            e.preventDefault();
            e.stopPropagation();
            dragCounter++;
            dropZone.classList.add('drag-over');
        });

        // Drag leave handler with counter to prevent flickering
        dropZone.addEventListener('dragleave', function(e) {
            e.preventDefault();
            e.stopPropagation();
            dragCounter--;
            if (dragCounter === 0) {
                dropZone.classList.remove('drag-over');
            }
        });

        // Drop handler
        dropZone.addEventListener('drop', function(e) {
            e.preventDefault();
            e.stopPropagation();
            dragCounter = 0;
            dropZone.classList.remove('drag-over');

            const files = e.dataTransfer.files;
            if (files.length > 0) {
                const file = files[0];
                
                // Validate file type
                if (!isValidFileType(file, acceptedTypes)) {
                    fileInfo.textContent = 'Please select a valid image file (JPG, PNG, GIF, BMP, WebP)';
                    fileInfo.className = 'text-danger small mt-2 mb-0 file-info';
                    return;
                }
                
                // Create a new FileList-like object and assign to input
                const dataTransfer = new DataTransfer();
                dataTransfer.items.add(file);
                fileInput.files = dataTransfer.files;
                
                // Trigger change event
                const event = new Event('change', { bubbles: true });
                fileInput.dispatchEvent(event);
            }
        });

        // Initial file info update (in case form is re-rendered with existing file)
        updateFileInfo(fileInput, fileInfo, dropZone);
    }

    /**
     * Validate if a file matches the accepted types
     * @param {File} file - The file to validate
     * @param {string} acceptedTypes - Comma-separated list of accepted MIME types or extensions
     * @returns {boolean} - True if file is valid
     */
    function isValidFileType(file, acceptedTypes) {
        if (!acceptedTypes || acceptedTypes === '*') {
            return true;
        }

        const fileType = file.type.toLowerCase();
        const fileName = file.name.toLowerCase();
        const types = acceptedTypes.split(',').map(t => t.trim().toLowerCase());

        return types.some(type => {
            // Check MIME type pattern (e.g., "image/*")
            if (type.endsWith('/*')) {
                const baseType = type.slice(0, -2);
                return fileType.startsWith(baseType + '/');
            }
            // Check specific MIME type (e.g., "image/jpeg")
            if (type.includes('/')) {
                return fileType === type;
            }
            // Check file extension (e.g., ".jpg")
            if (type.startsWith('.')) {
                return fileName.endsWith(type);
            }
            // Check extension without dot (e.g., "jpg")
            return fileName.endsWith('.' + type);
        });
    }

    /**
     * Update the file information display
     * @param {HTMLElement} fileInput - The file input element
     * @param {HTMLElement} fileInfo - The file info display element
     * @param {HTMLElement} dropZone - The drop zone element
     */
    function updateFileInfo(fileInput, fileInfo, dropZone) {
        if (fileInput.files && fileInput.files.length > 0) {
            const file = fileInput.files[0];
            const fileSize = formatFileSize(file.size);
            fileInfo.textContent = `Selected: ${file.name} (${fileSize})`;
            fileInfo.className = 'text-success small mt-2 mb-0 file-info';
            dropZone.classList.add('has-file');
        } else {
            fileInfo.textContent = 'No file selected';
            fileInfo.className = 'text-muted small mt-2 mb-0 file-info';
            dropZone.classList.remove('has-file');
        }
    }

    /**
     * Format file size in human-readable format
     * @param {number} bytes - File size in bytes
     * @returns {string} - Formatted file size
     */
    function formatFileSize(bytes) {
        if (bytes < 1024) {
            return bytes + ' B';
        } else if (bytes < 1024 * 1024) {
            return (bytes / 1024).toFixed(2) + ' KB';
        } else {
            return (bytes / (1024 * 1024)).toFixed(2) + ' MB';
        }
    }

    /**
     * Auto-initialize all file inputs with class 'drag-drop-upload'
     */
    function autoInit() {
        const fileInputs = document.querySelectorAll('input[type="file"].drag-drop-upload');
        fileInputs.forEach(function(input) {
            initDragDrop(input);
        });
    }

    // Auto-initialize on DOM ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', autoInit);
    } else {
        autoInit();
    }

    // Export for manual initialization if needed
    window.DragDropUpload = {
        init: initDragDrop,
        autoInit: autoInit
    };
})();
