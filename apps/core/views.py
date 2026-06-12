from django.contrib import messages
from django.shortcuts import render, redirect

from apps.products.models import Perfume, Gender, Nature, Taste, Season
from .forms import ContactForm
from .models import SiteSettings, Slider, FAQ


def home_view(request):
    """صفحه اصلی"""
    sliders = Slider.objects.filter(is_active=True)
    featured_perfumes = Perfume.objects.filter(
        is_active=True, is_featured=True
    ).prefetch_related('variants', 'images')[:8]

    latest_perfumes = Perfume.objects.filter(
        is_active=True
    ).prefetch_related('variants', 'images').order_by('-created_at')[:8]

    popular_perfumes = Perfume.objects.filter(
        is_active=True
    ).prefetch_related('variants', 'images').order_by('-views_count')[:8]

    # دسته‌بندی‌ها
    genders = Gender.objects.all()
    natures = Nature.objects.all()
    tastes = Taste.objects.all()
    seasons = Season.objects.all()

    # عطرهای تخفیف‌دار
    discounted_perfumes = Perfume.objects.filter(
        is_active=True,
        variants__discount_percent__gt=0,
    ).prefetch_related('variants', 'images').distinct()[:8]

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
            form.save()
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


def terms_view(request):
    """قوانین و مقررات"""
    settings_obj = SiteSettings.get_settings()
    return render(request, 'core/terms.html', {'site_settings': settings_obj})
