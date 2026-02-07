# JavaScript Utilities

This directory contains reusable JavaScript utilities for the Meutch application.

## Core Utilities (Loaded Site-wide in base.html)

### notifications.js
Provides toast notification functionality using Bootstrap 5 toasts.

**Usage:**
```javascript
// Basic usage
Notifications.show('Message text', 'success');

// Convenience methods
Notifications.success('Operation completed!');
Notifications.error('Something went wrong');
Notifications.warning('Please be careful');
Notifications.info('Just so you know');

// With options
Notifications.show('Custom message', 'primary', {
    delay: 3000,      // Auto-hide after 3 seconds
    autohide: false   // Don't auto-hide
});
```

**Available types:** `success`, `danger` (error), `warning`, `info`, `primary`, `secondary`

### timezone.js
Converts UTC timestamps to user's local timezone with clear timezone display.

### pagination.js
Automatically scrolls to items section when navigating to page > 1.

## Feature-Specific Scripts (Loaded on Specific Pages)

### photo-preview.js
Photo preview with rotation and cropping for file uploads.
- **Dependencies:** Cropper.js, notifications.js
- **Usage:** Add `photo-preview` class to file inputs
- **Pages:** list_item.html, edit_item.html

### drag-drop-upload.js
Drag and drop enhancement for file inputs.
- **Usage:** Add `drag-drop-upload` class to file inputs
- **Pages:** list_item.html, edit_item.html

## Adding New Utilities

1. **Site-wide utility:** Add to `app/templates/base.html` in the "Core JavaScript utilities" section
2. **Feature-specific utility:** Load in the specific page's `{% block scripts %}` section
3. **Dependencies:** Document any dependencies in the file header and this README
