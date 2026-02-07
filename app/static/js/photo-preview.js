/**
 * Photo Preview with Rotation and Cropping
 * Provides image preview, rotation, and cropping capabilities for file uploads
 * Uses Cropper.js for advanced image manipulation
 */

(function() {
    'use strict';

    let cropper = null;
    let currentFile = null;

    /**
     * Initialize photo preview for a file input element
     * @param {HTMLElement} fileInput - The file input element to enhance
     */
    function initPhotoPreview(fileInput) {
        if (!fileInput || fileInput.type !== 'file') {
            console.warn('Invalid file input element provided to initPhotoPreview');
            return;
        }

        // Check if Cropper is available
        if (typeof Cropper === 'undefined') {
            console.error('Cropper.js library not loaded. Photo preview will not work.');
            return;
        }

        // Check if already initialized
        if (fileInput.dataset.photoPreviewInitialized === 'true') {
            return;
        }
        fileInput.dataset.photoPreviewInitialized = 'true';

        // Create preview container
        const previewContainer = document.createElement('div');
        previewContainer.className = 'photo-preview-container mt-3';
        previewContainer.style.display = 'none';
        previewContainer.innerHTML = `
            <div class="card">
                <div class="card-body">
                    <h6 class="card-title">Photo Preview</h6>
                    <div class="photo-preview-wrapper">
                        <img id="preview-image" class="img-fluid" style="max-width: 100%; display: block;">
                    </div>
                    <div class="photo-preview-controls mt-3 d-flex gap-2 flex-wrap">
                        <button type="button" class="btn btn-sm btn-outline-secondary rotate-left-btn">
                            <i class="fas fa-undo"></i> Rotate Left
                        </button>
                        <button type="button" class="btn btn-sm btn-outline-secondary rotate-right-btn">
                            <i class="fas fa-redo"></i> Rotate Right
                        </button>
                        <button type="button" class="btn btn-sm btn-outline-secondary zoom-in-btn">
                            <i class="fas fa-search-plus"></i> Zoom In
                        </button>
                        <button type="button" class="btn btn-sm btn-outline-secondary zoom-out-btn">
                            <i class="fas fa-search-minus"></i> Zoom Out
                        </button>
                        <button type="button" class="btn btn-sm btn-outline-secondary reset-btn">
                            <i class="fas fa-sync-alt"></i> Reset
                        </button>
                        <button type="button" class="btn btn-sm btn-outline-danger remove-btn">
                            <i class="fas fa-trash"></i> Remove Photo
                        </button>
                    </div>
                    <small class="text-muted d-block mt-2">
                        Adjust your photo as needed. You can drag to reposition and use the zoom buttons. Changes will be applied when you submit the form.
                    </small>
                </div>
            </div>
        `;

        // Insert preview container after the file input's parent container
        const fileInputContainer = fileInput.closest('.mb-3') || fileInput.parentNode;
        fileInputContainer.parentNode.insertBefore(previewContainer, fileInputContainer.nextSibling);

        // Get references to elements
        const previewImage = previewContainer.querySelector('#preview-image');
        const rotateLeftBtn = previewContainer.querySelector('.rotate-left-btn');
        const rotateRightBtn = previewContainer.querySelector('.rotate-right-btn');
        const zoomInBtn = previewContainer.querySelector('.zoom-in-btn');
        const zoomOutBtn = previewContainer.querySelector('.zoom-out-btn');
        const resetBtn = previewContainer.querySelector('.reset-btn');
        const removeBtn = previewContainer.querySelector('.remove-btn');
        const controlsDiv = previewContainer.querySelector('.photo-preview-controls');
        
        console.log('Preview elements:', {
            previewImage: !!previewImage,
            rotateLeftBtn: !!rotateLeftBtn,
            rotateRightBtn: !!rotateRightBtn,
            zoomInBtn: !!zoomInBtn,
            zoomOutBtn: !!zoomOutBtn,
            removeBtn: !!removeBtn,
            controlsDiv: !!controlsDiv
        });

        // File input change handler
        fileInput.addEventListener('change', function() {
            const file = fileInput.files[0];
            if (file && file.type.startsWith('image/')) {
                currentFile = file;
                displayImage(file, previewImage, previewContainer);
                // Show controls when a new file is selected
                controlsDiv.style.display = 'flex';
                // Remove any existing success messages
                const existingMessages = previewContainer.querySelectorAll('.alert-success');
                existingMessages.forEach(msg => msg.remove());
            } else {
                hidePreview(previewContainer);
            }
        });

        // Control button handlers
        rotateLeftBtn.addEventListener('click', function(e) {
            e.preventDefault();
            console.log('Rotate left clicked', cropper);
            if (cropper) {
                // Get container dimensions before rotation
                const containerData = cropper.getContainerData();
                const imageData = cropper.getImageData();
                const currentRotation = imageData.rotate || 0;
                
                // Rotate to new angle
                cropper.rotateTo(currentRotation - 90);
                
                // After rotation, zoom to fit the container
                setTimeout(function() {
                    cropper.zoomTo(cropper.getImageData().aspectRatio > 1 ? 
                        containerData.width / cropper.getImageData().width :
                        containerData.height / cropper.getImageData().height);
                }, 10);
            }
        });

        rotateRightBtn.addEventListener('click', function(e) {
            e.preventDefault();
            console.log('Rotate right clicked', cropper);
            if (cropper) {
                // Get container dimensions before rotation
                const containerData = cropper.getContainerData();
                const imageData = cropper.getImageData();
                const currentRotation = imageData.rotate || 0;
                
                // Rotate to new angle
                cropper.rotateTo(currentRotation + 90);
                
                // After rotation, zoom to fit the container
                setTimeout(function() {
                    cropper.zoomTo(cropper.getImageData().aspectRatio > 1 ? 
                        containerData.width / cropper.getImageData().width :
                        containerData.height / cropper.getImageData().height);
                }, 10);
            }
        });

        zoomInBtn.addEventListener('click', function(e) {
            e.preventDefault();
            console.log('Zoom in clicked', cropper);
            if (cropper) {
                cropper.zoom(0.1);
            }
        });

        zoomOutBtn.addEventListener('click', function(e) {
            e.preventDefault();
            console.log('Zoom out clicked', cropper);
            if (cropper) {
                cropper.zoom(-0.1);
            }
        });

        resetBtn.addEventListener('click', function(e) {
            e.preventDefault();
            console.log('Reset clicked', currentFile);
            if (currentFile) {
                displayImage(currentFile, previewImage, previewContainer);
            }
        });

        removeBtn.addEventListener('click', function(e) {
            e.preventDefault();
            fileInput.value = '';
            currentFile = null;
            hidePreview(previewContainer);
            
            // Trigger change event to update file info display
            const event = new Event('change', { bubbles: true });
            fileInput.dispatchEvent(event);
        });
        
        // Add form submit handler to ensure cropped image is used
        const form = fileInput.closest('form');
        if (form) {
            // Track if we've already processed the image
            let imageProcessed = false;
            
            form.addEventListener('submit', function(e) {
                if (cropper && currentFile && !imageProcessed) {
                    // Prevent the form from submitting until we process the image
                    e.preventDefault();
                    console.log('Form submitting - updating file with cropped version');
                    
                    // Update file input with final cropped/rotated version
                    updateFileInputWithCroppedImage(fileInput, function() {
                        console.log('Image processed, submitting form');
                        imageProcessed = true;
                        // Use HTMLFormElement.prototype.submit to avoid conflict with named submit buttons
                        HTMLFormElement.prototype.submit.call(form);
                    });
                }
            });
        }
    }

    /**
     * Display an image in the preview
     * @param {File} file - The image file to display
     * @param {HTMLElement} previewImage - The preview image element
     * @param {HTMLElement} previewContainer - The preview container element
     */
    function displayImage(file, previewImage, previewContainer) {
        const reader = new FileReader();
        reader.onload = function(e) {
            // Destroy existing cropper instance
            if (cropper) {
                cropper.destroy();
                cropper = null;
            }

            // Set image source
            previewImage.src = e.target.result;
            previewContainer.style.display = 'block';

            // Wait for image to load before initializing Cropper
            previewImage.onload = function() {
                // Initialize Cropper.js
                cropper = new Cropper(previewImage, {
                    viewMode: 2, // Restrict canvas to container
                    dragMode: 'move',
                    aspectRatio: NaN, // Free aspect ratio
                    autoCropArea: 1,
                    restore: false,
                    guides: true,
                    center: true,
                    highlight: false,
                    cropBoxMovable: true,
                    cropBoxResizable: true,
                    toggleDragModeOnDblclick: false,
                    responsive: true,
                    background: false,
                    zoomable: true,
                    zoomOnWheel: true,
                    zoomOnTouch: true,
                    rotatable: true,
                    checkOrientation: false,
                    minContainerWidth: 200,
                    minContainerHeight: 200
                });
            };
        };
        reader.readAsDataURL(file);
    }

    /**
     * Hide the preview container
     * @param {HTMLElement} previewContainer - The preview container element
     */
    function hidePreview(previewContainer) {
        previewContainer.style.display = 'none';
        if (cropper) {
            cropper.destroy();
            cropper = null;
        }
    }

    /**
     * Update the file input with the cropped/rotated image
     * This converts the canvas to a blob and creates a new File object
     * @param {HTMLElement} fileInput - The file input element to update
     * @param {Function} callback - Optional callback function to call after update
     */
    function updateFileInputWithCroppedImage(fileInput, callback) {
        if (!cropper || !currentFile) {
            if (callback) callback();
            return;
        }

        // Get the cropped canvas
        const canvas = cropper.getCroppedCanvas();
        
        if (!canvas) {
            if (callback) callback();
            return;
        }

        // Convert canvas to blob
        canvas.toBlob(function(blob) {
            if (!blob) {
                if (callback) callback();
                return;
            }

            // Create a new file from the blob
            const fileName = currentFile.name;
            const newFile = new File([blob], fileName, {
                type: currentFile.type,
                lastModified: Date.now()
            });

            // Update the file input
            const dataTransfer = new DataTransfer();
            dataTransfer.items.add(newFile);
            fileInput.files = dataTransfer.files;

            // Store the updated file
            currentFile = newFile;
            
            if (callback) callback();
        }, currentFile.type);
    }

    /**
     * Auto-initialize all file inputs with class 'photo-preview'
     */
    let initAttempts = 0;
    const MAX_INIT_ATTEMPTS = 50; // Try for up to 5 seconds
    
    function autoInit() {
        // Check if Cropper.js is available
        if (typeof Cropper === 'undefined') {
            initAttempts++;
            if (initAttempts < MAX_INIT_ATTEMPTS) {
                console.warn('Cropper.js not loaded yet, retrying... (attempt ' + initAttempts + '/' + MAX_INIT_ATTEMPTS + ')');
                setTimeout(autoInit, 100);
            } else {
                console.error('Failed to load Cropper.js after ' + MAX_INIT_ATTEMPTS + ' attempts. Photo preview will not work.');
            }
            return;
        }
        
        console.log('Initializing photo preview...');
        const fileInputs = document.querySelectorAll('input[type="file"].photo-preview');
        console.log('Found', fileInputs.length, 'file inputs with photo-preview class');
        fileInputs.forEach(function(input) {
            initPhotoPreview(input);
        });
    }

    // Auto-initialize on DOM ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', autoInit);
    } else {
        autoInit();
    }

    // Export for manual initialization if needed
    window.PhotoPreview = {
        init: initPhotoPreview,
        autoInit: autoInit
    };
})();
