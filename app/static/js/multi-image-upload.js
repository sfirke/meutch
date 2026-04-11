(function () {
  'use strict';

  var DEFAULT_MAX_IMAGES = 8;
  var DEFAULT_MAX_FILE_SIZE = 100 * 1024 * 1024;
  var DEFAULT_MAX_FILE_SIZE_LABEL = '100 MB';
  var DEFAULT_MAX_SOURCE_IMAGE_PIXELS = 10000 * 10000;
  var DEFAULT_MAX_SOURCE_IMAGE_LABEL = '100 megapixels';
  var DEFAULT_MAX_SOURCE_IMAGE_EXAMPLE_DIMENSIONS = '10000 x 10000';
  var DEFAULT_COMPRESS_MAX_WIDTH = 800;
  var DEFAULT_COMPRESS_MAX_HEIGHT = 600;
  var DEFAULT_COMPRESSION_QUALITY = 0.85;
  var newIdCounter = 0;

  function init(container) {
    var imageContainer = container.querySelector('.multi-image-container');
    var fileInput = container.querySelector('input[type=file]');
    var deleteField = container.querySelector('input[name=delete_images]');
    var orderField = container.querySelector('input[name=image_order]');
    var form = container.closest('form');

    if (!imageContainer || !fileInput) return;

    fileInput.setAttribute('accept', 'image/*');
    fileInput.setAttribute('multiple', '');
    fileInput.style.display = 'none';

    var newFiles = new Map();
    var deletedIds = new Set();
    var clickedSubmitBtn = null;
    var pendingFilesCount = 0;
    var maxImages = parsePositiveInt(container.dataset.maxImages, DEFAULT_MAX_IMAGES);
    var maxFileSize = parsePositiveInt(container.dataset.maxFileSizeBytes, DEFAULT_MAX_FILE_SIZE);
    var maxFileSizeLabel = container.dataset.maxFileSizeLabel || DEFAULT_MAX_FILE_SIZE_LABEL;
    var maxSourceImagePixels = parsePositiveInt(container.dataset.maxSourceImagePixels, DEFAULT_MAX_SOURCE_IMAGE_PIXELS);
    var maxSourceImageLabel = container.dataset.maxSourceImageLabel || DEFAULT_MAX_SOURCE_IMAGE_LABEL;
    var maxSourceImageExampleDimensions = container.dataset.maxSourceImageExampleDimensions || DEFAULT_MAX_SOURCE_IMAGE_EXAMPLE_DIMENSIONS;
    var compressMaxWidth = parsePositiveInt(container.dataset.compressMaxWidth, DEFAULT_COMPRESS_MAX_WIDTH);
    var compressMaxHeight = parsePositiveInt(container.dataset.compressMaxHeight, DEFAULT_COMPRESS_MAX_HEIGHT);
    var compressionQuality = parseQuality(container.dataset.compressionQuality, DEFAULT_COMPRESSION_QUALITY);

    // Parse existing images from data attribute
    var existingImages = [];
    var existingData = imageContainer.dataset.existingImages;
    if (existingData) {
      try {
        existingImages = JSON.parse(existingData);
      } catch (e) {
        console.error('Failed to parse existing images:', e);
      }
    }

    // Build UI
    var grid = document.createElement('div');
    grid.className = 'multi-image-grid';
    imageContainer.appendChild(grid);

    var addBtn = document.createElement('div');
    addBtn.className = 'multi-image-add-btn';
    addBtn.setAttribute('role', 'button');
    addBtn.setAttribute('tabindex', '0');
    addBtn.setAttribute('aria-label', 'Add photo');

    var addIcon = document.createElement('i');
    addIcon.className = 'fas fa-plus fa-2x';
    addBtn.appendChild(addIcon);

    var addLabel = document.createElement('span');
    addLabel.textContent = 'Add Photo';
    addBtn.appendChild(addLabel);

    var counter = document.createElement('small');
    counter.className = 'image-counter';
    addBtn.appendChild(counter);

    grid.appendChild(addBtn);

    // Hidden capture input: opens camera directly on mobile (capture attr ignored on desktop)
    var captureInput = document.createElement('input');
    captureInput.type = 'file';
    captureInput.accept = 'image/*';
    captureInput.setAttribute('capture', 'environment');
    captureInput.style.display = 'none';
    container.appendChild(captureInput);

    // Camera button – only rendered on touch devices where capture="environment" gives a
    // meaningfully different experience from the regular gallery picker.
    // Firefox already includes a camera option in its standard file chooser, so the
    // button would be redundant there. No feature-detection API exists for this
    // distinction; targeted UA detection is the pragmatic best practice here.
    var isTouchDevice = window.matchMedia('(hover: none) and (pointer: coarse)').matches;
    var isFirefox = /Firefox\//.test(navigator.userAgent);
    var showCameraBtn = isTouchDevice && !isFirefox;
    var cameraBtn = document.createElement('div');
    cameraBtn.className = 'multi-image-add-btn';
    cameraBtn.setAttribute('role', 'button');
    cameraBtn.setAttribute('tabindex', '0');
    cameraBtn.setAttribute('aria-label', 'Take photo');
    if (!showCameraBtn) {
      cameraBtn.style.display = 'none';
    }
    var cameraIcon = document.createElement('i');
    cameraIcon.className = 'fas fa-camera fa-2x';
    cameraBtn.appendChild(cameraIcon);
    var cameraLabel = document.createElement('span');
    cameraLabel.textContent = 'Take Photo';
    cameraBtn.appendChild(cameraLabel);
    grid.appendChild(cameraBtn);

    // Aria-live region for screen readers
    var liveRegion = document.createElement('div');
    liveRegion.setAttribute('aria-live', 'polite');
    liveRegion.setAttribute('aria-atomic', 'true');
    liveRegion.className = 'visually-hidden';
    container.appendChild(liveRegion);

    function announce(msg) {
      liveRegion.textContent = '';
      // Force reannounce by toggling content in next frame
      requestAnimationFrame(function () {
        liveRegion.textContent = msg;
      });
    }

    function updateCounter() {
      var count = grid.querySelectorAll('.multi-image-thumb').length + pendingFilesCount;
      counter.textContent = count + ' / ' + maxImages;
      var atMax = count >= maxImages;
      addBtn.style.display = atMax ? 'none' : '';
      if (showCameraBtn) {
        cameraBtn.style.display = atMax ? 'none' : '';
      }
    }

    function updateBadges() {
      var thumbs = grid.querySelectorAll('.multi-image-thumb');
      thumbs.forEach(function (thumb, i) {
        thumb.dataset.index = i;
        var badge = thumb.querySelector('.multi-image-thumb-badge');
        if (badge) badge.textContent = i + 1;
      });
    }

    function updateHiddenFields() {
      if (deleteField) {
        deleteField.value = JSON.stringify(Array.from(deletedIds));
      }
      if (orderField) {
        var thumbs = grid.querySelectorAll('.multi-image-thumb');
        var fullOrder = [];
        thumbs.forEach(function (thumb) {
          var id = thumb.dataset.id;
          if (id && !deletedIds.has(id)) {
            fullOrder.push(id);
          }
        });
        orderField.value = JSON.stringify(fullOrder);
      }
    }

    function createThumb(id, url) {
      var thumb = document.createElement('div');
      thumb.className = 'multi-image-thumb';
      thumb.dataset.id = id;

      var img = document.createElement('img');
      img.src = url;
      img.alt = 'Photo';
      img.setAttribute('draggable', 'false');
      thumb.appendChild(img);

      var overlay = document.createElement('div');
      overlay.className = 'multi-image-thumb-overlay';

      var cropBtn = document.createElement('button');
      cropBtn.type = 'button';
      cropBtn.className = 'btn-thumb-action btn-thumb-crop';
      cropBtn.title = 'Crop & edit';
      cropBtn.setAttribute('aria-label', 'Crop and edit photo');
      var cropIcon = document.createElement('i');
      cropIcon.className = 'fas fa-crop-alt';
      cropBtn.appendChild(cropIcon);
      overlay.appendChild(cropBtn);

      var deleteBtn = document.createElement('button');
      deleteBtn.type = 'button';
      deleteBtn.className = 'btn-thumb-action btn-thumb-delete';
      deleteBtn.title = 'Remove';
      deleteBtn.setAttribute('aria-label', 'Remove photo');
      var deleteIcon = document.createElement('i');
      deleteIcon.className = 'fas fa-times';
      deleteBtn.appendChild(deleteIcon);
      overlay.appendChild(deleteBtn);

      thumb.appendChild(overlay);

      var badge = document.createElement('span');
      badge.className = 'multi-image-thumb-badge';
      thumb.appendChild(badge);

      // Delete handler
      deleteBtn.addEventListener('click', function (e) {
        e.stopPropagation();
        var thumbId = thumb.dataset.id;
        if (thumbId.startsWith('new-')) {
          var file = newFiles.get(thumbId);
          if (file && img.src.startsWith('blob:')) {
            URL.revokeObjectURL(img.src);
          }
          newFiles.delete(thumbId);
        } else {
          deletedIds.add(thumbId);
        }
        thumb.remove();
        updateCounter();
        updateBadges();
        updateHiddenFields();
        announce('Photo removed. ' + grid.querySelectorAll('.multi-image-thumb').length + ' of ' + maxImages + ' photos.');
      });

      // Crop handler
      cropBtn.addEventListener('click', function (e) {
        e.stopPropagation();
        var thumbId = thumb.dataset.id;
        var detail = {
          index: parseInt(thumb.dataset.index, 10),
          id: thumbId,
          container: container
        };
        if (thumbId.startsWith('new-')) {
          detail.file = newFiles.get(thumbId);
        } else {
          detail.url = img.src;
        }
        container.dispatchEvent(new CustomEvent('multi-image:edit', { detail: detail, bubbles: true }));
      });

      setupPointerDrag(thumb);
      setupTouchDrag(thumb);

      return thumb;
    }

    function clearDropIndicators() {
      grid.querySelectorAll('.drop-before, .drop-after').forEach(function (el) {
        el.classList.remove('drop-before', 'drop-after');
      });
    }

    function getDropTarget(x, y, exclude) {
      var thumbs = Array.from(grid.querySelectorAll('.multi-image-thumb')).filter(function (t) {
        return t !== exclude;
      });

      var closest = null;
      var closestDist = Infinity;
      thumbs.forEach(function (t) {
        var rect = t.getBoundingClientRect();
        var cx = rect.left + rect.width / 2;
        var cy = rect.top + rect.height / 2;
        var dist = Math.hypot(x - cx, y - cy);
        if (dist < closestDist) {
          closestDist = dist;
          closest = t;
        }
      });

      if (!closest) return null;

      var rect = closest.getBoundingClientRect();
      return {
        target: closest,
        before: x < rect.left + rect.width / 2
      };
    }

    function updatePointerReorder(thumb, clientX, clientY) {
      var placement = getDropTarget(clientX, clientY, thumb);
      clearDropIndicators();
      if (!placement) return;

      var target = placement.target;
      if (!target || target === thumb) return;

      var before = placement.before;
      target.classList.add(before ? 'drop-before' : 'drop-after');
      grid.insertBefore(thumb, before ? target : target.nextSibling);
    }

    function startVisualDrag(thumb, clientX, clientY) {
      var rect = thumb.getBoundingClientRect();
      var clone = thumb.cloneNode(true);
      clone.classList.add('multi-image-thumb-clone');
      clone.style.position = 'fixed';
      clone.style.zIndex = '9999';
      clone.style.width = rect.width + 'px';
      clone.style.height = rect.height + 'px';
      clone.style.pointerEvents = 'none';
      clone.style.opacity = '0.85';
      clone.style.left = clientX - (clientX - rect.left) + 'px';
      clone.style.top = clientY - (clientY - rect.top) + 'px';
      document.body.appendChild(clone);

      thumb.classList.add('dragging');
      document.body.classList.add('multi-image-reordering');

      return {
        clone: clone,
        offsetX: clientX - rect.left,
        offsetY: clientY - rect.top
      };
    }

    function moveVisualDrag(state, clientX, clientY) {
      state.clone.style.left = (clientX - state.offsetX) + 'px';
      state.clone.style.top = (clientY - state.offsetY) + 'px';
    }

    function finishVisualDrag(thumb, state, announceReorder) {
      if (state && state.clone) {
        state.clone.remove();
      }
      thumb.classList.remove('dragging');
      clearDropIndicators();
      document.body.classList.remove('multi-image-reordering');
      updateBadges();
      updateHiddenFields();
      if (announceReorder) {
        announce('Photo reordered.');
      }
    }

    function setupPointerDrag(thumb) {
      thumb.addEventListener('mousedown', function (e) {
        if (e.button !== 0) return;
        if (e.target.closest('.btn-thumb-action')) return;

        var startX = e.clientX;
        var startY = e.clientY;
        var dragState = null;

        function onMouseMove(moveEvent) {
          var distance = Math.hypot(moveEvent.clientX - startX, moveEvent.clientY - startY);
          if (!dragState) {
            if (distance < 5) return;
            dragState = startVisualDrag(thumb, startX, startY);
          }

          moveEvent.preventDefault();
          moveVisualDrag(dragState, moveEvent.clientX, moveEvent.clientY);
          updatePointerReorder(thumb, moveEvent.clientX, moveEvent.clientY);
        }

        function onMouseUp() {
          document.removeEventListener('mousemove', onMouseMove);
          document.removeEventListener('mouseup', onMouseUp);
          if (!dragState) return;
          finishVisualDrag(thumb, dragState, true);
        }

        document.addEventListener('mousemove', onMouseMove);
        document.addEventListener('mouseup', onMouseUp);
      });
    }

    // Touch drag for mobile reorder
    function setupTouchDrag(thumb) {
      var dragState = null;
      var touchStartX = 0;
      var touchStartY = 0;

      thumb.addEventListener('touchstart', function (e) {
        if (e.target.closest('.btn-thumb-action')) return;
        if (e.touches.length !== 1) return;
        var touch = e.touches[0];
        touchStartX = touch.clientX;
        touchStartY = touch.clientY;
        dragState = null;
      }, { passive: true });

      thumb.addEventListener('touchmove', function (e) {
        var touch = e.touches[0];
        if (!dragState) {
          var distance = Math.hypot(touch.clientX - touchStartX, touch.clientY - touchStartY);
          if (distance < 5) return;
          dragState = startVisualDrag(thumb, touchStartX, touchStartY);
        }

        e.preventDefault();
        moveVisualDrag(dragState, touch.clientX, touch.clientY);
        updatePointerReorder(thumb, touch.clientX, touch.clientY);
      }, { passive: false });

      thumb.addEventListener('touchend', function (e) {
        if (!dragState) return;
        var touch = e.changedTouches && e.changedTouches[0];
        if (touch) {
          updatePointerReorder(thumb, touch.clientX, touch.clientY);
        }
        finishVisualDrag(thumb, dragState, true);
        dragState = null;
      });

      thumb.addEventListener('touchcancel', function () {
        if (!dragState) return;
        finishVisualDrag(thumb, dragState, false);
        dragState = null;
      });
    }

    // Shared file processing used by both gallery and camera inputs
    function handleFiles(files, inputEl) {
      if (!files || files.length === 0) return;

      var currentCount = grid.querySelectorAll('.multi-image-thumb').length + pendingFilesCount;
      var filesToAdd = Array.from(files);
      var available = maxImages - currentCount;

      if (filesToAdd.length > available) {
        var msg = available === 0
          ? 'Maximum of ' + maxImages + ' images reached.'
          : 'Only ' + available + ' more image(s) can be added. Extra files were skipped.';
        showNotification(msg, 'warning');
        filesToAdd = filesToAdd.slice(0, available);
      }

      var candidateFiles = [];
      filesToAdd.forEach(function (file) {
        if (!file.type.startsWith('image/')) {
          showNotification(file.name + ' is not an image file.', 'warning');
          return;
        }
        if (file.size > maxFileSize) {
          showNotification(file.name + ' exceeds the ' + maxFileSizeLabel + ' size limit.', 'warning');
          return;
        }
        candidateFiles.push(file);
      });

      // Reset input so same file can be re-selected
      inputEl.value = '';

      if (candidateFiles.length === 0) {
        updateCounter();
        return;
      }

      pendingFilesCount += candidateFiles.length;
      updateCounter();

      Promise.all(candidateFiles.map(function (file) {
        return prepareImageFile(
          file,
          compressMaxWidth,
          compressMaxHeight,
          compressionQuality,
          maxSourceImagePixels,
          maxSourceImageLabel,
          maxSourceImageExampleDimensions
        );
      })).then(function (results) {
        results.forEach(function (result) {
          if (result.error) {
            showNotification(result.error, 'warning');
            return;
          }

          var id = 'new-' + newIdCounter++;
          newFiles.set(id, result.file);

          var url = URL.createObjectURL(result.file);
          var thumb = createThumb(id, url);
          grid.insertBefore(thumb, addBtn);
        });

        pendingFilesCount -= candidateFiles.length;
        updateCounter();
        updateBadges();
        updateHiddenFields();
      });
    }

    // Add button click / keyboard
    addBtn.addEventListener('click', function () {
      fileInput.click();
    });

    addBtn.addEventListener('keydown', function (e) {
      if (e.key === 'Enter' || e.key === ' ') {
        e.preventDefault();
        fileInput.click();
      }
    });

    // Camera button click / keyboard
    cameraBtn.addEventListener('click', function () {
      captureInput.click();
    });

    cameraBtn.addEventListener('keydown', function (e) {
      if (e.key === 'Enter' || e.key === ' ') {
        e.preventDefault();
        captureInput.click();
      }
    });

    // File selection
    fileInput.addEventListener('change', function () {
      handleFiles(fileInput.files, fileInput);
    });

    captureInput.addEventListener('change', function () {
      handleFiles(captureInput.files, captureInput);
    });

    // Listen for cropped image from external modal
    container.addEventListener('multi-image:cropped', function (e) {
      var id = e.detail.id;
      var blob = e.detail.blob;
      var thumb = grid.querySelector('.multi-image-thumb[data-id="' + id + '"]');
      if (!thumb) return;

      var img = thumb.querySelector('img');
      // Revoke old blob URL if applicable
      if (img.src.startsWith('blob:')) {
        URL.revokeObjectURL(img.src);
      }

      var newUrl = URL.createObjectURL(blob);
      img.src = newUrl;

      // Store the blob as a File for submission
      var file = new File([blob], 'cropped-' + id + '.jpg', {
        type: blob.type || 'image/jpeg'
      });

      if (id.startsWith('new-')) {
        newFiles.set(id, file);
      } else {
        // Cropping an existing image: mark old for deletion, treat as new
        deletedIds.add(id);
        var newId = 'new-' + newIdCounter++;
        thumb.dataset.id = newId;
        newFiles.set(newId, file);
        updateHiddenFields();
      }
    });

    // Form submission
    if (form) {
      // Track which submit button was clicked
      form.addEventListener('click', function (e) {
        var btn = e.target.closest('button[type=submit], input[type=submit]');
        if (btn && form.contains(btn)) {
          clickedSubmitBtn = btn;
        }
      });

      form.addEventListener('submit', function (e) {
        if (pendingFilesCount > 0) {
          e.preventDefault();
          showNotification('Please wait for photos to finish processing.', 'warning');
          return;
        }

        // Build ordered list of files from DOM order
        var thumbs = grid.querySelectorAll('.multi-image-thumb');
        var orderedFiles = [];

        thumbs.forEach(function (thumb) {
          var id = thumb.dataset.id;
          if (id.startsWith('new-')) {
            var f = newFiles.get(id);
            if (f) orderedFiles.push(f);
          }
        });

        // Update hidden fields before submission
        updateHiddenFields();

        // Build DataTransfer to set file input files
        try {
          var dt = new DataTransfer();
          orderedFiles.forEach(function (f) {
            dt.items.add(f);
          });
          fileInput.files = dt.files;
        } catch (err) {
          // DataTransfer not supported
          console.error('DataTransfer not supported, cannot set files:', err);
        }

        // Ensure clicked submit button value is included
        if (clickedSubmitBtn && clickedSubmitBtn.name) {
          var existing = form.querySelector('input[type=hidden][name="' + clickedSubmitBtn.name + '"].multi-image-submit-proxy');
          if (existing) existing.remove();
          var hidden = document.createElement('input');
          hidden.type = 'hidden';
          hidden.name = clickedSubmitBtn.name;
          hidden.value = clickedSubmitBtn.value;
          hidden.className = 'multi-image-submit-proxy';
          form.appendChild(hidden);
        }

        // Let the form submit naturally
      });
    }

    // Render existing images
    existingImages.forEach(function (img) {
      var thumb = createThumb(img.id, img.url);
      grid.insertBefore(thumb, addBtn);
    });

    updateCounter();
    updateBadges();
    updateHiddenFields();
  }

  function showNotification(message, type) {
    // Use Bootstrap toast or alert if available, otherwise console
    var alertContainer = document.querySelector('.flash-messages') || document.querySelector('.container');
    if (!alertContainer) {
      console.warn('[MultiImageUpload] ' + message);
      return;
    }
    var alert = document.createElement('div');
    alert.className = 'alert alert-' + (type || 'warning') + ' alert-dismissible fade show';
    alert.setAttribute('role', 'alert');
    alert.textContent = message;
    var closeBtn = document.createElement('button');
    closeBtn.type = 'button';
    closeBtn.className = 'btn-close';
    closeBtn.setAttribute('data-bs-dismiss', 'alert');
    closeBtn.setAttribute('aria-label', 'Close');
    alert.appendChild(closeBtn);
    alertContainer.prepend(alert);

    setTimeout(function () {
      if (alert.parentNode) alert.remove();
    }, 5000);
  }

  /**
   * Compress an image file client-side using a canvas.
   * Returns a Promise that resolves to an object containing either a
   * processed File or an error message.
   */
  function prepareImageFile(file, maxWidth, maxHeight, quality, maxSourceImagePixels, maxSourceImageLabel, maxSourceImageExampleDimensions) {
    return new Promise(function (resolve) {
      var img = new Image();
      var url = URL.createObjectURL(file);

      img.onload = function () {
        URL.revokeObjectURL(url);

        var w = img.naturalWidth;
        var h = img.naturalHeight;
        if ((w * h) > maxSourceImagePixels) {
          resolve({
            error: file.name + ' exceeds the source image limit of ' + buildSourceImageLimitLabel(maxSourceImageLabel, maxSourceImageExampleDimensions) + '.'
          });
          return;
        }

        var ratio = Math.min(maxWidth / w, maxHeight / h, 1);
        var newW = Math.round(w * ratio);
        var newH = Math.round(h * ratio);

        // If already within bounds and already a JPEG, skip recompression
        if (ratio === 1 && file.type === 'image/jpeg') {
          resolve({ file: file });
          return;
        }

        var canvas = document.createElement('canvas');
        canvas.width = newW;
        canvas.height = newH;
        canvas.getContext('2d').drawImage(img, 0, 0, newW, newH);

        canvas.toBlob(function (blob) {
          if (!blob || blob.size >= file.size) {
            resolve({ file: file });
            return;
          }
          var name = file.name.replace(/\.[^.]+$/, '.jpg');
          resolve({ file: new File([blob], name, { type: 'image/jpeg' }) });
        }, 'image/jpeg', quality);
      };

      img.onerror = function () {
        URL.revokeObjectURL(url);
        resolve({ error: file.name + ' could not be processed as an image.' });
      };

      img.src = url;
    });
  }

  function parsePositiveInt(value, fallback) {
    var parsed = parseInt(value, 10);
    return Number.isFinite(parsed) && parsed > 0 ? parsed : fallback;
  }

  function parseQuality(value, fallback) {
    var parsed = parseFloat(value);
    return Number.isFinite(parsed) && parsed > 0 && parsed <= 1 ? parsed : fallback;
  }

  function buildSourceImageLimitLabel(maxSourceImageLabel, maxSourceImageExampleDimensions) {
    if (!maxSourceImageExampleDimensions) {
      return maxSourceImageLabel;
    }
    return maxSourceImageLabel + ' (' + maxSourceImageExampleDimensions + ' pixels)';
  }

  function autoInit() {
    var containers = document.querySelectorAll('.multi-image-upload');
    containers.forEach(function (el) {
      init(el);
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', autoInit);
  } else {
    autoInit();
  }

  window.MultiImageUpload = { init: init, autoInit: autoInit };
})();
