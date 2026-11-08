from django.test import TestCase, Client
from django.urls import reverse, resolve
from apps.core.models import SiteSettings
from apps.core.views import return_policy_view
from apps.products.models import Perfume, Gender, PerfumeVariant


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


class HomePageStockFilteringTests(TestCase):
    """تست‌های عدم نمایش محصولات ناموجود در صفحه اصلی"""

    def setUp(self):
        self.client = Client()
        self.gender_male = Gender.objects.create(name='مردانه', slug='مردانه')
        self.gender_female = Gender.objects.create(name='زنانه', slug='زنانه')

        # عطر موجود مردانه (ویژه و محبوب)
        self.perfume_in_stock_men = Perfume.objects.create(
            name='عطر موجود مردانه',
            name_en='In Stock Men Perfume',
            slug='in-stock-men-perfume',
            brand='برند تست ۱',
            gender=self.gender_male,
            is_active=True,
            is_featured=True,
            views_count=100,
        )
        PerfumeVariant.objects.create(
            perfume=self.perfume_in_stock_men,
            size=50,
            price=2000000,
            stock=5,
            sku='SKU-MEN-IN-STOCK',
        )

        # عطر موجود زنانه (تخفیف‌دار)
        self.perfume_in_stock_women = Perfume.objects.create(
            name='عطر موجود زنانه',
            name_en='In Stock Women Perfume',
            slug='in-stock-women-perfume',
            brand='برند تست ۲',
            gender=self.gender_female,
            is_active=True,
            is_featured=True,
            views_count=80,
        )
        PerfumeVariant.objects.create(
            perfume=self.perfume_in_stock_women,
            size=100,
            price=3000000,
            discount_percent=15,
            stock=3,
            sku='SKU-WOMEN-IN-STOCK',
        )

        # عطر ناموجود (موجودی صفر)
        self.perfume_out_of_stock = Perfume.objects.create(
            name='عطر ناموجود تستی',
            name_en='Out Of Stock Perfume',
            slug='out-of-stock-perfume',
            brand='برند تست ۳',
            gender=self.gender_male,
            is_active=True,
            is_featured=True,
            views_count=200,
        )
        PerfumeVariant.objects.create(
            perfume=self.perfume_out_of_stock,
            size=50,
            price=1500000,
            stock=0,
            sku='SKU-OUT-OF-STOCK',
        )

        # عطر تخفیف‌دار ولی ناموجود
        self.perfume_discounted_out_of_stock = Perfume.objects.create(
            name='عطر تخفیف‌دار ناموجود',
            name_en='Discounted Out Of Stock Perfume',
            slug='discounted-out-of-stock-perfume',
            brand='برند تست ۴',
            gender=self.gender_female,
            is_active=True,
            is_featured=True,
        )
        PerfumeVariant.objects.create(
            perfume=self.perfume_discounted_out_of_stock,
            size=50,
            price=2500000,
            discount_percent=20,
            stock=0,
            sku='SKU-DISCOUNTED-OUT-OF-STOCK',
        )

        # عطر بدون هیچ واریانتی
        self.perfume_no_variants = Perfume.objects.create(
            name='عطر بدون واریانت',
            name_en='No Variants Perfume',
            slug='no-variants-perfume',
            brand='برند تست ۵',
            gender=self.gender_male,
            is_active=True,
            is_featured=True,
        )

    def test_out_of_stock_perfumes_excluded_from_homepage_context(self):
        """مطمئن شویم محصولات ناموجود در هیچ‌کدام از بخش‌های صفحه اصلی قرار ندارند"""
        response = self.client.get(reverse('core:home'))
        self.assertEqual(response.status_code, 200)

        context_keys = [
            'featured_perfumes',
            'latest_perfumes',
            'popular_perfumes',
            'discounted_perfumes',
            'men_perfumes',
            'women_perfumes',
        ]

        for key in context_keys:
            perfumes_in_section = list(response.context[key])
            self.assertNotIn(
                self.perfume_out_of_stock,
                perfumes_in_section,
                f"{self.perfume_out_of_stock.name} نباید در {key} باشد."
            )
            self.assertNotIn(
                self.perfume_discounted_out_of_stock,
                perfumes_in_section,
                f"{self.perfume_discounted_out_of_stock.name} نباید در {key} باشد."
            )
            self.assertNotIn(
                self.perfume_no_variants,
                perfumes_in_section,
                f"{self.perfume_no_variants.name} نباید در {key} باشد."
            )

    def test_in_stock_perfumes_included_in_homepage(self):
        """محصولات موجود در صفحه اصلی نمایش داده می‌شوند"""
        response = self.client.get(reverse('core:home'))
        self.assertEqual(response.status_code, 200)

        # مردانه موجود
        self.assertIn(self.perfume_in_stock_men, list(response.context['men_perfumes']))
        # زنانه موجود
        self.assertIn(self.perfume_in_stock_women, list(response.context['women_perfumes']))
        # تخفیف‌دار موجود
        self.assertIn(self.perfume_in_stock_women, list(response.context['discounted_perfumes']))

    def test_out_of_stock_perfumes_not_rendered_in_html(self):
        """مطمئن شویم نام عطرهای ناموجود در محتوای HTML صفحه اصلی رندر نمی‌شود"""
        response = self.client.get(reverse('core:home'))
        self.assertEqual(response.status_code, 200)

        content = response.content.decode('utf-8')
        self.assertNotIn('عطر ناموجود تستی', content)
        self.assertNotIn('عطر تخفیف‌دار ناموجود', content)
        self.assertNotIn('عطر بدون واریانت', content)

        self.assertIn('عطر موجود مردانه', content)
        self.assertIn('عطر موجود زنانه', content)


