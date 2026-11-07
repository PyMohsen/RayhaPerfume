"""
دستور مدیریتی جهت تست ارتباط و ارسال پیام به گروه ایتا از طریق وب‌سرویس ایتایار

نحوه استفاده:
python manage.py test_eitaa
python manage.py test_eitaa --text="پیام تستی سفارشی"
"""

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.orders.eitaayar import EitaayarService, format_datetime_jalali


class Command(BaseCommand):
    help = 'تست ارسال پیام به گروه ایتا از طریق وب‌سرویس ایتایار (eitaayar.ir)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--text',
            type=str,
            default=None,
            help='متن پیام تستی دلخواه جهت ارسال به گروه',
        )

    def handle(self, *args, **options):
        token = getattr(settings, 'EITAAYAR_TOKEN', '').strip()
        chat_id = getattr(settings, 'EITAAYAR_CHAT_ID', '').strip()
        enabled = getattr(settings, 'EITAAYAR_ENABLED', True)

        self.stdout.write(self.style.NOTICE('=== تست وب‌سرویس ایتایار (Eitaayar) ==='))
        self.stdout.write(f'وضعیت فعال‌بودن (EITAAYAR_ENABLED): {enabled}')
        
        masked_token = f'{token[:6]}...{token[-4:]}' if len(token) > 10 else (token or '(تنظیم نشده)')
        self.stdout.write(f'توکن ایتایار (EITAAYAR_TOKEN): {masked_token}')
        self.stdout.write(f'شناسه گروه/کانال (EITAAYAR_CHAT_ID): {chat_id or "(تنظیم نشده)"}')

        if not token or not chat_id:
            self.stdout.write(
                self.style.ERROR(
                    '\n❌ خطا: مقادیر EITAAYAR_TOKEN یا EITAAYAR_CHAT_ID در فایل .env یا تنظیمات وارد نشده است.\n'
                    'لطفاً ابتدا فایل .env را باز کرده و توکن دریافتی از eitaayar.ir و شناسه گروه خود را تنظیم کنید.'
                )
            )
            return

        now_jalali = format_datetime_jalali(timezone.now())
        custom_text = options.get('text')
        if custom_text:
            text = custom_text
        else:
            text = (
                '🔔 پیام تستی سیستم اطلاع‌رسانی رایحه پرفیوم\n'
                '━━━━━━━━━━━━━━━━━━━━\n'
                '✅ ارتباط با وب‌سرویس ایتایار با موفقیت برقرار است.\n'
                f'📅 تاریخ و ساعت ارسال: {now_jalali}\n'
                'از این پس اعلان‌های مربوط به سفارشات و درخواست‌های مرجوعی در این گروه ارسال خواهند شد.'
            )

        self.stdout.write('\nدر حال ارسال پیام به وب‌سرویس ایتایار...')
        service = EitaayarService(token=token, chat_id=chat_id)
        result = service.send_message(text=text, title='تست اتصال ایتایار')

        if result.get('ok'):
            msg_id = result.get('result', {}).get('message_id')
            self.stdout.write(
                self.style.SUCCESS(
                    f'\n✅ پیام تستی با موفقیت به گروه ارسال شد! (شناسه پیام: {msg_id})'
                )
            )
            self.stdout.write(str(result))
        else:
            self.stdout.write(
                self.style.ERROR(
                    f'\n❌ ارسال پیام با خطا مواجه شد:\n{result}'
                )
            )
