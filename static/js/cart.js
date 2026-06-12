/**
 * Rayha Perfume — Cart JavaScript (AJAX Operations)
 */

function getCSRF() {
    var cookie = document.cookie.split(';').find(function (c) {
        return c.trim().startsWith('csrftoken=');
    });
    return cookie ? cookie.split('=')[1] : '';
}

function showToast(message, type) {
    type = type || 'success';
    var container = document.getElementById('messages-container');
    if (!container) {
        container = document.createElement('div');
        container.id = 'messages-container';
        container.className = 'messages-container';
        document.body.appendChild(container);
    }

    var msg = document.createElement('div');
    msg.className = 'message message-' + type;
    msg.innerHTML = '<span class="message-text">' + message + '</span><button class="message-close" onclick="this.parentElement.remove()">&times;</button>';
    container.appendChild(msg);

    setTimeout(function () {
        msg.style.opacity = '0';
        msg.style.transform = 'translateY(-20px)';
        setTimeout(function () { msg.remove(); }, 300);
    }, 3000);
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
            showToast(data.message, 'success');
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
