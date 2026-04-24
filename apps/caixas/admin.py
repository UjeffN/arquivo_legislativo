from django.contrib import admin
from django.utils.html import format_html
from .models import Caixa


@admin.register(Caixa)
class CaixaAdmin(admin.ModelAdmin):
    """Admin para Caixas"""
    
    list_display = ['numero', 'nome', 'quantidade_documentos', 'percentual_ocupacao', 'criado_em']
    search_fields = ['numero', 'nome', 'descricao', 'localizacao_fisica']
    ordering = ['numero']
    
    # Configurações para facilitar criação/edição
    save_on_top = True
    list_per_page = 25
    
    fieldsets = (
        ('Informações da Caixa', {
            'fields': ('numero', 'nome', 'descricao'),
            'description': 'Número gerado automaticamente, nome pode ser personalizado'
        }),
        ('Configurações', {
            'fields': ('localizacao_fisica',),
            'description': 'Configurações da caixa'
        }),
        ('Informações de Sistema', {
            'fields': ('criado_em', 'atualizado_em'),
            'classes': ('collapse',),
            'description': 'Informações gerenciadas automaticamente'
        }),
    )
    
    readonly_fields = ['numero', 'criado_em', 'atualizado_em']
    
    def quantidade_documentos(self, obj):
        """Exibe quantidade de documentos com badge"""
        qtd = obj.quantidade_documentos
        color = 'success' if qtd < obj.capacidade_maxima * 0.8 else 'warning' if qtd < obj.capacidade_maxima else 'danger'
        return format_html(f'<span class="badge bg-{color}">{qtd}</span>')
    quantidade_documentos.short_description = 'Documentos'
    
    def percentual_ocupacao(self, obj):
        """Exibe percentual de ocupação com barra de progresso"""
        perc = obj.percentual_ocupacao
        color = 'success' if perc < 80 else 'warning' if perc < 100 else 'danger'
        return format_html(
            f'<div class="progress" style="height: 20px;">'
            f'<div class="progress-bar bg-{color}" style="width: {perc}%">'
            f'{perc:.1f}%'
            f'</div></div>'
        )
    percentual_ocupacao.short_description = 'Ocupação'
    
    def save_model(self, request, obj, form, change):
        """Personalizar salvamento"""
        if not change:  # Se é um novo objeto
            obj.nome = obj.nome.upper().strip()
            obj.descricao = obj.descricao.strip()
        else:  # Se é uma edição
            obj.nome = obj.nome.upper().strip()
            obj.descricao = obj.descricao.strip()
        
        super().save_model(request, obj, form, change)
