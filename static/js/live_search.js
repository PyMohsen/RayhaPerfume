/**
 * Rayha Perfume — Live Search (Autocomplete)
 * جستجوی لحظه‌ای با تکمیل خودکار
 * Supports both desktop (glass-search-input) and mobile (mobile-search-input)
 */

(function () {
    'use strict';

    // ==========================================
    // Configuration
    // ==========================================
    var DEBOUNCE_DELAY = 300;
    var MIN_QUERY_LENGTH = 2;
    var API_URL = '/products/api/live-search/';
    var SEARCH_URL = '/products/search/';

    // ==========================================
    // Desktop DOM Elements
    // ==========================================
    var desktopInput = document.getElementById('glass-search-input');
    var desktopDropdown = document.getElementById('live-search-dropdown');
    var searchOverlay = document.getElementById('glass-search-overlay');

    // ==========================================
    // Mobile DOM Elements
    // ==========================================
    var mobileInput = document.getElementById('mobile-search-input');
    var mobileDropdown = document.getElementById('mobile-live-search-dropdown');

    // If neither input exists, bail
    if (!desktopInput && !mobileInput) return;

    // ==========================================
    // Utility: Format Price in Persian
    // ==========================================
    function formatPrice(num) {
        if (!num) return '۰';
        return Number(num).toLocaleString('fa-IR');
    }

    // ==========================================
    // Utility: Convert to Persian Digits
    // ==========================================
    function toPersianDigits(str) {
        var persian = ['۰', '۱', '۲', '۳', '۴', '۵', '۶', '۷', '۸', '۹'];
        return String(str).replace(/[0-9]/g, function (d) {
            return persian[parseInt(d)];
        });
    }

    // ==========================================
    // Dynamically build dropdown DOM elements on first search
    // (Prevents crawler SERP indexing of empty/loading states)
    // ==========================================
    function ensureDropdownElements(ctx) {
        if (ctx.resultsContainer) return;
        var dropdown = ctx.dropdown;
        if (!dropdown) return;

        // Loading state
        var loading = document.createElement('div');
        loading.className = 'live-search-loading';
        loading.id = ctx.prefix + '-loading';
        loading.style.display = 'none';
        loading.innerHTML = '<div class="live-search-spinner"></div><span>در حال جستجو...</span>';
        dropdown.appendChild(loading);
        ctx.loadingEl = loading;

        // Results container
        var results = document.createElement('div');
        results.className = 'live-search-results';
        results.id = ctx.prefix + '-results';
        results.style.display = 'none';
        dropdown.appendChild(results);
        ctx.resultsContainer = results;

        // Empty state
        var empty = document.createElement('div');
        empty.className = 'live-search-empty';
        empty.id = ctx.prefix + '-empty';
        empty.style.display = 'none';
        empty.innerHTML =
            '<svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" opacity="0.4">' +
                '<circle cx="11" cy="11" r="8" />' +
                '<path d="m21 21-4.35-4.35" />' +
            '</svg>' +
            '<span>نتیجه‌ای یافت نشد</span>';
        dropdown.appendChild(empty);
        ctx.emptyEl = empty;

        // View All Link
        var viewAll = document.createElement('a');
        viewAll.href = '#';
        viewAll.className = 'live-search-view-all';
        viewAll.id = ctx.prefix + '-view-all';
        viewAll.style.display = 'none';
        viewAll.innerHTML =
            '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">' +
                '<circle cx="11" cy="11" r="8" />' +
                '<path d="m21 21-4.35-4.35" />' +
            '</svg>' +
            '<span>مشاهده همه نتایج (<span id="' + ctx.prefix + '-total">0</span>)</span>' +
            '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" class="arrow-icon">' +
                '<path d="m15 18-6-6 6-6" />' +
            '</svg>';
        dropdown.appendChild(viewAll);
        ctx.viewAllEl = viewAll;
        ctx.totalEl = viewAll.querySelector('#' + ctx.prefix + '-total');
    }

    // ==========================================
    // Create a search context for each mode
    // ==========================================
    function createSearchContext(input, dropdown, prefix) {
        if (!input || !dropdown) return null;

        var ctx = {
            input: input,
            dropdown: dropdown,
            prefix: prefix,
            resultsContainer: null,
            loadingEl: null,
            emptyEl: null,
            viewAllEl: null,
            totalEl: null,
            debounceTimer: null,
            currentRequest: null,
            activeIndex: -1,
            currentResults: []
        };

        // Show/Hide Helpers
        ctx.showDropdown = function () {
            ctx.dropdown.classList.add('active');
        };

        ctx.hideDropdown = function () {
            ctx.dropdown.classList.remove('active');
            ctx.activeIndex = -1;
            ctx.clearHighlight();
        };

        ctx.showLoading = function () {
            ensureDropdownElements(ctx);
            ctx.loadingEl.style.display = 'flex';
            ctx.resultsContainer.style.display = 'none';
            ctx.emptyEl.style.display = 'none';
            ctx.viewAllEl.style.display = 'none';
            ctx.showDropdown();
        };

        ctx.showResults = function () {
            ensureDropdownElements(ctx);
            ctx.loadingEl.style.display = 'none';
            ctx.resultsContainer.style.display = 'block';
            ctx.emptyEl.style.display = 'none';
            ctx.viewAllEl.style.display = 'flex';
            ctx.showDropdown();
        };

        ctx.showEmpty = function () {
            ensureDropdownElements(ctx);
            ctx.loadingEl.style.display = 'none';
            ctx.resultsContainer.style.display = 'none';
            ctx.emptyEl.style.display = 'flex';
            ctx.viewAllEl.style.display = 'none';
            ctx.showDropdown();
        };

        ctx.hideAll = function () {
            if (ctx.loadingEl) ctx.loadingEl.style.display = 'none';
            if (ctx.resultsContainer) ctx.resultsContainer.style.display = 'none';
            if (ctx.emptyEl) ctx.emptyEl.style.display = 'none';
            if (ctx.viewAllEl) ctx.viewAllEl.style.display = 'none';
            ctx.hideDropdown();
        };

        ctx.clearHighlight = function () {
            if (!ctx.resultsContainer) return;
            var items = ctx.resultsContainer.querySelectorAll('.live-search-item');
            for (var i = 0; i < items.length; i++) {
                items[i].classList.remove('active');
            }
        };

        ctx.highlightItem = function (index) {
            if (!ctx.resultsContainer) return;
            var items = ctx.resultsContainer.querySelectorAll('.live-search-item');
            if (index < 0 || index >= items.length) return;
            ctx.clearHighlight();
            items[index].classList.add('active');
            items[index].scrollIntoView({ block: 'nearest' });
        };

        return ctx;
    }

    // ==========================================
    // Render a Single Result Item
    // ==========================================
    function renderResultItem(item, index, ctx) {
        var div = document.createElement('a');
        div.className = 'live-search-item';
        div.href = item.url;
        div.setAttribute('data-index', index);

        // Image
        var imgWrap = document.createElement('div');
        imgWrap.className = 'live-search-item-image';
        if (item.image_url) {
            var img = document.createElement('img');
            img.src = item.image_url;
            img.alt = item.name;
            img.loading = 'lazy';
            imgWrap.appendChild(img);
        } else {
            imgWrap.innerHTML = '<svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1" opacity="0.3"><rect x="3" y="3" width="18" height="18" rx="2" ry="2"/><circle cx="8.5" cy="8.5" r="1.5"/><polyline points="21 15 16 10 5 21"/></svg>';
        }

        // Info
        var info = document.createElement('div');
        info.className = 'live-search-item-info';

        var title = document.createElement('div');
        title.className = 'live-search-item-title';
        title.textContent = item.name;

        var brand = document.createElement('div');
        brand.className = 'live-search-item-brand';
        brand.textContent = item.brand;
        if (item.gender) {
            brand.textContent += ' · ' + item.gender;
        }

        info.appendChild(title);
        info.appendChild(brand);

        // Price
        var priceWrap = document.createElement('div');
        priceWrap.className = 'live-search-item-price';

        if (!item.is_available) {
            priceWrap.innerHTML = '<span class="live-search-unavailable">ناموجود</span>';
        } else if (item.has_discount) {
            priceWrap.innerHTML =
                '<span class="live-search-discount-badge">-' + toPersianDigits(item.discount_percent) + '٪</span>' +
                '<div class="live-search-price-stack">' +
                '<span class="live-search-original-price">' + formatPrice(item.price) + '</span>' +
                '<span class="live-search-final-price">' + formatPrice(item.final_price) + ' <small>تومان</small></span>' +
                '</div>';
        } else {
            priceWrap.innerHTML = '<span class="live-search-final-price">' + formatPrice(item.price) + ' <small>تومان</small></span>';
        }

        div.appendChild(imgWrap);
        div.appendChild(info);
        div.appendChild(priceWrap);

        // Hover events
        div.addEventListener('mouseenter', function () {
            ctx.activeIndex = index;
            ctx.clearHighlight();
            div.classList.add('active');
        });

        div.addEventListener('mouseleave', function () {
            div.classList.remove('active');
        });

        return div;
    }

    // ==========================================
    // Render All Results
    // ==========================================
    function renderResults(data, ctx) {
        ctx.resultsContainer.innerHTML = '';
        ctx.currentResults = data.results;
        ctx.activeIndex = -1;

        if (!data.results || data.results.length === 0) {
            ctx.showEmpty();
            return;
        }

        for (var i = 0; i < data.results.length; i++) {
            ctx.resultsContainer.appendChild(renderResultItem(data.results[i], i, ctx));
        }

        // Update total count and view-all link
        ctx.totalEl.textContent = toPersianDigits(data.total);
        ctx.viewAllEl.href = SEARCH_URL + '?q=' + encodeURIComponent(data.query);

        ctx.showResults();
    }

    // ==========================================
    // Fetch Search Results
    // ==========================================
    function fetchResults(query, ctx) {
        // Cancel previous request
        if (ctx.currentRequest) {
            ctx.currentRequest.abort();
        }

        ctx.showLoading();

        var controller = new AbortController();
        ctx.currentRequest = controller;

        fetch(API_URL + '?q=' + encodeURIComponent(query), {
            signal: controller.signal,
        })
            .then(function (response) {
                if (!response.ok) throw new Error('Network error');
                return response.json();
            })
            .then(function (data) {
                ctx.currentRequest = null;
                renderResults(data, ctx);
            })
            .catch(function (err) {
                ctx.currentRequest = null;
                if (err.name !== 'AbortError') {
                    ctx.hideAll();
                }
            });
    }

    // ==========================================
    // Initialize a search context with event listeners
    // ==========================================
    function initSearchContext(ctx) {
        if (!ctx) return;

        // Debounced input handler
        ctx.input.addEventListener('input', function () {
            var query = ctx.input.value.trim();

            if (ctx.debounceTimer) {
                clearTimeout(ctx.debounceTimer);
            }

            if (query.length < MIN_QUERY_LENGTH) {
                ctx.hideAll();
                return;
            }

            ctx.debounceTimer = setTimeout(function () {
                fetchResults(query, ctx);
            }, DEBOUNCE_DELAY);
        });

        // Keyboard navigation
        ctx.input.addEventListener('keydown', function (e) {
            if (!ctx.resultsContainer) return;
            var items = ctx.resultsContainer.querySelectorAll('.live-search-item');
            if (!ctx.dropdown.classList.contains('active') || items.length === 0) return;

            switch (e.key) {
                case 'ArrowDown':
                    e.preventDefault();
                    ctx.activeIndex = (ctx.activeIndex + 1) % items.length;
                    ctx.highlightItem(ctx.activeIndex);
                    break;

                case 'ArrowUp':
                    e.preventDefault();
                    ctx.activeIndex = (ctx.activeIndex - 1 + items.length) % items.length;
                    ctx.highlightItem(ctx.activeIndex);
                    break;

                case 'Enter':
                    if (ctx.activeIndex >= 0 && ctx.activeIndex < items.length) {
                        e.preventDefault();
                        window.location.href = items[ctx.activeIndex].href;
                    }
                    break;

                case 'Escape':
                    ctx.hideAll();
                    break;
            }
        });

        // Close on outside click
        document.addEventListener('click', function (e) {
            if (!ctx.dropdown.contains(e.target) && e.target !== ctx.input) {
                ctx.hideAll();
            }
        });

        // Initialize hidden state
        ctx.hideAll();
    }

    // ==========================================
    // Create and initialize desktop search
    // ==========================================
    var desktopCtx = createSearchContext(desktopInput, desktopDropdown, 'live-search');
    initSearchContext(desktopCtx);

    // Close desktop dropdown when search overlay closes
    if (desktopCtx && searchOverlay) {
        var observer = new MutationObserver(function (mutations) {
            mutations.forEach(function (mutation) {
                if (mutation.attributeName === 'class') {
                    if (!searchOverlay.classList.contains('active')) {
                        desktopCtx.hideAll();
                    }
                }
            });
        });
        observer.observe(searchOverlay, { attributes: true });
    }

    // ==========================================
    // Create and initialize mobile search
    // ==========================================
    var mobileCtx = createSearchContext(mobileInput, mobileDropdown, 'mobile-live-search');
    initSearchContext(mobileCtx);

})();
