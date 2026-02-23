// Shared utility functions for sharing links via Web Share API or clipboard fallback

function shareLink(button) {
    if (!button) {
        return;
    }

    const url = button.getAttribute('data-share-url');
    if (!url) {
        return;
    }

    const title = button.getAttribute('data-share-title') || '';
    const text = button.getAttribute('data-share-text') || title;
    const shareData = {
        title: title,
        text: text,
        url: url
    };

    if (!navigator.share) {
        copyToClipboardFallback(url, button);
        return;
    }

    if (navigator.canShare) {
        try {
            if (!navigator.canShare(shareData)) {
                copyToClipboardFallback(url, button);
                return;
            }
        } catch (error) {
            copyToClipboardFallback(url, button);
            return;
        }
    }

    navigator.share(shareData).catch(function(err) {
        if (err.name !== 'AbortError') {
            copyToClipboardFallback(url, button);
        }
    });
}

function showCopiedState(button) {
    if (!button) {
        return;
    }

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
    if (!url) {
        return;
    }

    if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(url).then(function() {
            showCopiedState(button);
        }).catch(function() {
            copyWithExecCommand(url, button);
        });
        return;
    }

    copyWithExecCommand(url, button);
}

function copyWithExecCommand(url, button) {
    var tempTextarea = document.createElement('textarea');
    tempTextarea.value = url;
    tempTextarea.setAttribute('readonly', '');
    tempTextarea.style.position = 'fixed';
    tempTextarea.style.top = '0';
    tempTextarea.style.left = '0';
    tempTextarea.style.opacity = '0';

    document.body.appendChild(tempTextarea);
    tempTextarea.focus();
    tempTextarea.select();
    tempTextarea.setSelectionRange(0, tempTextarea.value.length);

    var copied = false;
    try {
        copied = document.execCommand('copy');
    } catch (error) {
        copied = false;
    }

    document.body.removeChild(tempTextarea);

    if (copied) {
        showCopiedState(button);
        return;
    }

    window.prompt('Copy this link:', url);
}
