// Shared utility functions for sharing links via Web Share API or clipboard fallback

function shareLink(button) {
    const url = button.getAttribute('data-share-url');
    const title = button.getAttribute('data-share-title');
    const text = button.getAttribute('data-share-text') || ('Check this out on Meutch: ' + title);
    const shareData = {
        title: title,
        text: text,
        url: url
    };

    if (navigator.share) {
        if (!navigator.canShare || navigator.canShare(shareData)) {
            navigator.share(shareData).catch(function(err) {
                if (err.name !== 'AbortError') {
                    copyToClipboardFallback(url, button);
                }
            });
            return;
        }
        copyToClipboardFallback(url, button);
    } else {
        copyToClipboardFallback(url, button);
    }
}

function showCopiedState(button) {
    var originalHTML = button.innerHTML;
    var hadOutlinePrimary = button.classList.contains('btn-outline-primary');
    var hadOutlineSecondary = button.classList.contains('btn-outline-secondary');

    button.innerHTML = '<i class="fas fa-check me-1"></i>Link Copied!';
    button.classList.remove('btn-outline-primary', 'btn-outline-secondary');
    button.classList.add('btn-success');

    setTimeout(function() {
        button.innerHTML = originalHTML;
        button.classList.remove('btn-success');

        if (hadOutlinePrimary) {
            button.classList.add('btn-outline-primary');
        } else if (hadOutlineSecondary) {
            button.classList.add('btn-outline-secondary');
        } else {
            button.classList.add('btn-outline-primary');
        }
    }, 2000);
}

function copyToClipboardFallback(url, button) {
    navigator.clipboard.writeText(url).then(function() {
        showCopiedState(button);
    }).catch(function() {
        var tempInput = document.createElement('input');
        tempInput.value = url;
        document.body.appendChild(tempInput);
        tempInput.select();
        document.execCommand('copy');
        document.body.removeChild(tempInput);
        showCopiedState(button);
    });
}
