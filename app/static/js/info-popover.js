// Click-to-open info popovers. A button with data-info-popover="<template id>"
// shows that template's HTML; clicking outside or pressing Escape closes it.

document.addEventListener('DOMContentLoaded', function() {
    const triggers = document.querySelectorAll('[data-info-popover]');
    triggers.forEach(function(trigger) {
        const template = document.getElementById(trigger.dataset.infoPopover);
        if (!template) return;
        new bootstrap.Popover(trigger, {
            content: template.innerHTML,
            html: true,
            trigger: 'click',
            placement: 'bottom',
        });
    });

    document.addEventListener('click', function(event) {
        triggers.forEach(function(trigger) {
            const popover = bootstrap.Popover.getInstance(trigger);
            const tip = popover && popover.tip;
            if (!popover || trigger.contains(event.target) || (tip && tip.contains(event.target))) return;
            popover.hide();
        });
    });

    document.addEventListener('keydown', function(event) {
        if (event.key !== 'Escape') return;
        triggers.forEach(function(trigger) {
            const popover = bootstrap.Popover.getInstance(trigger);
            if (popover) popover.hide();
        });
    });
});
