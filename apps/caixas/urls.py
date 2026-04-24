"""
URLs do app Caixas
"""
from django.urls import path
from . import views

app_name = 'caixas'

urlpatterns = [
    # Gerenciamento de caixas
    path('', views.listar_caixas, name='listar_caixas'),
    path('criar/', views.criar_caixa, name='criar_caixa'),
    path('<int:pk>/', views.detalhe_caixa, name='detalhe_caixa'),
    path('<int:pk>/editar/', views.editar_caixa, name='editar_caixa'),
    path('<int:pk>/etiqueta/', views.imprimir_etiqueta, name='imprimir_etiqueta'),
]
