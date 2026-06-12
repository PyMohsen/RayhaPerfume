/**
 * Rayha Perfume — Main JavaScript
 */

document.addEventListener('DOMContentLoaded', function () {

    // ==========================================
    // Mobile Menu Toggle
    // ==========================================
    const menuToggle = document.getElementById('mobile-menu-toggle');
    const categoryNav = document.querySelector('.category-nav');

    if (menuToggle && categoryNav) {
        menuToggle.addEventListener('click', function () {
            categoryNav.classList.toggle('open');
            this.classList.toggle('active');
        });
    }

    // ==========================================
    // Auto-hide Messages
    // ==========================================
    const messages = document.querySelectorAll('.message');
    messages.forEach(function (msg, index) {
        setTimeout(function () {
            msg.style.opacity = '0';
            msg.style.transform = 'translateY(-20px)';
            setTimeout(function () { msg.remove(); }, 300);
        }, 4000 + (index * 500));
    });

    // ==========================================
    // Smooth Scroll for Anchor Links
    // ==========================================
    document.querySelectorAll('a[href^="#"]').forEach(function (anchor) {
        anchor.addEventListener('click', function (e) {
            var target = document.querySelector(this.getAttribute('href'));
            if (target) {
                e.preventDefault();
                target.scrollIntoView({ behavior: 'smooth', block: 'start' });
            }
        });
    });

    // ==========================================
    // Lazy Load Images
    // ==========================================
    if ('IntersectionObserver' in window) {
        var lazyImages = document.querySelectorAll('img[loading="lazy"]');
        var imageObserver = new IntersectionObserver(function (entries) {
            entries.forEach(function (entry) {
                if (entry.isIntersecting) {
                    var img = entry.target;
                    if (img.dataset.src) {
                        img.src = img.dataset.src;
                        img.removeAttribute('data-src');
                    }
                    imageObserver.unobserve(img);
                }
            });
        });

        lazyImages.forEach(function (img) {
            imageObserver.observe(img);
        });
    }

    // ==========================================
    // Scroll to Top Button
    // ==========================================
    var scrollTopBtn = document.createElement('button');
    scrollTopBtn.className = 'scroll-top-btn';
    scrollTopBtn.innerHTML = '▲';
    scrollTopBtn.title = 'بازگشت به بالا';
    scrollTopBtn.style.cssText = 'position:fixed;bottom:24px;left:24px;width:44px;height:44px;border-radius:50%;background:var(--primary);color:white;border:none;font-size:16px;cursor:pointer;opacity:0;visibility:hidden;transition:all 0.3s ease;z-index:999;box-shadow:0 4px 12px rgba(107,76,154,0.3);';
    document.body.appendChild(scrollTopBtn);

    window.addEventListener('scroll', function () {
        if (window.scrollY > 400) {
            scrollTopBtn.style.opacity = '1';
            scrollTopBtn.style.visibility = 'visible';
        } else {
            scrollTopBtn.style.opacity = '0';
            scrollTopBtn.style.visibility = 'hidden';
        }
    });

    scrollTopBtn.addEventListener('click', function () {
        window.scrollTo({ top: 0, behavior: 'smooth' });
    });

    // ==========================================
    // Number formatting helper
    // ==========================================
    window.formatPrice = function (num) {
        return Number(num).toLocaleString('fa-IR');
    };

    // ==========================================
    // CSRF Token Helper
    // ==========================================
    window.getCSRFToken = function () {
        var cookie = document.cookie.split(';').find(function (c) {
            return c.trim().startsWith('csrftoken=');
        });
        return cookie ? cookie.split('=')[1] : '';
    };

});
