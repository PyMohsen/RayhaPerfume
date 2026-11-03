from django.urls import path
from . import views

urlpatterns = [
    path('', views.direct_pay_view, name='pay'),
    path('callback/', views.direct_pay_callback_view, name='pay_callback'),
    path('result/<str:tracking_number>/', views.direct_pay_result_view, name='pay_result'),
    path('retry/<str:tracking_number>/', views.retry_direct_pay_torobpay_view, name='pay_retry_torobpay'),
]

