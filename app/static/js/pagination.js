/**
 * Pagination scroll utility for Meutch
 * Automatically scrolls to items section when navigating to page > 1
 */

(function() {
    'use strict';

    /**
     * Scroll to items section if we arrived from pagination
     */
    function handlePaginationScroll() {
        const urlParams = new URLSearchParams(window.location.search);
        const page = urlParams.get('page');
        
        if (page && parseInt(page) > 1) {
            // Find the items section and scroll to it
            const itemsSection = document.getElementById('items-section');
            if (itemsSection) {
                setTimeout(function() {
                    itemsSection.scrollIntoView({ 
                        behavior: 'smooth', 
                        block: 'start' 
                    });
                }, 100); // Small delay to ensure page is fully loaded
            }
        }
    }

    // Run on DOM load
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', handlePaginationScroll);
    } else {
        handlePaginationScroll();
    }
})();
