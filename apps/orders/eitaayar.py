"""
سرویس یکپارچه‌سازی با ایتا از طریق وب‌سرویس ایتایار (eitaayar.ir)

طبق مستندات رسمی وب‌سرویس ایتایار:
- آدرس وب‌سرویس: https://eitaayar.ir/api/TOKEN/METHOD_NAME
- متد ارسال پیام متنی: sendMessage
- پارامترهای اصلی: chat_id (شناسه گروه یا کانال)، text (متن پیام)
- پارامترهای اختیاری: title (عنوان در پنل)، disable_notification، pin و ...
"""

import logging
import threading
from typing import Any, Dict, Optional, Union

import requests
from django.conf import settings
from django.db import transaction
from django.utils import timezone

logger = logging.getLogger(__name__)


def format_datetime_jalali(dt) -> str:
    """تبدیل تاریخ و زمان میلادی به شمسی با فرمت خوانا"""
    if not dt:
        return '-'
    try:
        import jdatetime
        dt_local = timezone.localtime(dt)
        jdt = jdatetime.datetime.fromgregorian(datetime=dt_local)
        return jdt.strftime('%Y/%m/%d ساعت %H:%M')
    except Exception:
        try:
            return timezone.localtime(dt).strftime('%Y-%m-%d %H:%M')
        except Exception:
            return str(dt)


class EitaayarService:
    """
    سرویس ارسال پیام و اعلان به کانال یا گروه در پیام‌رسان ایتا از طریق ایتایار
    """
    BASE_URL = 'https://eitaayar.ir/api'
    TIMEOUT = 10  # ثانیه

    def __init__(self, token: Optional[str] = None, chat_id: Optional[str] = None):
        self.token = (token or getattr(settings, 'EITAAYAR_TOKEN', '')).strip()
        self.chat_id = (chat_id or getattr(settings, 'EITAAYAR_CHAT_ID', '')).strip()
        self.enabled = getattr(settings, 'EITAAYAR_ENABLED', True)

    def is_configured(self) -> bool:
        """بررسی فعال بودن و کامل بودن تنظیمات"""
        return bool(self.enabled and self.token and self.chat_id)

    def send_message(
        self,
        text: str,
        title: Optional[str] = None,
        pin: bool = False,
        disable_notification: bool = False,
        reply_to_message_id: Optional[int] = None,
        date: Optional[int] = None,
        view_count_for_delete: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        ارسال پیام متنی به چت/گروه ایتا مطابق مستندات متد sendMessage

        :param text: متن پیام (اجباری)
        :param title: عنوان مطلب در پنل ایتایار برای جستجو (اختیاری)
        :param pin: در صورت True سنجاق شدن پیام در چت (اختیاری)
        :param disable_notification: ارسال بدون اعلان/بی‌صدا (اختیاری)
        :param reply_to_message_id: شناسه پیام جهت پاسخ (اختیاری)
        :param date: زمان‌بندی ارسال به فرمت یونیکس تایم‌استمپ (اختیاری)
        :param view_count_for_delete: حذف خودکار پس از رسیدن به این تعداد بازدید (اختیاری)
        :return: دیکشنری خروجی جیسون سرور
        """
        if not self.enabled:
            logger.debug('Eitaayar notifications are disabled in settings.')
            return {'ok': False, 'description': 'Eitaayar is disabled in settings.'}

        if not self.token or not self.chat_id:
            logger.warning(
                'Eitaayar configuration is incomplete (EITAAYAR_TOKEN or EITAAYAR_CHAT_ID is missing).'
            )
            return {'ok': False, 'description': 'Token or chat_id is missing.'}

        url = f'{self.BASE_URL}/{self.token}/sendMessage'
        payload = {
            'chat_id': self.chat_id,
            'text': text,
        }

        if title:
            payload['title'] = str(title)
        if pin:
            payload['pin'] = 1
        if disable_notification:
            payload['disable_notification'] = 1
        if reply_to_message_id:
            payload['reply_to_message_id'] = reply_to_message_id
        if date:
            payload['date'] = date
        if view_count_for_delete:
            payload['viewCountForDelete'] = view_count_for_delete

        try:
            response = requests.post(
                url,
                data=payload,
                timeout=self.TIMEOUT,
            )
            response.raise_for_status()
            data = response.json()
            if not data.get('ok'):
                logger.error('Eitaayar API returned failure: %s', data)
            else:
                logger.info(
                    'Eitaa message sent successfully (message_id: %s).',
                    data.get('result', {}).get('message_id'),
                )
            return data
        except requests.RequestException as exc:
            logger.error('Eitaayar request failed: %s', exc)
            return {'ok': False, 'description': str(exc)}
        except ValueError as exc:
            logger.error('Failed to parse Eitaayar response JSON: %s', exc)
            return {'ok': False, 'description': 'Invalid JSON response from Eitaayar'}
        except Exception as exc:
            logger.exception('Unexpected error sending message to Eitaa: %s', exc)
            return {'ok': False, 'description': str(exc)}

    def send_async(
        self,
        text: str,
        title: Optional[str] = None,
        pin: bool = False,
        disable_notification: bool = False,
    ) -> None:
        """
        ارسال غیرهمگام پیام در یک ترد پس‌زمینه برای جلوگیری از تاخیر در پاسخ به کاربر
        """
        if not self.is_configured():
            return

        thread = threading.Thread(
            target=self.send_message,
            args=(text,),
            kwargs={
                'title': title,
                'pin': pin,
                'disable_notification': disable_notification,
            },
            daemon=True,
            name='EitaayarNotifierThread',
        )
        thread.start()


def _get_admin_domain() -> str:
    """دریافت دامنه سایت جهت تولید لینک مستقیم به پنل ادمین"""
    domain = getattr(settings, 'SITE_DOMAIN', 'rayhaperfume.ir').strip()
    return domain.removeprefix('https://').removeprefix('http://').rstrip('/')


# ==============================================================================
# توابع ارسال اعلان رویدادهای مختلف سفارش به گروه ادمین
# ==============================================================================

def notify_admin_new_order(order_or_id: Union[int, Any]) -> None:
    """
    ارسال اعلان ثبت سفارش جدید و پرداخت‌شده به گروه ادمین
    """
    from apps.orders.models import Order

    try:
        if isinstance(order_or_id, Order):
            order = order_or_id
        else:
            order = Order.objects.prefetch_related('items', 'coupon').get(pk=order_or_id)
    except Exception as exc:
        logger.error('Could not load order %s for Eitaa notification: %s', order_or_id, exc)
        return

    # جمع‌آوری و فرمت‌بندی اقلام سفارش
    items = list(order.items.all())
    items_lines = []
    for idx, item in enumerate(items, 1):
        items_lines.append(
            f'  {idx}. {item.perfume_name} ({item.size} میل) × {item.quantity} عدد — {item.final_price:,} تومان'
        )
    items_summary = '\n'.join(items_lines) if items_lines else '  (بدون قلم)'

    # فرمت اطلاعات تخفیف
    discount_parts = []
    if order.discount_amount > 0:
        discount_parts.append(f'تخفیف محصولات: {order.discount_amount:,} تومان')
    if order.coupon_discount > 0:
        coupon_code = f' ({order.coupon.code})' if order.coupon else ''
        discount_parts.append(f'کوپن تخفیف{coupon_code}: {order.coupon_discount:,} تومان')
    discount_line = f'🏷 تخفیف‌ها: {" | ".join(discount_parts)}\n' if discount_parts else ''

    # یادداشت مشتری
    note_line = f'💬 یادداشت مشتری:\n{order.note.strip()}\n\n' if order.note else ''

    # لینک پنل مدیریت
    domain = _get_admin_domain()
    protocol = 'http' if getattr(settings, 'DEBUG', False) else 'https'
    admin_url = f'{protocol}://{domain}/admin/orders/order/{order.id}/change/'

    ref_info = order.ref_id or order.payment_ref_num or order.torob_transaction_id or '-'

    text = (
        '🛍 ثبت سفارش جدید در رایحه پرفیوم\n'
        '━━━━━━━━━━━━━━━━━━━━\n'
        f'📦 شماره سفارش: {order.order_number}\n'
        f'📅 زمان ثبت: {format_datetime_jalali(order.paid_at or order.created_at)}\n'
        f'📊 وضعیت: {order.get_status_display()}\n\n'
        '👤 مشخصات گیرنده:\n'
        f'• نام: {order.full_name}\n'
        f'• شماره تماس: {order.phone_number}\n'
        f'• استان و شهر: {order.province} - {order.city}\n'
        f'• نشانی: {order.address}\n'
        f'• کد پستی: {order.postal_code}\n\n'
        '💳 اطلاعات پرداخت:\n'
        f'• درگاه / روش: {order.get_payment_method_display()}\n'
        f'• شماره پیگیری: {ref_info}\n'
        f'• هزینه ارسال: {order.shipping_cost:,} تومان\n'
        f'{discount_line}'
        f'• مبلغ کل نهایی: {order.final_price:,} تومان\n\n'
        '📋 اقلام سفارش:\n'
        f'{items_summary}\n\n'
        f'{note_line}'
        '🔗 مشاهده و پردازش سفارش:\n'
        f'{admin_url}'
    )

    EitaayarService().send_async(text=text, title=f'سفارش جدید {order.order_number}')


def notify_admin_return_requested(order_or_id: Union[int, Any]) -> None:
    """
    ارسال اعلان ثبت درخواست مرجوعی توسط مشتری به گروه ادمین
    """
    from apps.orders.models import Order

    try:
        if isinstance(order_or_id, Order):
            order = order_or_id
        else:
            order = Order.objects.get(pk=order_or_id)
    except Exception as exc:
        logger.error('Could not load order %s for return notification: %s', order_or_id, exc)
        return

    domain = _get_admin_domain()
    protocol = 'http' if getattr(settings, 'DEBUG', False) else 'https'
    admin_url = f'{protocol}://{domain}/admin/orders/order/{order.id}/change/'

    image_line = ''
    if order.return_image:
        image_url = f'{protocol}://{domain}{order.return_image.url}'
        image_line = f'📸 تصویر ارسالی مشتری:\n{image_url}\n\n'

    text = (
        '⚠️ ثبت درخواست مرجوعی سفارش\n'
        '━━━━━━━━━━━━━━━━━━━━\n'
        f'📦 شماره سفارش: {order.order_number}\n'
        f'📅 زمان درخواست: {format_datetime_jalali(order.return_requested_at or timezone.now())}\n'
        f'👤 نام خریدار: {order.full_name}\n'
        f'📞 شماره تماس: {order.phone_number}\n'
        f'💰 مبلغ سفارش: {order.final_price:,} تومان\n\n'
        '📝 علت درخواست مرجوعی:\n'
        f'{order.return_reason.strip() if order.return_reason else "(توضیحی ثبت نشده)"}\n\n'
        f'{image_line}'
        '🔗 بررسی و تایید/رد در پنل مدیریت:\n'
        f'{admin_url}'
    )

    EitaayarService().send_async(text=text, title=f'درخواست مرجوعی {order.order_number}')


def notify_admin_return_cancelled(order_or_id: Union[int, Any]) -> None:
    """
    ارسال اعلان انصراف و لغو درخواست مرجوعی توسط مشتری
    """
    from apps.orders.models import Order

    try:
        if isinstance(order_or_id, Order):
            order = order_or_id
        else:
            order = Order.objects.get(pk=order_or_id)
    except Exception as exc:
        logger.error('Could not load order %s for cancel-return notification: %s', order_or_id, exc)
        return

    domain = _get_admin_domain()
    protocol = 'http' if getattr(settings, 'DEBUG', False) else 'https'
    admin_url = f'{protocol}://{domain}/admin/orders/order/{order.id}/change/'

    text = (
        'ℹ️ لغو درخواست مرجوعی توسط مشتری\n'
        '━━━━━━━━━━━━━━━━━━━━\n'
        f'📦 شماره سفارش: {order.order_number}\n'
        f'👤 نام خریدار: {order.full_name}\n'
        f'📞 شماره تماس: {order.phone_number}\n'
        f'📊 وضعیت فعلی سفارش: {order.get_status_display()}\n'
        f'📅 زمان انصراف: {format_datetime_jalali(timezone.now())}\n\n'
        'مشتری از درخواست مرجوعی سفارش فوق انصراف داد و سفارش به وضعیت پیشین بازگشت.\n\n'
        '🔗 مشاهده در پنل مدیریت:\n'
        f'{admin_url}'
    )

    EitaayarService().send_async(text=text, title=f'انصراف از مرجوعی {order.order_number}')


def notify_admin_order_cancelled(order_or_id: Union[int, Any]) -> None:
    """
    ارسال اعلان لغو سفارش توسط مشتری قبل از ارسال
    """
    from apps.orders.models import Order

    try:
        if isinstance(order_or_id, Order):
            order = order_or_id
        else:
            order = Order.objects.get(pk=order_or_id)
    except Exception as exc:
        logger.error('Could not load order %s for cancel notification: %s', order_or_id, exc)
        return

    domain = _get_admin_domain()
    protocol = 'http' if getattr(settings, 'DEBUG', False) else 'https'
    admin_url = f'{protocol}://{domain}/admin/orders/order/{order.id}/change/'

    ref_info = order.ref_id or order.payment_ref_num or order.torob_transaction_id or '-'

    text = (
        '🚫 لغو سفارش توسط مشتری\n'
        '━━━━━━━━━━━━━━━━━━━━\n'
        f'📦 شماره سفارش: {order.order_number}\n'
        f'📅 زمان لغو: {format_datetime_jalali(timezone.now())}\n'
        f'👤 نام خریدار: {order.full_name}\n'
        f'📞 شماره تماس: {order.phone_number}\n'
        f'💰 مبلغ پرداخت‌شده: {order.final_price:,} تومان\n'
        f'💳 روش پرداخت: {order.get_payment_method_display()}\n'
        f'🔍 شماره پیگیری: {ref_info}\n\n'
        '⚠️ موجودی اقلام سفارش به صورت خودکار به انبار بازگشت. '
        'لطفاً در صورت نیاز جهت عودت وجه به حساب مشتری اقدام فرمایید.\n\n'
        '🔗 مشاهده سفارش در پنل مدیریت:\n'
        f'{admin_url}'
    )

    EitaayarService().send_async(text=text, title=f'لغو سفارش {order.order_number}')


def notify_admin_direct_payment(payment_or_id: Union[int, Any]) -> None:
    """
    ارسال اعلان ثبت پرداخت مستقیم / آزاد به گروه ادمین
    """
    from apps.orders.models import DirectPayment

    try:
        if isinstance(payment_or_id, DirectPayment):
            payment = payment_or_id
        else:
            payment = DirectPayment.objects.select_related('user').get(pk=payment_or_id)
    except Exception as exc:
        logger.error('Could not load direct payment %s for Eitaa notification: %s', payment_or_id, exc)
        return

    domain = _get_admin_domain()
    protocol = 'http' if getattr(settings, 'DEBUG', False) else 'https'
    admin_url = f'{protocol}://{domain}/admin/orders/directpayment/{payment.id}/change/'

    user_name = payment.user.get_full_name() or payment.user.phone_number
    ref_info = payment.ref_id or payment.payment_ref_num or payment.torob_transaction_id or '-'
    desc_line = f'📝 توضیحات پرداخت: {payment.description.strip()}\n' if payment.description else ''

    text = (
        '💳 ثبت پرداخت مستقیم جدید (موفق)\n'
        '━━━━━━━━━━━━━━━━━━━━\n'
        f'🔖 شناسه پرداخت: {payment.tracking_number}\n'
        f'📅 زمان پرداخت: {format_datetime_jalali(payment.paid_at or payment.created_at)}\n'
        f'👤 پرداخت‌کننده: {user_name}\n'
        f'📞 شماره تماس: {payment.user.phone_number}\n'
        f'💰 مبلغ: {payment.amount:,} تومان\n'
        f'💳 روش پرداخت: {payment.get_payment_method_display()}\n'
        f'🔍 شماره پیگیری: {ref_info}\n'
        f'{desc_line}\n'
        '🔗 مشاهده در پنل مدیریت:\n'
        f'{admin_url}'
    )

    EitaayarService().send_async(text=text, title=f'پرداخت مستقیم {payment.tracking_number}')


def notify_admin_tracking_code_updated(order_or_id: Union[int, Any]) -> None:
    """
    ارسال اعلان ثبت یا به‌روزرسانی کد رهگیری پستی مرسوله به گروه ادمین
    """
    from apps.orders.models import Order

    try:
        if isinstance(order_or_id, Order):
            order = order_or_id
        else:
            order = Order.objects.get(pk=order_or_id)
    except Exception as exc:
        logger.error('Could not load order %s for tracking update notification: %s', order_or_id, exc)
        return

    domain = _get_admin_domain()
    protocol = 'http' if getattr(settings, 'DEBUG', False) else 'https'
    admin_url = f'{protocol}://{domain}/admin/orders/order/{order.id}/change/'

    text = (
        '📮 ثبت کد رهگیری پستی سفارش\n'
        '━━━━━━━━━━━━━━━━━━━━\n'
        f'📦 شماره سفارش: {order.order_number}\n'
        f'👤 نام گیرنده: {order.full_name}\n'
        f'📞 شماره تماس: {order.phone_number}\n'
        f'🚚 کد رهگیری پستی: {order.tracking_code}\n'
        f'📊 وضعیت: {order.get_status_display()}\n'
        f'📅 زمان: {format_datetime_jalali(timezone.now())}\n\n'
        '🔗 مشاهده سفارش در پنل مدیریت:\n'
        f'{admin_url}'
    )

    EitaayarService().send_async(text=text, title=f'کد رهگیری پستی {order.order_number}')


def notify_admin_order_status_changed(
    order_or_id: Union[int, Any],
    old_status: str,
    new_status: str,
) -> None:
    """
    ارسال اعلان تغییر وضعیت سفارش در پنل ادمین به گروه
    """
    from apps.orders.models import Order

    try:
        if isinstance(order_or_id, Order):
            order = order_or_id
        else:
            order = Order.objects.get(pk=order_or_id)
    except Exception as exc:
        logger.error('Could not load order %s for status update notification: %s', order_or_id, exc)
        return

    domain = _get_admin_domain()
    protocol = 'http' if getattr(settings, 'DEBUG', False) else 'https'
    admin_url = f'{protocol}://{domain}/admin/orders/order/{order.id}/change/'

    status_dict = dict(Order.Status.choices)
    old_label = status_dict.get(old_status, old_status)
    new_label = status_dict.get(new_status, new_status)

    text = (
        '🔄 تغییر وضعیت سفارش\n'
        '━━━━━━━━━━━━━━━━━━━━\n'
        f'📦 شماره سفارش: {order.order_number}\n'
        f'👤 نام خریدار: {order.full_name}\n'
        f'📞 شماره تماس: {order.phone_number}\n'
        f'📊 وضعیت قبلی: {old_label}\n'
        f'👉 وضعیت جدید: {new_label}\n'
        f'📅 زمان: {format_datetime_jalali(timezone.now())}\n\n'
        '🔗 مشاهده در پنل مدیریت:\n'
        f'{admin_url}'
    )

    EitaayarService().send_async(text=text, title=f'تغییر وضعیت {order.order_number}')
