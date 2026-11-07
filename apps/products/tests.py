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
