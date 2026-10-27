from django.contrib import admin, messages
from django.db import transaction
from django.utils.html import format_html
from uuid import uuid4

from .models import (
    Gender, Season, ScentFamily, Nature, Taste, Scent,
    Note, Perfume, PerfumeNote, PerfumeVariant, PerfumeImage,
    Wishlist, Review, ReviewLike,
)


@admin.register(Gender)
class GenderAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug', 'order')
    prepopulated_fields = {'slug': ('name',)}
    ordering = ['order']


@admin.register(Season)
class SeasonAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug', 'order')
    prepopulated_fields = {'slug': ('name',)}
    ordering = ['order']


@admin.register(ScentFamily)
class ScentFamilyAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug', 'color')
    prepopulated_fields = {'slug': ('name',)}


@admin.register(Nature)
class NatureAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug', 'order')
    prepopulated_fields = {'slug': ('name',)}
    ordering = ['order']


@admin.register(Taste)
class TasteAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug', 'order')
    prepopulated_fields = {'slug': ('name',)}
    ordering = ['order']


@admin.register(Scent)
class ScentAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug', 'color', 'order')
    prepopulated_fields = {'slug': ('name',)}
    ordering = ['order']


@admin.register(Note)
class NoteAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug')
    prepopulated_fields = {'slug': ('name',)}
    search_fields = ('name',)


class PerfumeNoteInline(admin.TabularInline):
    model = PerfumeNote
    extra = 1
    autocomplete_fields = ['note']


class PerfumeVariantInline(admin.TabularInline):
    model = PerfumeVariant
    extra = 1
    min_num = 1


class PerfumeImageInline(admin.TabularInline):
    model = PerfumeImage
    extra = 1


@admin.register(Perfume)
class PerfumeAdmin(admin.ModelAdmin):
    change_list_template = 'admin/products/perfume/change_list.html'
    list_display = (
        'name', # 'brand', 'gender', 
        'variant_50_price_input', 'variant_50_stock_input',
        'variant_100_price_input', 'variant_100_stock_input',
        # 'is_active', 'is_featured', 'views_count', 'created_at'
        'updated_at',
    )
    list_filter = (
        'is_active', 'is_featured', 'gender', 'nature',
        'scent_families', 'seasons', 'tastes'
    )
    search_fields = ('name', 'name_en', 'brand', 'description')
    prepopulated_fields = {'slug': ('name_en',)}
    filter_horizontal = ('seasons', 'tastes', 'scents', 'scent_families')
    readonly_fields = ('views_count', 'created_at', 'updated_at')

    inlines = [PerfumeVariantInline, PerfumeImageInline, PerfumeNoteInline]

    def get_queryset(self, request):
        return super().get_queryset(request).prefetch_related('variants')

    def _variant_input(self, perfume, size, field, label):
        variant = next((item for item in perfume.variants.all() if item.size == size), None)
        return format_html(
            '<input type="number" min="0" step="1" name="variant_{}_{}_{}" '
            'value="{}" aria-label="{} {}" style="width: 7.5em">',
            size, field, perfume.pk, getattr(variant, field, ''), label, perfume.name,
        )

    @admin.display(description='قیمت ۵۰ میل')
    def variant_50_price_input(self, obj):
        return self._variant_input(obj, 50, 'price', 'قیمت ۵۰ میل')

    @admin.display(description='موجودی ۵۰ میل')
    def variant_50_stock_input(self, obj):
        return self._variant_input(obj, 50, 'stock', 'موجودی ۵۰ میل')

    @admin.display(description='قیمت ۱۰۰ میل')
    def variant_100_price_input(self, obj):
        return self._variant_input(obj, 100, 'price', 'قیمت ۱۰۰ میل')

    @admin.display(description='موجودی ۱۰۰ میل')
    def variant_100_stock_input(self, obj):
        return self._variant_input(obj, 100, 'stock', 'موجودی ۱۰۰ میل')

    def changelist_view(self, request, extra_context=None):
        if request.method == 'POST' and '_save_variant_values' in request.POST:
            self._save_variant_values(request)
            from django.http import HttpResponseRedirect
            from django.utils.http import urlencode

            query = urlencode(request.GET, doseq=True)
            return HttpResponseRedirect(f'{request.path}?{query}' if query else request.path)
        return super().changelist_view(request, extra_context=extra_context)

    def _save_variant_values(self, request):
        values_by_variant = {}
        fields = {'price': 'قیمت', 'stock': 'موجودی'}
        for key, raw_value in request.POST.items():
            if not key.startswith('variant_'):
                continue
            try:
                _, size, field, perfume_id = key.split('_')
                size, perfume_id = int(size), int(perfume_id)
                if size not in (50, 100) or field not in fields:
                    continue
                values_by_variant.setdefault((perfume_id, size), {})[field] = raw_value.strip()
            except (ValueError, TypeError):
                continue

        invalid = any(
            value and not value.isdigit()
            for values in values_by_variant.values()
            for value in values.values()
        )
        if invalid:
            self.message_user(
                request,
                'مقدار قیمت و موجودی باید عدد صحیحِ صفر یا بیشتر باشد؛ هیچ تغییری ذخیره نشد.',
                level=messages.ERROR,
            )
            return

        created_count = updated_count = deleted_count = 0
        with transaction.atomic():
            for (perfume_id, size), values in values_by_variant.items():
                price = values.get('price', '')
                stock = values.get('stock', '')
                variant = PerfumeVariant.objects.filter(perfume_id=perfume_id, size=size).first()

                if variant and (not price or not stock):
                    variant.delete()
                    deleted_count += 1
                elif price and stock:
                    if variant:
                        variant.price = int(price)
                        variant.stock = int(stock)
                        variant.save(update_fields=['price', 'stock'])
                        updated_count += 1
                    else:
                        PerfumeVariant.objects.create(
                            perfume_id=perfume_id,
                            size=size,
                            price=int(price),
                            stock=int(stock),
                            sku=f'P{perfume_id}-{size}-{uuid4().hex[:12]}',
                        )
                        created_count += 1

        self.message_user(
            request,
            f'{created_count} واریانت ساخته شد، {updated_count} واریانت ویرایش شد و '
            f'{deleted_count} واریانت حذف شد.',
            level=messages.SUCCESS,
        )

    fieldsets = (
        ('اطلاعات اصلی', {
            'fields': ('name', 'name_en', 'slug', 'brand', 'short_description', 'description')
        }),
        ('دسته‌بندی‌ها', {
            'fields': ('gender', 'seasons', 'scent_families', 'nature', 'tastes', 'scents')
        }),
        ('مشخصات فنی', {
            'fields': ('longevity', 'sillage', 'gender_male_percent', 'gender_female_percent')
        }),
        ('وضعیت', {
            'fields': ('is_active', 'is_featured', 'views_count', 'created_at', 'updated_at')
        }),
    )


@admin.register(Wishlist)
class WishlistAdmin(admin.ModelAdmin):
    list_display = ('user', 'perfume', 'created_at')
    raw_id_fields = ('user', 'perfume')


class ReviewLikeInline(admin.TabularInline):
    model = ReviewLike
    extra = 0
    readonly_fields = ('user', 'created_at')


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ('user', 'perfume', 'short_body', 'is_approved', 'parent', 'likes_count', 'created_at')
    list_filter = ('is_approved', 'created_at')
    search_fields = ('body', 'user__full_name', 'user__phone_number', 'perfume__name')
    raw_id_fields = ('user', 'perfume', 'parent')
    list_editable = ('is_approved',)
    readonly_fields = ('created_at', 'updated_at')
    actions = ['approve_reviews', 'reject_reviews']
    inlines = [ReviewLikeInline]

    def short_body(self, obj):
        return obj.body[:50] + '...' if len(obj.body) > 50 else obj.body
    short_body.short_description = 'متن نظر'

    def likes_count(self, obj):
        return obj.likes.count()
    likes_count.short_description = 'تعداد لایک'

    @admin.action(description='تأیید نظرات انتخاب شده')
    def approve_reviews(self, request, queryset):
        updated = queryset.update(is_approved=True)
        self.message_user(request, f'{updated} نظر تأیید شد.')

    @admin.action(description='رد نظرات انتخاب شده')
    def reject_reviews(self, request, queryset):
        updated = queryset.update(is_approved=False)
        self.message_user(request, f'{updated} نظر رد شد.')

