/**
 * Toast Notification Utility for Meutch
 * Provides consistent notification UI across the application
 * Uses Bootstrap 5 toasts with graceful fallback to browser alerts
 */

(function() {
    'use strict';

    /**
     * Show a toast notification to the user
     * @param {string} message - The message to display
     * @param {string} type - Bootstrap alert type: 'success', 'danger', 'warning', 'info', 'primary', 'secondary'
     * @param {Object} options - Optional configuration
     * @param {number} options.delay - Auto-hide delay in milliseconds (default: 5000)
     * @param {boolean} options.autohide - Whether to auto-hide the toast (default: true)
     */
    function showNotification(message, type, options) {
        // Default options
        const config = {
            delay: 5000,
            autohide: true,
            ...options
        };

        // Default to 'info' type if not specified
        type = type || 'info';
        
        // Try to use Bootstrap toasts if available
        const toastContainer = document.querySelector('.toast-container');
        
        if (toastContainer && typeof bootstrap !== 'undefined' && bootstrap.Toast) {
            const toastEl = document.createElement('div');
            toastEl.className = 'toast align-items-center text-white bg-' + type + ' border-0';
            toastEl.setAttribute('role', 'alert');
            toastEl.setAttribute('aria-live', 'assertive');
            toastEl.setAttribute('aria-atomic', 'true');
            
            toastEl.innerHTML = `
                <div class="d-flex">
                    <div class="toast-body">${message}</div>
                    <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast" aria-label="Close"></button>
                </div>
            `;
            
            toastContainer.appendChild(toastEl);
            const toast = new bootstrap.Toast(toastEl, { 
                autohide: config.autohide, 
                delay: config.delay 
            });
            toast.show();
            
            // Remove toast element after it's hidden to prevent DOM buildup
            toastEl.addEventListener('hidden.bs.toast', function() {
                toastEl.remove();
            });
        } else {
            // Fallback to alert if Bootstrap toasts aren't available
            alert(message);
        }
    }

    /**
     * Convenience methods for common notification types
     */
    const Notifications = {
        show: showNotification,
        success: function(message, options) {
            showNotification(message, 'success', options);
        },
        error: function(message, options) {
            showNotification(message, 'danger', options);
        },
        warning: function(message, options) {
            showNotification(message, 'warning', options);
        },
        info: function(message, options) {
            showNotification(message, 'info', options);
        }
    };

    // Export to global scope for use in other scripts
    window.Notifications = Notifications;
})();
