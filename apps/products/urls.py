from django.urls import path
from . import views

app_name = 'products'

urlpatterns = [
    path('', views.product_list_view, name='list'),
    path('search/', views.search_view, name='search'),
    path('wishlist/', views.wishlist_view, name='wishlist'),
    path('wishlist/toggle/', views.toggle_wishlist_view, name='toggle_wishlist'),

    # فیلتر بر اساس دسته‌بندی (str برای پشتیبانی از اسلاگ فارسی)
    path('gender/<str:slug>/', views.products_by_gender_view, name='by_gender'),
    path('nature/<str:slug>/', views.products_by_nature_view, name='by_nature'),
    path('taste/<str:slug>/', views.products_by_taste_view, name='by_taste'),

    # جزئیات محصول (باید آخرین URL باشد)
    path('<str:slug>/', views.product_detail_view, name='detail'),
]
