import requests
import time

from django.conf import settings


class SepPaymentService:
    """درگاه پرداخت اینترنتی سپ (پرداخت الکترونیک سامان)."""

    TOKEN_URL = 'https://sep.shaparak.ir/onlinepg/onlinepg'
    PAYMENT_URL = 'https://sep.shaparak.ir/OnlinePG/OnlinePG'
    VERIFY_URL = 'https://sep.shaparak.ir/verifyTxnRandomSessionkey/ipg/VerifyTransaction'

    def __init__(self):
        self.terminal_id = settings.SEP_TERMINAL_ID

    def request_payment(self, amount, res_num, callback_url, mobile=None):
        """دریافت توکن SEP؛ amount ورودی به تومان و Amount ارسالی به ریال است."""
        if not self.terminal_id:
            return {'success': False, 'error': 'شناسه ترمینال درگاه سپ تنظیم نشده است.'}

        data = {
            # نام پارامترها مطابق مستند SEP حساس به بزرگی/کوچکی حروف است.
            'action': 'token',
            'TerminalId': self.terminal_id,
            'Amount': int(amount) * 10,
            'ResNum': res_num,
            'RedirectUrl': callback_url,
        }
        if mobile:
            data['CellNumber'] = mobile

        try:
            response = requests.post(self.TOKEN_URL, json=data, timeout=15)
            response.raise_for_status()
            result = response.json()
        except (requests.RequestException, ValueError) as exc:
            return {'success': False, 'error': f'خطا در دریافت توکن درگاه سپ: {exc}'}
        if not isinstance(result, dict):
            return {'success': False, 'error': 'پاسخ درگاه سپ معتبر نیست.'}

        token = result.get('token')
        if result.get('status') == 1 and token:
            return {
                'success': True,
                'token': str(token),
                # ترمینال‌های Neo-PG آدرس پرداخت را در header پاسخ برمی‌گردانند.
                'url': response.headers.get('X-IPG-Url') or self.PAYMENT_URL,
            }
        return {
            'success': False,
            'error': result.get('errorDesc', 'درگاه سپ درخواست پرداخت را نپذیرفت.'),
        }

    def verify_payment(self, ref_num, amount):
        """تأیید پرداخت و تطبیق مبلغ اصلی تراکنش (هر دو به ریال)."""
        if not self.terminal_id or not ref_num:
            return {'success': False, 'error': 'اطلاعات تأیید پرداخت ناقص است.'}
        try:
            terminal_number = int(self.terminal_id)
        except (TypeError, ValueError):
            return {'success': False, 'error': 'شناسه ترمینال سپ معتبر نیست.'}

        result = None
        for attempt in range(3):
            try:
                response = requests.post(
                    self.VERIFY_URL,
                    json={'RefNum': ref_num, 'TerminalNumber': terminal_number},
                    timeout=15,
                )
                response.raise_for_status()
                result = response.json()
                break
            except (requests.Timeout, requests.ConnectionError) as exc:
                if attempt == 2:
                    return {'success': False, 'error': f'خطا در تأیید پرداخت سپ: {exc}'}
                time.sleep(1)
            except (requests.RequestException, ValueError) as exc:
                return {'success': False, 'error': f'خطا در تأیید پرداخت سپ: {exc}'}
        if not isinstance(result, dict):
            return {'success': False, 'error': 'پاسخ تأیید درگاه سپ معتبر نیست.'}

        detail = result.get('TransactionDetail') or {}
        verified_amount = detail.get('OrginalAmount')
        verified_ref = str(detail.get('RefNum', ''))
        try:
            amount_matches = int(verified_amount) == int(amount) * 10
        except (TypeError, ValueError):
            amount_matches = False
        if (
            result.get('Success') is True
            and result.get('ResultCode') == 0
            and verified_ref == str(ref_num)
            and amount_matches
        ):
            return {
                'success': True,
                'ref_id': str(detail.get('RRN') or detail.get('StraceNo') or ref_num),
                'payment_ref_num': verified_ref,
            }

        return {
            'success': False,
            'error': result.get('ResultDescription', 'تأیید پرداخت یا مبلغ تراکنش معتبر نیست.'),
        }
