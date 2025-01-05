// Initialize Parallax
document.addEventListener('DOMContentLoaded', function() {
    var elements = document.querySelectorAll('.parallax-window');
    elements.forEach(function(el) {
        new Parallax(el);
    });
});
