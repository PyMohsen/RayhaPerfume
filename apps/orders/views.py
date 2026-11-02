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
from apps.products.models import PerfumeVariant
from .models import Order, OrderItem, CouponCode, PaymentSession
from .sep import SepPaymentService
from .torobpay import TorobPayError, TorobPayService
from .postex import PostexTrackingService

logger = logging.getLogger(__name__)


def _verify_and_create_torobpay_order(payment_session):
    """Confirm the provider's current state, settle if needed, and create order once."""
    service = TorobPayService()

    def settled_transaction(status):
        try:
            amount_matches = int(status.get('amount')) == int(payment_session.final_price) * 10
        except (TypeError, ValueError):
            amount_matches = False
        transaction_id = str(status.get('transactionId') or '')
        if status.get('status') != 'SETTLE' or not amount_matches or not transaction_id:
            raise TorobPayError('وضعیت نهایی یا مبلغ سفارش در ترب‌پی تأیید نشد.')
        return transaction_id

    try:
        status = service.get_status(payment_session.torob_payment_token)
        try:
            status_amount_matches = int(status.get('amount')) == int(payment_session.final_price) * 10
        except (TypeError, ValueError):
            status_amount_matches = False
        if not status_amount_matches:
            raise TorobPayError('مبلغ سفارش با وضعیت ترب‌پی مطابقت ندارد.')

        state = status.get('status')
        if state == 'SETTLE':
            transaction_id = settled_transaction(status)
        elif state == 'PENDING':
            verification = service.verify(payment_session.torob_payment_token)
            verified_transaction_id = str(verification.get('transactionId') or '')
            if not verified_transaction_id:
                raise TorobPayError('پاسخ تأیید ترب‌پی شناسه تراکنش ندارد.')
            settlement = service.settle(payment_session.torob_payment_token)
            transaction_id = str(settlement.get('transactionId') or '')
            if transaction_id != verified_transaction_id:
                raise TorobPayError('شناسه تراکنش در تأیید و تسویه ترب‌پی یکسان نیست.')
        elif state == 'VERIFY':
            settlement = service.settle(payment_session.torob_payment_token)
            transaction_id = str(settlement.get('transactionId') or '')
            if not transaction_id:
                raise TorobPayError('پاسخ تسویه ترب‌پی شناسه تراکنش ندارد.')
        else:
            raise TorobPayError('سفارش در وضعیت قابل تأیید ترب‌پی نیست.')
    except TorobPayError as payment_error:
        # Recover from a timeout or a previously processed callback if settlement
        # completed at TorobPay but the merchant did not receive its response.
        settled_status = service.get_status(payment_session.torob_payment_token)
        try:
            transaction_id = settled_transaction(settled_status)
        except TorobPayError:
            raise payment_error

    with transaction.atomic():
        payment_session = PaymentSession.objects.select_for_update().get(pk=payment_session.pk)
        if payment_session.status == PaymentSession.Status.COMPLETED and payment_session.order:
            return payment_session.order

        # Verify stock and lock variants
        for item_data in payment_session.items_data:
            variant_id = item_data.get('variant_id')
            qty = item_data.get('quantity', 1)
            if variant_id:
                variant = PerfumeVariant.objects.select_for_update().get(pk=variant_id)
                if variant.stock < qty:
                    raise TorobPayError('موجودی سفارش تأییدشده کافی نیست؛ سفارش نیازمند بررسی است.')
                variant.stock -= qty
                variant.save(update_fields=['stock'])

        order = Order.objects.create(
            user=payment_session.user,
            order_number=payment_session.session_key,
            full_name=payment_session.full_name,
            phone_number=payment_session.phone_number,
            province=payment_session.province,
            city=payment_session.city,
            address=payment_session.address,
            postal_code=payment_session.postal_code,
            total_price=payment_session.total_price,
            discount_amount=payment_session.discount_amount,
            coupon_discount=payment_session.coupon_discount,
            shipping_cost=payment_session.shipping_cost,
            final_price=payment_session.final_price,
            status=Order.Status.PROCESSING,
            payment_method=Order.PaymentMethod.TOROBPAY,
            torob_payment_token=payment_session.torob_payment_token,
            torob_transaction_id=transaction_id,
            ref_id=transaction_id,
            paid_at=timezone.now(),
            coupon=payment_session.coupon,
            note=payment_session.note,
        )

        for item_data in payment_session.items_data:
            variant_id = item_data.get('variant_id')
            variant = PerfumeVariant.objects.filter(pk=variant_id).first() if variant_id else None
            OrderItem.objects.create(
                order=order,
                variant=variant,
                perfume_name=item_data.get('perfume_name', ''),
                size=item_data.get('size', 0),
                quantity=item_data.get('quantity', 1),
                price=item_data.get('price', 0),
                discount_percent=item_data.get('discount_percent', 0),
            )

        if order.coupon:
            type(order.coupon).objects.filter(pk=order.coupon_id).update(
                used_count=F('used_count') + 1
            )

        payment_session.status = PaymentSession.Status.COMPLETED
        payment_session.order = order
        payment_session.save(update_fields=['status', 'order', 'updated_at'])

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

    shipping_cost = getattr(settings, 'SHIPPING_COST', 0)
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
    shipping_cost = getattr(settings, 'SHIPPING_COST', 0)

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
    """ایجاد جلسه پرداخت و هدایت به درگاه (بدون ثبت سفارش قبل از پرداخت)"""
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

    # دریافت یا ایجاد آدرس
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

    shipping_cost = getattr(settings, 'SHIPPING_COST', 0)
    final_price = subtotal - coupon_discount + shipping_cost

    # Eligibility is checked again at order submission; never trust a stale UI choice.
    if payment_method == Order.PaymentMethod.TOROBPAY and not TorobPayService().is_eligible(final_price):
        messages.error(request, 'پرداخت اعتباری ترب‌پی برای این سفارش در دسترس نیست. روش دیگری انتخاب کنید.')
        return redirect('orders:checkout')

    # ساخت اطلاعات جلسه پرداخت (هیچ سفارشی در Order ساخته نمی‌شود)
    address_data = {
        'full_name': address.full_name,
        'phone_number': address.phone_number,
        'province': address.province,
        'city': address.city,
        'address': address.address,
        'postal_code': address.postal_code,
    }
    items_data = [
        {
            'variant_id': item['variant'].pk,
            'perfume_name': item['variant'].perfume.name,
            'size': item['variant'].size,
            'quantity': item['quantity'],
            'price': item['variant'].price,
            'discount_percent': item['variant'].discount_percent,
        }
        for item in items
    ]
    order_number = Order.generate_order_number()

    payment_session = PaymentSession.objects.create(
        user=request.user,
        session_key=order_number,
        payment_method=payment_method,
        address_data=address_data,
        items_data=items_data,
        total_price=total_price,
        discount_amount=discount_amount,
        coupon_discount=coupon_discount,
        shipping_cost=shipping_cost,
        final_price=final_price,
        coupon=coupon,
        note=note,
        status=PaymentSession.Status.PENDING,
    )

    callback_url = request.build_absolute_uri(
        reverse('orders:payment_callback')
    )

    if payment_method == Order.PaymentMethod.TOROBPAY:
        try:
            result = TorobPayService().create_payment(
                order=payment_session,
                items=items,
                return_url=callback_url,
            )
        except TorobPayError as exc:
            logger.error('TorobPay token request failed for session %s: %s', payment_session.session_key, exc)
            payment_session.status = PaymentSession.Status.FAILED
            payment_session.save(update_fields=['status', 'updated_at'])
            messages.error(request, 'خطا در اتصال به ترب‌پی. لطفاً روش دیگری انتخاب یا دوباره تلاش کنید.')
            return redirect('orders:checkout')

        payment_session.torob_payment_token = result['payment_token']
        payment_session.save(update_fields=['torob_payment_token', 'updated_at'])
        return render(request, 'orders/redirect_to_gateway.html', {
            'gateway_url': result['payment_page_url'],
            'order': payment_session,
            'payment_provider': 'torobpay',
        })

    # Existing SEP bank card flow.
    sep = SepPaymentService()
    result = sep.request_payment(
        amount=final_price,
        res_num=payment_session.session_key,
        callback_url=callback_url,
        mobile=request.user.phone_number,
    )

    if result['success']:
        payment_session.payment_token = result['token']
        payment_session.save(update_fields=['payment_token', 'updated_at'])
        return render(request, 'orders/redirect_to_gateway.html', {
            'gateway_url': result['url'],
            'payment_token': result['token'],
            'order': payment_session,
        })
    else:
        logger.error(
            'SEP token request failed for session %s: %s',
            payment_session.session_key,
            result.get('error', 'unknown error'),
        )
        payment_session.status = PaymentSession.Status.FAILED
        payment_session.save(update_fields=['status', 'updated_at'])
        if settings.DEBUG:
            messages.error(
                request,
                f'خطا در اتصال به درگاه پرداخت: {result.get("error", "خطای نامشخص")}',
            )
        else:
            messages.error(request, 'خطا در اتصال به درگاه پرداخت. لطفاً دوباره تلاش کنید.')
        return redirect('cart:detail')


@csrf_exempt
@require_http_methods(['GET', 'POST'])
def payment_callback_view(request):
    """دریافت نتیجه درگاه؛ سفارش فقط در صورت پرداخت قطعی و موفق ثبت می‌شود."""
    callback_data = request.POST if request.method == 'POST' else request.GET
    res_num = (callback_data.get('ResNum') or '').strip()
    torob_transaction_id = (callback_data.get('transactionId') or '').strip()
    state = callback_data.get('State', '').strip().upper()
    ref_num = callback_data.get('RefNum')

    session_key = torob_transaction_id or res_num
    if not session_key:
        logger.warning('Payment callback received without identifier.')
        return redirect('core:home')

    payment_session = PaymentSession.objects.filter(session_key=session_key).first()
    if payment_session is None:
        logger.warning('Payment session not found for key: %s', session_key)
        return redirect('core:home')

    # اگر سفارش این پرداخت قبلاً با موفقیت ساخته شده باشد (مثلاً رفرش یا تکرار کال‌بک)
    if payment_session.status == PaymentSession.Status.COMPLETED and payment_session.order:
        return redirect('orders:payment_result', order_number=payment_session.order.order_number)

    if payment_session.payment_method == Order.PaymentMethod.TOROBPAY:
        transaction_id = torob_transaction_id
        state = callback_data.get('state', '').strip().upper()
        amount = callback_data.get('amount', '').strip()
        try:
            amount_matches = int(amount) == int(payment_session.final_price) * 10
        except (TypeError, ValueError):
            amount_matches = False

        if (
            state != 'OK'
            or not transaction_id
            or transaction_id != payment_session.session_key
            or not amount_matches
            or not payment_session.torob_payment_token
        ):
            payment_session.status = PaymentSession.Status.FAILED
            payment_session.save(update_fields=['status', 'updated_at'])
            return redirect('orders:payment_failure')

        try:
            order = _verify_and_create_torobpay_order(payment_session)
        except TorobPayError as exc:
            logger.error('TorobPay verification/settlement failed for session %s: %s', payment_session.session_key, exc)
            payment_session.status = PaymentSession.Status.FAILED
            payment_session.save(update_fields=['status', 'updated_at'])
            return redirect('orders:payment_failure')
        except (DatabaseError, ValueError) as exc:
            logger.exception('TorobPay verification/settlement failed for session %s: %s', payment_session.session_key, exc)
            return redirect('orders:payment_failure')

        try:
            Cart(request).clear()
            request.session.pop('coupon_code', None)
        except Exception:
            pass

        return redirect('orders:payment_result', order_number=order.order_number)

    if payment_session.payment_method != Order.PaymentMethod.SEP:
        return redirect('orders:payment_failure')

    # اگر کاربر انصراف داده یا درگاه سپ خطا برگردانده باشد
    if state != 'OK' or not ref_num:
        payment_session.status = PaymentSession.Status.FAILED
        payment_session.save(update_fields=['status', 'updated_at'])
        return redirect('orders:payment_failure')

    callback_terminal = callback_data.get('TerminalId')
    if callback_terminal and str(callback_terminal) != str(settings.SEP_TERMINAL_ID):
        payment_session.status = PaymentSession.Status.FAILED
        payment_session.save(update_fields=['status', 'updated_at'])
        return redirect('orders:payment_failure')

    result = SepPaymentService().verify_payment(ref_num=ref_num, amount=payment_session.final_price)
    if not result['success']:
        payment_session.status = PaymentSession.Status.FAILED
        payment_session.save(update_fields=['status', 'updated_at'])
        return redirect('orders:payment_failure')

    try:
        with transaction.atomic():
            payment_session = PaymentSession.objects.select_for_update().get(pk=payment_session.pk)
            if payment_session.status == PaymentSession.Status.COMPLETED and payment_session.order:
                return redirect('orders:payment_result', order_number=payment_session.order.order_number)

            if Order.objects.filter(payment_ref_num=result['payment_ref_num']).exists():
                raise IntegrityError('SEP RefNum was already used for another order.')

            # بررسی و کسر موجودی واریانت‌ها
            for item_data in payment_session.items_data:
                variant_id = item_data.get('variant_id')
                qty = item_data.get('quantity', 1)
                if variant_id:
                    variant = PerfumeVariant.objects.select_for_update().get(pk=variant_id)
                    if variant.stock < qty:
                        raise ValueError(f"Insufficient stock for {variant}")
                    variant.stock -= qty
                    variant.save(update_fields=['stock'])

            # ایجاد سفارش نهایی در وضعیت "در حال پردازش"
            order = Order.objects.create(
                user=payment_session.user,
                order_number=payment_session.session_key,
                full_name=payment_session.full_name,
                phone_number=payment_session.phone_number,
                province=payment_session.province,
                city=payment_session.city,
                address=payment_session.address,
                postal_code=payment_session.postal_code,
                total_price=payment_session.total_price,
                discount_amount=payment_session.discount_amount,
                coupon_discount=payment_session.coupon_discount,
                shipping_cost=payment_session.shipping_cost,
                final_price=payment_session.final_price,
                status=Order.Status.PROCESSING,
                payment_method=Order.PaymentMethod.SEP,
                payment_token=payment_session.payment_token,
                payment_ref_num=result['payment_ref_num'],
                ref_id=result['ref_id'],
                paid_at=timezone.now(),
                coupon=payment_session.coupon,
                note=payment_session.note,
            )

            for item_data in payment_session.items_data:
                variant_id = item_data.get('variant_id')
                variant = PerfumeVariant.objects.filter(pk=variant_id).first() if variant_id else None
                OrderItem.objects.create(
                    order=order,
                    variant=variant,
                    perfume_name=item_data.get('perfume_name', ''),
                    size=item_data.get('size', 0),
                    quantity=item_data.get('quantity', 1),
                    price=item_data.get('price', 0),
                    discount_percent=item_data.get('discount_percent', 0),
                )

            if order.coupon:
                type(order.coupon).objects.filter(pk=order.coupon_id).update(used_count=F('used_count') + 1)

            payment_session.status = PaymentSession.Status.COMPLETED
            payment_session.order = order
            payment_session.save(update_fields=['status', 'order', 'updated_at'])
    except IntegrityError:
        return redirect('orders:payment_failure')
    except (DatabaseError, ValueError) as exc:
        logger.exception('Could not create order for session %s: %s', payment_session.session_key, exc)
        return redirect('orders:payment_failure')

    try:
        Cart(request).clear()
        request.session.pop('coupon_code', None)
    except Exception:
        pass

    return redirect('orders:payment_result', order_number=order.order_number)


def payment_failure_view(request):
    """صفحه نتیجه پرداخت ناموفق (هیچ سفارشی ثبت نشده است)"""
    return render(request, 'orders/payment_result.html', {
        'order': None,
        'success': False,
        'error_message': 'متأسفانه پرداخت انجام نشد یا توسط کاربر لغو گردید. هیچ سفارشی ثبت نشد.',
    })


@login_required
def payment_result_view(request, order_number):
    """صفحه نتیجه پرداخت موفق"""
    order = get_object_or_404(Order, order_number=order_number, user=request.user)
    success = order.status in [
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
    tracking = PostexTrackingService().get_tracking(order.tracking_code)

    context = {
        'order': order,
        'items': items,
        'tracking': tracking,
    }
    return render(request, 'orders/order_detail.html', context)


@login_required
@require_POST
def retry_torobpay_verification_view(request, order_number):
    """بررسی مجدد پرداخت ترب‌پی در صورت قطعی اتصال کاربر پس از پرداخت"""
    order = Order.objects.filter(order_number=order_number, user=request.user).first()
    if order:
        return redirect('orders:detail', order_number=order.order_number)

    payment_session = PaymentSession.objects.filter(
        session_key=order_number,
        user=request.user,
        payment_method=Order.PaymentMethod.TOROBPAY,
        status=PaymentSession.Status.PENDING,
    ).first()

    if not payment_session or not payment_session.torob_payment_token:
        messages.error(request, 'این پرداخت برای بررسی مجدد ترب‌پی قابل استفاده نیست.')
        return redirect('cart:detail')

    try:
        order = _verify_and_create_torobpay_order(payment_session)
    except TorobPayError as exc:
        logger.warning('TorobPay retry failed for session %s: %s', payment_session.session_key, exc)
        messages.error(request, 'ترب‌پی هنوز پرداخت را تأیید نکرده است. کمی بعد دوباره تلاش کنید.')
        return redirect('cart:detail')
    except (DatabaseError, ValueError) as exc:
        logger.exception('Could not finalize retried TorobPay session %s: %s', payment_session.session_key, exc)
        messages.error(request, 'پرداخت تأیید شده اما ثبت سفارش با خطا مواجه شد؛ با پشتیبانی تماس بگیرید.')
        return redirect('cart:detail')

    messages.success(request, 'پرداخت ترب‌پی تأیید شد و سفارش شما با موفقیت ثبت شد.')
    return redirect('orders:detail', order_number=order.order_number)


@login_required
@require_POST
def cancel_order_view(request, order_number):
    """لغو سفارش توسط کاربر (فقط در وضعیت در حال پردازش)"""
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

            # برگشت موجودی و استفاده از کد تخفیف
            if order.status == Order.Status.PROCESSING:
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
