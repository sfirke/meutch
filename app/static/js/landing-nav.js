(function () {
    'use strict';
    var navbar = document.querySelector('.navbar');
    if (!document.body.classList.contains('landing-page') || !navbar) return;

    function onScroll() {
        navbar.classList.toggle('scrolled', window.scrollY > 50);
    }
    window.addEventListener('scroll', onScroll, { passive: true });
    onScroll();
})();
