import requests
from django.conf import settings


class ZarinPalService:
    """
    سرویس درگاه پرداخت زرین‌پال
    پشتیبانی از حالت Sandbox و Production
    """

    def __init__(self):
        self.merchant_id = settings.ZARINPAL_MERCHANT_ID
        self.is_sandbox = getattr(settings, 'ZARINPAL_SANDBOX', True)

        if self.is_sandbox:
            self.request_url = 'https://sandbox.zarinpal.com/pg/v4/payment/request.json'
            self.verify_url = 'https://sandbox.zarinpal.com/pg/v4/payment/verify.json'
            self.gateway_url = 'https://sandbox.zarinpal.com/pg/StartPay/{authority}'
        else:
            self.request_url = 'https://api.zarinpal.com/pg/v4/payment/request.json'
            self.verify_url = 'https://api.zarinpal.com/pg/v4/payment/verify.json'
            self.gateway_url = 'https://www.zarinpal.com/pg/StartPay/{authority}'

    def request_payment(self, amount, description, callback_url, mobile=None, email=None):
        """
        ارسال درخواست پرداخت
        
        Args:
            amount: مبلغ به تومان
            description: توضیحات پرداخت
            callback_url: آدرس بازگشت
            mobile: شماره موبایل (اختیاری)
            email: ایمیل (اختیاری)
        
        Returns:
            dict: {'success': bool, 'authority': str, 'url': str} or {'success': bool, 'error': str}
        """
        data = {
            'merchant_id': self.merchant_id,
            'amount': amount * 10,  # تبدیل تومان به ریال
            'description': description,
            'callback_url': callback_url,
        }

        # اطلاعات اختیاری
        metadata = {}
        if mobile:
            metadata['mobile'] = mobile
        if email:
            metadata['email'] = email
        if metadata:
            data['metadata'] = metadata

        try:
            response = requests.post(
                self.request_url,
                json=data,
                timeout=10
            )
            result = response.json()

            if result.get('data', {}).get('code') == 100:
                authority = result['data']['authority']
                return {
                    'success': True,
                    'authority': authority,
                    'url': self.gateway_url.format(authority=authority),
                }
            else:
                errors = result.get('errors', {})
                return {
                    'success': False,
                    'error': str(errors.get('message', 'خطای ناشناخته')),
                }

        except requests.RequestException as e:
            return {
                'success': False,
                'error': f'خطا در اتصال به درگاه پرداخت: {str(e)}',
            }

    def verify_payment(self, authority, amount):
        """
        تأیید پرداخت
        
        Args:
            authority: کد Authority دریافتی
            amount: مبلغ به تومان
        
        Returns:
            dict: {'success': bool, 'ref_id': str} or {'success': bool, 'error': str}
        """
        data = {
            'merchant_id': self.merchant_id,
            'authority': authority,
            'amount': amount * 10,  # تبدیل تومان به ریال
        }

        try:
            response = requests.post(
                self.verify_url,
                json=data,
                timeout=10
            )
            result = response.json()

            code = result.get('data', {}).get('code')
            if code == 100:
                return {
                    'success': True,
                    'ref_id': str(result['data']['ref_id']),
                }
            elif code == 101:
                # پرداخت قبلاً تأیید شده
                return {
                    'success': True,
                    'ref_id': str(result['data']['ref_id']),
                    'already_verified': True,
                }
            else:
                return {
                    'success': False,
                    'error': 'پرداخت ناموفق بود',
                }

        except requests.RequestException as e:
            return {
                'success': False,
                'error': f'خطا در تأیید پرداخت: {str(e)}',
            }
