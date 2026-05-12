"""
Configuração de URLs do Sistema de Arquivo Digital
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.contrib.auth import views as auth_views
from apps.core import views_custom

urlpatterns = [
    # URLs de autenticação
    path('accounts/login/', auth_views.LoginView.as_view(template_name='login.html'), name='login'),
    path('accounts/logout/', views_custom.custom_logout, name='logout'),
    path('sair/', views_custom.custom_logout, name='custom_logout'),

    path('admin/', admin.site.urls),

    # URLs do sistema
    path('', include('apps.core.urls')),
    path('documentos/', include('apps.documentos.urls')),
    path('caixas/', include('apps.caixas.urls')),
    path('departamentos/', include('apps.departamentos.urls')),
]

# URLs de mídia em desenvolvimento
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
