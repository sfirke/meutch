/**
 * Find page filter controls
 * Keeps category/circle badge counts and "All" toggles in sync.
 */

(function() {
    'use strict';

    function getCheckedCount(itemCheckboxes) {
        return Array.from(itemCheckboxes).filter((checkbox) => checkbox.checked).length;
    }

    function updateBadge(badge, checkedCount) {
        if (!badge) {
            return;
        }

        if (checkedCount > 0) {
            badge.textContent = String(checkedCount);
            badge.classList.remove('d-none');
            badge.setAttribute('aria-hidden', 'false');
            return;
        }

        badge.textContent = '0';
        badge.classList.add('d-none');
        badge.setAttribute('aria-hidden', 'true');
    }

    function updateGroup(group) {
        const checkedCount = getCheckedCount(group.itemCheckboxes);

        group.allCheckbox.checked = checkedCount === 0;
        updateBadge(group.badge, checkedCount);
    }

    function setupGroup(allSelector, itemSelector, badgeSelector) {
        const allCheckbox = document.querySelector(allSelector);
        const itemCheckboxes = document.querySelectorAll(itemSelector);
        const badge = document.querySelector(badgeSelector);

        if (!allCheckbox) {
            return;
        }

        const group = {
            allCheckbox,
            itemCheckboxes,
            badge
        };

        allCheckbox.addEventListener('change', function() {
            if (allCheckbox.checked) {
                itemCheckboxes.forEach((checkbox) => {
                    checkbox.checked = false;
                });
            } else if (getCheckedCount(itemCheckboxes) === 0) {
                allCheckbox.checked = true;
            }

            updateGroup(group);
        });

        itemCheckboxes.forEach((checkbox) => {
            checkbox.addEventListener('change', function() {
                updateGroup(group);
            });
        });

        updateGroup(group);
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
