"""
URLs do app Departamentos
"""
from django.urls import path
from . import views

app_name = 'departamentos'

urlpatterns = [
    path('', views.listar_departamentos, name='listar'),
    path('novo/', views.criar_departamento, name='criar'),
    path('<int:departamento_id>/editar/', views.editar_departamento, name='editar'),
    path('<int:departamento_id>/excluir/', views.excluir_departamento, name='excluir'),
]
