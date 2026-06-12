from .cart import Cart


def cart_context(request):
    """سبد خرید برای دسترسی در تمام قالب‌ها"""
    cart = Cart(request)
    return {
        'cart': cart,
        'cart_count': len(cart),
    }
