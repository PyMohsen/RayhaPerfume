from django.urls import path
from . import views

app_name = 'ai_assistant'

urlpatterns = [
    path('init/', views.init_advisor_view, name='init'),
    path('chat/', views.chat_api_view, name='chat'),
    path('reset/', views.reset_chat_view, name='reset'),
]
