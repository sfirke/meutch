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
            return;
        }

        // Cropper.js must be loaded - it's a required dependency
        if (typeof Cropper === 'undefined') {
            return;
        }

        // Check if already initialized
        if (fileInput.dataset.photoPreviewInitialized === 'true') {
            return;
        }
        fileInput.dataset.photoPreviewInitialized = 'true';

        // Create preview container using DOM methods (safer than innerHTML)
        const previewContainer = document.createElement('div');
        previewContainer.className = 'photo-preview-container mt-3';
        previewContainer.style.display = 'none';
        
        const card = document.createElement('div');
        card.className = 'card';
        
        const cardBody = document.createElement('div');
        cardBody.className = 'card-body';
        
        const title = document.createElement('h6');
        title.className = 'card-title';
        title.textContent = 'Photo Preview';
        
        const wrapper = document.createElement('div');
        wrapper.className = 'photo-preview-wrapper';
        
        const previewImage = document.createElement('img');
        previewImage.id = 'preview-image';
        previewImage.className = 'img-fluid';
        previewImage.style.maxWidth = '100%';
        previewImage.style.display = 'block';
        previewImage.alt = 'Photo preview';
        
        wrapper.appendChild(previewImage);
        
        const controls = document.createElement('div');
        controls.className = 'photo-preview-controls mt-3 d-flex gap-2 flex-wrap';
        
        // Create control buttons
        const buttons = [
            { class: 'rotate-left-btn', icon: 'fa-undo', text: 'Rotate Left', style: 'btn-outline-secondary' },
            { class: 'rotate-right-btn', icon: 'fa-redo', text: 'Rotate Right', style: 'btn-outline-secondary' },
            { class: 'zoom-in-btn', icon: 'fa-search-plus', text: 'Zoom In', style: 'btn-outline-secondary' },
            { class: 'zoom-out-btn', icon: 'fa-search-minus', text: 'Zoom Out', style: 'btn-outline-secondary' },
            { class: 'reset-btn', icon: 'fa-sync-alt', text: 'Reset', style: 'btn-outline-secondary' },
            { class: 'remove-btn', icon: 'fa-trash', text: 'Remove Photo', style: 'btn-outline-danger' }
        ];
        
        buttons.forEach(function(btnConfig) {
            const btn = document.createElement('button');
            btn.type = 'button';
            btn.className = 'btn btn-sm ' + btnConfig.style + ' ' + btnConfig.class;
            
            const icon = document.createElement('i');
            icon.className = 'fas ' + btnConfig.icon;
            
            btn.appendChild(icon);
            btn.appendChild(document.createTextNode(' ' + btnConfig.text));
            controls.appendChild(btn);
        });
        
        const helpText = document.createElement('small');
        helpText.className = 'text-muted d-block mt-2';
        helpText.textContent = 'Adjust your photo as needed. You can drag to reposition and use the zoom buttons. Changes will be applied when you submit the form.';
        
        cardBody.appendChild(title);
        cardBody.appendChild(wrapper);
        cardBody.appendChild(controls);
        cardBody.appendChild(helpText);
        card.appendChild(cardBody);
        previewContainer.appendChild(card);

        // Insert preview container after the file input's parent container
        const fileInputContainer = fileInput.closest('.mb-3') || fileInput.parentNode;
        fileInputContainer.parentNode.insertBefore(previewContainer, fileInputContainer.nextSibling);

        // Get references to elements
        const rotateLeftBtn = previewContainer.querySelector('.rotate-left-btn');
        const rotateRightBtn = previewContainer.querySelector('.rotate-right-btn');
        const zoomInBtn = previewContainer.querySelector('.zoom-in-btn');
        const zoomOutBtn = previewContainer.querySelector('.zoom-out-btn');
        const resetBtn = previewContainer.querySelector('.reset-btn');
        const removeBtn = previewContainer.querySelector('.remove-btn');
        const controlsDiv = previewContainer.querySelector('.photo-preview-controls');

        // File input change handler with security validations
        fileInput.addEventListener('change', function() {
            const file = fileInput.files[0];
            
            // Validate file exists and is an image
            if (!file) {
                hidePreview(previewContainer);
                return;
            }
            
            // Strict file type validation - only allow specific image types
            const allowedTypes = ['image/jpeg', 'image/jpg', 'image/png', 'image/gif', 'image/webp', 'image/bmp'];
            if (!allowedTypes.includes(file.type.toLowerCase())) {
                alert('Invalid file type. Please select a valid image file (JPEG, PNG, GIF, WebP, or BMP).');
                fileInput.value = '';
                hidePreview(previewContainer);
                return;
            }
            
            // File size limit: 20MB (prevent DoS from huge files)
            const maxSize = 20 * 1024 * 1024; // 20MB in bytes
            if (file.size > maxSize) {
                alert('File is too large. Please select an image under 20MB.');
                fileInput.value = '';
                hidePreview(previewContainer);
                return;
            }
            
            currentFile = file;
            displayImage(file, previewImage, previewContainer);
            // Show controls when a new file is selected
            controlsDiv.style.display = 'flex';
        });

        // Control button handlers
        rotateLeftBtn.addEventListener('click', function(e) {
            e.preventDefault();
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
            if (cropper) {
                cropper.zoom(0.1);
            }
        });

        zoomOutBtn.addEventListener('click', function(e) {
            e.preventDefault();
            if (cropper) {
                cropper.zoom(-0.1);
            }
        });

        resetBtn.addEventListener('click', function(e) {
            e.preventDefault();
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
                    
                    // Update file input with final cropped/rotated version
                    updateFileInputWithCroppedImage(fileInput, function() {
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
        // Additional security check
        if (!file || !file.type || !file.type.startsWith('image/')) {
            return;
        }
        
        const reader = new FileReader();
        
        reader.onerror = function() {
            alert('Failed to read image file. Please try another file.');
        };
        
        reader.onload = function(e) {
            // Validate the result is a data URL
            if (!e.target.result || !e.target.result.startsWith('data:image/')) {
                alert('Failed to load image. Please try another file.');
                return;
            }
            
            // Destroy existing cropper instance
            if (cropper) {
                cropper.destroy();
                cropper = null;
            }

            // Set image source
            previewImage.src = e.target.result;
            previewContainer.style.display = 'block';

            // Clean up previous onload handler to prevent memory leaks
            previewImage.onload = null;
            
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
                    checkOrientation: true,
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

        // Convert canvas to blob with error handling
        try {
            canvas.toBlob(function(blob) {
                if (!blob) {
                    console.warn('Failed to create blob from canvas');
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
        } catch (e) {
            console.error('Error converting canvas to blob:', e);
            if (callback) callback();
        }
    }

    /**
     * Auto-initialize all file inputs with class 'photo-preview'
     */
    function autoInit() {
        // Cropper.js must be loaded synchronously before this script
        if (typeof Cropper === 'undefined') {
            return;
        }
        
        const fileInputs = document.querySelectorAll('input[type="file"].photo-preview');
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
