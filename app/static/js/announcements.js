// Dismisses the announcement banner without a page reload. Without JS, the form posts normally.
document.addEventListener('submit', function(event) {
    const form = event.target.closest('[data-announcement-dismiss]');
    if (!form) return;
    event.preventDefault();

    fetch(form.action, {
        method: 'POST',
        headers: { 'X-Requested-With': 'XMLHttpRequest' },
        body: new FormData(form),
    })
    .then(function(r) {
        if (!r.ok) throw new Error('Request failed');
        form.closest('[data-announcement-banner]').parentElement.remove();
    })
    .catch(function() {
        form.submit();
    });
});
