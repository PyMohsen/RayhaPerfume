from django.urls import path
from . import views

app_name = 'accounts'

urlpatterns = [
    # ورود و ثبت‌نام
    path('login/', views.login_view, name='login'),
    path('verify-otp/', views.verify_otp_view, name='verify_otp'),
    path('resend-otp/', views.resend_otp_view, name='resend_otp'),
    path('logout/', views.logout_view, name='logout'),

    # پروفایل
    path('profile/', views.profile_view, name='profile'),
    path('profile/update/', views.profile_update_view, name='profile_update'),
    path('profile/complete/', views.complete_profile_view, name='complete_profile'),

    # آدرس‌ها
    path('addresses/', views.address_list_view, name='address_list'),
    path('addresses/add/', views.address_create_view, name='address_create'),
    path('addresses/<int:pk>/edit/', views.address_update_view, name='address_update'),
    path('addresses/<int:pk>/delete/', views.address_delete_view, name='address_delete'),

    # تاریخچه سفارشات
    path('orders/', views.order_history_view, name='order_history'),
]
