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

        // Create drag & drop zone wrapper
        const dropZone = document.createElement('div');
        dropZone.className = 'drag-drop-zone';
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

        // File input change handler
        fileInput.addEventListener('change', function() {
            updateFileInfo(fileInput, fileInfo, dropZone);
        });

        // Drag over handler
        dropZone.addEventListener('dragover', function(e) {
            e.preventDefault();
            e.stopPropagation();
            dropZone.classList.add('drag-over');
        });

        // Drag leave handler
        dropZone.addEventListener('dragleave', function(e) {
            e.preventDefault();
            e.stopPropagation();
            dropZone.classList.remove('drag-over');
        });

        // Drop handler
        dropZone.addEventListener('drop', function(e) {
            e.preventDefault();
            e.stopPropagation();
            dropZone.classList.remove('drag-over');

            const files = e.dataTransfer.files;
            if (files.length > 0) {
                // Create a new FileList-like object and assign to input
                const dataTransfer = new DataTransfer();
                dataTransfer.items.add(files[0]);
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
     * Update the file information display
     * @param {HTMLElement} fileInput - The file input element
     * @param {HTMLElement} fileInfo - The file info display element
     * @param {HTMLElement} dropZone - The drop zone element
     */
    function updateFileInfo(fileInput, fileInfo, dropZone) {
        if (fileInput.files && fileInput.files.length > 0) {
            const file = fileInput.files[0];
            const fileSize = (file.size / 1024).toFixed(2); // Convert to KB
            fileInfo.textContent = `Selected: ${file.name} (${fileSize} KB)`;
            fileInfo.className = 'text-success small mt-2 mb-0 file-info';
            dropZone.classList.add('has-file');
        } else {
            fileInfo.textContent = 'No file selected';
            fileInfo.className = 'text-muted small mt-2 mb-0 file-info';
            dropZone.classList.remove('has-file');
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
