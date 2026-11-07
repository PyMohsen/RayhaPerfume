"""
تست‌های مربوط به سرویس و اعلان‌های وب‌سرویس ایتایار (eitaayar.ir)
"""

from unittest.mock import MagicMock, patch
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.utils import timezone
from io import StringIO

from apps.orders.eitaayar import (
    EitaayarService,
    format_datetime_jalali,
    notify_admin_new_order,
    notify_admin_return_requested,
    notify_admin_return_cancelled,
    notify_admin_order_cancelled,
    notify_admin_direct_payment,
    notify_admin_tracking_code_updated,
    notify_admin_order_status_changed,
)
from apps.orders.models import Order, OrderItem, DirectPayment
from apps.products.models import Perfume, PerfumeVariant

User = get_user_model()


class EitaayarServiceTests(TestCase):
    """تست‌های متدها و رفتارهای پایه سرویس ایتایار"""

    def test_service_not_configured_when_empty_settings(self):
        service = EitaayarService(token='', chat_id='')
        self.assertFalse(service.is_configured())
        res = service.send_message(text='سلام')
        self.assertFalse(res['ok'])
        self.assertIn('missing', res['description'])

    def test_service_disabled_via_settings(self):
        service = EitaayarService(token='dummy_token', chat_id='dummy_chat')
        service.enabled = False
        res = service.send_message(text='سلام')
        self.assertFalse(res['ok'])
        self.assertIn('disabled', res['description'])

    @patch('requests.post')
    def test_send_message_success(self, mock_post):
        mock_response = MagicMock()
        mock_response.json.return_value = {
            'ok': True,
            'result': {
                'message_id': 12345,
                'chat': {'id': 100, 'type': 'group'},
                'text': 'سلام تست',
            }
        }
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response

        service = EitaayarService(token='my_secret_token', chat_id='my_group_123')
        res = service.send_message(
            text='سلام تست',
            title='تست عنوان',
            pin=True,
            disable_notification=True,
        )

        self.assertTrue(res['ok'])
        self.assertEqual(res['result']['message_id'], 12345)

        # بررسی فراخوانی درست آدرس و پارامترها مطابق مستندات
        mock_post.assert_called_once()
        called_url = mock_post.call_args[0][0]
        self.assertEqual(called_url, 'https://eitaayar.ir/api/my_secret_token/sendMessage')
        called_data = mock_post.call_args[1]['data']
        self.assertEqual(called_data['chat_id'], 'my_group_123')
        self.assertEqual(called_data['text'], 'سلام تست')
        self.assertEqual(called_data['title'], 'تست عنوان')
        self.assertEqual(called_data['pin'], 1)
        self.assertEqual(called_data['disable_notification'], 1)

    @patch('requests.post')
    def test_send_message_handles_api_failure(self, mock_post):
        mock_response = MagicMock()
        mock_response.json.return_value = {
            'ok': False,
            'description': 'Chat not found'
        }
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response

        service = EitaayarService(token='tok', chat_id='invalid_chat')
        res = service.send_message(text='تست')
        self.assertFalse(res['ok'])
        self.assertEqual(res['description'], 'Chat not found')

    @patch('requests.post')
    def test_send_message_network_error_graceful(self, mock_post):
        import requests
        mock_post.side_effect = requests.exceptions.ConnectTimeout('Connection timed out')

        service = EitaayarService(token='tok', chat_id='chat')
        res = service.send_message(text='تست خطا')
        self.assertFalse(res['ok'])
        self.assertIn('Connection timed out', res['description'])

    @patch('threading.Thread')
    def test_send_async_spawns_daemon_thread(self, mock_thread_cls):
        service = EitaayarService(token='tok', chat_id='chat')
        service.send_async(text='پیام غیرهمگام', title='عنوان')

        mock_thread_cls.assert_called_once()
        kwargs = mock_thread_cls.call_args[1]
        self.assertTrue(kwargs.get('daemon'))
        self.assertEqual(kwargs.get('args'), ('پیام غیرهمگام',))


class OrderNotificationsTests(TestCase):
    """تست‌های توابع تولید اعلان برای انواع رویدادهای سفارش"""

    def setUp(self):
        self.user = User.objects.create_user(
            phone_number='09123456789',
            full_name='علی محمدی',
        )
        self.perfume = Perfume.objects.create(
            name='دیور ساواج',
            slug='dior-sauvage',
            brand='Dior',
            description='توضیحات عطر',
        )
        self.variant = PerfumeVariant.objects.create(
            perfume=self.perfume,
            size=100,
            price=2500000,
            stock=10,
        )
        self.order = Order.objects.create(
            user=self.user,
            order_number='RP-TEST1234',
            full_name='علی محمدی',
            phone_number='09123456789',
            province='تهران',
            city='تهران',
            address='خیابان ولیعصر، پلاک ۱',
            postal_code='1234567890',
            total_price=2500000,
            discount_amount=0,
            coupon_discount=0,
            shipping_cost=0,
            final_price=2500000,
            status=Order.Status.PROCESSING,
            payment_method=Order.PaymentMethod.SEP,
            ref_id='SEP-REF-999',
            paid_at=timezone.now(),
            note='لطفاً در ساعات عصر تحویل داده شود',
        )
        self.item = OrderItem.objects.create(
            order=self.order,
            variant=self.variant,
            perfume_name='دیور ساواج',
            size=100,
            quantity=1,
            price=2500000,
            discount_percent=0,
        )

    @patch.object(EitaayarService, 'send_async')
    def test_notify_admin_new_order(self, mock_send_async):
        notify_admin_new_order(self.order.id)
        mock_send_async.assert_called_once()
        text = mock_send_async.call_args[1]['text']

        self.assertIn('ثبت سفارش جدید در رایحه پرفیوم', text)
        self.assertIn('RP-TEST1234', text)
        self.assertIn('علی محمدی', text)
        self.assertIn('09123456789', text)
        self.assertIn('دیور ساواج (100 میل)', text)
        self.assertIn('2,500,000 تومان', text)
        self.assertIn('درگاه بانکی سپ', text)
        self.assertIn('SEP-REF-999', text)
        self.assertIn('خیابان ولیعصر', text)
        self.assertIn('لطفاً در ساعات عصر تحویل داده شود', text)
        self.assertIn('/admin/orders/order/', text)

    @patch.object(EitaayarService, 'send_async')
    def test_notify_admin_return_requested(self, mock_send_async):
        self.order.status = Order.Status.RETURN_REQUESTED
        self.order.return_reason = 'شیشه عطر نشتی داشت'
        self.order.return_requested_at = timezone.now()
        self.order.save()

        notify_admin_return_requested(self.order)
        mock_send_async.assert_called_once()
        text = mock_send_async.call_args[1]['text']

        self.assertIn('ثبت درخواست مرجوعی سفارش', text)
        self.assertIn('RP-TEST1234', text)
        self.assertIn('علی محمدی', text)
        self.assertIn('شیشه عطر نشتی داشت', text)
        self.assertIn('/admin/orders/order/', text)

    @patch.object(EitaayarService, 'send_async')
    def test_notify_admin_return_cancelled(self, mock_send_async):
        notify_admin_return_cancelled(self.order.id)
        mock_send_async.assert_called_once()
        text = mock_send_async.call_args[1]['text']

        self.assertIn('لغو درخواست مرجوعی توسط مشتری', text)
        self.assertIn('RP-TEST1234', text)
        self.assertIn('علی محمدی', text)

    @patch.object(EitaayarService, 'send_async')
    def test_notify_admin_order_cancelled(self, mock_send_async):
        notify_admin_order_cancelled(self.order.id)
        mock_send_async.assert_called_once()
        text = mock_send_async.call_args[1]['text']

        self.assertIn('لغو سفارش توسط مشتری', text)
        self.assertIn('RP-TEST1234', text)
        self.assertIn('عودت وجه', text)
        self.assertIn('2,500,000 تومان', text)

    @patch.object(EitaayarService, 'send_async')
    def test_notify_admin_direct_payment(self, mock_send_async):
        payment = DirectPayment.objects.create(
            user=self.user,
            amount=500000,
            status=DirectPayment.Status.COMPLETED,
            payment_method='sep',
            ref_id='RRN-112233',
            description='بیعانه سفارش عمده',
            paid_at=timezone.now(),
        )

        notify_admin_direct_payment(payment.id)
        mock_send_async.assert_called_once()
        text = mock_send_async.call_args[1]['text']

        self.assertIn('ثبت پرداخت مستقیم جدید', text)
        self.assertIn(payment.tracking_number, text)
        self.assertIn('500,000 تومان', text)
        self.assertIn('RRN-112233', text)
        self.assertIn('بیعانه سفارش عمده', text)

    @patch.object(EitaayarService, 'send_async')
    def test_notify_admin_tracking_code_updated(self, mock_send_async):
        self.order.tracking_code = '19876543210987654321'
        self.order.save()

        notify_admin_tracking_code_updated(self.order.id)
        mock_send_async.assert_called_once()
        text = mock_send_async.call_args[1]['text']

        self.assertIn('ثبت کد رهگیری پستی سفارش', text)
        self.assertIn('RP-TEST1234', text)
        self.assertIn('19876543210987654321', text)

    @patch.object(EitaayarService, 'send_async')
    def test_notify_admin_order_status_changed(self, mock_send_async):
        notify_admin_order_status_changed(
            self.order.id,
            old_status=Order.Status.PROCESSING,
            new_status=Order.Status.SHIPPED,
        )
        mock_send_async.assert_called_once()
        text = mock_send_async.call_args[1]['text']

        self.assertIn('تغییر وضعیت سفارش', text)
        self.assertIn('در حال پردازش', text)
        self.assertIn('ارسال شده', text)


class ManagementCommandTests(TestCase):
    """تست دستور مدیریتی test_eitaa"""

    @override_settings(EITAAYAR_TOKEN='', EITAAYAR_CHAT_ID='')
    def test_command_fails_gracefully_when_unconfigured(self):
        out = StringIO()
        call_command('test_eitaa', stdout=out)
        output = out.getvalue()
        self.assertIn('خطا: مقادیر EITAAYAR_TOKEN یا EITAAYAR_CHAT_ID', output)

    @override_settings(EITAAYAR_TOKEN='dummy_token_12345678', EITAAYAR_CHAT_ID='group_999')
    @patch.object(EitaayarService, 'send_message')
    def test_command_succeeds_when_api_ok(self, mock_send_message):
        mock_send_message.return_value = {
            'ok': True,
            'result': {'message_id': 9999}
        }
        out = StringIO()
        call_command('test_eitaa', stdout=out)
        output = out.getvalue()
        self.assertIn('پیام تستی با موفقیت به گروه ارسال شد', output)
        self.assertIn('9999', output)
