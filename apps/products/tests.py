from django.test import TestCase, Client
from django.urls import reverse
from apps.products.models import Perfume, Gender, PerfumeVariant


class PerfumeSeoTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.gender = Gender.objects.create(name='مردانه', slug='مردانه')

    def test_seo_description_with_short_description(self):
        perfume = Perfume.objects.create(
            name='اونتوس',
            name_en='Aventus',
            slug='aventus',
            brand='کرید',
            gender=self.gender,
            short_description='عطر مردانه بسیار جذاب و پرطرفدار با ماندگاری بالا.',
        )
        self.assertEqual(perfume.seo_description, 'عطر مردانه بسیار جذاب و پرطرفدار با ماندگاری بالا.')

    def test_seo_description_with_html_description(self):
        perfume = Perfume.objects.create(
            name='ساواج',
            name_en='Sauvage',
            slug='sauvage',
            brand='دیور',
            gender=self.gender,
            description='<p>عطر دیور ساواج با رایحه <strong>خنک و تند</strong> مناسب فصول گرم سال است.</p>',
        )
        self.assertEqual(
            perfume.seo_description,
            'عطر دیور ساواج با رایحه خنک و تند مناسب فصول گرم سال است.'
        )

    def test_seo_description_fallback_when_empty(self):
        perfume = Perfume.objects.create(
            name='بلو شنل',
            name_en='Bleu de Chanel',
            slug='bleu-de-chanel',
            brand='شنل',
            gender=self.gender,
        )
        self.assertIn('خرید آنلاین عطر مردانه بلو شنل از برند شنل', perfume.seo_description)
        self.assertIn('ضمانت ۱۰۰٪ اصالت کالا', perfume.seo_description)

    def test_product_detail_page_meta_description_rendered(self):
        perfume = Perfume.objects.create(
            name='تست عطر',
            name_en='Test Perfume',
            slug='test-perfume',
            brand='برند تست',
            gender=self.gender,
            short_description='توضیحات کوتاه برای تست سئو و اسنیپت گوگل.',
            is_active=True,
        )
        PerfumeVariant.objects.create(perfume=perfume, size=100, price=5000000, stock=10)

        response = self.client.get(reverse('products:detail', kwargs={'slug': perfume.slug}))
        self.assertEqual(response.status_code, 200)
        content = response.content.decode('utf-8')
        self.assertIn('<meta name="description" content="توضیحات کوتاه برای تست سئو و اسنیپت گوگل.">', content)
        self.assertIn('<meta property="og:title"', content)
        self.assertIn('<meta property="og:description"', content)


class ProductListStockOrderingTests(TestCase):
    """تست‌های نمایش محصولات ناموجود در انتهای لیست در صفحه محصولات"""

    def setUp(self):
        self.client = Client()
        self.gender = Gender.objects.create(name='مردانه', slug='مردانه')

        # محصول ۱: موجود، قیمت گران، بازدید کم
        self.p_in_stock_expensive = Perfume.objects.create(
            name='عطر موجود گران',
            name_en='In Stock Expensive',
            slug='in-stock-expensive',
            brand='برند A',
            gender=self.gender,
            is_active=True,
            views_count=10,
        )
        PerfumeVariant.objects.create(
            perfume=self.p_in_stock_expensive,
            size=50,
            price=10000000,
            stock=5,
            sku='SKU-EXP-50',
        )

        # محصول ۲: موجود، قیمت متوسط، بازدید زیاد
        self.p_in_stock_cheap = Perfume.objects.create(
            name='عطر موجود ارزان',
            name_en='In Stock Cheap',
            slug='in-stock-cheap',
            brand='برند B',
            gender=self.gender,
            is_active=True,
            views_count=100,
        )
        PerfumeVariant.objects.create(
            perfume=self.p_in_stock_cheap,
            size=50,
            price=2000000,
            stock=10,
            sku='SKU-CHP-50',
        )

        # محصول ۳: ناموجود، قیمت بسیار ارزان، بازدید بسیار زیاد
        self.p_out_of_stock = Perfume.objects.create(
            name='عطر ناموجود خیلی ارزان',
            name_en='Out Of Stock Super Cheap',
            slug='out-of-stock-super-cheap',
            brand='برند C',
            gender=self.gender,
            is_active=True,
            views_count=999,
        )
        PerfumeVariant.objects.create(
            perfume=self.p_out_of_stock,
            size=50,
            price=500000,  # ارزان‌ترین قیمت کل محصولات
            stock=0,       # ناموجود
            sku='SKU-OOS-50',
        )

    def test_out_of_stock_is_last_in_default_sort(self):
        """در مرتب‌سازی پیش‌فرض (جدیدترین)، محصول ناموجود باید در انتهای لیست باشد"""
        response = self.client.get(reverse('products:list'))
        self.assertEqual(response.status_code, 200)

        perfumes = list(response.context['perfumes'])
        self.assertEqual(perfumes[-1], self.p_out_of_stock)
        self.assertIn(self.p_in_stock_expensive, perfumes[:-1])
        self.assertIn(self.p_in_stock_cheap, perfumes[:-1])

    def test_out_of_stock_is_last_in_price_low_sort(self):
        """حتی با مرتب‌سازی ارزان‌ترین، محصول ناموجود ارزان‌قیمت باید در انتهای لیست باشد"""
        response = self.client.get(reverse('products:list') + '?sort=price_low')
        self.assertEqual(response.status_code, 200)

        perfumes = list(response.context['perfumes'])
        self.assertEqual(perfumes[-1], self.p_out_of_stock)
        self.assertEqual(perfumes[0], self.p_in_stock_cheap)
        self.assertEqual(perfumes[1], self.p_in_stock_expensive)

    def test_out_of_stock_is_last_in_price_high_sort(self):
        """در مرتب‌سازی گران‌ترین، محصول ناموجود در انتهای لیست باشد"""
        response = self.client.get(reverse('products:list') + '?sort=price_high')
        self.assertEqual(response.status_code, 200)

        perfumes = list(response.context['perfumes'])
        self.assertEqual(perfumes[-1], self.p_out_of_stock)
        self.assertEqual(perfumes[0], self.p_in_stock_expensive)
        self.assertEqual(perfumes[1], self.p_in_stock_cheap)

    def test_out_of_stock_is_last_in_popular_sort(self):
        """حتی با بالاترین بازدید، محصول ناموجود باید در انتهای لیست محبوب‌ترین باشد"""
        response = self.client.get(reverse('products:list') + '?sort=popular')
        self.assertEqual(response.status_code, 200)

        perfumes = list(response.context['perfumes'])
        self.assertEqual(perfumes[-1], self.p_out_of_stock)
        self.assertEqual(perfumes[0], self.p_in_stock_cheap)
        self.assertEqual(perfumes[1], self.p_in_stock_expensive)

    def test_filter_only_available_excludes_out_of_stock(self):
        """با فعال‌سازی فیلتر 'فقط کالاهای موجود'، محصول ناموجود به کل حذف می‌شود"""
        response = self.client.get(reverse('products:list') + '?available=1')
        self.assertEqual(response.status_code, 200)

        perfumes = list(response.context['perfumes'])
        self.assertNotIn(self.p_out_of_stock, perfumes)
        self.assertIn(self.p_in_stock_cheap, perfumes)
        self.assertIn(self.p_in_stock_expensive, perfumes)

