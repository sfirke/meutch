// Shared utility functions for sharing links via Web Share API or clipboard fallback

function generateAndCopyShareLink(button) {
    const formId = button.dataset.formId;
    const itemId = button.dataset.itemId;
    const form = document.getElementById(formId);
    if (!form) return;

    const formData = new FormData(form);
    const originalHTML = button.innerHTML;
    button.disabled = true;
    button.innerHTML = '<i class="fas fa-spinner fa-spin me-1"></i>Generating…';

    fetch(form.action, {
        method: 'POST',
        headers: { 'X-Requested-With': 'XMLHttpRequest' },
        body: formData,
    })
    .then(function(r) {
        if (!r.ok) throw new Error('Request failed');
        return r.json();
    })
    .then(function(data) {
        const url = data.url;

        const section = document.getElementById('share-link-section-' + itemId);
        const linkInput = document.getElementById('item-share-link-' + itemId);
        const shareBtn = section ? section.querySelector('.share-btn') : null;

        if (linkInput) linkInput.value = url;
        if (shareBtn) shareBtn.setAttribute('data-share-url', url);
        if (section) section.classList.remove('d-none');

        button.disabled = false;
        button.innerHTML = originalHTML;
        copyToClipboardFallback(url, button);
    })
    .catch(function() {
        // Fall back to full-page form submit on any error
        button.disabled = false;
        button.innerHTML = originalHTML;
        form.submit();
    });
}

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

    const originalHTML = button.innerHTML;
    const hadOutlinePrimary = button.classList.contains('btn-outline-primary');
    const hadOutlineSecondary = button.classList.contains('btn-outline-secondary');

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
    const tempTextarea = document.createElement('textarea');
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

    let copied = false;
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
