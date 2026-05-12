from django.contrib import admin
from .models import Departamento


@admin.register(Departamento)
class DepartamentoAdmin(admin.ModelAdmin):
    """Admin para Departamentos"""

    list_display = ['nome', 'ativo', 'criado_em', 'atualizado_em']
    list_filter = ['ativo', 'criado_em']
    search_fields = ['nome']
    list_editable = ['ativo']
    ordering = ['nome']

    # Configurações para facilitar criação/edição
    save_on_top = True
    list_per_page = 25

    fieldsets = (
        ('Informações Básicas', {
            'fields': ('nome', 'ativo'),
            'description': 'Preencha os dados básicos do departamento'
        }),
        ('Informações de Sistema', {
            'fields': ('criado_em', 'atualizado_em'),
            'classes': ('collapse',),
            'description': 'Datas de criação e última atualização (gerenciadas automaticamente)'
        }),
    )

    readonly_fields = ['criado_em', 'atualizado_em']

    def get_queryset(self, request):
        """Mostrar todos os departamentos, mas destacar os ativos"""
        qs = super().get_queryset(request)
        return qs

    def get_list_display(self, request):
        """Customizar display baseado no usuário"""
        if request.user.is_superuser:
            return ['nome', 'ativo', 'criado_em', 'atualizado_em']
        return ['nome', 'ativo', 'criado_em']

    def get_list_filter(self, request):
        """Filtros baseados no usuário"""
        if request.user.is_superuser:
            return ['ativo', 'criado_em', 'atualizado_em']
        return ['ativo', 'criado_em']

    def save_model(self, request, obj, form, change):
        """Personalizar salvamento"""
        obj.nome = obj.nome.upper().strip()

        super().save_model(request, obj, form, change)
