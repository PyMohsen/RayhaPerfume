"""TorobPay CPG integration.

All amounts passed to TorobPay are in rials; this shop stores prices in toman.
"""
import logging
from urllib.parse import urlparse

import requests
from django.conf import settings
from django.core.cache import cache

logger = logging.getLogger(__name__)


class TorobPayError(Exception):
    """Raised when TorobPay rejects a request or returns an invalid response."""


class TorobPayService:
    BASE_URL = 'https://cpg.torobpay.com'
    TOKEN_URL = '/api/online/v1/oauth/token'
    ELIGIBLE_URL = '/api/online/offer/v1/eligible'
    PAYMENT_URL = '/api/online/payment/v1/token'
    VERIFY_URL = '/api/online/payment/v1/verify'
    SETTLE_URL = '/api/online/payment/v1/settle'
    STATUS_URL = '/api/online/payment/v1/status'
    CANCEL_URL = '/api/online/payment/v1/cancel'
    REQUEST_TIMEOUT = (5, 15)
    CACHE_KEY = 'torobpay_access_token'

    def __init__(self):
        self.client_id = getattr(settings, 'TOROBPAY_CLIENT_ID', '').strip()
        self.client_secret = getattr(settings, 'TOROBPAY_CLIENT_SECRET', '').strip()
        self.username = getattr(settings, 'TOROBPAY_USERNAME', '').strip()
        self.password = getattr(settings, 'TOROBPAY_PASSWORD', '').strip()

    @property
    def configured(self):
        return all((self.client_id, self.client_secret, self.username, self.password))

    def _access_token(self, force_refresh=False):
        if not self.configured:
            raise TorobPayError('تنظیمات اتصال ترب‌پی کامل نیست.')
        if not force_refresh:
            cached = cache.get(self.CACHE_KEY)
            if cached:
                return cached

        try:
            response = requests.post(
                self.BASE_URL + self.TOKEN_URL,
                auth=(self.client_id, self.client_secret),
                json={'username': self.username, 'password': self.password},
                timeout=self.REQUEST_TIMEOUT,
            )
            response.raise_for_status()
            data = response.json()
        except (requests.RequestException, ValueError) as exc:
            logger.warning('TorobPay authentication request failed: %s', exc)
            raise TorobPayError('احراز هویت در ترب‌پی انجام نشد.') from exc

        token = data.get('access_token') if isinstance(data, dict) else None
        if not token:
            raise TorobPayError('پاسخ احراز هویت ترب‌پی معتبر نیست.')
        # The documented JWT lifetime is one hour; expire early to avoid edge races.
        cache.set(self.CACHE_KEY, token, timeout=3500)
        return token

    def _request(self, method, path, *, params=None, payload=None):
        for attempt in range(2):
            token = self._access_token(force_refresh=bool(attempt))
            try:
                response = requests.request(
                    method,
                    self.BASE_URL + path,
                    headers={'Authorization': f'Bearer {token}'},
                    params=params,
                    json=payload,
                    timeout=self.REQUEST_TIMEOUT,
                )
                if response.status_code == 401 and attempt == 0:
                    cache.delete(self.CACHE_KEY)
                    continue
                response.raise_for_status()
                data = response.json()
            except (requests.RequestException, ValueError) as exc:
                logger.warning('TorobPay %s request failed: %s', path, exc)
                raise TorobPayError('ارتباط با سرویس ترب‌پی برقرار نشد.') from exc
            if not isinstance(data, dict) or data.get('successful') is not True:
                logger.warning('TorobPay %s returned an unsuccessful response: %s', path, data)
                raise TorobPayError('ترب‌پی درخواست را نپذیرفت.')
            return data.get('response') or {}
        raise TorobPayError('احراز هویت ترب‌پی معتبر نیست.')

    def is_eligible(self, amount_toman):
        """Return False on any eligibility error; SEP remains available."""
        try:
            amount_rial = int(amount_toman) * 10
            if amount_rial <= 0:
                return False
            result = self._request('GET', self.ELIGIBLE_URL, params={'amount': amount_rial})
            return result.get('eligible') is True
        except (TorobPayError, TypeError, ValueError):
            return False

    def create_payment(self, *, order, items, return_url):
        cart_items = []
        for item in items:
            unit_price = item['variant'].price
            cart_items.append({
                'id': str(item['variant'].pk),
                'name': f"{item['variant'].perfume.name} ({item['variant'].size}ml)",
                'count': int(item['quantity']),
                'amount': int(unit_price) * 10,
                'category': 'عطر',
                'commissionType': 0,
            })
        payload = {
            'amount': int(order.final_price) * 10,
            'discountAmount': (int(order.discount_amount) + int(order.coupon_discount)) * 10,
            'externalSourceAmount': 0,
            'mobile': order.phone_number,
            'paymentMethodTypeDto': 'ONLINE_CREDIT',
            'returnURL': return_url,
            'transactionId': order.order_number,
            'customer_full_name': order.full_name,
            'registration_phone_number': order.user.phone_number,
            'address': order.address,
            'postalCode': order.postal_code,
            'city': order.city,
            'province': order.province,
            'cartList': [{
                'cartId': order.order_number,
                'totalAmount': (int(order.total_price) + int(order.shipping_cost)) * 10,
                'taxAmount': 0,
                'shippingAmount': int(order.shipping_cost) * 10,
                'isTaxIncluded': True,
                'isShipmentIncluded': True,
                'cartItems': cart_items,
            }],
        }
        result = self._request('POST', self.PAYMENT_URL, payload=payload)
        payment_token = result.get('paymentToken')
        payment_page_url = result.get('paymentPageUrl')
        parsed_url = urlparse(str(payment_page_url or ''))
        if (
            not payment_token
            or len(str(payment_token)) > 200
            or parsed_url.scheme != 'https'
            or not parsed_url.netloc
        ):
            raise TorobPayError('اطلاعات صفحه پرداخت ترب‌پی معتبر نیست.')
        return {'payment_token': str(payment_token), 'payment_page_url': str(payment_page_url)}

    def verify(self, payment_token):
        return self._request('POST', self.VERIFY_URL, payload={'paymentToken': payment_token})

    def settle(self, payment_token):
        return self._request('POST', self.SETTLE_URL, payload={'paymentToken': payment_token})

    def get_status(self, payment_token):
        return self._request('GET', self.STATUS_URL, params={'paymentToken': payment_token})

    def cancel(self, payment_token):
        return self._request('POST', self.CANCEL_URL, payload={'paymentToken': payment_token})
