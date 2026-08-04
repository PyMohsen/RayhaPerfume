from urllib.parse import unquote
from django.db.models import Q, Min, Count, Exists, OuterRef
from django.http import JsonResponse
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.views.decorators.http import require_POST

from .models import (
    Perfume, Gender, Season, Nature, Taste,
    ScentFamily, PerfumeVariant, Wishlist,
    Review, ReviewLike,
)
from apps.orders.models import Order, OrderItem


def get_filter_list(request, param_name):
    """استخراج لیست فیلترها از GET (چه به صورت کلیدهای تکراری چه به صورت جدا شده با کاما)"""
    raw_list = request.GET.getlist(param_name)
    result = []
    for item in raw_list:
        if not item:
            continue
        for sub_item in item.split(','):
            val = sub_item.strip()
            if val and val not in result:
                result.append(val)
    return result


def product_list_view(request):
    """لیست محصولات با فیلترهای چندتایی"""
    perfumes = Perfume.objects.filter(is_active=True).select_related(
        'gender', 'nature', 'scent_family'
    ).prefetch_related('variants', 'images', 'seasons', 'tastes')

    # دسته‌بندی‌ها برای سایدبار
    genders = Gender.objects.all()
    natures = Nature.objects.all()
    tastes = Taste.objects.all()
    seasons = Season.objects.all()
    scent_families = ScentFamily.objects.all()

    # فیلترها
    selected_genders = get_filter_list(request, 'gender')
    selected_natures = get_filter_list(request, 'nature')
    selected_tastes = get_filter_list(request, 'taste')
    selected_seasons = get_filter_list(request, 'season')
    selected_scent_families = get_filter_list(request, 'scent_family')
    search_query = request.GET.get('q', '').strip()
    sort = request.GET.get('sort', 'newest')
    only_available = request.GET.get('available') in ['1', 'true', 'on']
    only_discount = request.GET.get('discount') in ['1', 'true', 'on']

    if selected_genders:
        perfumes = perfumes.filter(gender__slug__in=selected_genders)

    if selected_natures:
        perfumes = perfumes.filter(nature__slug__in=selected_natures)

    if selected_tastes:
        perfumes = perfumes.filter(tastes__slug__in=selected_tastes)

    if selected_seasons:
        perfumes = perfumes.filter(seasons__slug__in=selected_seasons)

    if selected_scent_families:
        perfumes = perfumes.filter(scent_family__slug__in=selected_scent_families)

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

    # چیپ‌های فیلترهای فعال برای نمایش به کاربر
    active_chips = []
    for g in genders:
        if g.slug in selected_genders:
            active_chips.append({'type': 'gender', 'value': g.slug, 'label': g.name})
    for n in natures:
        if n.slug in selected_natures:
            active_chips.append({'type': 'nature', 'value': n.slug, 'label': f"طبع {n.name}"})
    for t in tastes:
        if t.slug in selected_tastes:
            active_chips.append({'type': 'taste', 'value': t.slug, 'label': f"طعم {t.name}"})
    for s in seasons:
        if s.slug in selected_seasons:
            active_chips.append({'type': 'season', 'value': s.slug, 'label': f"فصل {s.name}"})
    for sf in scent_families:
        if sf.slug in selected_scent_families:
            active_chips.append({'type': 'scent_family', 'value': sf.slug, 'label': sf.name})
    if only_available:
        active_chips.append({'type': 'available', 'value': '1', 'label': 'فقط کالاهای موجود'})
    if only_discount:
        active_chips.append({'type': 'discount', 'value': '1', 'label': 'فقط کالاهای تخفیف‌دار'})

    has_active_filters = bool(active_chips)

    context = {
        'perfumes': perfumes,
        'genders': genders,
        'natures': natures,
        'tastes': tastes,
        'seasons': seasons,
        'scent_families': scent_families,
        'selected_genders': selected_genders,
        'selected_natures': selected_natures,
        'selected_tastes': selected_tastes,
        'selected_seasons': selected_seasons,
        'selected_scent_families': selected_scent_families,
        'only_available': only_available,
        'only_discount': only_discount,
        'active_chips': active_chips,
        'has_active_filters': has_active_filters,
        'search_query': search_query,
        'current_sort': sort,
    }
    return render(request, 'products/product_list.html', context)


def product_detail_view(request, slug):
    """جزئیات محصول"""
    slug = unquote(slug)
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

    # ---- نظرات ----
    reviews_qs = Review.objects.filter(
        perfume=perfume,
        parent__isnull=True,
        is_approved=True,
    ).select_related('user').prefetch_related(
        'replies__user', 'replies__likes', 'likes',
    ).annotate(
        total_likes=Count('likes'),
    ).order_by('-created_at')

    # بررسی لایک‌های کاربر فعلی و خریدار بودن
    buyer_user_ids = set()
    user_liked_reviews = set()
    if request.user.is_authenticated:
        # لایک‌های کاربر
        user_liked_reviews = set(
            ReviewLike.objects.filter(
                user=request.user,
                review__perfume=perfume,
            ).values_list('review_id', flat=True)
        )

    # شناسایی خریداران این محصول
    paid_statuses = ['paid', 'processing', 'shipped', 'delivered']
    buyer_user_ids = set(
        Order.objects.filter(
            status__in=paid_statuses,
            items__variant__perfume=perfume,
        ).values_list('user_id', flat=True)
    )

    # تعداد کل نظرات تأیید شده
    reviews_count = Review.objects.filter(
        perfume=perfume, is_approved=True,
    ).count()

    context = {
        'perfume': perfume,
        'related_perfumes': related_perfumes,
        'is_wishlisted': is_wishlisted,
        'reviews': reviews_qs,
        'reviews_count': reviews_count,
        'buyer_user_ids': buyer_user_ids,
        'user_liked_reviews': user_liked_reviews,
    }
    return render(request, 'products/product_detail.html', context)


def products_by_gender_view(request, slug):
    """لیست محصولات بر اساس جنسیت"""
    slug = unquote(slug)
    return redirect(f"{reverse('products:list')}?gender={slug}")


def products_by_nature_view(request, slug):
    """لیست محصولات بر اساس طبع"""
    slug = unquote(slug)
    return redirect(f"{reverse('products:list')}?nature={slug}")


def products_by_taste_view(request, slug):
    """لیست محصولات بر اساس طعم"""
    slug = unquote(slug)
    return redirect(f"{reverse('products:list')}?taste={slug}")


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


@login_required
@require_POST
def add_review_view(request, slug):
    """ثبت نظر جدید برای محصول"""
    slug = unquote(slug)
    perfume = get_object_or_404(Perfume, slug=slug, is_active=True)

    body = request.POST.get('body', '').strip()
    parent_id = request.POST.get('parent_id')

    if not body:
        messages.error(request, 'لطفاً متن نظر را وارد کنید.')
        return redirect('products:detail', slug=slug)

    if len(body) > 1000:
        messages.error(request, 'متن نظر نباید بیشتر از ۱۰۰۰ کاراکتر باشد.')
        return redirect('products:detail', slug=slug)

    parent = None
    if parent_id:
        parent = Review.objects.filter(
            pk=parent_id, perfume=perfume, is_approved=True, parent__isnull=True
        ).first()

    Review.objects.create(
        user=request.user,
        perfume=perfume,
        parent=parent,
        body=body,
        is_approved=False,
    )

    messages.success(request, 'نظر شما ثبت شد و پس از تأیید نمایش داده خواهد شد.')
    return redirect('products:detail', slug=slug)


@login_required
@require_POST
def toggle_review_like_view(request, review_id):
    """لایک/آنلایک نظر (AJAX)"""
    try:
        review = Review.objects.get(pk=review_id, is_approved=True)
    except Review.DoesNotExist:
        return JsonResponse({'error': 'نظر یافت نشد'}, status=404)

    like, created = ReviewLike.objects.get_or_create(
        user=request.user, review=review
    )

    if not created:
        like.delete()
        return JsonResponse({
            'status': 'unliked',
            'likes_count': review.likes.count(),
        })

    return JsonResponse({
        'status': 'liked',
        'likes_count': review.likes.count(),
    })
