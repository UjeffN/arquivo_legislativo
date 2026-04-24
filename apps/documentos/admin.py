from django.contrib import admin
from django import forms
from .models import Documento, TipoDocumento
from .widgets_admin import DepartamentoSelectAdmin

print("DEBUG: admin.py sendo importado...")


@admin.register(TipoDocumento)
class TipoDocumentoAdmin(admin.ModelAdmin):
    """Admin para Tipos de Documento"""
    
    list_display = ['nome', 'ativo', 'criado_em']
    list_filter = ['ativo', 'criado_em']
    search_fields = ['nome', 'descricao']
    list_editable = ['ativo']
    ordering = ['nome']
    
    fieldsets = (
        ('Informações Básicas', {
            'fields': ('nome', 'descricao', 'ativo')
        }),
        ('Informações de Sistema', {
            'fields': ('criado_em',),
            'classes': ('collapse',)
        }),
    )
    
    readonly_fields = ['criado_em']
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related()


@admin.register(Documento)
class DocumentoAdmin(admin.ModelAdmin):
    """Admin para Documentos"""
    
    list_display = ['nome', 'tipo_documento', 'departamento', 'data_documento', 'data_upload']
    list_filter = ['tipo_documento', 'departamento', 'data_documento', 'data_upload']
    search_fields = ['nome', 'assunto', 'numero_documento']
    ordering = ['-data_upload']
    
    fieldsets = (
        ('Informações do Documento', {
            'fields': ('nome', 'assunto', 'numero_documento', 'data_documento')
        }),
        ('Classificação', {
            'fields': ('tipo_documento', 'departamento', 'caixa')
        }),
        ('Conteúdo', {
            'fields': ('arquivo_pdf', 'palavra_chave', 'observacao', 'texto_extraido')
        }),
        ('Informações de Sistema', {
            'fields': ('data_upload', 'atualizado_em'),
            'classes': ('collapse',)
        }),
    )
    
    readonly_fields = ['data_upload', 'atualizado_em', 'texto_extraido']
    
    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        """Usar widget customizado para campo departamento"""
        if db_field.name == 'departamento':
            kwargs['widget'] = DepartamentoSelectAdmin()
            
        return super().formfield_for_foreignkey(db_field, request, **kwargs)
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'tipo_documento', 'departamento', 'caixa'
        )
    
