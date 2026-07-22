/**
 * Messaging inbox — checkbox selection &amp; bulk action bar.
 *
 * Behaviour:
 *  - "Select All" toggles every conversation checkbox on the page.
 *  - Changing any individual checkbox updates the bulk-action bar.
 *  - Clicking a conversation row navigates to that conversation, but
 *    clicking the checkbox itself does NOT navigate (stopPropagation).
 *  - The bulk-action bar is sticky at the bottom of the viewport;
 *    it slides in/out via CSS class toggling.
 *  - "Mark Read" / "Mark Unread" buttons are shown or hidden based on
 *    whether the checked conversations are all-unread, all-read, or mixed.
 *  - All hidden conversation-id inputs are kept in sync.
 */
(function () {
    'use strict';

    function init() {
        var selectAll = document.getElementById('select-all');
        var checkboxes = document.querySelectorAll('.conversation-checkbox');
        var bulkBar = document.getElementById('bulk-action-bar');
        var selectedCount = document.getElementById('selected-count');

        // Hidden inputs for each bulk-action form
        var archiveInput = document.getElementById('conversation-ids');
        var markReadInput = document.getElementById('conversation-ids-mark-read');
        var markUnreadInput = document.getElementById('conversation-ids-mark-unread');

        // Button forms (to show/hide based on read state)
        var markReadForm = document.getElementById('bulk-mark-read-form');
        var markUnreadForm = document.getElementById('bulk-mark-unread-form');

        if (!checkboxes.length || !bulkBar) return;

        /**
         * Collect the values of all checked conversation checkboxes.
         */
        function getCheckedIds() {
            var ids = [];
            document.querySelectorAll('.conversation-checkbox:checked').forEach(function (cb) {
                ids.push(cb.value);
            });
            return ids;
        }

        /**
         * Determine the read/unread mix of the checked conversations.
         *
         * Returns one of 'all-unread', 'all-read', or 'mixed'.
         * A conversation is considered "unread" when its row has the
         * ``conversation-unread`` CSS class.
         */
        function getCheckedReadState() {
            var hasUnread = false;
            var hasRead = false;
            document.querySelectorAll('.conversation-checkbox:checked').forEach(function (cb) {
                var row = cb.closest('.conversation-row');
                if (row && row.classList.contains('conversation-unread')) {
                    hasUnread = true;
                } else {
                    hasRead = true;
                }
            });
            if (hasUnread && hasRead) return 'mixed';
            if (hasUnread) return 'all-unread';
            return 'all-read';
        }

        /**
         * Copy ids into every hidden input so all bulk forms submit the
         * same set of conversation IDs.
         */
        function syncHiddenInputs(ids) {
            var value = ids.join(',');
            if (archiveInput) archiveInput.value = value;
            if (markReadInput) markReadInput.value = value;
            if (markUnreadInput) markUnreadInput.value = value;
        }

        /**
         * Show / hide the Mark Read and Mark Unread buttons based on the
         * read state of the checked conversations.
         */
        function updateReadUnreadButtons(state) {
            if (!markReadForm || !markUnreadForm) return;

            // Reset to defaults first
            markReadForm.classList.remove('d-none');
            markUnreadForm.classList.add('d-none');

            if (state === 'all-unread') {
                // Every checked conversation is unread — only "Mark Read" makes sense.
                markReadForm.classList.remove('d-none');
                markUnreadForm.classList.add('d-none');
            } else if (state === 'all-read') {
                // Every checked conversation is already read — only "Mark Unread".
                markReadForm.classList.add('d-none');
                markUnreadForm.classList.remove('d-none');
            } else {
                // Mixed — show both so the user can decide.
                markReadForm.classList.remove('d-none');
                markUnreadForm.classList.remove('d-none');
            }
        }

        /**
         * Main update routine — called whenever checkbox state changes.
         */
        function updateBulkBar() {
            var ids = getCheckedIds();
            var count = ids.length;

            if (count > 0) {
                bulkBar.classList.add('bulk-action-bar--visible');
                if (selectedCount) selectedCount.textContent = count;
                syncHiddenInputs(ids);
                updateReadUnreadButtons(getCheckedReadState());
            } else {
                bulkBar.classList.remove('bulk-action-bar--visible');
                syncHiddenInputs([]);
            }
        }

        // "Select All" checkbox
        if (selectAll) {
            selectAll.addEventListener('change', function () {
                checkboxes.forEach(function (cb) { cb.checked = selectAll.checked; });
                updateBulkBar();
            });
        }

        // Individual checkboxes — stopPropagation prevents row navigation.
        // We also stop propagation on the 48×48 hitbox label so that clicks
        // on the big visible area don't bleed through to the <a> row.
        checkboxes.forEach(function (cb) {
            cb.addEventListener('change', updateBulkBar);
            cb.addEventListener('click', function (e) { e.stopPropagation(); });
            var hitbox = cb.closest('.conv-checkbox-hitbox');
            if (hitbox) {
                hitbox.addEventListener('click', function (e) { e.stopPropagation(); });
            }
        });
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
