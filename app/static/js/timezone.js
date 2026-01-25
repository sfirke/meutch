/**
 * Timezone conversion utility for Meutch
 * Converts UTC timestamps to user's local timezone with clear timezone display
 */

(function() {
    'use strict';

    /**
     * Get user-friendly timezone abbreviation
     * Falls back to offset if abbreviation isn't available
     */
    function getTimezoneAbbreviation() {
        try {
            const options = { timeZoneName: 'short' };
            const formatter = new Intl.DateTimeFormat('en-US', options);
            const parts = formatter.formatToParts(new Date());
            const tzPart = parts.find(part => part.type === 'timeZoneName');
            return tzPart ? tzPart.value : getTimezoneOffset();
        } catch (e) {
            return getTimezoneOffset();
        }
    }

    /**
     * Get timezone offset as string (e.g., "UTC-5")
     */
    function getTimezoneOffset() {
        const offset = new Date().getTimezoneOffset();
        const hours = Math.abs(Math.floor(offset / 60));
        const sign = offset <= 0 ? '+' : '-';
        return `UTC${sign}${hours}`;
    }

    /**
     * Format a date for display
     * @param {Date} date - The date to format
     * @param {string} format - 'full' (date and time), 'date' (date only), 'time' (time only), 'relative' (relative time)
     */
    function formatDate(date, format) {
        const tz = getTimezoneAbbreviation();
        
        switch (format) {
            case 'date':
                // Format: January 24, 2026
                return date.toLocaleDateString('en-US', {
                    year: 'numeric',
                    month: 'long',
                    day: 'numeric'
                });
            
            case 'short-date':
                // Format: Jan 24, 2026
                return date.toLocaleDateString('en-US', {
                    year: 'numeric',
                    month: 'short',
                    day: 'numeric'
                });
            
            case 'time':
                // Format: 09:05 PM EST
                return date.toLocaleTimeString('en-US', {
                    hour: 'numeric',
                    minute: '2-digit',
                    hour12: true
                }) + ' ' + tz;
            
            case 'datetime':
                // Format: January 24, 2026 at 09:05 PM EST
                return date.toLocaleDateString('en-US', {
                    year: 'numeric',
                    month: 'long',
                    day: 'numeric'
                }) + ' at ' + date.toLocaleTimeString('en-US', {
                    hour: 'numeric',
                    minute: '2-digit',
                    hour12: true
                }) + ' ' + tz;
            
            case 'short-datetime':
                // Format: Jan 24, 09:05 PM EST
                return date.toLocaleDateString('en-US', {
                    month: 'short',
                    day: 'numeric'
                }) + ', ' + date.toLocaleTimeString('en-US', {
                    hour: 'numeric',
                    minute: '2-digit',
                    hour12: true
                }) + ' ' + tz;
            
            case 'compact':
                // Format: 2026-01-24 21:05 EST
                return date.toLocaleDateString('en-CA') + ' ' + 
                    date.toLocaleTimeString('en-US', {
                        hour: '2-digit',
                        minute: '2-digit',
                        hour12: false
                    }) + ' ' + tz;
            
            case 'message':
                // Format for message timestamps: Jan 24, 21:05
                return date.toLocaleDateString('en-US', {
                    month: 'short',
                    day: 'numeric'
                }) + ', ' + date.toLocaleTimeString('en-US', {
                    hour: '2-digit',
                    minute: '2-digit',
                    hour12: false
                });
            
            default:
                // Default to full datetime format
                return formatDate(date, 'datetime');
        }
    }

    /**
     * Convert all elements with data-utc-timestamp attribute
     */
    function convertTimestamps() {
        const elements = document.querySelectorAll('[data-utc-timestamp]');
        
        elements.forEach(function(el) {
            const timestamp = el.getAttribute('data-utc-timestamp');
            const format = el.getAttribute('data-format') || 'datetime';
            
            if (timestamp) {
                try {
                    // Parse the ISO timestamp (assumes UTC if no timezone specified)
                    let date;
                    if (timestamp.endsWith('Z') || timestamp.includes('+') || timestamp.includes('-', 10)) {
                        // Already has timezone info
                        date = new Date(timestamp);
                    } else {
                        // Assume UTC
                        date = new Date(timestamp + 'Z');
                    }
                    
                    if (!isNaN(date.getTime())) {
                        el.textContent = formatDate(date, format);
                        // Add title attribute with full datetime for accessibility
                        if (!el.hasAttribute('title')) {
                            el.setAttribute('title', date.toLocaleString('en-US', {
                                weekday: 'long',
                                year: 'numeric',
                                month: 'long',
                                day: 'numeric',
                                hour: 'numeric',
                                minute: '2-digit',
                                timeZoneName: 'long'
                            }));
                        }
                    }
                } catch (e) {
                    console.warn('Failed to parse timestamp:', timestamp, e);
                }
            }
        });
    }

    // Run on DOM load
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', convertTimestamps);
    } else {
        convertTimestamps();
    }

    // Watch for dynamically added timestamps (e.g., via AJAX)
    if (typeof MutationObserver !== 'undefined') {
        const observer = new MutationObserver(function(mutations) {
            mutations.forEach(function(mutation) {
                if (mutation.addedNodes.length > 0) {
                    convertTimestamps();
                }
            });
        });
        
        // Start observing when DOM is ready
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', function() {
                observer.observe(document.body, {
                    childList: true,
                    subtree: true
                });
            });
        } else {
            observer.observe(document.body, {
                childList: true,
                subtree: true
            });
        }
    }

    // Expose for manual conversion if needed
    window.MeutchTimezone = {
        convertTimestamps: convertTimestamps,
        formatDate: formatDate,
        getTimezoneAbbreviation: getTimezoneAbbreviation
    };
})();
