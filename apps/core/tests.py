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


class SeoAndSerpLeakTests(TestCase):
    def setUp(self):
        self.client = Client()

    def test_footer_has_data_nosnippet(self):
        """مطمئن شویم فوتر دارای صفت data-nosnippet است تا توسط گوگل در اسنیپت SERP ایندکس نشود"""
        response = self.client.get(reverse('core:home'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '<footer class="footer" data-nosnippet>')

    def test_live_search_raw_text_not_in_dom(self):
        """مطمئن شویم متن‌های استاتیک سرچ زنده در DOM اولیه وجود ندارند"""
        response = self.client.get(reverse('core:home'))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'در حال جستجو...')
        self.assertNotContains(response, 'نتیجه‌ای یافت نشد')
        self.assertNotContains(response, 'مشاهده همه نتایج')

    def test_cart_notification_raw_text_not_in_dom(self):
        """مطمئن شویم متن نوتیفیکیشن سبد خرید در DOM اولیه صفحات وجود ندارد"""
        response = self.client.get(reverse('core:home'))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'کالا اضافه شد!')
        self.assertNotContains(response, 'برو به سبد خرید')

    def test_dedicated_meta_descriptions(self):
        """مطمئن شویم صفحات اصلی دارای تگ meta description اختصاصی هستند"""
        pages = [
            (reverse('core:home'), 'فروشگاه اینترنتی عطر رایحا'),
            (reverse('core:about'), 'آشنایی با فروشگاه اینترنتی عطر رایحا'),
            (reverse('core:contact'), 'اطلاعات تماس با عطر رایحا'),
            (reverse('core:faq'), 'پاسخ به متداول‌ترین سوالات کاربران'),
            (reverse('core:return_policy'), 'قوانین، ضوابط و شرایط بازگشت و مرجوعی کالا'),
            (reverse('products:list'), 'فروشگاه آنلاین عطر رایحا'),
        ]
        for url, expected_phrase in pages:
            with self.subTest(url=url):
                res = self.client.get(url)
                self.assertEqual(res.status_code, 200)
                content = res.content.decode('utf-8')
                self.assertIn('<meta name="description" content="', content)
                self.assertIn(expected_phrase, content)

