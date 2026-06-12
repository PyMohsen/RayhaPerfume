from django.contrib import messages
from django.http import JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.http import require_POST

from apps.products.models import PerfumeVariant
from .cart import Cart


def cart_detail_view(request):
    """نمایش سبد خرید"""
    cart = Cart(request)
    items = cart.get_items()

    context = {
        'cart': cart,
        'items': items,
        'total_price': cart.get_total_price(),
        'total_original_price': cart.get_total_original_price(),
        'total_discount': cart.get_total_discount(),
    }
    return render(request, 'cart/cart_detail.html', context)


@require_POST
def cart_add_view(request):
    """افزودن محصول به سبد خرید (AJAX)"""
    variant_id = request.POST.get('variant_id')
    quantity = int(request.POST.get('quantity', 1))

    variant = get_object_or_404(PerfumeVariant, id=variant_id)

    # بررسی موجودی
    if not variant.is_available:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'error': 'این محصول موجود نیست',
            }, status=400)
        messages.error(request, 'این محصول موجود نیست.')
        return redirect(variant.perfume.get_absolute_url())

    # بررسی تعداد با موجودی
    cart = Cart(request)
    current_qty = 0
    variant_str = str(variant.id)
    if variant_str in cart.cart:
        current_qty = cart.cart[variant_str]['quantity']

    if current_qty + quantity > variant.stock:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'error': f'حداکثر {variant.stock} عدد موجود است',
            }, status=400)
        messages.error(request, f'حداکثر {variant.stock} عدد موجود است.')
        return redirect(variant.perfume.get_absolute_url())

    cart.add(variant, quantity)

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({
            'message': 'محصول به سبد خرید اضافه شد',
            'cart_count': len(cart),
            'total_price': cart.get_total_price(),
        })

    messages.success(request, 'محصول به سبد خرید اضافه شد.')
    return redirect('cart:detail')


@require_POST
def cart_remove_view(request):
    """حذف محصول از سبد خرید (AJAX)"""
    variant_id = request.POST.get('variant_id')
    cart = Cart(request)
    cart.remove(variant_id)

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({
            'message': 'محصول از سبد خرید حذف شد',
            'cart_count': len(cart),
            'total_price': cart.get_total_price(),
            'total_original_price': cart.get_total_original_price(),
            'total_discount': cart.get_total_discount(),
        })

    messages.success(request, 'محصول از سبد خرید حذف شد.')
    return redirect('cart:detail')


@require_POST
def cart_update_view(request):
    """به‌روزرسانی تعداد محصول (AJAX)"""
    variant_id = request.POST.get('variant_id')
    quantity = int(request.POST.get('quantity', 1))

    variant = get_object_or_404(PerfumeVariant, id=variant_id)

    if quantity > variant.stock:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'error': f'حداکثر {variant.stock} عدد موجود است',
            }, status=400)
        messages.error(request, f'حداکثر {variant.stock} عدد موجود است.')
        return redirect('cart:detail')

    cart = Cart(request)
    cart.update_quantity(variant_id, quantity)

    # محاسبه مجدد
    item_total = variant.final_price * quantity

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({
            'message': 'سبد خرید به‌روزرسانی شد',
            'cart_count': len(cart),
            'item_total': item_total,
            'total_price': cart.get_total_price(),
            'total_original_price': cart.get_total_original_price(),
            'total_discount': cart.get_total_discount(),
        })

    messages.success(request, 'سبد خرید به‌روزرسانی شد.')
    return redirect('cart:detail')


@require_POST
def cart_clear_view(request):
    """خالی کردن سبد خرید"""
    cart = Cart(request)
    cart.clear()

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({
            'message': 'سبد خرید خالی شد',
            'cart_count': 0,
        })

    messages.success(request, 'سبد خرید خالی شد.')
    return redirect('cart:detail')
