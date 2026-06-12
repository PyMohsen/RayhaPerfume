from django.urls import path
from . import views

app_name = 'orders'

urlpatterns = [
    path('checkout/', views.checkout_view, name='checkout'),
    path('create/', views.create_order_view, name='create'),
    path('coupon/apply/', views.apply_coupon_view, name='apply_coupon'),
    path('coupon/remove/', views.remove_coupon_view, name='remove_coupon'),
    path('payment/callback/', views.payment_callback_view, name='payment_callback'),
    path('<str:order_number>/', views.order_detail_view, name='detail'),
]
