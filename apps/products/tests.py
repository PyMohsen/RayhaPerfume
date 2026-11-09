from django.test import TestCase, Client
from django.urls import reverse
from apps.products.models import Perfume, Gender, PerfumeVariant, PerfumeImage


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


class ProductPaginationTests(TestCase):
    """تست‌های کامل سیستم صفحه‌بندی محصولات"""

    def setUp(self):
        self.client = Client()
        self.gender = Gender.objects.create(name='یونیسکس', slug='unisex')
        # ایجاد ۲۸ عطر تستی
        self.perfumes = []
        for i in range(1, 29):
            p = Perfume.objects.create(
                name=f'عطر شماره {i}',
                name_en=f'Perfume {i}',
                slug=f'perfume-{i}',
                brand='رایحا',
                gender=self.gender,
                is_active=True,
            )
            PerfumeVariant.objects.create(
                perfume=p,
                size=50,
                price=1000000 * i,
                stock=5,
                sku=f'SKU-TEST-{i}',
            )
            self.perfumes.append(p)

    def test_pagination_page_1_has_12_items_and_total_count(self):
        """صفحه اول شامل ۱۲ محصول است و total_count کل محصولات را برمی‌گرداند"""
        response = self.client.get(reverse('products:list'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['total_count'], 28)
        self.assertEqual(len(response.context['page_obj']), 12)
        self.assertEqual(response.context['page_obj'].number, 1)
        self.assertEqual(response.context['paginator'].num_pages, 3)

        content = response.content.decode('utf-8')
        # بررسی نمایش کل تعداد در هدر
        self.assertIn('۲۸ عطر یافت شد', content)
        # بررسی وضعیت ناوبری: دکمه قبلی باید غیرفعال باشد
        self.assertIn('pagination-btn-prev is-disabled', content)
        # دکمه بعدی باید فعال باشد
        self.assertIn('pagination-btn-next', content)
        self.assertNotIn('pagination-btn-next is-disabled', content)

    def test_pagination_page_2(self):
        """صفحه دوم شامل ۱۲ محصول بعدی است"""
        response = self.client.get(reverse('products:list') + '?page=2')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['total_count'], 28)
        self.assertEqual(len(response.context['page_obj']), 12)
        self.assertEqual(response.context['page_obj'].number, 2)

        content = response.content.decode('utf-8')
        # هم دکمه قبلی و هم بعدی باید فعال باشند
        self.assertNotIn('pagination-btn-prev is-disabled', content)
        self.assertNotIn('pagination-btn-next is-disabled', content)

    def test_pagination_last_page(self):
        """صفحه آخر شامل محصولات باقیمانده (۴ محصول) است و دکمه بعدی غیرفعال است"""
        response = self.client.get(reverse('products:list') + '?page=3')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context['page_obj']), 4)
        self.assertEqual(response.context['page_obj'].number, 3)

        content = response.content.decode('utf-8')
        # دکمه بعدی باید غیرفعال باشد
        self.assertIn('pagination-btn-next is-disabled', content)
        # دکمه قبلی باید فعال باشد
        self.assertNotIn('pagination-btn-prev is-disabled', content)

    def test_invalid_page_number_falls_back_to_page_1(self):
        """ورود شماره صفحه نامعتبر (رشته یا منفی) بدون خطا صفحه اول را لود می‌کند"""
        response = self.client.get(reverse('products:list') + '?page=invalid')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['page_obj'].number, 1)

    def test_out_of_range_page_number_falls_back_to_last_page(self):
        """ورود شماره صفحه فراتر از محدوده، صفحه آخر را لود می‌کند"""
        response = self.client.get(reverse('products:list') + '?page=9999')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['page_obj'].number, 3)

    def test_url_replace_template_tag_preserves_multiple_filters(self):
        """تگ url_replace تمام پارامترهای GET شامل فیلترهای چند مقداره را حفظ کرده و فقط page را جایگزین می‌کند"""
        from django.test import RequestFactory
        from apps.products.templatetags.product_tags import url_replace
        factory = RequestFactory()
        request = factory.get('/products/?gender=men&gender=women&sort=popular&page=1')
        context = {'request': request}
        new_qs = url_replace(context, page=2)
        self.assertIn('gender=men', new_qs)
        self.assertIn('gender=women', new_qs)
        self.assertIn('sort=popular', new_qs)
        self.assertIn('page=2', new_qs)
        self.assertNotIn('page=1', new_qs)

    def test_single_page_hides_pagination_block(self):
        """اگر تعداد کل محصولات کمتر یا مساوی ۱۲ باشد، کل بلاک صفحه‌بندی مخفی می‌شود"""
        Perfume.objects.filter(id__gt=self.perfumes[4].id).delete()
        self.assertEqual(Perfume.objects.count(), 5)

        response = self.client.get(reverse('products:list'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['paginator'].num_pages, 1)
        content = response.content.decode('utf-8')
        self.assertNotIn('pagination-wrapper', content)
        self.assertNotIn('pagination-nav', content)


class ProductCardSecondaryImageTests(TestCase):
    """تست‌های تصویر دوم عطر و نمایش آن روی کارت محصول"""

    def setUp(self):
        self.client = Client()
        self.gender = Gender.objects.create(name='مردانه', slug='مردانه')
        self.perfume = Perfume.objects.create(
            name='عطر تست دو تصویر',
            name_en='Dual Image Perfume',
            slug='dual-image-perfume',
            brand='رایحا',
            gender=self.gender,
            is_active=True,
        )
        PerfumeVariant.objects.create(
            perfume=self.perfume,
            size=50,
            price=2500000,
            stock=5,
            sku='SKU-DUAL-50',
        )

    def test_secondary_image_none_when_zero_or_one_image(self):
        self.assertIsNone(self.perfume.primary_image)
        self.assertIsNone(self.perfume.secondary_image)

        img1 = PerfumeImage.objects.create(
            perfume=self.perfume,
            image='perfumes/img1.jpg',
            is_primary=True,
            order=0,
        )
        self.assertEqual(self.perfume.primary_image, img1)
        self.assertIsNone(self.perfume.secondary_image)

    def test_secondary_image_picks_second_ordered_image(self):
        img_second = PerfumeImage.objects.create(
            perfume=self.perfume,
            image='perfumes/second.jpg',
            is_primary=False,
            order=1,
        )
        img_third = PerfumeImage.objects.create(
            perfume=self.perfume,
            image='perfumes/third.jpg',
            is_primary=False,
            order=2,
        )
        img_primary = PerfumeImage.objects.create(
            perfume=self.perfume,
            image='perfumes/primary.jpg',
            is_primary=True,
            order=5,
        )

        # بدون prefetch
        self.assertEqual(self.perfume.primary_image, img_primary)
        self.assertEqual(self.perfume.secondary_image, img_second)
        self.assertNotEqual(self.perfume.secondary_image, img_third)

        # با prefetch (بدون کوئری اضافی)
        prefetched = Perfume.objects.prefetch_related('images').get(pk=self.perfume.pk)
        with self.assertNumQueries(0):
            self.assertEqual(prefetched.primary_image, img_primary)
            self.assertEqual(prefetched.secondary_image, img_second)

    def test_secondary_image_without_primary_flag(self):
        img1 = PerfumeImage.objects.create(
            perfume=self.perfume,
            image='perfumes/first_no_flag.jpg',
            is_primary=False,
            order=0,
        )
        img2 = PerfumeImage.objects.create(
            perfume=self.perfume,
            image='perfumes/second_no_flag.jpg',
            is_primary=False,
            order=1,
        )

        prefetched = Perfume.objects.prefetch_related('images').get(pk=self.perfume.pk)
        self.assertEqual(prefetched.primary_image, img1)
        self.assertEqual(prefetched.secondary_image, img2)

    def test_product_card_renders_secondary_image_when_present(self):
        PerfumeImage.objects.create(
            perfume=self.perfume,
            image='perfumes/card_primary.jpg',
            is_primary=True,
            order=0,
        )
        PerfumeImage.objects.create(
            perfume=self.perfume,
            image='perfumes/card_secondary.jpg',
            is_primary=False,
            order=1,
        )

        response = self.client.get(reverse('products:list'))
        self.assertEqual(response.status_code, 200)
        content = response.content.decode('utf-8')
        self.assertIn('has-secondary-image', content)
        self.assertIn('product-card-img-primary', content)
        self.assertIn('product-card-img-secondary', content)
        self.assertIn('card_primary.jpg', content)
        self.assertIn('card_secondary.jpg', content)

    def test_product_card_without_secondary_image_omits_secondary_markup(self):
        PerfumeImage.objects.create(
            perfume=self.perfume,
            image='perfumes/only_primary.jpg',
            is_primary=True,
            order=0,
        )

        response = self.client.get(reverse('products:list'))
        self.assertEqual(response.status_code, 200)
        content = response.content.decode('utf-8')
        self.assertIn('product-card-img-primary', content)
        self.assertIn('only_primary.jpg', content)
        self.assertNotIn('has-secondary-image', content)
        self.assertNotIn('product-card-img-secondary', content)


