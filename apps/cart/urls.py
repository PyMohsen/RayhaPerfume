from django.urls import path
from . import views

app_name = 'cart'

urlpatterns = [
    path('', views.cart_detail_view, name='detail'),
    path('add/', views.cart_add_view, name='add'),
    path('remove/', views.cart_remove_view, name='remove'),
    path('update/', views.cart_update_view, name='update'),
    path('clear/', views.cart_clear_view, name='clear'),
]
