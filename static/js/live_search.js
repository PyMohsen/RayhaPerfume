/**
 * Rayha Perfume — Live Search (Autocomplete)
 * جستجوی لحظه‌ای با تکمیل خودکار
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
    // DOM Elements
    // ==========================================
    var searchInput = document.getElementById('glass-search-input');
    var dropdown = document.getElementById('live-search-dropdown');
    var resultsContainer = document.getElementById('live-search-results');
    var loadingEl = document.getElementById('live-search-loading');
    var emptyEl = document.getElementById('live-search-empty');
    var viewAllEl = document.getElementById('live-search-view-all');
    var totalEl = document.getElementById('live-search-total');
    var searchOverlay = document.getElementById('glass-search-overlay');

    if (!searchInput || !dropdown) return;

    // ==========================================
    // State
    // ==========================================
    var debounceTimer = null;
    var currentRequest = null;
    var activeIndex = -1;
    var currentResults = [];

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
    // Show/Hide Helpers
    // ==========================================
    function showDropdown() {
        dropdown.classList.add('active');
    }

    function hideDropdown() {
        dropdown.classList.remove('active');
        activeIndex = -1;
        clearHighlight();
    }

    function showLoading() {
        loadingEl.style.display = 'flex';
        resultsContainer.style.display = 'none';
        emptyEl.style.display = 'none';
        viewAllEl.style.display = 'none';
        showDropdown();
    }

    function showResults() {
        loadingEl.style.display = 'none';
        resultsContainer.style.display = 'block';
        emptyEl.style.display = 'none';
        viewAllEl.style.display = 'flex';
        showDropdown();
    }

    function showEmpty() {
        loadingEl.style.display = 'none';
        resultsContainer.style.display = 'none';
        emptyEl.style.display = 'flex';
        viewAllEl.style.display = 'none';
        showDropdown();
    }

    function hideAll() {
        loadingEl.style.display = 'none';
        resultsContainer.style.display = 'none';
        emptyEl.style.display = 'none';
        viewAllEl.style.display = 'none';
        hideDropdown();
    }

    // ==========================================
    // Render a Single Result Item
    // ==========================================
    function renderResultItem(item, index) {
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
            activeIndex = index;
            clearHighlight();
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
    function renderResults(data) {
        resultsContainer.innerHTML = '';
        currentResults = data.results;
        activeIndex = -1;

        if (!data.results || data.results.length === 0) {
            showEmpty();
            return;
        }

        for (var i = 0; i < data.results.length; i++) {
            resultsContainer.appendChild(renderResultItem(data.results[i], i));
        }

        // Update total count and view-all link
        totalEl.textContent = toPersianDigits(data.total);
        viewAllEl.href = SEARCH_URL + '?q=' + encodeURIComponent(data.query);

        showResults();
    }

    // ==========================================
    // Fetch Search Results
    // ==========================================
    function fetchResults(query) {
        // Cancel previous request
        if (currentRequest) {
            currentRequest.abort();
        }

        showLoading();

        var controller = new AbortController();
        currentRequest = controller;

        fetch(API_URL + '?q=' + encodeURIComponent(query), {
            signal: controller.signal,
        })
            .then(function (response) {
                if (!response.ok) throw new Error('Network error');
                return response.json();
            })
            .then(function (data) {
                currentRequest = null;
                renderResults(data);
            })
            .catch(function (err) {
                currentRequest = null;
                if (err.name !== 'AbortError') {
                    hideAll();
                }
            });
    }

    // ==========================================
    // Debounce Input Handler
    // ==========================================
    searchInput.addEventListener('input', function () {
        var query = searchInput.value.trim();

        if (debounceTimer) {
            clearTimeout(debounceTimer);
        }

        if (query.length < MIN_QUERY_LENGTH) {
            hideAll();
            return;
        }

        debounceTimer = setTimeout(function () {
            fetchResults(query);
        }, DEBOUNCE_DELAY);
    });

    // ==========================================
    // Keyboard Navigation
    // ==========================================
    function clearHighlight() {
        var items = resultsContainer.querySelectorAll('.live-search-item');
        for (var i = 0; i < items.length; i++) {
            items[i].classList.remove('active');
        }
    }

    function highlightItem(index) {
        var items = resultsContainer.querySelectorAll('.live-search-item');
        if (index < 0 || index >= items.length) return;

        clearHighlight();
        items[index].classList.add('active');
        items[index].scrollIntoView({ block: 'nearest' });
    }

    searchInput.addEventListener('keydown', function (e) {
        var items = resultsContainer.querySelectorAll('.live-search-item');
        if (!dropdown.classList.contains('active') || items.length === 0) return;

        switch (e.key) {
            case 'ArrowDown':
                e.preventDefault();
                activeIndex = (activeIndex + 1) % items.length;
                highlightItem(activeIndex);
                break;

            case 'ArrowUp':
                e.preventDefault();
                activeIndex = (activeIndex - 1 + items.length) % items.length;
                highlightItem(activeIndex);
                break;

            case 'Enter':
                if (activeIndex >= 0 && activeIndex < items.length) {
                    e.preventDefault();
                    window.location.href = items[activeIndex].href;
                }
                break;

            case 'Escape':
                hideAll();
                break;
        }
    });

    // ==========================================
    // Close on outside click
    // ==========================================
    document.addEventListener('click', function (e) {
        if (!dropdown.contains(e.target) && e.target !== searchInput) {
            hideAll();
        }
    });

    // ==========================================
    // Close dropdown when search overlay closes
    // ==========================================
    if (searchOverlay) {
        var observer = new MutationObserver(function (mutations) {
            mutations.forEach(function (mutation) {
                if (mutation.attributeName === 'class') {
                    if (!searchOverlay.classList.contains('active')) {
                        hideAll();
                    }
                }
            });
        });
        observer.observe(searchOverlay, { attributes: true });
    }

    // Initialize hidden state
    hideAll();

})();
