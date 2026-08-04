/**
 * Rayha Perfume — Main JavaScript
 */

document.addEventListener('DOMContentLoaded', function () {

    // ==========================================
    // Liquid Glass Search Overlay Toggle
    // ==========================================
    const searchToggleBtn = document.getElementById('search-toggle-btn');
    const searchOverlay = document.getElementById('glass-search-overlay');
    const searchCloseBtn = document.getElementById('glass-search-close');
    const searchInput = document.getElementById('glass-search-input');

    if (searchToggleBtn && searchOverlay) {
        searchToggleBtn.addEventListener('click', function (e) {
            e.stopPropagation();
            searchOverlay.classList.toggle('active');
            if (searchOverlay.classList.contains('active') && searchInput) {
                searchInput.focus();
            }
        });

        if (searchCloseBtn) {
            searchCloseBtn.addEventListener('click', function () {
                searchOverlay.classList.remove('active');
            });
        }

        document.addEventListener('click', function (e) {
            if (searchOverlay.classList.contains('active') && !searchOverlay.contains(e.target) && e.target !== searchToggleBtn) {
                searchOverlay.classList.remove('active');
            }
        });

        document.addEventListener('keydown', function (e) {
            if (e.key === 'Escape' && searchOverlay.classList.contains('active')) {
                searchOverlay.classList.remove('active');
            }
        });
    }

    // ==========================================
    // Glass Mobile Drawer Toggle
    // ==========================================
    const menuToggle = document.getElementById('mobile-menu-toggle');
    const mobileDrawer = document.getElementById('glass-mobile-drawer');
    const drawerCloseBtn = document.getElementById('mobile-drawer-close');
    const drawerBackdrop = document.getElementById('mobile-drawer-backdrop');

    if (menuToggle && mobileDrawer) {
        menuToggle.addEventListener('click', function (e) {
            e.stopPropagation();
            mobileDrawer.classList.add('active');
            document.body.style.overflow = 'hidden';
        });

        function closeDrawer() {
            mobileDrawer.classList.remove('active');
            document.body.style.overflow = '';
        }

        if (drawerCloseBtn) drawerCloseBtn.addEventListener('click', closeDrawer);
        if (drawerBackdrop) drawerBackdrop.addEventListener('click', closeDrawer);
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
    scrollTopBtn.innerHTML = '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="m18 15-6-6-6 6"/></svg>';
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
        var meta = document.querySelector('meta[name="csrf-token"]');
        if (meta && meta.getAttribute('content')) {
            return meta.getAttribute('content');
        }
        var cookie = document.cookie.split(';').find(function (c) {
            return c.trim().startsWith('csrftoken=');
        });
        return cookie ? cookie.split('=')[1] : '';
    };

});
