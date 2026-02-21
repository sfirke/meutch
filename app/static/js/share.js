// Shared utility functions for sharing links via Web Share API or clipboard fallback

function shareLink(button) {
    const url = button.getAttribute('data-share-url');
    const title = button.getAttribute('data-share-title');

    if (navigator.share) {
        navigator.share({
            title: title,
            url: url
        }).catch(function(err) {
            if (err.name !== 'AbortError') {
                copyToClipboardFallback(url, button);
            }
        });
    } else {
        copyToClipboardFallback(url, button);
    }
}

function copyToClipboardFallback(url, button) {
    navigator.clipboard.writeText(url).then(function() {
        var originalHTML = button.innerHTML;
        button.innerHTML = '<i class="fas fa-check me-1"></i>Link Copied!';
        button.classList.remove('btn-outline-secondary');
        button.classList.add('btn-success');

        setTimeout(function() {
            button.innerHTML = originalHTML;
            button.classList.remove('btn-success');
            button.classList.add('btn-outline-secondary');
        }, 2000);
    }).catch(function() {
        var tempInput = document.createElement('input');
        tempInput.value = url;
        document.body.appendChild(tempInput);
        tempInput.select();
        document.execCommand('copy');
        document.body.removeChild(tempInput);

        var originalHTML = button.innerHTML;
        button.innerHTML = '<i class="fas fa-check me-1"></i>Link Copied!';
        button.classList.remove('btn-outline-secondary');
        button.classList.add('btn-success');

        setTimeout(function() {
            button.innerHTML = originalHTML;
            button.classList.remove('btn-success');
            button.classList.add('btn-outline-secondary');
        }, 2000);
    });
}
