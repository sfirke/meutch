/**
 * Find page filter controls
 * Keeps category/circle badge counts and "All" toggles in sync.
 */

(function() {
    'use strict';

    function updateGroup(allSelector, itemSelector, badgeSelector) {
        const allCheckbox = document.querySelector(allSelector);
        const itemCheckboxes = document.querySelectorAll(itemSelector);
        const badge = document.querySelector(badgeSelector);

        if (!allCheckbox || !badge) {
            return;
        }

        const checkedCount = Array.from(itemCheckboxes).filter((checkbox) => checkbox.checked).length;

        allCheckbox.checked = checkedCount === 0;

        if (checkedCount > 0) {
            badge.textContent = String(checkedCount);
            badge.classList.remove('d-none');
        } else {
            badge.textContent = '0';
            badge.classList.add('d-none');
        }
    }

    function setupGroup(allSelector, itemSelector, badgeSelector) {
        const allCheckbox = document.querySelector(allSelector);
        const itemCheckboxes = document.querySelectorAll(itemSelector);

        if (!allCheckbox) {
            return;
        }

        allCheckbox.addEventListener('change', function() {
            if (allCheckbox.checked) {
                itemCheckboxes.forEach((checkbox) => {
                    checkbox.checked = false;
                });
            } else {
                const anyChecked = Array.from(itemCheckboxes).some((checkbox) => checkbox.checked);
                if (!anyChecked) {
                    allCheckbox.checked = true;
                }
            }

            updateGroup(allSelector, itemSelector, badgeSelector);
        });

        itemCheckboxes.forEach((checkbox) => {
            checkbox.addEventListener('change', function() {
                updateGroup(allSelector, itemSelector, badgeSelector);
            });
        });

        updateGroup(allSelector, itemSelector, badgeSelector);
    }

    function init() {
        setupGroup('#categories-all', '.category-checkbox', '#categories-badge');
        setupGroup('#circles-all', '.circle-checkbox', '#circles-badge');
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
