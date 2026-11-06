/**
 * Rayha Perfume — Main JavaScript
 */

document.addEventListener('DOMContentLoaded', function () {

    // ==========================================
    // Search Auto-Focus Helper
    // ==========================================
    function focusSearchInput(input) {
        if (!input) return;

        // Immediate focus
        input.focus({ preventScroll: true });

        // Next frame focus (after DOM reflow)
        requestAnimationFrame(function () {
            input.focus({ preventScroll: true });
        });

        // 50ms fallback to guarantee focus after CSS transition / visibility changes
        setTimeout(function () {
            input.focus({ preventScroll: true });
            if (input.value && typeof input.setSelectionRange === 'function') {
                var len = input.value.length;
                input.setSelectionRange(len, len);
            }
        }, 50);

        // 120ms safety check
        setTimeout(function () {
            if (document.activeElement !== input) {
                input.focus({ preventScroll: true });
            }
        }, 120);
    }

    // ==========================================
    // Liquid Glass Search Overlay Toggle (Desktop)
    // ==========================================
    const searchToggleBtn = document.getElementById('search-toggle-btn');
    const searchOverlay = document.getElementById('glass-search-overlay');
    const searchCloseBtn = document.getElementById('glass-search-close');
    const searchInput = document.getElementById('glass-search-input');
    const searchBox = searchOverlay ? searchOverlay.querySelector('.glass-search-box') : null;

    function openSearchOverlay() {
        if (!searchOverlay) return;
        searchOverlay.classList.add('active');
        focusSearchInput(searchInput);
    }

    function closeSearchOverlay() {
        if (!searchOverlay) return;
        searchOverlay.classList.remove('active');
        if (searchInput) {
            searchInput.blur();
        }
    }

    if (searchToggleBtn && searchOverlay) {
        searchToggleBtn.addEventListener('click', function (e) {
            e.preventDefault();
            e.stopPropagation();
            if (searchOverlay.classList.contains('active')) {
                closeSearchOverlay();
            } else {
                openSearchOverlay();
            }
        });

        if (searchCloseBtn) {
            searchCloseBtn.addEventListener('click', function (e) {
                e.preventDefault();
                e.stopPropagation();
                closeSearchOverlay();
            });
        }

        // Clicking on the search box background also focuses the search input
        if (searchBox && searchInput) {
            searchBox.addEventListener('click', function (e) {
                if (!e.target.closest('button') && !e.target.closest('a') && !e.target.closest('.live-search-dropdown')) {
                    focusSearchInput(searchInput);
                }
            });
        }

        // Click outside closes overlay
        document.addEventListener('click', function (e) {
            if (searchOverlay.classList.contains('active')) {
                if (!searchOverlay.contains(e.target) && !searchToggleBtn.contains(e.target)) {
                    closeSearchOverlay();
                }
            }
        });

        // Escape key closes overlay
        document.addEventListener('keydown', function (e) {
            if (e.key === 'Escape' && searchOverlay.classList.contains('active')) {
                closeSearchOverlay();
            }
        });

        // MutationObserver: whenever overlay becomes active (regardless of trigger), auto-focus input
        if (window.MutationObserver && searchInput) {
            let wasActive = searchOverlay.classList.contains('active');
            const overlayObserver = new MutationObserver(function () {
                const isActive = searchOverlay.classList.contains('active');
                if (isActive && !wasActive) {
                    focusSearchInput(searchInput);
                }
                wasActive = isActive;
            });
            overlayObserver.observe(searchOverlay, { attributes: true, attributeFilter: ['class'] });
        }
    }

    // ==========================================
    // Mobile Search Expansion — Full Navbar Takeover
    // ==========================================
    const mobileSearchInput = document.getElementById('mobile-search-input');
    const mobileSearchPill = document.querySelector('.glass-pill-mobile-search');
    const mobileSearchCloseBtn = document.getElementById('mobile-search-close-btn');
    const mobileSearchIcon = document.querySelector('.mobile-search-icon');
    const navbarInner = document.querySelector('.floating-navbar-inner');

    function isMobileView() {
        return window.innerWidth <= 768;
    }

    function expandMobileSearch() {
        if (!isMobileView() || !navbarInner) return;
        navbarInner.classList.add('mobile-search-expanded');
        if (mobileSearchInput) {
            focusSearchInput(mobileSearchInput);
        }
    }

    function collapseMobileSearch() {
        if (!navbarInner) return;
        navbarInner.classList.remove('mobile-search-expanded');
        if (mobileSearchInput) {
            mobileSearchInput.blur();
        }
    }

    if (mobileSearchPill && mobileSearchInput) {
        // Expand when clicking the search pill area
        mobileSearchPill.addEventListener('click', function (e) {
            if (e.target.closest('.mobile-search-close-btn')) return;
            expandMobileSearch();
        });

        // Search icon click inside mobile pill: expand & focus instead of submitting empty form
        if (mobileSearchIcon) {
            mobileSearchIcon.addEventListener('click', function (e) {
                if (!navbarInner.classList.contains('mobile-search-expanded') || !mobileSearchInput.value.trim()) {
                    e.preventDefault();
                    e.stopPropagation();
                    expandMobileSearch();
                    focusSearchInput(mobileSearchInput);
                }
            });
        }

        mobileSearchInput.addEventListener('focus', function () {
            expandMobileSearch();
        });

        // Collapse when clicking the close button
        if (mobileSearchCloseBtn) {
            mobileSearchCloseBtn.addEventListener('click', function (e) {
                e.preventDefault();
                e.stopPropagation();
                collapseMobileSearch();
            });
        }

        // Collapse when clicking outside the search pill
        document.addEventListener('click', function (e) {
            if (navbarInner && navbarInner.classList.contains('mobile-search-expanded')) {
                if (!mobileSearchPill.contains(e.target)) {
                    collapseMobileSearch();
                }
            }
        });

        // Collapse on Escape key
        document.addEventListener('keydown', function (e) {
            if (e.key === 'Escape' && navbarInner && navbarInner.classList.contains('mobile-search-expanded')) {
                collapseMobileSearch();
            }
        });

        // MutationObserver for mobile search expansion
        if (window.MutationObserver && navbarInner) {
            let wasExpanded = navbarInner.classList.contains('mobile-search-expanded');
            const mobileObserver = new MutationObserver(function () {
                const isExpanded = navbarInner.classList.contains('mobile-search-expanded');
                if (isExpanded && !wasExpanded) {
                    focusSearchInput(mobileSearchInput);
                }
                wasExpanded = isExpanded;
            });
            mobileObserver.observe(navbarInner, { attributes: true, attributeFilter: ['class'] });
        }
    }

    // ==========================================
    // Keyboard Shortcut (e.g. '/' or Ctrl+K / Cmd+K)
    // ==========================================
    document.addEventListener('keydown', function (e) {
        const activeTag = document.activeElement ? document.activeElement.tagName.toLowerCase() : '';
        const isEditing = activeTag === 'input' || activeTag === 'textarea' || (document.activeElement && document.activeElement.isContentEditable);

        if ((e.key === '/' && !isEditing) || ((e.ctrlKey || e.metaKey) && (e.key === 'k' || e.key === 'K'))) {
            e.preventDefault();
            if (isMobileView()) {
                expandMobileSearch();
            } else {
                openSearchOverlay();
            }
        }
    });

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
