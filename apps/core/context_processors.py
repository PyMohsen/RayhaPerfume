from django.conf import settings

from .models import SiteSettings


def site_settings_context(request):
    """تنظیمات سایت برای دسترسی در تمام قالب‌ها"""
    return {
        'site_settings': SiteSettings.get_settings(),
        'site_domain': settings.SITE_DOMAIN,
    }
