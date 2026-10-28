// Stop a POST form from submitting twice, e.g. from a double tap on its button

(function () {
    'use strict';

    function submitButtons(form) {
        return form.querySelectorAll('button[type=submit], input[type=submit], button:not([type])');
    }

    document.addEventListener('submit', function (e) {
        const form = e.target;
        if (e.defaultPrevented || form.method !== 'post') return;

        if (form.dataset.submitting === 'true') {
            e.preventDefault();
            return;
        }

        form.dataset.submitting = 'true';
        // A class, not the disabled property: a disabled button's name/value
        // would be dropped from the submitted form data.
        submitButtons(form).forEach(function (button) {
            button.classList.add('disabled');
            button.setAttribute('aria-disabled', 'true');
        });
    });

    // Re-enable forms when the page is restored with the Back button
    window.addEventListener('pageshow', function () {
        document.querySelectorAll('form[data-submitting]').forEach(function (form) {
            delete form.dataset.submitting;
            submitButtons(form).forEach(function (button) {
                button.classList.remove('disabled');
                button.removeAttribute('aria-disabled');
            });
        });
    });
})();
