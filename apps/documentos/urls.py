"""
URLs do app Documentos
"""
from django.urls import path
from . import views
from . import views_pasta as pasta_views

app_name = 'documentos'

urlpatterns = [
    path('', views.listar_documentos, name='listar'),
    path('upload/', views.upload_documento, name='upload'),
    path('upload/confirmar/', views.confirmar_upload, name='confirmar_upload'),
    path('upload/selecionar-pasta/', pasta_views.selecionar_pasta, name='selecionar_pasta'),
    path('upload/salvar-com-caixa/', views.salvar_com_caixa, name='salvar_com_caixa'),
    path('upload/salvar-final/', pasta_views.salvar_final, name='salvar_final'),
    path('pesquisar/', views.pesquisar_documentos, name='pesquisar'),
    path('<int:documento_id>/', views.detalhe_documento, name='detalhe'),
    path('<int:documento_id>/editar/', views.editar_documento, name='editar'),
    path('<int:documento_id>/download/', views.download_documento, name='download'),
    path('autocomplete/departamentos/', views.departamento_autocomplete, name='departamento_autocomplete'),
]
