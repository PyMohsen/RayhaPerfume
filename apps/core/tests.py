from django.test import TestCase, Client
from django.urls import reverse, resolve
from apps.core.models import SiteSettings
from apps.core.views import return_policy_view


class ReturnPolicyViewTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.settings = SiteSettings.get_settings()

    def test_terms_url_does_not_exist(self):
        """مطمئن شویم که آدرس قوانین و مقررات دیگر وجود ندارد"""
        response = self.client.get('/terms/')
        self.assertEqual(response.status_code, 404)

    def test_return_policy_url_resolves(self):
        """مطمئن شویم که URL شرایط مرجوعی کالا به درستی resolve می‌شود"""
        url = reverse('core:return_policy')
        self.assertEqual(url, '/return-policy/')
        resolved = resolve(url)
        self.assertEqual(resolved.func, return_policy_view)

    def test_return_policy_page_default_content(self):
        """مطمئن شویم صفحه شرایط مرجوعی با محتوای پیش‌فرض لود می‌شود"""
        self.settings.return_policy = ''
        self.settings.save()

        response = self.client.get(reverse('core:return_policy'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'core/return_policy.html')
        self.assertContains(response, 'شرایط مرجوعی کالا')

    def test_return_policy_page_custom_content(self):
        """مطمئن شویم متن تنظیم‌شده در SiteSettings در صفحه نمایش داده می‌شود"""
        self.settings.return_policy = '<p>قوانین اختصاصی مرجوعی <strong>تست رایحا</strong></p>'
        self.settings.save()

        response = self.client.get(reverse('core:return_policy'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '<p>قوانین اختصاصی مرجوعی <strong>تست رایحا</strong></p>', html=False)

    def test_footer_contains_return_policy_link(self):
        """مطمئن شویم لینک فوتر به شرایط مرجوعی تغییر یافته و لینک قوانین حذف شده است"""
        response = self.client.get(reverse('core:home'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, reverse('core:return_policy'))
        self.assertContains(response, 'شرایط مرجوعی کالا')
        self.assertNotContains(response, '/terms/')

    def test_sitemap_contains_return_policy(self):
        """مطمئن شویم در sitemap آدرس return-policy قرار دارد و terms نیست"""
        from apps.core.sitemaps import StaticViewSitemap
        sitemap = StaticViewSitemap()
        self.assertIn('core:return_policy', sitemap.items())
        self.assertNotIn('core:terms', sitemap.items())

