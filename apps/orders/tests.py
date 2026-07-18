from django.test import TestCase
from django.urls import reverse
from apps.accounts.models import CustomUser
from apps.products.models import Perfume, PerfumeVariant

class OrderCreateAddressValidationTests(TestCase):
    def setUp(self):
        # Create user
        self.user = CustomUser.objects.create_user(
            phone_number='09123456789',
            full_name='Test User',
            email='testuser@example.com'
        )
        self.client.force_login(self.user)

        # Create Perfume and Variant
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

        # Setup cart in session
        session = self.client.session
        session['cart'] = {
            str(self.variant.id): {
                'quantity': 1,
                'price': 100000
            }
        }
        session.save()

        self.create_url = reverse('orders:create')
        self.checkout_url = reverse('orders:checkout')

    def test_create_order_without_address_id(self):
        """
        Submitting the create order form without address_id should redirect
        to the checkout page with an error message.
        """
        response = self.client.post(self.create_url, {})
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, self.checkout_url)

        # Verify the error message is present
        messages = list(response.wsgi_request._messages)
        self.assertEqual(len(messages), 1)
        self.assertEqual(str(messages[0]), 'لطفاً یک آدرس برای ارسال سفارش انتخاب کنید.')

    def test_create_order_with_invalid_address_id(self):
        """
        Submitting the create order form with an invalid address_id should redirect
        to the checkout page with an error message.
        """
        response = self.client.post(self.create_url, {'address_id': 99999})
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, self.checkout_url)

        # Verify the error message is present
        messages = list(response.wsgi_request._messages)
        self.assertEqual(len(messages), 1)
        self.assertEqual(str(messages[0]), 'آدرس انتخاب شده معتبر نیست. لطفاً یک آدرس معتبر انتخاب کنید.')
