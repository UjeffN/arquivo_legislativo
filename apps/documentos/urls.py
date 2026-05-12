"""
URLs do app Documentos
"""
from django.urls import path
from . import views
from . import views_download
from . import views_categoria
from . import views_pasta as pasta_views

app_name = 'documentos'

urlpatterns = [
    path('', views.listar_documentos, name='listar'),
    path('categorias/', views_categoria.listar_categorias_documentos, name='categorias_listar'),
    path('categorias/nova/', views_categoria.criar_categoria_documento, name='categorias_criar'),
    path('categorias/<int:categoria_id>/editar/', views_categoria.editar_categoria_documento, name='categorias_editar'),
    path('categorias/<int:categoria_id>/excluir/', views_categoria.excluir_categoria_documento, name='categorias_excluir'),
    path('upload/', views.upload_documento, name='upload'),
    path('upload/confirmar/', views.confirmar_upload, name='confirmar_upload'),
    path('upload/preview-pdf/', views.preview_upload_pdf, name='preview_upload_pdf'),
    path('upload/selecionar-pasta/', pasta_views.selecionar_pasta, name='selecionar_pasta'),
    path('upload/salvar-com-caixa/', views.salvar_com_caixa, name='salvar_com_caixa'),
    path('upload/salvar-final/', pasta_views.salvar_final, name='salvar_final'),
    path('pesquisar/', views.pesquisar_documentos, name='pesquisar'),
    path('<int:documento_id>/', views.detalhe_documento, name='detalhe'),
    path('<int:documento_id>/editar/', views.editar_documento, name='editar'),
    path('<int:documento_id>/download/', views.download_documento, name='download'),
    path('download-lote/', views.download_lote_documentos, name='download_lote'),
    path('download-lote/preview/', views.preview_download_lote, name='preview_download_lote'),
    path('download-lote-avancado/', views_download.download_lote_avancado, name='download_lote_avancado'),
    path('download-progress/<str:cache_key>/', views_download.download_progress, name='download_progress'),
    path('download-arquivo/<str:token>/', views_download.download_arquivo_zip, name='download_arquivo_zip'),
    path('download-preview-avancado/', views_download.preview_download_lote_avancado, name='preview_download_lote_avancado'),
    path('download/tipo/<int:tipo_id>/', views.download_por_tipo, name='download_por_tipo'),
    path('download/departamento/<int:depto_id>/', views.download_por_departamento, name='download_por_departamento'),
    path('autocomplete/departamentos/', views.departamento_autocomplete, name='departamento_autocomplete'),
]
