from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.accounts.models import UserAddress
from apps.cart.cart import Cart
from .models import Order, OrderItem, CouponCode
from .zarinpal import ZarinPalService


@login_required
def checkout_view(request):
    """صفحه تکمیل سفارش"""
    cart = Cart(request)
    if not cart:
        messages.warning(request, 'سبد خرید شما خالی است.')
        return redirect('cart:detail')

    items = cart.get_items()
    addresses = request.user.addresses.all()
    default_address = addresses.filter(is_default=True).first()

    # بررسی کد تخفیف از session
    coupon_discount = 0
    coupon_code = request.session.get('coupon_code')
    coupon = None
    if coupon_code:
        try:
            coupon = CouponCode.objects.get(code__iexact=coupon_code)
            if coupon.is_valid:
                coupon_discount = coupon.calculate_discount(cart.get_total_price())
        except CouponCode.DoesNotExist:
            pass

    shipping_cost = 0  # هزینه ارسال (فعلاً رایگان)
    total = cart.get_total_price()
    final_price = total - coupon_discount + shipping_cost

    context = {
        'items': items,
        'addresses': addresses,
        'default_address': default_address,
        'total_price': cart.get_total_original_price(),
        'discount_amount': cart.get_total_discount(),
        'subtotal': total,
        'coupon_discount': coupon_discount,
        'coupon': coupon,
        'shipping_cost': shipping_cost,
        'final_price': final_price,
    }
    return render(request, 'orders/checkout.html', context)


@login_required
@require_POST
def apply_coupon_view(request):
    """اعمال کد تخفیف (AJAX)"""
    code = request.POST.get('code', '').strip().upper()
    cart = Cart(request)

    try:
        coupon = CouponCode.objects.get(code__iexact=code)
    except CouponCode.DoesNotExist:
        return JsonResponse({'error': 'کد تخفیف نامعتبر است'}, status=400)

    if not coupon.is_valid:
        return JsonResponse({'error': 'کد تخفیف منقضی شده یا به حد استفاده رسیده'}, status=400)

    total = cart.get_total_price()
    if total < coupon.min_order_amount:
        return JsonResponse({
            'error': f'حداقل مبلغ سفارش برای این کد {coupon.min_order_amount:,} تومان است'
        }, status=400)

    discount = coupon.calculate_discount(total)
    request.session['coupon_code'] = code

    return JsonResponse({
        'success': True,
        'discount': discount,
        'final_price': total - discount,
        'message': f'کد تخفیف {coupon.discount_percent}% اعمال شد',
    })


@login_required
@require_POST
def remove_coupon_view(request):
    """حذف کد تخفیف"""
    if 'coupon_code' in request.session:
        del request.session['coupon_code']
    return JsonResponse({'success': True})


@login_required
@require_POST
def create_order_view(request):
    """ایجاد سفارش و هدایت به درگاه پرداخت"""
    cart = Cart(request)
    if not cart:
        messages.warning(request, 'سبد خرید شما خالی است.')
        return redirect('cart:detail')

    address_id = request.POST.get('address_id')
    note = request.POST.get('note', '')

    # دریافت آدرس
    address = get_object_or_404(UserAddress, pk=address_id, user=request.user)

    # بررسی موجودی
    items = cart.get_items()
    for item in items:
        if item['variant'].stock < item['quantity']:
            messages.error(
                request,
                f'موجودی {item["variant"].perfume.name} ({item["variant"].get_size_display()}) '
                f'کافی نیست. موجودی فعلی: {item["variant"].stock}'
            )
            return redirect('cart:detail')

    # محاسبه مبالغ
    total_price = cart.get_total_original_price()
    discount_amount = cart.get_total_discount()
    subtotal = cart.get_total_price()

    # کد تخفیف
    coupon = None
    coupon_discount = 0
    coupon_code = request.session.get('coupon_code')
    if coupon_code:
        try:
            coupon = CouponCode.objects.get(code__iexact=coupon_code)
            if coupon.is_valid:
                coupon_discount = coupon.calculate_discount(subtotal)
        except CouponCode.DoesNotExist:
            pass

    shipping_cost = 0
    final_price = subtotal - coupon_discount + shipping_cost

    # ایجاد سفارش
    order = Order.objects.create(
        user=request.user,
        full_name=address.full_name,
        phone_number=address.phone_number,
        province=address.province,
        city=address.city,
        address=address.address,
        postal_code=address.postal_code,
        total_price=total_price,
        discount_amount=discount_amount,
        coupon_discount=coupon_discount,
        shipping_cost=shipping_cost,
        final_price=final_price,
        coupon=coupon,
        note=note,
    )

    # ایجاد آیتم‌های سفارش
    for item in items:
        OrderItem.objects.create(
            order=order,
            variant=item['variant'],
            perfume_name=item['variant'].perfume.name,
            size=item['variant'].size,
            quantity=item['quantity'],
            price=item['variant'].price,
            discount_percent=item['variant'].discount_percent,
        )

    # درخواست پرداخت
    zarinpal = ZarinPalService()
    callback_url = request.build_absolute_uri(
        reverse('orders:payment_callback')
    )

    result = zarinpal.request_payment(
        amount=final_price,
        description=f'سفارش {order.order_number} - فروشگاه عطر رایحه',
        callback_url=callback_url,
        mobile=request.user.phone_number,
        email=request.user.email,
    )

    if result['success']:
        order.payment_authority = result['authority']
        order.save()
        return redirect(result['url'])
    else:
        messages.error(request, f'خطا در اتصال به درگاه: {result["error"]}')
        order.status = Order.Status.CANCELLED
        order.save()
        return redirect('cart:detail')


@login_required
def payment_callback_view(request):
    """بازگشت از درگاه پرداخت"""
    authority = request.GET.get('Authority')
    status = request.GET.get('Status')

    try:
        order = Order.objects.get(
            payment_authority=authority,
            user=request.user,
        )
    except Order.DoesNotExist:
        messages.error(request, 'سفارش یافت نشد.')
        return redirect('core:home')

    if status == 'OK':
        zarinpal = ZarinPalService()
        result = zarinpal.verify_payment(
            authority=authority,
            amount=order.final_price,
        )

        if result['success']:
            # پرداخت موفق
            order.status = Order.Status.PAID
            order.ref_id = result['ref_id']
            order.paid_at = timezone.now()
            order.save()

            # کاهش موجودی
            for item in order.items.all():
                if item.variant:
                    item.variant.stock -= item.quantity
                    item.variant.save()

            # افزایش استفاده کد تخفیف
            if order.coupon:
                order.coupon.used_count += 1
                order.coupon.save()

            # خالی کردن سبد خرید
            cart = Cart(request)
            cart.clear()

            # پاک کردن کد تخفیف از session
            if 'coupon_code' in request.session:
                del request.session['coupon_code']

            messages.success(request, 'پرداخت با موفقیت انجام شد!')
            return render(request, 'orders/payment_result.html', {
                'order': order,
                'success': True,
            })
        else:
            order.status = Order.Status.CANCELLED
            order.save()
            messages.error(request, 'پرداخت ناموفق بود.')
    else:
        order.status = Order.Status.CANCELLED
        order.save()
        messages.error(request, 'پرداخت توسط کاربر لغو شد.')

    return render(request, 'orders/payment_result.html', {
        'order': order,
        'success': False,
    })


@login_required
def order_detail_view(request, order_number):
    """جزئیات سفارش"""
    order = get_object_or_404(
        Order,
        order_number=order_number,
        user=request.user,
    )
    items = order.items.all()

    context = {
        'order': order,
        'items': items,
    }
    return render(request, 'orders/order_detail.html', context)
