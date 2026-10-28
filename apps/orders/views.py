import logging

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db import DatabaseError, IntegrityError
from django.db.models import F
from django.http import JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST, require_http_methods

from apps.accounts.models import UserAddress
from apps.accounts.forms import UserAddressForm, IRAN_PROVINCES_CITIES
from apps.cart.cart import Cart
from .models import Order, OrderItem, CouponCode
from .sep import SepPaymentService
from .torobpay import TorobPayError, TorobPayService

logger = logging.getLogger(__name__)


def _verify_and_finalize_torobpay_order(order):
    """Confirm the provider's current state, settle if needed, and fulfill once."""
    service = TorobPayService()

    def settled_transaction(status):
        try:
            amount_matches = int(status.get('amount')) == int(order.final_price) * 10
        except (TypeError, ValueError):
            amount_matches = False
        transaction_id = str(status.get('transactionId') or '')
        if status.get('status') != 'SETTLE' or not amount_matches or not transaction_id:
            raise TorobPayError('وضعیت نهایی یا مبلغ سفارش در ترب‌پی تأیید نشد.')
        return transaction_id

    try:
        status = service.get_status(order.torob_payment_token)
        try:
            status_amount_matches = int(status.get('amount')) == int(order.final_price) * 10
        except (TypeError, ValueError):
            status_amount_matches = False
        if not status_amount_matches:
            raise TorobPayError('مبلغ سفارش با وضعیت ترب‌پی مطابقت ندارد.')

        state = status.get('status')
        if state == 'SETTLE':
            transaction_id = settled_transaction(status)
        elif state == 'PENDING':
            verification = service.verify(order.torob_payment_token)
            verified_transaction_id = str(verification.get('transactionId') or '')
            if not verified_transaction_id:
                raise TorobPayError('پاسخ تأیید ترب‌پی شناسه تراکنش ندارد.')
            settlement = service.settle(order.torob_payment_token)
            transaction_id = str(settlement.get('transactionId') or '')
            if transaction_id != verified_transaction_id:
                raise TorobPayError('شناسه تراکنش در تأیید و تسویه ترب‌پی یکسان نیست.')
        elif state == 'VERIFY':
            settlement = service.settle(order.torob_payment_token)
            transaction_id = str(settlement.get('transactionId') or '')
            if not transaction_id:
                raise TorobPayError('پاسخ تسویه ترب‌پی شناسه تراکنش ندارد.')
        else:
            raise TorobPayError('سفارش در وضعیت قابل تأیید ترب‌پی نیست.')
    except TorobPayError as payment_error:
        # Recover from a timeout or a previously processed callback if settlement
        # completed at TorobPay but the merchant did not receive its response.
        settled_status = service.get_status(order.torob_payment_token)
        try:
            transaction_id = settled_transaction(settled_status)
        except TorobPayError:
            raise payment_error

    with transaction.atomic():
        order = Order.objects.select_for_update().get(pk=order.pk)
        if order.status != Order.Status.PAID:
            for item in order.items.select_related('variant').all():
                if item.variant_id:
                    variant = item.variant.__class__.objects.select_for_update().get(pk=item.variant_id)
                    if variant.stock < item.quantity:
                        raise TorobPayError('موجودی سفارش تأییدشده کافی نیست؛ سفارش نیازمند بررسی است.')
                    variant.stock -= item.quantity
                    variant.save(update_fields=['stock'])
            order.status = Order.Status.PAID
            order.torob_transaction_id = transaction_id
            order.ref_id = transaction_id
            order.paid_at = timezone.now()
            order.save(update_fields=[
                'status', 'torob_transaction_id', 'ref_id', 'paid_at', 'updated_at'
            ])
            if order.coupon:
                type(order.coupon).objects.filter(pk=order.coupon_id).update(
                    used_count=F('used_count') + 1
                )
    return order


@login_required
def checkout_view(request):
    """صفحه تکمیل سفارش"""
    cart = Cart(request)
    if not cart:
        messages.warning(request, 'سبد خرید شما خالی است.')
        return redirect('cart:detail')

    address_form = UserAddressForm() if not request.user.addresses.exists() else None
    return render(request, 'orders/checkout.html', _checkout_context(request, address_form))


def _checkout_context(request, address_form=None):
    cart = Cart(request)
    items = cart.get_items()
    addresses = list(request.user.addresses.all())
    selected_address = addresses[0] if len(addresses) == 1 else None

    coupon_discount = 0
    coupon = None
    coupon_code = request.session.get('coupon_code')
    if coupon_code:
        try:
            coupon = CouponCode.objects.get(code__iexact=coupon_code)
            if coupon.is_valid:
                coupon_discount = coupon.calculate_discount(cart.get_total_price())
        except CouponCode.DoesNotExist:
            pass

    shipping_cost = getattr(settings, 'SHIPPING_COST')
    total = cart.get_total_price()
    final_price = total - coupon_discount + shipping_cost
    return {
        'items': items,
        'addresses': addresses,
        'selected_address': selected_address,
        'address_form': address_form,
        'address_cities': IRAN_PROVINCES_CITIES,
        'note_value': request.POST.get('note', ''),
        'total_price': cart.get_total_original_price(),
        'discount_amount': cart.get_total_discount(),
        'subtotal': total,
        'coupon_discount': coupon_discount,
        'coupon': coupon,
        'shipping_cost': shipping_cost,
        'final_price': final_price,
        'torobpay_eligible': TorobPayService().is_eligible(final_price),
    }


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
    shipping_cost = getattr(settings, 'SHIPPING_COST', 98000)

    return JsonResponse({
        'success': True,
        'discount': discount,
        'final_price': total - discount + shipping_cost,
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
    payment_method = request.POST.get('payment_method', Order.PaymentMethod.SEP)
    if payment_method not in Order.PaymentMethod.values:
        messages.error(request, 'روش پرداخت انتخاب‌شده معتبر نیست.')
        return redirect('orders:checkout')

    # دریافت آدرس
    if not address_id:
        addresses = list(request.user.addresses.all())
        if len(addresses) == 1:
            address = addresses[0]
        elif len(addresses) > 1:
            messages.error(request, 'لطفاً یکی از آدرس‌های تحویل را انتخاب کنید.')
            return redirect('orders:checkout')
        else:
            address_fields = UserAddressForm.base_fields
            if not any(field_name in request.POST for field_name in address_fields):
                messages.error(request, 'لطفاً یک آدرس برای ارسال سفارش انتخاب کنید.')
                return redirect('orders:checkout')

            address_form = UserAddressForm(request.POST)
            if not address_form.is_valid():
                return render(
                    request,
                    'orders/checkout.html',
                    _checkout_context(request, address_form),
                )

            address = address_form.save(commit=False)
            address.user = request.user
            address.save()
    else:
        try:
            address = UserAddress.objects.get(pk=address_id, user=request.user)
        except (UserAddress.DoesNotExist, ValueError, TypeError):
            messages.error(request, 'آدرس انتخاب شده معتبر نیست. لطفاً یک آدرس معتبر انتخاب کنید.')
            return redirect('orders:checkout')

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

    shipping_cost = getattr(settings, 'SHIPPING_COST', 98000)
    final_price = subtotal - coupon_discount + shipping_cost

    # Eligibility is checked again at order submission; never trust a stale UI choice.
    if payment_method == Order.PaymentMethod.TOROBPAY and not TorobPayService().is_eligible(final_price):
        messages.error(request, 'پرداخت اعتباری ترب‌پی برای این سفارش در دسترس نیست. روش دیگری انتخاب کنید.')
        return redirect('orders:checkout')

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
        payment_method=payment_method,
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

    callback_url = request.build_absolute_uri(
        reverse('orders:payment_callback')
    )

    if payment_method == Order.PaymentMethod.TOROBPAY:
        try:
            result = TorobPayService().create_payment(
                order=order,
                items=items,
                return_url=callback_url,
            )
        except TorobPayError as exc:
            logger.error('TorobPay token request failed for order %s: %s', order.order_number, exc)
            order.status = Order.Status.CANCELLED
            order.save(update_fields=['status', 'updated_at'])
            messages.error(request, 'خطا در اتصال به ترب‌پی. لطفاً روش دیگری انتخاب یا دوباره تلاش کنید.')
            return redirect('orders:checkout')

        order.torob_payment_token = result['payment_token']
        order.save(update_fields=['torob_payment_token', 'updated_at'])
        return render(request, 'orders/redirect_to_gateway.html', {
            'gateway_url': result['payment_page_url'],
            'order': order,
            'payment_provider': 'torobpay',
        })

    # Existing SEP bank card flow.
    sep = SepPaymentService()

    result = sep.request_payment(
        amount=final_price,
        res_num=order.order_number,
        callback_url=callback_url,
        mobile=request.user.phone_number,
    )

    if result['success']:
        order.payment_token = result['token']
        order.save()
        return render(request, 'orders/redirect_to_gateway.html', {
            'gateway_url': result['url'],
            'payment_token': result['token'],
            'order': order,
        })
    else:
        logger.error(
            'SEP token request failed for order %s: %s',
            order.order_number,
            result.get('error', 'unknown error'),
        )
        if settings.DEBUG:
            messages.error(
                request,
                f'خطا در اتصال به درگاه پرداخت: {result.get("error", "خطای نامشخص")}',
            )
        else:
            messages.error(request, 'خطا در اتصال به درگاه پرداخت. لطفاً دوباره تلاش کنید.')
        order.status = Order.Status.CANCELLED
        order.save()
        return redirect('cart:detail')


@csrf_exempt
@require_http_methods(['GET', 'POST'])
def payment_callback_view(request):
    """دریافت نتیجه SEP و تأیید سمت سرور؛ درگاه نتیجه را با POST می‌فرستد."""
    callback_data = request.POST if request.method == 'POST' else request.GET
    # SEP returns ResNum; TorobPay returns the merchant transactionId.
    res_num = (callback_data.get('ResNum') or '').strip()
    torob_transaction_id = (callback_data.get('transactionId') or '').strip()
    state = callback_data.get('State', '').strip().upper()
    ref_num = callback_data.get('RefNum')

    order_number = torob_transaction_id or res_num
    order = Order.objects.filter(order_number=order_number).first() if order_number else None
    if order is None:
        logger.warning(
            'Payment callback order not found (provider identifier present: %s).',
            bool(order_number),
        )
        return redirect('core:home')

    if order.status == Order.Status.PAID:
        return redirect('orders:payment_result', order_number=order.order_number)

    if order.payment_method == Order.PaymentMethod.TOROBPAY:
        transaction_id = torob_transaction_id
        state = callback_data.get('state', '').strip().upper()
        amount = callback_data.get('amount', '').strip()
        try:
            amount_matches = int(amount) == int(order.final_price) * 10
        except (TypeError, ValueError):
            amount_matches = False

        # TorobPay posts an untrusted browser callback. Verify identifiers and amount,
        # then confirm and settle server-to-server before fulfilling the order.
        if (
            state != 'OK'
            or not transaction_id
            or transaction_id != order.order_number
            or not amount_matches
            or not order.torob_payment_token
        ):
            return redirect('orders:payment_result', order_number=order.order_number)

        try:
            order = _verify_and_finalize_torobpay_order(order)
        except TorobPayError as exc:
            logger.error('TorobPay verification/settlement failed for order %s: %s', order.order_number, exc)
            return redirect('orders:payment_result', order_number=order.order_number)
        except (DatabaseError, ValueError) as exc:
            logger.exception('TorobPay verification/settlement failed for order %s: %s', order.order_number, exc)
            return redirect('orders:payment_result', order_number=order.order_number)

        return redirect('orders:payment_result', order_number=order.order_number)

    if order.payment_method != Order.PaymentMethod.SEP:
        return redirect('orders:payment_result', order_number=order.order_number)

    if state != 'OK' or not ref_num:
        order.status = Order.Status.CANCELLED
        order.save()
        return redirect('orders:payment_result', order_number=order.order_number)

    callback_terminal = callback_data.get('TerminalId')
    if callback_terminal and str(callback_terminal) != str(settings.SEP_TERMINAL_ID):
        return redirect('orders:payment_result', order_number=order.order_number)

    result = SepPaymentService().verify_payment(ref_num=ref_num, amount=order.final_price)
    if not result['success']:
        # در خطای شبکه وضعیت را باز نگه می‌داریم تا تأیید مجدد ممکن باشد.
        return redirect('orders:payment_result', order_number=order.order_number)

    try:
        with transaction.atomic():
            order = Order.objects.select_for_update().get(pk=order.pk)
            if order.status != Order.Status.PAID:
                if Order.objects.filter(payment_ref_num=result['payment_ref_num']).exclude(pk=order.pk).exists():
                    raise IntegrityError('SEP RefNum was already used for another order.')

                order.status = Order.Status.PAID
                order.payment_ref_num = result['payment_ref_num']
                order.ref_id = result['ref_id']
                order.paid_at = timezone.now()
                order.save(update_fields=[
                    'status', 'payment_ref_num', 'ref_id', 'paid_at', 'updated_at'
                ])

                for item in order.items.select_related('variant').all():
                    if item.variant_id:
                        item.variant.__class__.objects.filter(
                            pk=item.variant_id,
                            stock__gte=item.quantity,
                        ).update(stock=F('stock') - item.quantity)

                if order.coupon:
                    type(order.coupon).objects.filter(pk=order.coupon_id).update(used_count=F('used_count') + 1)
    except IntegrityError:
        return redirect('orders:payment_result', order_number=order.order_number)

    return redirect('orders:payment_result', order_number=order.order_number)


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


@login_required
def payment_result_view(request, order_number):
    """Same-site landing page: safe place to update the user's session after callback."""
    order = get_object_or_404(Order, order_number=order_number, user=request.user)
    success = order.status in [
        Order.Status.PAID,
        Order.Status.PROCESSING,
        Order.Status.SHIPPED,
        Order.Status.DELIVERED,
    ]
    if success:
        Cart(request).clear()
        request.session.pop('coupon_code', None)
    return render(request, 'orders/payment_result.html', {
        'order': order,
        'success': success,
        'pending_payment': order.status == Order.Status.PENDING,
    })


@login_required
@require_POST
def retry_torobpay_verification_view(request, order_number):
    """Let the owning customer recover a paid TorobPay order after a lost callback."""
    order = get_object_or_404(Order, order_number=order_number, user=request.user)
    if (
        order.payment_method != Order.PaymentMethod.TOROBPAY
        or order.status != Order.Status.PENDING
        or not order.torob_payment_token
    ):
        messages.error(request, 'این سفارش برای بررسی مجدد پرداخت ترب‌پی قابل استفاده نیست.')
        return redirect('orders:detail', order_number=order.order_number)

    try:
        _verify_and_finalize_torobpay_order(order)
    except TorobPayError as exc:
        logger.warning('TorobPay retry failed for order %s: %s', order.order_number, exc)
        messages.error(request, 'ترب‌پی هنوز پرداخت را تأیید نکرده است. کمی بعد دوباره تلاش کنید.')
    except (DatabaseError, ValueError) as exc:
        logger.exception('Could not finalize retried TorobPay order %s: %s', order.order_number, exc)
        messages.error(request, 'پرداخت تأیید شده اما ثبت سفارش نیازمند بررسی پشتیبانی است.')
    else:
        messages.success(request, 'پرداخت ترب‌پی تأیید شد و سفارش با موفقیت ثبت شد.')
    return redirect('orders:detail', order_number=order.order_number)


@login_required
@require_POST
def cancel_order_view(request, order_number):
    """لغو سفارش توسط کاربر"""
    order = get_object_or_404(Order, order_number=order_number, user=request.user)

    try:
        with transaction.atomic():
            order = Order.objects.select_for_update().get(pk=order.pk)
            if not order.can_cancel:
                messages.error(request, 'این سفارش قابل لغو نیست.')
                return redirect('orders:detail', order_number=order.order_number)

            if (
                order.payment_method == Order.PaymentMethod.TOROBPAY
                and order.torob_payment_token
            ):
                try:
                    TorobPayService().cancel(order.torob_payment_token)
                except TorobPayError as cancel_error:
                    # A retry after a completed cancel should still finish locally.
                    try:
                        provider_status = TorobPayService().get_status(order.torob_payment_token)
                    except TorobPayError:
                        provider_status = {}
                    if provider_status.get('status') not in ('REVERT', 'CANCELED'):
                        logger.error(
                            'TorobPay cancellation failed for order %s: %s',
                            order.order_number,
                            cancel_error,
                        )
                        messages.error(
                            request,
                            'لغو سفارش در ترب‌پی تأیید نشد؛ سفارش در سایت هم لغو نشد. کمی بعد دوباره تلاش کنید.',
                        )
                        return redirect('orders:detail', order_number=order.order_number)

            # Restore stock and coupon use only after provider cancellation succeeds.
            if order.status in [Order.Status.PAID, Order.Status.PROCESSING]:
                for item in order.items.select_related('variant').all():
                    if item.variant_id:
                        variant = item.variant.__class__.objects.select_for_update().get(
                            pk=item.variant_id,
                        )
                        variant.stock += item.quantity
                        variant.save(update_fields=['stock'])

                if order.coupon_id:
                    type(order.coupon).objects.filter(
                        pk=order.coupon_id,
                        used_count__gt=0,
                    ).update(used_count=F('used_count') - 1)

            order.status = Order.Status.CANCELLED
            order.save(update_fields=['status', 'updated_at'])
    except DatabaseError:
        logger.exception('Could not save cancellation for order %s.', order.order_number)
        messages.error(request, 'لغو سفارش ثبت نشد؛ لطفاً دوباره تلاش کنید یا با پشتیبانی تماس بگیرید.')
        return redirect('orders:detail', order_number=order.order_number)

    messages.success(request, 'سفارش شما با موفقیت لغو شد.')
    return redirect('orders:detail', order_number=order.order_number)
