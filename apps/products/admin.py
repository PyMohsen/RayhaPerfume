from django.contrib import admin

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
    list_display = (
        'name', 'brand', 'gender', 'nature',
        'is_active', 'is_featured', 'views_count', 'created_at'
    )
    list_filter = (
        'is_active', 'is_featured', 'gender', 'nature',
        'scent_family', 'seasons', 'tastes'
    )
    search_fields = ('name', 'name_en', 'brand', 'description')
    prepopulated_fields = {'slug': ('name_en',)}
    filter_horizontal = ('seasons', 'tastes', 'scents')
    readonly_fields = ('views_count', 'created_at', 'updated_at')

    inlines = [PerfumeVariantInline, PerfumeImageInline, PerfumeNoteInline]

    fieldsets = (
        ('اطلاعات اصلی', {
            'fields': ('name', 'name_en', 'slug', 'brand', 'short_description', 'description')
        }),
        ('دسته‌بندی‌ها', {
            'fields': ('gender', 'seasons', 'scent_family', 'nature', 'tastes', 'scents')
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

