// Keeps the admin announcement end date from falling before the start date.
// The end date's min follows the start date (today when it's blank), and submitting
// with an earlier end date shows an error instead. The server checks this too.
(function () {
    'use strict';

    const form = document.querySelector('[data-announcement-form]');
    if (!form) return;
    const start = form.querySelector('input[name=starts_at]');
    const end = form.querySelector('input[name=ends_at]');
    if (!start || !end) return;

    const MESSAGE = "The end date can't be before the start date.";
    let error = null;

    function minEndDate() {
        return start.value || end.dataset.today;
    }

    function showError() {
        end.classList.add('is-invalid');
        if (!error) {
            error = document.createElement('div');
            error.className = 'invalid-feedback';
            error.textContent = MESSAGE;
        }
        end.insertAdjacentElement('afterend', error);
    }

    function clearError() {
        if (!error) return;
        end.classList.remove('is-invalid');
        error.remove();
    }

    // ISO dates (YYYY-MM-DD) compare correctly as strings.
    function endIsTooEarly() {
        return end.value !== '' && end.value < minEndDate();
    }

    start.addEventListener('change', function () {
        end.min = minEndDate();
        if (!endIsTooEarly()) clearError();
    });

    end.addEventListener('change', function () {
        if (!endIsTooEarly()) clearError();
    });

    // Listening on the form runs before single-submit.js's document listener,
    // so a blocked submit doesn't leave the button disabled.
    form.addEventListener('submit', function (event) {
        if (!endIsTooEarly()) return;
        event.preventDefault();
        showError();
        end.focus();
    });
})();
