/**
 * Messaging inbox — checkbox selection & bulk action bar.
 *
 * Behaviour:
 *  - "Select All" toggles every conversation checkbox on the page.
 *  - Changing any individual checkbox updates the bulk-action bar.
 *  - Clicking a conversation row navigates to that conversation, but
 *    clicking the checkbox itself does NOT navigate (stopPropagation).
 *  - The bulk-action bar is sticky at the bottom of the viewport;
 *    it slides in/out via CSS class toggling.
 */
(function () {
    'use strict';

    function init() {
        var selectAll = document.getElementById('select-all');
        var checkboxes = document.querySelectorAll('.conversation-checkbox');
        var bulkBar = document.getElementById('bulk-action-bar');
        var selectedCount = document.getElementById('selected-count');
        var conversationIdsInput = document.getElementById('conversation-ids');

        if (!checkboxes.length || !bulkBar) return;

        /**
         * Update the bulk-action bar visibility and the hidden input value.
         */
        function updateBulkBar() {
            var checked = document.querySelectorAll('.conversation-checkbox:checked');
            var count = checked.length;

            if (count > 0) {
                bulkBar.classList.add('bulk-action-bar--visible');
                if (selectedCount) selectedCount.textContent = count;
                if (conversationIdsInput) {
                    var ids = [];
                    checked.forEach(function (cb) { ids.push(cb.value); });
                    conversationIdsInput.value = ids.join(',');
                }
            } else {
                bulkBar.classList.remove('bulk-action-bar--visible');
                if (conversationIdsInput) conversationIdsInput.value = '';
            }
        }

        // "Select All" checkbox
        if (selectAll) {
            selectAll.addEventListener('change', function () {
                checkboxes.forEach(function (cb) { cb.checked = selectAll.checked; });
                updateBulkBar();
            });
        }

        // Individual checkboxes — stopPropagation prevents row navigation
        checkboxes.forEach(function (cb) {
            cb.addEventListener('change', updateBulkBar);
            cb.addEventListener('click', function (e) { e.stopPropagation(); });
        });
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
