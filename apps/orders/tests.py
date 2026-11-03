import io
import os
from unittest.mock import patch
from PIL import Image

from django.conf import settings
from django.core.files.storage import default_storage
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from apps.accounts.models import CustomUser, UserAddress
from apps.orders.models import Order, OrderItem, PaymentSession, DirectPayment
from apps.products.models import Perfume, PerfumeVariant


@override_settings(SECURE_SSL_REDIRECT=False)
class OrderPaymentFlowTests(TestCase):
    def setUp(self):
        self.user = CustomUser.objects.create_user(
            phone_number='09123456789',
            full_name='Test User',
            email='testuser@example.com'
        )
        self.client.force_login(self.user)

        self.address = UserAddress.objects.create(
            user=self.user,
            title='Home',
            full_name='Test User',
            phone_number='09123456789',
            province='Tehran',
            city='Tehran',
            address='Street 1',
            postal_code='1234567890'
        )

        self.perfume = Perfume.objects.create(
            name='Test Perfume',
            slug='test-perfume',
            brand='Test Brand',
            description='Test Description'
        )
        self.variant = PerfumeVariant.objects.create(
            perfume=self.perfume,
            size=100,
            price=100000,
            stock=10,
            sku='test-sku'
        )

        session = self.client.session
        session['cart'] = {
            str(self.variant.id): {
                'quantity': 2,
                'price': 100000
            }
        }
        session.save()

        self.create_url = reverse('orders:create')
        self.checkout_url = reverse('orders:checkout')
        self.callback_url = reverse('orders:payment_callback')
        self.failure_url = reverse('orders:payment_failure')

    def test_create_order_without_address_id(self):
        """Submitting without address when multiple addresses exist redirects with error."""
        UserAddress.objects.create(
            user=self.user,
            title='Work',
            full_name='Test User 2',
            phone_number='09123456789',
            province='Tehran',
            city='Tehran',
            address='Street 2',
            postal_code='1234567891'
        )
        response = self.client.post(self.create_url, {})
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, self.checkout_url)
        self.assertEqual(Order.objects.count(), 0)
        self.assertEqual(PaymentSession.objects.count(), 0)

    def test_create_order_with_invalid_address_id(self):
        """Submitting with an invalid address_id redirects with error."""
        response = self.client.post(self.create_url, {'address_id': 99999})
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, self.checkout_url)
        self.assertEqual(Order.objects.count(), 0)
        self.assertEqual(PaymentSession.objects.count(), 0)

    @patch('apps.orders.views.SepPaymentService')
    def test_create_order_creates_payment_session_and_NO_order(self, mock_sep_cls):
        """Clicking submit order creates a PaymentSession, but absolutely NO Order yet."""
        mock_instance = mock_sep_cls.return_value
        mock_instance.request_payment.return_value = {
            'success': True,
            'token': 'sep-token-123',
            'url': 'https://sep.shaparak.ir/OnlinePG/OnlinePG'
        }

        response = self.client.post(self.create_url, {'address_id': self.address.id})
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'orders/redirect_to_gateway.html')

        # NO Order registered before payment
        self.assertEqual(Order.objects.count(), 0)
        self.assertEqual(OrderItem.objects.count(), 0)

        # PaymentSession was created
        self.assertEqual(PaymentSession.objects.count(), 1)
        ps = PaymentSession.objects.first()
        self.assertEqual(ps.user, self.user)
        self.assertEqual(ps.payment_token, 'sep-token-123')
        self.assertEqual(ps.status, PaymentSession.Status.PENDING)
        self.assertEqual(ps.final_price, 200000)

        # Stock is NOT deducted yet
        self.variant.refresh_from_db()
        self.assertEqual(self.variant.stock, 10)

    @patch('apps.orders.views.SepPaymentService')
    def test_create_order_gateway_failure_registers_NO_order(self, mock_sep_cls):
        """If IPG token request fails, no order is created and session is marked failed."""
        mock_instance = mock_sep_cls.return_value
        mock_instance.request_payment.return_value = {
            'success': False,
            'error': 'Terminal inactive'
        }

        response = self.client.post(self.create_url, {'address_id': self.address.id})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Order.objects.count(), 0)

        ps = PaymentSession.objects.first()
        self.assertEqual(ps.status, PaymentSession.Status.FAILED)

    def test_callback_cancelled_by_user_registers_NO_order(self):
        """If user cancels on IPG or payment fails, NO order is created."""
        ps = PaymentSession.objects.create(
            user=self.user,
            session_key='RP-TEST1234',
            payment_method=Order.PaymentMethod.SEP,
            address_data={'full_name': 'Test User', 'phone_number': '09123456789'},
            items_data=[{
                'variant_id': self.variant.id,
                'perfume_name': 'Test Perfume',
                'size': 100,
                'quantity': 2,
                'price': 100000,
                'discount_percent': 0,
            }],
            total_price=200000,
            final_price=200000,
            status=PaymentSession.Status.PENDING,
        )

        response = self.client.post(self.callback_url, {
            'ResNum': ps.session_key,
            'State': 'CanceledByUser',
            'RefNum': '',
        })
        self.assertRedirects(response, self.failure_url)

        # Confirm NO Order created
        self.assertEqual(Order.objects.count(), 0)
        self.assertEqual(OrderItem.objects.count(), 0)

        ps.refresh_from_db()
        self.assertEqual(ps.status, PaymentSession.Status.FAILED)

        # Stock untouched
        self.variant.refresh_from_db()
        self.assertEqual(self.variant.stock, 10)

    @patch('apps.orders.views.SepPaymentService')
    def test_callback_successful_payment_registers_order_in_processing_status(self, mock_sep_cls):
        """Successful payment creates Order directly with 'processing' status and deducts stock."""
        mock_instance = mock_sep_cls.return_value
        mock_instance.verify_payment.return_value = {
            'success': True,
            'ref_id': 'RRN-999888',
            'payment_ref_num': 'REF-111222',
        }

        ps = PaymentSession.objects.create(
            user=self.user,
            session_key='RP-TEST5678',
            payment_method=Order.PaymentMethod.SEP,
            address_data={
                'full_name': 'Test User',
                'phone_number': '09123456789',
                'province': 'Tehran',
                'city': 'Tehran',
                'address': 'Street 1',
                'postal_code': '1234567890',
            },
            items_data=[{
                'variant_id': self.variant.id,
                'perfume_name': 'Test Perfume',
                'size': 100,
                'quantity': 2,
                'price': 100000,
                'discount_percent': 0,
            }],
            total_price=200000,
            final_price=200000,
            payment_token='sep-token-123',
            status=PaymentSession.Status.PENDING,
        )

        response = self.client.post(self.callback_url, {
            'ResNum': ps.session_key,
            'State': 'OK',
            'RefNum': 'REF-111222',
        })

        # Order created!
        self.assertEqual(Order.objects.count(), 1)
        order = Order.objects.first()
        self.assertEqual(order.order_number, ps.session_key)
        self.assertEqual(order.status, Order.Status.PROCESSING)  # "در حال پردازش"
        self.assertEqual(order.payment_ref_num, 'REF-111222')
        self.assertEqual(order.ref_id, 'RRN-999888')

        # OrderItem created
        self.assertEqual(order.items.count(), 1)
        self.assertEqual(order.items.first().quantity, 2)

        # Stock deducted
        self.variant.refresh_from_db()
        self.assertEqual(self.variant.stock, 8)

        # Session linked
        ps.refresh_from_db()
        self.assertEqual(ps.status, PaymentSession.Status.COMPLETED)
        self.assertEqual(ps.order, order)

        # Redirected to success page
        self.assertRedirects(response, reverse('orders:payment_result', kwargs={'order_number': order.order_number}))

    @patch('apps.orders.views.TorobPayService')
    def test_torobpay_successful_callback_creates_order_in_processing_status(self, mock_torob_cls):
        """TorobPay successful payment creates Order directly in processing status."""
        mock_instance = mock_torob_cls.return_value
        mock_instance.get_status.return_value = {
            'status': 'SETTLE',
            'amount': 2000000,  # 200,000 toman in rials
            'transactionId': 'RP-TOROB123',
        }

        ps = PaymentSession.objects.create(
            user=self.user,
            session_key='RP-TOROB123',
            payment_method=Order.PaymentMethod.TOROBPAY,
            address_data={
                'full_name': 'Test User',
                'phone_number': '09123456789',
                'province': 'Tehran',
                'city': 'Tehran',
                'address': 'Street 1',
                'postal_code': '1234567890',
            },
            items_data=[{
                'variant_id': self.variant.id,
                'perfume_name': 'Test Perfume',
                'size': 100,
                'quantity': 2,
                'price': 100000,
                'discount_percent': 0,
            }],
            total_price=200000,
            final_price=200000,
            torob_payment_token='torob-token-123',
            status=PaymentSession.Status.PENDING,
        )

        response = self.client.get(self.callback_url, {
            'transactionId': ps.session_key,
            'state': 'OK',
            'amount': '2000000',
        })

        self.assertEqual(Order.objects.count(), 1)
        order = Order.objects.first()
        self.assertEqual(order.order_number, ps.session_key)
        self.assertEqual(order.status, Order.Status.PROCESSING)
        self.assertEqual(order.payment_method, Order.PaymentMethod.TOROBPAY)
        self.assertEqual(order.torob_transaction_id, 'RP-TOROB123')

        ps.refresh_from_db()
        self.assertEqual(ps.status, PaymentSession.Status.COMPLETED)
        self.assertEqual(ps.order, order)

        self.assertRedirects(response, reverse('orders:payment_result', kwargs={'order_number': order.order_number}))

    def test_order_status_choices_exclude_pending_and_paid(self):
        """Neither 'pending' nor 'paid' exists in Order.Status choices."""
        status_keys = [choice[0] for choice in Order.Status.choices]
        self.assertNotIn('pending', status_keys)
        self.assertNotIn('paid', status_keys)
        self.assertIn('processing', status_keys)
        self.assertIn('shipped', status_keys)
        self.assertIn('delivered', status_keys)
        self.assertIn('return_requested', status_keys)
        self.assertIn('cancelled', status_keys)
        self.assertIn('refunded', status_keys)

    def test_cancel_processing_order_restores_stock(self):
        """User can cancel an order in processing status, which restores stock."""
        order = Order.objects.create(
            user=self.user,
            order_number='RP-CANCEL1',
            full_name='Test User',
            phone_number='09123456789',
            province='Tehran',
            city='Tehran',
            address='Street 1',
            postal_code='1234567890',
            total_price=200000,
            final_price=200000,
            status=Order.Status.PROCESSING,
        )
        OrderItem.objects.create(
            order=order,
            variant=self.variant,
            perfume_name='Test Perfume',
            size=100,
            quantity=2,
            price=100000,
        )
        self.variant.stock = 8
        self.variant.save()

        self.assertTrue(order.can_cancel)

        cancel_url = reverse('orders:cancel', kwargs={'order_number': order.order_number})
        response = self.client.post(cancel_url)
        self.assertEqual(response.status_code, 302)

        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.CANCELLED)

        self.variant.refresh_from_db()
        self.assertEqual(self.variant.stock, 10)  # Stock restored

    def test_return_request_success(self):
        """User can submit return request with a reason for an eligible order."""
        order = Order.objects.create(
            user=self.user,
            order_number='RP-RET1',
            full_name='Test User',
            phone_number='09123456789',
            province='Tehran',
            city='Tehran',
            address='Street 1',
            postal_code='1234567890',
            total_price=100000,
            final_price=100000,
            status=Order.Status.DELIVERED,
        )
        self.assertTrue(order.can_return)

        return_url = reverse('orders:request_return', kwargs={'order_number': order.order_number})
        reason = 'محصول دچار شکستگی شیشه در حین ارسال شده است.'
        response = self.client.post(return_url, {'return_reason': reason})

        self.assertRedirects(response, reverse('orders:detail', kwargs={'order_number': order.order_number}))

        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.RETURN_REQUESTED)
        self.assertEqual(order.return_reason, reason)
        self.assertIsNotNone(order.return_requested_at)
        self.assertFalse(order.can_return)
        self.assertFalse(order.can_cancel)

    def test_return_request_without_reason_fails(self):
        """Submitting return request without reason redirects with error and leaves status unchanged."""
        order = Order.objects.create(
            user=self.user,
            order_number='RP-RET2',
            full_name='Test User',
            phone_number='09123456789',
            province='Tehran',
            city='Tehran',
            address='Street 1',
            postal_code='1234567890',
            total_price=100000,
            final_price=100000,
            status=Order.Status.DELIVERED,
        )

        return_url = reverse('orders:request_return', kwargs={'order_number': order.order_number})
        response = self.client.post(return_url, {'return_reason': '   '})

        self.assertRedirects(response, reverse('orders:detail', kwargs={'order_number': order.order_number}))

        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.DELIVERED)
        self.assertEqual(order.return_reason, '')
        self.assertIsNone(order.return_requested_at)

    def test_return_request_on_cancelled_order_fails(self):
        """User cannot submit return request for a cancelled order."""
        order = Order.objects.create(
            user=self.user,
            order_number='RP-RET3',
            full_name='Test User',
            phone_number='09123456789',
            province='Tehran',
            city='Tehran',
            address='Street 1',
            postal_code='1234567890',
            total_price=100000,
            final_price=100000,
            status=Order.Status.CANCELLED,
        )
        self.assertFalse(order.can_return)

        return_url = reverse('orders:request_return', kwargs={'order_number': order.order_number})
        response = self.client.post(return_url, {'return_reason': 'علت لغو قبلی'})

        self.assertRedirects(response, reverse('orders:detail', kwargs={'order_number': order.order_number}))

        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.CANCELLED)

    def test_return_request_by_another_user_returns_404(self):
        """User cannot submit return request on another user's order."""
        other_user = CustomUser.objects.create_user(
            phone_number='09999999999',
            full_name='Other User',
        )
        order = Order.objects.create(
            user=other_user,
            order_number='RP-RET4',
            full_name='Other User',
            phone_number='09999999999',
            province='Tehran',
            city='Tehran',
            address='Street 1',
            postal_code='1234567890',
            total_price=100000,
            final_price=100000,
            status=Order.Status.DELIVERED,
        )

        return_url = reverse('orders:request_return', kwargs={'order_number': order.order_number})
        response = self.client.post(return_url, {'return_reason': 'تلاش کاربر دیگر'})
        self.assertEqual(response.status_code, 404)
        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.DELIVERED)

    def test_cancel_return_request_restores_previous_status(self):
        """User can cancel return request, reverting order to its previous status."""
        order = Order.objects.create(
            user=self.user,
            order_number='RP-RET-CANCEL',
            full_name='Test User',
            phone_number='09123456789',
            province='Tehran',
            city='Tehran',
            address='Street 1',
            postal_code='1234567890',
            total_price=100000,
            final_price=100000,
            status=Order.Status.RETURN_REQUESTED,
            pre_return_status=Order.Status.SHIPPED,
            return_reason='انصراف دادم',
        )
        self.assertTrue(order.can_cancel_return)

        cancel_return_url = reverse('orders:cancel_return', kwargs={'order_number': order.order_number})
        response = self.client.post(cancel_return_url)

        self.assertRedirects(response, reverse('orders:detail', kwargs={'order_number': order.order_number}))

        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.SHIPPED)
        self.assertEqual(order.pre_return_status, '')
        self.assertEqual(order.return_reason, '')
        self.assertIsNone(order.return_requested_at)

    def test_cancel_return_request_on_non_return_requested_order_fails(self):
        """Cannot cancel return request if order is not in RETURN_REQUESTED status."""
        order = Order.objects.create(
            user=self.user,
            order_number='RP-RET-INVALID',
            full_name='Test User',
            phone_number='09123456789',
            province='Tehran',
            city='Tehran',
            address='Street 1',
            postal_code='1234567890',
            total_price=100000,
            final_price=100000,
            status=Order.Status.PROCESSING,
        )
        self.assertFalse(order.can_cancel_return)

        cancel_return_url = reverse('orders:cancel_return', kwargs={'order_number': order.order_number})
        response = self.client.post(cancel_return_url)

        self.assertRedirects(response, reverse('orders:detail', kwargs={'order_number': order.order_number}))

        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.PROCESSING)

    @staticmethod
    def _create_test_image(format='JPEG', size=(50, 50), color=(255, 0, 0)):
        buffer = io.BytesIO()
        image = Image.new('RGB', size, color=color)
        image.save(buffer, format=format)
        buffer.seek(0)
        return buffer.getvalue()

    def test_return_request_with_valid_image_success(self):
        """User can submit return request with a reason and a valid uploaded image."""
        order = Order.objects.create(
            user=self.user,
            order_number='RP-RET-IMG1',
            full_name='Test User',
            phone_number='09123456789',
            province='Tehran',
            city='Tehran',
            address='Street 1',
            postal_code='1234567890',
            total_price=100000,
            final_price=100000,
            status=Order.Status.DELIVERED,
        )

        image_data = self._create_test_image(format='JPEG')
        uploaded_image = SimpleUploadedFile(
            name='damaged_bottle.jpg',
            content=image_data,
            content_type='image/jpeg'
        )

        return_url = reverse('orders:request_return', kwargs={'order_number': order.order_number})
        reason = 'شیشه عطر هنگام تحویل ترک خورده و نشتی دارد.'
        response = self.client.post(return_url, {
            'return_reason': reason,
            'return_image': uploaded_image,
        })

        self.assertRedirects(response, reverse('orders:detail', kwargs={'order_number': order.order_number}))

        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.RETURN_REQUESTED)
        self.assertEqual(order.return_reason, reason)
        self.assertTrue(bool(order.return_image))
        # Verify safe filename is used instead of user-supplied name
        self.assertNotIn('damaged_bottle.jpg', order.return_image.name)
        self.assertTrue(order.return_image.name.startswith(f'returns/{order.order_number}/'))
        self.assertTrue(order.return_image.name.endswith('.jpg'))
        self.assertTrue(default_storage.exists(order.return_image.name))

        # Cleanup test image from disk
        order.return_image.delete(save=False)

    def test_return_request_with_oversized_image_fails(self):
        """Uploading an image larger than 5MB fails validation and does not update order."""
        order = Order.objects.create(
            user=self.user,
            order_number='RP-RET-OVERSIZE',
            full_name='Test User',
            phone_number='09123456789',
            province='Tehran',
            city='Tehran',
            address='Street 1',
            postal_code='1234567890',
            total_price=100000,
            final_price=100000,
            status=Order.Status.DELIVERED,
        )

        # 5MB + 1024 bytes
        large_content = b'0' * (5 * 1024 * 1024 + 1024)
        uploaded_image = SimpleUploadedFile(
            name='large.jpg',
            content=large_content,
            content_type='image/jpeg'
        )

        return_url = reverse('orders:request_return', kwargs={'order_number': order.order_number})
        response = self.client.post(return_url, {
            'return_reason': 'محصول مغایرت دارد و حجم عکس زیاد است.',
            'return_image': uploaded_image,
        })

        self.assertRedirects(response, reverse('orders:detail', kwargs={'order_number': order.order_number}))

        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.DELIVERED)
        self.assertFalse(bool(order.return_image))

    def test_return_request_with_disallowed_extension_fails(self):
        """Uploading an executable/disallowed extension fails validation."""
        order = Order.objects.create(
            user=self.user,
            order_number='RP-RET-EXT',
            full_name='Test User',
            phone_number='09123456789',
            province='Tehran',
            city='Tehran',
            address='Street 1',
            postal_code='1234567890',
            total_price=100000,
            final_price=100000,
            status=Order.Status.DELIVERED,
        )

        uploaded_file = SimpleUploadedFile(
            name='malicious.php',
            content=b'<?php phpinfo(); ?>',
            content_type='application/x-php'
        )

        return_url = reverse('orders:request_return', kwargs={'order_number': order.order_number})
        response = self.client.post(return_url, {
            'return_reason': 'تست آپلود غیرمجاز با فایل نامعتبر',
            'return_image': uploaded_file,
        })

        self.assertRedirects(response, reverse('orders:detail', kwargs={'order_number': order.order_number}))

        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.DELIVERED)
        self.assertFalse(bool(order.return_image))

    def test_return_request_with_fake_image_fails_pillow_check(self):
        """Uploading a non-image file renamed with .jpg extension fails deep validation."""
        order = Order.objects.create(
            user=self.user,
            order_number='RP-RET-FAKE',
            full_name='Test User',
            phone_number='09123456789',
            province='Tehran',
            city='Tehran',
            address='Street 1',
            postal_code='1234567890',
            total_price=100000,
            final_price=100000,
            status=Order.Status.DELIVERED,
        )

        fake_image = SimpleUploadedFile(
            name='not_an_image.jpg',
            content=b'<script>alert("xss")</script>',
            content_type='image/jpeg'
        )

        return_url = reverse('orders:request_return', kwargs={'order_number': order.order_number})
        response = self.client.post(return_url, {
            'return_reason': 'تست تصویر جعلی با کد مخرب درون هدر',
            'return_image': fake_image,
        })

        self.assertRedirects(response, reverse('orders:detail', kwargs={'order_number': order.order_number}))

        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.DELIVERED)
        self.assertFalse(bool(order.return_image))

    def test_cancel_return_request_cleans_up_uploaded_image(self):
        """Cancelling return request deletes the uploaded image from disk storage."""
        order = Order.objects.create(
            user=self.user,
            order_number='RP-RET-CLEAN',
            full_name='Test User',
            phone_number='09123456789',
            province='Tehran',
            city='Tehran',
            address='Street 1',
            postal_code='1234567890',
            total_price=100000,
            final_price=100000,
            status=Order.Status.DELIVERED,
        )

        image_data = self._create_test_image(format='PNG')
        uploaded_image = SimpleUploadedFile(
            name='item_photo.png',
            content=image_data,
            content_type='image/png'
        )

        return_url = reverse('orders:request_return', kwargs={'order_number': order.order_number})
        self.client.post(return_url, {
            'return_reason': 'کالای ارسالی با فاکتور مطابقت ندارد.',
            'return_image': uploaded_image,
        })

        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.RETURN_REQUESTED)
        self.assertTrue(bool(order.return_image))
        image_path = order.return_image.name
        self.assertTrue(default_storage.exists(image_path))

        # Now cancel the return request
        cancel_url = reverse('orders:cancel_return', kwargs={'order_number': order.order_number})
        cancel_res = self.client.post(cancel_url)
        self.assertRedirects(cancel_res, reverse('orders:detail', kwargs={'order_number': order.order_number}))

        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.DELIVERED)
        self.assertFalse(bool(order.return_image))
        # Verify file is deleted from disk
        self.assertFalse(default_storage.exists(image_path))


@override_settings(SECURE_SSL_REDIRECT=False)
class DirectPaymentTests(TestCase):
    def setUp(self):
        self.user = CustomUser.objects.create_user(
            phone_number='09123456789',
            full_name='محمد رضایی',
            email='mohammad@example.com'
        )
        self.other_user = CustomUser.objects.create_user(
            phone_number='09987654321',
            full_name='علی احمدی',
            email='ali@example.com'
        )
        self.admin_user = CustomUser.objects.create_superuser(
            phone_number='09000000000',
            full_name='مدیر سیستم',
            password='admin_password_123'
        )
        self.client.force_login(self.user)

    def test_pay_page_requires_login(self):
        """ورود به صفحه /pay بدون لاگین به صفحه ورود هدایت می‌شود"""
        self.client.logout()
        response = self.client.get('/pay/')
        self.assertEqual(response.status_code, 302)
        self.assertIn('/accounts/login/', response.url)

    def test_pay_page_renders_for_logged_in_user(self):
        """کاربر لاگین کرده به صفحه پرداخت دسترسی دارد و اطلاعات وی نمایش داده می‌شود"""
        self.client.force_login(self.user)
        response = self.client.get('/pay/')
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'orders/pay.html')
        self.assertContains(response, 'محمد رضایی')
        self.assertContains(response, 'درگاه بانکی سپ')
        self.assertContains(response, 'پرداخت اعتباری ترب‌پی')

    @patch('apps.orders.views.SepPaymentService.request_payment')
    def test_pay_submission_with_sep(self, mock_request_payment):
        """ارسال فرم با درگاه سپ، رکورد پرداخت در وضعیت PENDING می‌سازد و به درگاه هدایت می‌کند"""
        mock_request_payment.return_value = {
            'success': True,
            'token': 'mock_sep_token_999',
            'url': 'https://sep.shaparak.ir/OnlinePG/OnlinePG'
        }
        self.client.force_login(self.user)
        response = self.client.post('/pay/', {
            'amount': '۵۰,۰۰۰',  # ورودی فارسی همراه با کاما
            'payment_method': 'sep',
            'description': 'بابت تست درگاه سپ'
        })
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'orders/redirect_to_gateway.html')

        payment = DirectPayment.objects.filter(user=self.user).first()
        self.assertIsNotNone(payment)
        self.assertEqual(payment.amount, 50000)
        self.assertEqual(payment.payment_method, 'sep')
        self.assertEqual(payment.description, 'بابت تست درگاه سپ')
        self.assertEqual(payment.status, DirectPayment.Status.PENDING)
        self.assertEqual(payment.payment_token, 'mock_sep_token_999')

    @patch('apps.orders.views.TorobPayService.create_direct_payment')
    def test_pay_submission_with_torobpay(self, mock_torob_payment):
        """ارسال فرم با ترب‌پی، رکورد پرداخت را ساخته و به درگاه ترب هدایت می‌کند"""
        mock_torob_payment.return_value = {
            'payment_token': 'mock_torob_token_888',
            'payment_page_url': 'https://cpg.torobpay.com/pay/888'
        }
        self.client.force_login(self.user)
        response = self.client.post('/pay/', {
            'amount': '150000',
            'payment_method': 'torobpay',
            'description': 'خرید اقساطی ترب'
        })
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'orders/redirect_to_gateway.html')

        payment = DirectPayment.objects.filter(user=self.user).first()
        self.assertIsNotNone(payment)
        self.assertEqual(payment.amount, 150000)
        self.assertEqual(payment.payment_method, 'torobpay')
        self.assertEqual(payment.torob_payment_token, 'mock_torob_token_888')

    @patch('apps.orders.views.SepPaymentService.verify_payment')
    def test_sep_callback_successful(self, mock_verify):
        """کال‌بک موفق سپ، پرداخت را تکمیل کرده و به صفحه نتیجه هدایت می‌کند"""
        mock_verify.return_value = {
            'success': True,
            'ref_id': 'RRN-998877',
            'payment_ref_num': 'REF-112233'
        }
        payment = DirectPayment.objects.create(
            user=self.user,
            amount=50000,
            payment_method='sep',
            status=DirectPayment.Status.PENDING
        )

        response = self.client.post('/pay/callback/', {
            'ResNum': payment.tracking_number,
            'State': 'OK',
            'RefNum': 'REF-112233',
            'TerminalId': settings.SEP_TERMINAL_ID,
            'CID': '603799******1234'
        })
        self.assertRedirects(response, f'/pay/result/{payment.tracking_number}/')

        payment.refresh_from_db()
        self.assertEqual(payment.status, DirectPayment.Status.COMPLETED)
        self.assertEqual(payment.ref_id, 'RRN-998877')
        self.assertEqual(payment.payment_ref_num, 'REF-112233')
        self.assertEqual(payment.card_number, '603799******1234')
        self.assertIsNotNone(payment.paid_at)

    def test_sep_callback_failed(self):
        """کال‌بک ناموفق سپ، وضعیت پرداخت را FAILED قرار می‌دهد"""
        payment = DirectPayment.objects.create(
            user=self.user,
            amount=50000,
            payment_method='sep',
            status=DirectPayment.Status.PENDING
        )
        response = self.client.post('/pay/callback/', {
            'ResNum': payment.tracking_number,
            'State': 'CanceledByUser',
            'RefNum': ''
        })
        self.assertRedirects(response, f'/pay/result/{payment.tracking_number}/')
        payment.refresh_from_db()
        self.assertEqual(payment.status, DirectPayment.Status.FAILED)

    @patch('apps.orders.views.TorobPayService.get_status')
    def test_torobpay_callback_successful(self, mock_get_status):
        """کال‌بک ترب‌پی در صورت تأیید تسویه، پرداخت را موفق ثبت می‌کند"""
        mock_get_status.return_value = {
            'status': 'SETTLE',
            'amount': 500000,  # ریال
            'transactionId': 'TX-TOROB-777'
        }
        payment = DirectPayment.objects.create(
            user=self.user,
            amount=50000,  # تومان
            payment_method='torobpay',
            torob_payment_token='token_torob_test',
            status=DirectPayment.Status.PENDING
        )

        response = self.client.get(f'/pay/callback/?transactionId={payment.tracking_number}&state=OK&amount=500000')
        self.assertRedirects(response, f'/pay/result/{payment.tracking_number}/')

        payment.refresh_from_db()
        self.assertEqual(payment.status, DirectPayment.Status.COMPLETED)
        self.assertEqual(payment.ref_id, 'TX-TOROB-777')
        self.assertIsNotNone(payment.paid_at)

    @patch('apps.orders.views.TorobPayService.get_status')
    def test_torobpay_callback_timeout_keeps_pending_and_retries(self, mock_get_status):
        """در صورت بروز تایم‌اوت ترب‌پی در کال‌بک، تراکنش به عنوان PENDING حفظ شده و با دکمه استعلام مجدد تکمیل می‌شود"""
        from apps.orders.torobpay import TorobPayError

        # ابتدا در کال‌بک، ترب‌پی دچار تایم‌اوت می‌شود
        mock_get_status.side_effect = TorobPayError('Read timed out')
        payment = DirectPayment.objects.create(
            user=self.user,
            amount=50000,
            payment_method='torobpay',
            torob_payment_token='token_timeout_test',
            status=DirectPayment.Status.PENDING
        )

        response = self.client.get(f'/pay/callback/?transactionId={payment.tracking_number}&state=OK&amount=500000')
        payment.refresh_from_db()
        # نباید بلافاصله FAILED شود تا وجه مشتری از دست نرود
        self.assertEqual(payment.status, DirectPayment.Status.PENDING)

        # حالا در استعلام مجدد، ترب‌پی پاسخ موفق می‌دهد
        mock_get_status.side_effect = None
        mock_get_status.return_value = {
            'status': 'SETTLE',
            'amount': 500000,
            'transactionId': 'TX-RETRY-SUCCESS-123'
        }
        retry_response = self.client.post(f'/pay/retry/{payment.tracking_number}/')
        self.assertRedirects(retry_response, f'/pay/result/{payment.tracking_number}/')

        payment.refresh_from_db()
        self.assertEqual(payment.status, DirectPayment.Status.COMPLETED)
        self.assertEqual(payment.ref_id, 'TX-RETRY-SUCCESS-123')
        self.assertIsNotNone(payment.paid_at)

    def test_direct_payment_result_permissions(self):
        """کاربر مالک می‌تواند رسید پرداخت را ببیند، اما کاربر دیگر به خانه هدایت می‌شود"""
        payment = DirectPayment.objects.create(
            user=self.user,
            amount=50000,
            status=DirectPayment.Status.COMPLETED,
            ref_id='12345678'
        )

        # کاربر صاحب پرداخت
        self.client.force_login(self.user)
        response = self.client.get(f'/pay/result/{payment.tracking_number}/')
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'orders/pay_result.html')
        self.assertContains(response, 'پرداخت با موفقیت انجام شد')
        self.assertContains(response, payment.tracking_number)

        # کاربر بدون لاگین اما دارای نشست پرداخت معتبر (حالت بازگشت از درگاه)
        self.client.logout()
        session = self.client.session
        session['direct_pay_tracking'] = payment.tracking_number
        session.save()
        response_session = self.client.get(f'/pay/result/{payment.tracking_number}/')
        self.assertEqual(response_session.status_code, 200)
        self.assertContains(response_session, payment.tracking_number)

        # کاربر غریبه بدون لاگین و بدون نشست پرداخت (هدایت به لاگین)
        self.client.session.flush()
        response_anon = self.client.get(f'/pay/result/{payment.tracking_number}/')
        self.assertEqual(response_anon.status_code, 302)
        self.assertIn('/accounts/login/', response_anon.url)

        # کاربر لاگین‌کرده دیگر (غیره)
        self.client.force_login(self.other_user)
        response_other = self.client.get(f'/pay/result/{payment.tracking_number}/')
        self.assertEqual(response_other.status_code, 302)
        self.assertEqual(response_other.url, '/')

    def test_admin_displays_direct_payments(self):
        """پرداخت‌ها در پنل ادمین ثبت و با فیلدها و بج وضعیت نمایش داده می‌شوند"""
        payment = DirectPayment.objects.create(
            user=self.user,
            amount=75000,
            payment_method='sep',
            status=DirectPayment.Status.COMPLETED,
            ref_id='ADMIN-REF-123',
            description='توضیحات تست در ادمین'
        )

        self.client.force_login(self.admin_user)
        admin_list_url = reverse('admin:orders_directpayment_changelist')
        response = self.client.get(admin_list_url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, payment.tracking_number)
        self.assertContains(response, '75,000 تومان')
        self.assertContains(response, 'موفق')

        admin_detail_url = reverse('admin:orders_directpayment_change', args=[payment.pk])
        detail_response = self.client.get(admin_detail_url)
        self.assertEqual(detail_response.status_code, 200)
        self.assertContains(detail_response, 'توضیحات تست در ادمین')
        self.assertContains(detail_response, 'ADMIN-REF-123')

