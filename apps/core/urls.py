"""
URLs do app Core
"""
from django.urls import path
from . import views
from . import views_custom

app_name = 'core'

urlpatterns = [
    path('', views.landing_page, name='landing'),
    path('dashboard/', views.home, name='home'),
    path('sair/', views_custom.custom_logout, name='custom_logout'),
]
