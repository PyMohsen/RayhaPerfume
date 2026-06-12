from django.db.models import Q, Min
from django.http import JsonResponse
from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST

from .models import (
    Perfume, Gender, Season, Nature, Taste,
    ScentFamily, PerfumeVariant, Wishlist,
)


def product_list_view(request):
    """لیست محصولات با فیلتر"""
    perfumes = Perfume.objects.filter(is_active=True).select_related(
        'gender', 'nature', 'scent_family'
    ).prefetch_related('variants', 'images', 'seasons', 'tastes')

    # فیلترها
    gender_slug = request.GET.get('gender')
    nature_slug = request.GET.get('nature')
    taste_slug = request.GET.get('taste')
    season_slug = request.GET.get('season')
    scent_family_slug = request.GET.get('scent_family')
    search_query = request.GET.get('q')
    sort = request.GET.get('sort', 'newest')
    only_available = request.GET.get('available')
    only_discount = request.GET.get('discount')

    # فیلتر عنوان فعال
    active_filter = None

    if gender_slug:
        perfumes = perfumes.filter(gender__slug=gender_slug)
        active_filter = get_object_or_404(Gender, slug=gender_slug)

    if nature_slug:
        perfumes = perfumes.filter(nature__slug=nature_slug)
        active_filter = get_object_or_404(Nature, slug=nature_slug)

    if taste_slug:
        perfumes = perfumes.filter(tastes__slug=taste_slug)
        active_filter = get_object_or_404(Taste, slug=taste_slug)

    if season_slug:
        perfumes = perfumes.filter(seasons__slug=season_slug)

    if scent_family_slug:
        perfumes = perfumes.filter(scent_family__slug=scent_family_slug)

    if search_query:
        perfumes = perfumes.filter(
            Q(name__icontains=search_query) |
            Q(brand__icontains=search_query) |
            Q(description__icontains=search_query)
        )

    if only_available:
        perfumes = perfumes.filter(variants__stock__gt=0)

    if only_discount:
        perfumes = perfumes.filter(variants__discount_percent__gt=0)

    # مرتب‌سازی
    if sort == 'price_low':
        perfumes = perfumes.annotate(
            min_price=Min('variants__price')
        ).order_by('min_price')
    elif sort == 'price_high':
        perfumes = perfumes.annotate(
            min_price=Min('variants__price')
        ).order_by('-min_price')
    elif sort == 'popular':
        perfumes = perfumes.order_by('-views_count')
    elif sort == 'oldest':
        perfumes = perfumes.order_by('created_at')
    else:  # newest
        perfumes = perfumes.order_by('-created_at')

    perfumes = perfumes.distinct()

    # دسته‌بندی‌ها برای سایدبار
    genders = Gender.objects.all()
    natures = Nature.objects.all()
    tastes = Taste.objects.all()
    seasons = Season.objects.all()
    scent_families = ScentFamily.objects.all()

    context = {
        'perfumes': perfumes,
        'genders': genders,
        'natures': natures,
        'tastes': tastes,
        'seasons': seasons,
        'scent_families': scent_families,
        'active_filter': active_filter,
        'search_query': search_query,
        'current_sort': sort,
    }
    return render(request, 'products/product_list.html', context)


def product_detail_view(request, slug):
    """جزئیات محصول"""
    perfume = get_object_or_404(
        Perfume.objects.select_related(
            'gender', 'nature', 'scent_family'
        ).prefetch_related(
            'variants', 'images', 'seasons', 'tastes', 'scents',
            'perfume_notes__note',
        ),
        slug=slug,
        is_active=True,
    )

    # افزایش تعداد بازدید
    perfume.increment_views()

    # محصولات مرتبط
    related_perfumes = Perfume.objects.filter(
        is_active=True,
        gender=perfume.gender
    ).exclude(pk=perfume.pk).prefetch_related('variants', 'images')[:4]

    # بررسی علاقه‌مندی
    is_wishlisted = False
    if request.user.is_authenticated:
        is_wishlisted = Wishlist.objects.filter(
            user=request.user, perfume=perfume
        ).exists()

    context = {
        'perfume': perfume,
        'related_perfumes': related_perfumes,
        'is_wishlisted': is_wishlisted,
    }
    return render(request, 'products/product_detail.html', context)


def products_by_gender_view(request, slug):
    """لیست محصولات بر اساس جنسیت"""
    gender = get_object_or_404(Gender, slug=slug)
    perfumes = Perfume.objects.filter(
        is_active=True, gender=gender
    ).prefetch_related('variants', 'images')

    context = {
        'perfumes': perfumes,
        'active_filter': gender,
        'category_type': 'gender',
        'genders': Gender.objects.all(),
        'natures': Nature.objects.all(),
        'tastes': Taste.objects.all(),
        'current_sort': 'newest',
    }
    return render(request, 'products/product_list.html', context)


def products_by_nature_view(request, slug):
    """لیست محصولات بر اساس طبع"""
    nature = get_object_or_404(Nature, slug=slug)
    perfumes = Perfume.objects.filter(
        is_active=True, nature=nature
    ).prefetch_related('variants', 'images')

    context = {
        'perfumes': perfumes,
        'active_filter': nature,
        'category_type': 'nature',
        'genders': Gender.objects.all(),
        'natures': Nature.objects.all(),
        'tastes': Taste.objects.all(),
        'current_sort': 'newest',
    }
    return render(request, 'products/product_list.html', context)


def products_by_taste_view(request, slug):
    """لیست محصولات بر اساس طعم"""
    taste = get_object_or_404(Taste, slug=slug)
    perfumes = Perfume.objects.filter(
        is_active=True, tastes=taste
    ).prefetch_related('variants', 'images')

    context = {
        'perfumes': perfumes,
        'active_filter': taste,
        'category_type': 'taste',
        'genders': Gender.objects.all(),
        'natures': Nature.objects.all(),
        'tastes': Taste.objects.all(),
        'current_sort': 'newest',
    }
    return render(request, 'products/product_list.html', context)


def search_view(request):
    """جستجوی محصولات"""
    query = request.GET.get('q', '')
    perfumes = Perfume.objects.none()

    if query:
        perfumes = Perfume.objects.filter(
            Q(name__icontains=query) |
            Q(brand__icontains=query) |
            Q(description__icontains=query),
            is_active=True,
        ).prefetch_related('variants', 'images')

    context = {
        'perfumes': perfumes,
        'query': query,
    }
    return render(request, 'products/search_results.html', context)


@login_required
@require_POST
def toggle_wishlist_view(request):
    """اضافه/حذف محصول از علاقه‌مندی‌ها (AJAX)"""
    perfume_id = request.POST.get('perfume_id')
    try:
        perfume = Perfume.objects.get(pk=perfume_id)
    except Perfume.DoesNotExist:
        return JsonResponse({'error': 'محصول یافت نشد'}, status=404)

    wishlist, created = Wishlist.objects.get_or_create(
        user=request.user, perfume=perfume
    )

    if not created:
        wishlist.delete()
        return JsonResponse({'status': 'removed', 'message': 'از علاقه‌مندی‌ها حذف شد'})

    return JsonResponse({'status': 'added', 'message': 'به علاقه‌مندی‌ها اضافه شد'})


@login_required
def wishlist_view(request):
    """لیست علاقه‌مندی‌ها"""
    wishlists = Wishlist.objects.filter(
        user=request.user
    ).select_related('perfume').prefetch_related(
        'perfume__variants', 'perfume__images'
    )

    context = {
        'wishlists': wishlists,
    }
    return render(request, 'products/wishlist.html', context)
