(function () {
  'use strict';

  var MAX_IMAGES = 8;
  var MAX_FILE_SIZE = 20 * 1024 * 1024; // 20MB
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

    // State: ordered list of {id, url, isExisting}
    var images = [];

    // Parse existing images from data attribute
    var existingData = imageContainer.dataset.existingImages;
    if (existingData) {
      try {
        var parsed = JSON.parse(existingData);
        parsed.forEach(function (img) {
          images.push({ id: img.id, url: img.url, isExisting: true });
        });
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
      var count = grid.querySelectorAll('.multi-image-thumb').length;
      counter.textContent = count + ' / ' + MAX_IMAGES;
      addBtn.style.display = count >= MAX_IMAGES ? 'none' : '';
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
      thumb.setAttribute('draggable', 'true');
      thumb.dataset.id = id;

      var img = document.createElement('img');
      img.src = url;
      img.alt = 'Photo';
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

      var handle = document.createElement('div');
      handle.className = 'multi-image-thumb-handle';
      handle.title = 'Drag to reorder';
      handle.setAttribute('aria-label', 'Drag to reorder');
      var handleIcon = document.createElement('i');
      handleIcon.className = 'fas fa-grip-vertical';
      handle.appendChild(handleIcon);
      thumb.appendChild(handle);

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
        announce('Photo removed. ' + grid.querySelectorAll('.multi-image-thumb').length + ' of ' + MAX_IMAGES + ' photos.');
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

      // Desktop drag-and-drop
      thumb.addEventListener('dragstart', function (e) {
        thumb.classList.add('dragging');
        e.dataTransfer.effectAllowed = 'move';
        e.dataTransfer.setData('text/plain', thumb.dataset.id);
      });

      thumb.addEventListener('dragend', function () {
        thumb.classList.remove('dragging');
        updateBadges();
        updateHiddenFields();
      });

      // Touch reorder on handle
      setupTouchDrag(handle, thumb);

      return thumb;
    }

    // Drag over / drop on grid
    grid.addEventListener('dragover', function (e) {
      e.preventDefault();
      e.dataTransfer.dropEffect = 'move';
      var dragging = grid.querySelector('.dragging');
      if (!dragging) return;
      var target = getDropTarget(e.clientX, e.clientY, dragging);
      if (target && target !== dragging) {
        var rect = target.getBoundingClientRect();
        var midX = rect.left + rect.width / 2;
        if (e.clientX < midX) {
          grid.insertBefore(dragging, target);
        } else {
          grid.insertBefore(dragging, target.nextSibling);
        }
      }
    });

    grid.addEventListener('drop', function (e) {
      e.preventDefault();
      updateBadges();
      updateHiddenFields();
      announce('Photo reordered.');
    });

    function getDropTarget(x, y, exclude) {
      var thumbs = grid.querySelectorAll('.multi-image-thumb');
      var closest = null;
      var closestDist = Infinity;
      thumbs.forEach(function (t) {
        if (t === exclude) return;
        var rect = t.getBoundingClientRect();
        var cx = rect.left + rect.width / 2;
        var cy = rect.top + rect.height / 2;
        var dist = Math.hypot(x - cx, y - cy);
        if (dist < closestDist) {
          closestDist = dist;
          closest = t;
        }
      });
      return closest;
    }

    // Touch drag for mobile reorder
    function setupTouchDrag(handle, thumb) {
      var clone = null;
      var offsetX = 0;
      var offsetY = 0;
      var scrollLocked = false;

      handle.addEventListener('touchstart', function (e) {
        if (e.touches.length !== 1) return;
        var touch = e.touches[0];
        var rect = thumb.getBoundingClientRect();
        offsetX = touch.clientX - rect.left;
        offsetY = touch.clientY - rect.top;

        clone = thumb.cloneNode(true);
        clone.classList.add('multi-image-thumb-clone');
        clone.style.position = 'fixed';
        clone.style.zIndex = '9999';
        clone.style.width = rect.width + 'px';
        clone.style.height = rect.height + 'px';
        clone.style.pointerEvents = 'none';
        clone.style.opacity = '0.85';
        clone.style.left = (touch.clientX - offsetX) + 'px';
        clone.style.top = (touch.clientY - offsetY) + 'px';
        document.body.appendChild(clone);

        thumb.classList.add('dragging');
        scrollLocked = true;
      }, { passive: true });

      handle.addEventListener('touchmove', function (e) {
        if (!clone) return;
        e.preventDefault();
        var touch = e.touches[0];
        clone.style.left = (touch.clientX - offsetX) + 'px';
        clone.style.top = (touch.clientY - offsetY) + 'px';

        var target = getDropTarget(touch.clientX, touch.clientY, thumb);
        if (target && target !== thumb) {
          var rect = target.getBoundingClientRect();
          var midX = rect.left + rect.width / 2;
          if (touch.clientX < midX) {
            grid.insertBefore(thumb, target);
          } else {
            grid.insertBefore(thumb, target.nextSibling);
          }
        }
      }, { passive: false });

      handle.addEventListener('touchend', function () {
        if (clone) {
          clone.remove();
          clone = null;
        }
        thumb.classList.remove('dragging');
        scrollLocked = false;
        updateBadges();
        updateHiddenFields();
        announce('Photo reordered.');
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

    // File selection
    fileInput.addEventListener('change', function () {
      if (!fileInput.files || fileInput.files.length === 0) return;

      var currentCount = grid.querySelectorAll('.multi-image-thumb').length;
      var filesToAdd = Array.from(fileInput.files);
      var available = MAX_IMAGES - currentCount;

      if (filesToAdd.length > available) {
        var msg = available === 0
          ? 'Maximum of ' + MAX_IMAGES + ' images reached.'
          : 'Only ' + available + ' more image(s) can be added. Extra files were skipped.';
        showNotification(msg, 'warning');
        filesToAdd = filesToAdd.slice(0, available);
      }

      filesToAdd.forEach(function (file) {
        if (!file.type.startsWith('image/')) {
          showNotification(file.name + ' is not an image file.', 'warning');
          return;
        }
        if (file.size > MAX_FILE_SIZE) {
          showNotification(file.name + ' exceeds the 20MB size limit.', 'warning');
          return;
        }
        var id = 'new-' + newIdCounter++;
        newFiles.set(id, file);

        var url = URL.createObjectURL(file);
        var thumb = createThumb(id, url);
        grid.insertBefore(thumb, addBtn);
      });

      // Reset file input so same file can be re-selected
      fileInput.value = '';
      updateCounter();
      updateBadges();
      updateHiddenFields();
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
          // DataTransfer not supported in older browsers — fallback to fetch
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
    images.forEach(function (img) {
      var thumb = createThumb(img.id, img.url);
      grid.insertBefore(thumb, addBtn);
    });

    updateCounter();
    updateBadges();
    updateHiddenFields();

    return {
      getNewFiles: function () { return newFiles; },
      getDeletedIds: function () { return deletedIds; }
    };
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
