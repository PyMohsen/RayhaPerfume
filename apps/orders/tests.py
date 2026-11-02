from unittest.mock import patch

from django.conf import settings
from django.test import TestCase, override_settings
from django.urls import reverse

from apps.accounts.models import CustomUser, UserAddress
from apps.orders.models import Order, OrderItem, PaymentSession
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
