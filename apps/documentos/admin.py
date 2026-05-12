from django.contrib import admin
from django import forms
from .models import Documento, TipoDocumento
from .widgets_admin import DepartamentoSelectAdmin


@admin.register(TipoDocumento)
class TipoDocumentoAdmin(admin.ModelAdmin):
    """Admin para Tipos de Documento"""

    list_display = ['nome', 'ativo', 'criado_em']
    list_filter = ['ativo', 'criado_em']
    search_fields = ['nome', 'descricao']
    list_editable = ['ativo']
    ordering = ['nome']
    actions = ['download_todos_tipo']

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

    def download_todos_tipo(self, request, queryset):
        """Download de todos os documentos de um tipo selecionado"""
        from django.shortcuts import redirect

        if queryset.count() != 1:
            self.message_user(request, "Selecione apenas um tipo de documento", level='error')
            return None

        tipo = queryset.first()
        return redirect('documentos:download_por_tipo', tipo_id=tipo.id)
    download_todos_tipo.short_description = "Download todos os documentos deste tipo"


@admin.register(Documento)
class DocumentoAdmin(admin.ModelAdmin):
    """Admin para Documentos"""

    list_display = ['nome', 'tipo_documento', 'departamento', 'data_documento', 'data_upload']
    list_filter = ['tipo_documento', 'departamento', 'data_documento', 'data_upload']
    search_fields = ['nome', 'assunto', 'numero_documento']
    ordering = ['-data_upload']
    actions = ['download_lote_selected']

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

    def download_lote_selected(self, request, queryset):
        """Ação de download em lote"""
        from django.shortcuts import redirect

        request.session['download_lote_ids'] = list(queryset.values_list('id', flat=True))
        return redirect('documentos:download_lote')
    download_lote_selected.short_description = "Download em lote dos selecionados"

