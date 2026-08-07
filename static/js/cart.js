/**
 * Rayha Perfume — Cart JavaScript (AJAX Operations)
 */

function getCSRF() {
    var meta = document.querySelector('meta[name="csrf-token"]');
    if (meta && meta.getAttribute('content')) {
        return meta.getAttribute('content');
    }
    var cookie = document.cookie.split(';').find(function (c) {
        return c.trim().startsWith('csrftoken=');
    });
    return cookie ? cookie.split('=')[1] : '';
}

var _toastIcons = {
    success: '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="#10B981"><path fill-rule="evenodd" d="M2.25 12c0-5.385 4.365-9.75 9.75-9.75s9.75 4.365 9.75 9.75-4.365 9.75-9.75 9.75S2.25 17.385 2.25 12zm13.36-1.814a.75.75 0 10-1.22-.872l-3.236 4.53L9.53 12.22a.75.75 0 00-1.06 1.06l2.25 2.25a.75.75 0 001.14-.094l3.75-5.25z" clip-rule="evenodd" /></svg>',
    error: '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="#EF4444"><path fill-rule="evenodd" d="M12 2.25c-5.385 0-9.75 4.365-9.75 9.75s4.365 9.75 9.75 9.75 9.75-4.365 9.75-9.75S17.385 2.25 12 2.25zm-1.72 6.97a.75.75 0 10-1.06 1.06L10.94 12l-1.72 1.72a.75.75 0 101.06 1.06L12 13.06l1.72 1.72a.75.75 0 101.06-1.06L13.06 12l1.72-1.72a.75.75 0 10-1.06-1.06L12 10.94l-1.72-1.72z" clip-rule="evenodd" /></svg>',
    warning: '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="#F59E0B"><path fill-rule="evenodd" d="M9.401 3.003c1.155-2 4.043-2 5.197 0l7.355 12.748c1.154 2-.29 4.5-2.599 4.5H4.645c-2.309 0-3.752-2.5-2.598-4.5L9.4 3.003zM12 8.25a.75.75 0 01.75.75v3.75a.75.75 0 01-1.5 0V9a.75.75 0 01.75-.75zm0 8.25a.75.75 0 100-1.5.75.75 0 000 1.5z" clip-rule="evenodd" /></svg>',
    info: '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="#3B82F6"><path fill-rule="evenodd" d="M2.25 12c0-5.385 4.365-9.75 9.75-9.75s9.75 4.365 9.75 9.75-4.365 9.75-9.75 9.75S2.25 17.385 2.25 12zm8.706-1.442c1.146-.573 2.437.463 2.126 1.706l-.709 2.836.042-.02a.75.75 0 01.67 1.34l-.04.022c-1.147.573-2.438-.463-2.127-1.706l.71-2.836-.042.02a.75.75 0 11-.671-1.34l.041-.022zM12 9a.75.75 0 100-1.5.75.75 0 000 1.5z" clip-rule="evenodd" /></svg>'
};

var _toastColors = {
    success: { text: '#059669', bar: 'linear-gradient(90deg, #10B981, #34d399)' },
    error:   { text: '#DC2626', bar: 'linear-gradient(90deg, #EF4444, #f87171)' },
    warning: { text: '#D97706', bar: 'linear-gradient(90deg, #F59E0B, #fbbf24)' },
    info:    { text: '#2563EB', bar: 'linear-gradient(90deg, #3B82F6, #60a5fa)' }
};

function showToast(message, type) {
    type = type || 'success';
    var duration = 4000;

    var container = document.getElementById('toast-stack');
    if (!container) {
        container = document.createElement('div');
        container.id = 'toast-stack';
        container.className = 'toast-stack';
        document.body.appendChild(container);
    }

    var colors = _toastColors[type] || _toastColors.success;
    var icon = _toastIcons[type] || _toastIcons.success;

    var toast = document.createElement('div');
    toast.className = 'site-toast';
    toast.innerHTML =
        '<div class="site-toast-content">' +
            '<div class="site-toast-right">' +
                '<button class="site-toast-close" aria-label="بستن">&times;</button>' +
                '<span class="site-toast-icon">' + icon + '</span>' +
                '<span class="site-toast-text" style="color:' + colors.text + '">' + message + '</span>' +
            '</div>' +
        '</div>' +
        '<div class="site-toast-progress">' +
            '<div class="site-toast-progress-bar" style="background:' + colors.bar + '"></div>' +
        '</div>';

    container.appendChild(toast);

    // Close button
    toast.querySelector('.site-toast-close').addEventListener('click', function () {
        dismissToast(toast);
    });

    // Force reflow then show
    void toast.offsetWidth;
    toast.classList.add('show');

    // Start progress bar
    var bar = toast.querySelector('.site-toast-progress-bar');
    bar.style.animation = 'cart-notification-timeout ' + duration + 'ms linear forwards';

    // Auto dismiss
    var timer = setTimeout(function () {
        dismissToast(toast);
    }, duration);

    toast._timer = timer;
}

function dismissToast(toast) {
    if (!toast || toast._dismissed) return;
    toast._dismissed = true;
    if (toast._timer) clearTimeout(toast._timer);

    toast.classList.remove('show');
    toast.classList.add('hide');

    setTimeout(function () {
        toast.remove();
        // Remove container if empty
        var container = document.getElementById('toast-stack');
        if (container && container.children.length === 0) {
            container.remove();
        }
    }, 400);
}


function updateCartBadge(count) {
    var badge = document.getElementById('cart-badge');
    if (count > 0) {
        if (badge) {
            badge.textContent = count;
        } else {
            var cartAction = document.querySelector('.cart-action');
            if (cartAction) {
                badge = document.createElement('span');
                badge.className = 'cart-badge';
                badge.id = 'cart-badge';
                badge.textContent = count;
                cartAction.appendChild(badge);
            }
        }
    } else {
        if (badge) badge.remove();
    }
}

/**
 * Cart Floating Notification
 */
var _cartNotificationTimer = null;

function showCartNotification(duration) {
    duration = duration || 4000;
    var notification = document.getElementById('cart-notification');
    var progressBar = document.getElementById('cart-notification-progress-bar');
    if (!notification || !progressBar) return;

    // Clear any existing timer
    if (_cartNotificationTimer) {
        clearTimeout(_cartNotificationTimer);
        _cartNotificationTimer = null;
    }

    // Reset animation
    notification.classList.remove('show', 'hide');
    progressBar.style.animation = 'none';

    // Force reflow to restart animation
    void notification.offsetWidth;

    // Show notification
    notification.classList.add('show');

    // Start progress bar animation
    progressBar.style.animation = 'cart-notification-timeout ' + duration + 'ms linear forwards';

    // Auto-hide after duration
    _cartNotificationTimer = setTimeout(function () {
        hideCartNotification();
    }, duration);
}

function hideCartNotification() {
    var notification = document.getElementById('cart-notification');
    if (!notification) return;

    if (_cartNotificationTimer) {
        clearTimeout(_cartNotificationTimer);
        _cartNotificationTimer = null;
    }

    notification.classList.remove('show');
    notification.classList.add('hide');

    // Reset after transition
    setTimeout(function () {
        notification.classList.remove('hide');
        var progressBar = document.getElementById('cart-notification-progress-bar');
        if (progressBar) progressBar.style.animation = 'none';
    }, 400);
}

/**
 * Add to Cart
 */
function addToCart(variantId, quantity) {
    quantity = quantity || 1;
    var formData = new FormData();
    formData.append('variant_id', variantId);
    formData.append('quantity', quantity);

    fetch('/cart/add/', {
        method: 'POST',
        headers: {
            'X-CSRFToken': getCSRF(),
            'X-Requested-With': 'XMLHttpRequest',
        },
        body: formData,
    })
    .then(function (res) { return res.json(); })
    .then(function (data) {
        if (data.error) {
            showToast(data.error, 'error');
        } else {
            showCartNotification(4000);
            updateCartBadge(data.cart_count);
        }
    })
    .catch(function () {
        showToast('خطا در ارتباط با سرور', 'error');
    });
}

/**
 * Remove from Cart
 */
function removeFromCart(variantId) {
    var formData = new FormData();
    formData.append('variant_id', variantId);

    fetch('/cart/remove/', {
        method: 'POST',
        headers: {
            'X-CSRFToken': getCSRF(),
            'X-Requested-With': 'XMLHttpRequest',
        },
        body: formData,
    })
    .then(function (res) { return res.json(); })
    .then(function (data) {
        if (data.error) {
            showToast(data.error, 'error');
        } else {
            showToast(data.message, 'success');
            updateCartBadge(data.cart_count);

            // Remove item from DOM
            var item = document.getElementById('cart-item-' + variantId);
            if (item) {
                item.style.opacity = '0';
                item.style.transform = 'translateX(50px)';
                setTimeout(function () {
                    item.remove();
                    updateCartSummary(data);
                    // Check if cart is empty
                    if (data.cart_count === 0) {
                        location.reload();
                    }
                }, 300);
            }
        }
    })
    .catch(function () {
        showToast('خطا در ارتباط با سرور', 'error');
    });
}

/**
 * Update Cart Quantity
 */
function updateCart(variantId, quantity) {
    if (quantity < 1) {
        removeFromCart(variantId);
        return;
    }

    var formData = new FormData();
    formData.append('variant_id', variantId);
    formData.append('quantity', quantity);

    fetch('/cart/update/', {
        method: 'POST',
        headers: {
            'X-CSRFToken': getCSRF(),
            'X-Requested-With': 'XMLHttpRequest',
        },
        body: formData,
    })
    .then(function (res) { return res.json(); })
    .then(function (data) {
        if (data.error) {
            showToast(data.error, 'error');
        } else {
            updateCartBadge(data.cart_count);
            updateCartSummary(data);

            // Update item total
            var itemTotal = document.getElementById('item-total-' + variantId);
            if (itemTotal) {
                itemTotal.textContent = Number(data.item_total).toLocaleString('fa-IR');
            }

            // Reload to update quantity displays
            location.reload();
        }
    })
    .catch(function () {
        showToast('خطا در ارتباط با سرور', 'error');
    });
}

/**
 * Update cart summary section
 */
function updateCartSummary(data) {
    var totalOriginal = document.getElementById('total-original');
    var totalDiscount = document.getElementById('total-discount');
    var totalPrice = document.getElementById('total-price');

    if (totalOriginal) {
        totalOriginal.textContent = Number(data.total_original_price).toLocaleString('fa-IR') + ' تومان';
    }
    if (totalDiscount) {
        totalDiscount.textContent = Number(data.total_discount).toLocaleString('fa-IR') + ' تومان';
    }
    if (totalPrice) {
        totalPrice.textContent = Number(data.total_price).toLocaleString('fa-IR') + ' تومان';
    }
}

/**
 * Toggle Wishlist
 */
function toggleWishlist(perfumeId, btn) {
    var formData = new FormData();
    formData.append('perfume_id', perfumeId);

    fetch('/products/wishlist/toggle/', {
        method: 'POST',
        headers: {
            'X-CSRFToken': getCSRF(),
            'X-Requested-With': 'XMLHttpRequest',
        },
        body: formData,
    })
    .then(function (res) { return res.json(); })
    .then(function (data) {
        if (data.error) {
            showToast(data.error, 'error');
        } else {
            showToast(data.message, 'success');
            if (btn) {
                btn.classList.toggle('active');
                var svg = btn.querySelector('svg');
                if (svg) {
                    svg.setAttribute('fill', data.status === 'added' ? 'currentColor' : 'none');
                }
            }
        }
    })
    .catch(function () {
        showToast('خطا در ارتباط با سرور', 'error');
    });
}

/**
 * Apply Coupon
 */
document.addEventListener('DOMContentLoaded', function () {
    var applyCouponBtn = document.getElementById('apply-coupon-btn');
    if (applyCouponBtn) {
        applyCouponBtn.addEventListener('click', function () {
            var code = document.getElementById('coupon-input').value.trim();
            if (!code) {
                showToast('لطفاً کد تخفیف را وارد کنید', 'warning');
                return;
            }

            var formData = new FormData();
            formData.append('code', code);

            fetch('/orders/coupon/apply/', {
                method: 'POST',
                headers: {
                    'X-CSRFToken': getCSRF(),
                    'X-Requested-With': 'XMLHttpRequest',
                },
                body: formData,
            })
            .then(function (res) { return res.json(); })
            .then(function (data) {
                if (data.error) {
                    showToast(data.error, 'error');
                } else {
                    showToast(data.message, 'success');
                    location.reload();
                }
            })
            .catch(function () {
                showToast('خطا در ارتباط با سرور', 'error');
            });
        });
    }

    var removeCouponBtn = document.getElementById('remove-coupon-btn');
    if (removeCouponBtn) {
        removeCouponBtn.addEventListener('click', function () {
            fetch('/orders/coupon/remove/', {
                method: 'POST',
                headers: {
                    'X-CSRFToken': getCSRF(),
                    'X-Requested-With': 'XMLHttpRequest',
                },
            })
            .then(function () { location.reload(); })
            .catch(function () {
                showToast('خطا', 'error');
            });
        });
    }
});
