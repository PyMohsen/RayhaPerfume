from django.contrib import messages
from django.db.models import Q
from django.http import HttpResponse
from django.conf import settings
from django.shortcuts import render, redirect
from django.views.decorators.clickjacking import xframe_options_exempt

from apps.products.models import Perfume, Gender, Nature, Taste, Season
from apps.orders.eitaayar import notify_admin_contact_message
from .forms import ContactForm
from .models import SiteSettings, Slider, FAQ


@xframe_options_exempt
def home_view(request):
    """صفحه اصلی"""
    sliders = Slider.objects.filter(is_active=True)

    # فقط عطرهای فعال با موجودی بیشتر از صفر در صفحه اصلی نمایش داده می‌شوند
    available_perfumes = Perfume.objects.filter(
        is_active=True,
        variants__stock__gt=0,
    )

    featured_perfumes = (
        available_perfumes.filter(is_featured=True)
        .prefetch_related('variants', 'images')
        .distinct()[:8]
    )

    latest_perfumes = (
        available_perfumes
        .prefetch_related('variants', 'images')
        .order_by('-created_at')
        .distinct()[:8]
    )

    popular_perfumes = (
        available_perfumes
        .prefetch_related('variants', 'images')
        .order_by('-views_count')
        .distinct()[:8]
    )

    # دسته‌بندی‌ها
    genders = Gender.objects.all()
    natures = Nature.objects.all()
    tastes = Taste.objects.all()
    seasons = Season.objects.all()

    # عطرهای تخفیف‌دار موجود (تخفیف بیشتر از صفر و موجودی انبار بیشتر از صفر)
    discounted_perfumes = (
        Perfume.objects.filter(
            is_active=True,
            variants__discount_percent__gt=0,
            variants__stock__gt=0,
        )
        .prefetch_related('variants', 'images')
        .distinct()[:8]
    )

    # عطرهای مردانه موجود
    men_perfumes = (
        available_perfumes.filter(
            Q(gender__slug='مردانه')
        )
        .prefetch_related('variants', 'images')
        .order_by('-created_at')
        .distinct()[:8]
    )

    # عطرهای زنانه موجود
    women_perfumes = (
        available_perfumes.filter(
            Q(gender__slug='زنانه')
        )
        .prefetch_related('variants', 'images')
        .order_by('-created_at')
        .distinct()[:8]
    )

    context = {
        'sliders': sliders,
        'featured_perfumes': featured_perfumes,
        'latest_perfumes': latest_perfumes,
        'popular_perfumes': popular_perfumes,
        'discounted_perfumes': discounted_perfumes,
        'genders': genders,
        'natures': natures,
        'tastes': tastes,
        'seasons': seasons,
        'men_perfumes': men_perfumes,
        'women_perfumes': women_perfumes,
    }
    return render(request, 'core/home.html', context)


def about_view(request):
    """درباره ما"""
    settings_obj = SiteSettings.get_settings()
    return render(request, 'core/about.html', {'site_settings': settings_obj})


def contact_view(request):
    """تماس با ما"""
    if request.method == 'POST':
        form = ContactForm(request.POST)
        if form.is_valid():
            contact_msg = form.save()
            notify_admin_contact_message(contact_msg.id)
            messages.success(request, 'پیام شما با موفقیت ارسال شد. با تشکر!')
            return redirect('core:contact')
    else:
        form = ContactForm()

    settings_obj = SiteSettings.get_settings()
    return render(request, 'core/contact.html', {
        'form': form,
        'site_settings': settings_obj,
    })


def faq_view(request):
    """سوالات متداول"""
    faqs = FAQ.objects.filter(is_active=True)
    return render(request, 'core/faq.html', {'faqs': faqs})


def return_policy_view(request):
    """شرایط مرجوعی کالا"""
    settings_obj = SiteSettings.get_settings()
    return render(request, 'core/return_policy.html', {'site_settings': settings_obj})


def robots_txt_view(request):
    """فایل راهنمای موتورهای جستجو (robots.txt)"""
    lines = [
        "User-agent: *",
        "Disallow: /admin/",
        "Disallow: /cart/",
        "Disallow: /orders/",
        "Disallow: /accounts/",
        "Disallow: /products/search/",
        "Disallow: /products/api/",
        "Disallow: /products/wishlist/",
        "Disallow: /*?sort=*",
        "Disallow: /*?*next=*",
        "Allow: /",
        "",
        f"Sitemap: https://{settings.SITE_DOMAIN}/sitemap.xml",
    ]
    return HttpResponse("\n".join(lines), content_type="text/plain; charset=utf-8")
