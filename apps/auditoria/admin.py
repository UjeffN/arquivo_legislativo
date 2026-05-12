"""
Interface Django Admin para o módulo de auditoria
"""

import json
import csv
import zipfile
import io
from datetime import datetime, timedelta
from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from django.http import HttpResponse
from django.db.models import Count, Q
from django.forms import ModelForm
from django import forms

from .models import LogAuditoria, ConfiguracaoRetencao, EstatisticaAuditoria, AlertaSeguranca
from .services import AuditoriaService

User = get_user_model()


@admin.register(LogAuditoria)
class LogAuditoriaAdmin(admin.ModelAdmin):
    """
    Interface administrativa para logs de auditoria
    """

    list_display = [
        'timestamp', 'usuario_info', 'tipo_operacao', 'nivel_severidade_badge',
        'modulo', 'acao_resumida', 'ip_address', 'sucesso_badge'
    ]

    list_filter = [
        'timestamp', 'tipo_operacao', 'nivel_severidade', 'modulo',
        'sucesso', 'ip_address'
    ]

    search_fields = [
        'usuario__username', 'nome_usuario', 'acao', 'descricao',
        'objeto_repr', 'ip_address'
    ]

    date_hierarchy = 'timestamp'
    ordering = ['-timestamp']

    readonly_fields = [
        'timestamp', 'hash_dados', 'checksum_verificado', 'integridade_status',
        'dados_antes_formatado', 'dados_depois_formatado', 'metadados_formatado'
    ]

    filter_horizontal = []

    fieldsets = (
        ('Informações Gerais', {
            'fields': (
                'timestamp', 'nivel_severidade', 'tipo_operacao',
                'sucesso', 'modulo', 'acao', 'descricao'
            )
        }),
        ('Informações do Usuário', {
            'fields': (
                'usuario', 'nome_usuario', 'ip_address', 'user_agent',
                'sessao_id', 'request_id', 'duracao_ms'
            )
        }),
        ('Informações do Recurso', {
            'fields': (
                'modelo', 'objeto_id', 'objeto_repr'
            )
        }),
        ('Dados Estruturados', {
            'fields': (
                'dados_antes_formatado', 'dados_depois_formatado',
                'metadados_formatado'
            ),
            'classes': ('collapse',)
        }),
        ('Segurança e Integridade', {
            'fields': (
                'hash_dados', 'checksum_verificado', 'integridade_status',
                'erro_msg'
            ),
            'classes': ('collapse',)
        }),
    )

    actions = [
        'exportar_selecionados_json', 'exportar_selecionados_csv',
        'verificar_integridade_selecionados', 'marcar_como_visualizado'
    ]

    def get_queryset(self, request):
        """
        Filtra logs baseado nas permissões do usuário
        """
        qs = super().get_queryset(request)

        # Se não for superusuário, mostrar apenas logs do seu departamento
        if not request.user.is_superuser:
            # Implementar lógica de filtragem por departamento se necessário
            pass

        return qs.select_related('usuario')

    def get_actions(self, request):
        """
        Filtra ações baseado nas permissões
        """
        actions = super().get_actions(request)

        if not request.user.has_perm('auditoria.export_logs'):
            actions.pop('exportar_selecionados_json', None)
            actions.pop('exportar_selecionados_csv', None)

        if not request.user.has_perm('auditoria.verify_integrity'):
            actions.pop('verificar_integridade_selecionados', None)

        return actions

    # Métodos de exibição personalizados
    def usuario_info(self, obj):
        """Exibe informações do usuário de forma formatada"""
        if obj.usuario:
            return format_html(
                '<strong>{}</strong><br><small>{}</small>',
                obj.usuario.get_username(),
                obj.usuario.get_full_name() or obj.usuario.email
            )
        return obj.nome_usuario or 'Sistema'
    usuario_info.short_description = 'Usuário'
    usuario_info.admin_order_field = 'usuario__username'

    def nivel_severidade_badge(self, obj):
        """Exibe nível de severidade com cores"""
        cores = {
            'DEBUG': '#6c757d',
            'INFO': '#17a2b8',
            'WARNING': '#ffc107',
            'ERROR': '#dc3545',
            'CRITICAL': '#6f42c1'
        }

        cor = cores.get(obj.nivel_severidade, '#6c757d')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 2px 6px; '
            'border-radius: 3px; font-size: 11px;">{}</span>',
            cor,
            obj.get_nivel_severidade_display()
        )
    nivel_severidade_badge.short_description = 'Severidade'
    nivel_severidade_badge.admin_order_field = 'nivel_severidade'

    def sucesso_badge(self, obj):
        """Exibe status de sucesso com cores"""
        if obj.sucesso:
            return '<span style="color: #28a745;">✓ Sucesso</span>'
        return '<span style="color: #dc3545;">✗ Falha</span>'
    sucesso_badge.short_description = 'Status'
    sucesso_badge.admin_order_field = 'sucesso'

    def acao_resumida(self, obj):
        """Exibe ação resumida com tooltip"""
        acao = obj.acao[:50] + '...' if len(obj.acao) > 50 else obj.acao
        return format_html(
            '<span title="{}">{}</span>',
            obj.acao,
            acao
        )
    acao_resumida.short_description = 'Ação'

    def dados_antes_formatado(self, obj):
        """Formata dados anteriores para exibição"""
        if not obj.dados_antes:
            return 'Nenhum dado'

        return format_html(
            '<pre style="background: #f8f9fa; padding: 10px; border-radius: 4px; '
            'max-height: 200px; overflow-y: auto;">{}</pre>',
            json.dumps(obj.dados_antes, indent=2, ensure_ascii=False)
        )
    dados_antes_formatado.short_description = 'Dados Antes'

    def dados_depois_formatado(self, obj):
        """Formata dados posteriores para exibição"""
        if not obj.dados_depois:
            return 'Nenhum dado'

        return format_html(
            '<pre style="background: #f8f9fa; padding: 10px; border-radius: 4px; '
            'max-height: 200px; overflow-y: auto;">{}</pre>',
            json.dumps(obj.dados_depois, indent=2, ensure_ascii=False)
        )
    dados_depois_formatado.short_description = 'Dados Depois'

    def metadados_formatado(self, obj):
        """Formata metadados para exibição"""
        if not obj.metadados:
            return 'Nenhum metadado'

        return format_html(
            '<pre style="background: #f8f9fa; padding: 10px; border-radius: 4px; '
            'max-height: 200px; overflow-y: auto;">{}</pre>',
            json.dumps(obj.metadados, indent=2, ensure_ascii=False)
        )
    metadados_formatado.short_description = 'Metadados'

    def integridade_status(self, obj):
        """Verifica e exibe status da integridade"""
        if obj.verificar_integridade():
            return format_html(
                '<span style="color: #28a745;">✓ Integridade verificada</span>'
            )
        return format_html(
            '<span style="color: #dc3545;">✗ Integridade comprometida</span>'
        )
    integridade_status.short_description = 'Integridade'

    # Ações personalizadas
    def exportar_selecionados_json(self, request, queryset):
        """Exporta logs selecionados para JSON"""
        auditoria = AuditoriaService()

        # Criar arquivo JSON
        json_data = []
        for log in queryset:
            json_data.append({
                'id': log.id,
                'timestamp': log.timestamp.isoformat(),
                'nivel_severidade': log.get_nivel_severidade_display(),
                'tipo_operacao': log.get_tipo_operacao_display(),
                'usuario': log.usuario.get_username() if log.usuario else log.nome_usuario,
                'ip_address': log.ip_address,
                'modulo': log.modulo,
                'acao': log.acao,
                'descricao': log.descricao,
                'dados_antes': log.dados_antes,
                'dados_depois': log.dados_depois,
                'metadados': log.metadados,
                'sucesso': log.sucesso,
                'erro_msg': log.erro_msg
            })

        response = HttpResponse(
            json.dumps(json_data, indent=2, ensure_ascii=False),
            content_type='application/json'
        )
        response['Content-Disposition'] = f'attachment; filename="logs_auditoria_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json"'

        return response
    exportar_selecionados_json.short_description = 'Exportar selecionados para JSON'

    def exportar_selecionados_csv(self, request, queryset):
        """Exporta logs selecionados para CSV"""
        output = io.StringIO()
        writer = csv.writer(output)

        # Cabeçalho
        writer.writerow([
            'ID', 'Timestamp', 'Nível', 'Operação', 'Usuário', 'IP',
            'Módulo', 'Ação', 'Sucesso', 'Descrição'
        ])

        # Dados
        for log in queryset:
            writer.writerow([
                log.id,
                log.timestamp.isoformat(),
                log.get_nivel_severidade_display(),
                log.get_tipo_operacao_display(),
                log.usuario.get_username() if log.usuario else log.nome_usuario,
                log.ip_address,
                log.modulo,
                log.acao,
                log.sucesso,
                log.descricao
            ])

        response = HttpResponse(
            output.getvalue(),
            content_type='text/csv'
        )
        response['Content-Disposition'] = f'attachment; filename="logs_auditoria_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv"'

        return response
    exportar_selecionados_csv.short_description = 'Exportar selecionados para CSV'

    def verificar_integridade_selecionados(self, request, queryset):
        """Verifica integridade dos logs selecionados"""
        comprometidos = 0

        for log in queryset:
            if not log.verificar_integridade():
                comprometidos += 1

        self.message_user(
            request,
            f'Verificação concluída. {comprometidos} de {queryset.count()} logs comprometidos.',
            'error' if comprometidos > 0 else 'success'
        )
    verificar_integridade_selecionados.short_description = 'Verificar integridade dos selecionados'


@admin.register(ConfiguracaoRetencao)
class ConfiguracaoRetencaoAdmin(admin.ModelAdmin):
    """
    Interface para configurações de retenção de logs
    """

    list_display = [
        'tipo_operacao', 'dias_retencao', 'nivel_severidade_minimo_badge', 'ativo'
    ]

    list_filter = ['tipo_operacao', 'ativo', 'nivel_severidade_minimo']
    search_fields = ['tipo_operacao']

    actions = ['ativar_selecionados', 'desativar_selecionados']

    def nivel_severidade_minimo_badge(self, obj):
        """Exibe nível de severidade mínimo com cor"""
        cores = {
            'DEBUG': '#6c757d',
            'INFO': '#17a2b8',
            'WARNING': '#ffc107',
            'ERROR': '#dc3545',
            'CRITICAL': '#6f42c1'
        }

        cor = cores.get(obj.nivel_severidade_minimo, '#6c757d')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 2px 6px; '
            'border-radius: 3px;">{}</span>',
            cor,
            obj.get_nivel_severidade_minimo_display()
        )
    nivel_severidade_minimo_badge.short_description = 'Nível Mínimo'

    def ativar_selecionados(self, request, queryset):
        """Ativa configurações selecionadas"""
        queryset.update(ativo=True)
        self.message_user(request, 'Configurações ativadas com sucesso.')
    ativar_selecionados.short_description = 'Ativar selecionados'

    def desativar_selecionados(self, request, queryset):
        """Desativa configurações selecionadas"""
        queryset.update(ativo=False)
        self.message_user(request, 'Configurações desativadas com sucesso.')
    desativar_selecionados.short_description = 'Desativar selecionados'


@admin.register(EstatisticaAuditoria)
class EstatisticaAuditoriaAdmin(admin.ModelAdmin):
    """
    Interface para estatísticas de auditoria
    """

    list_display = [
        'data', 'tipo_operacao_badge', 'nivel_severidade_badge',
        'total_registros', 'usuarios_unicos', 'ip_unicos', 'falhas'
    ]

    list_filter = [
        'data', 'tipo_operacao', 'nivel_severidade'
    ]

    date_hierarchy = 'data'
    ordering = ['-data', 'tipo_operacao']

    def has_add_permission(self, request):
        """Não permite adicionar manualmente"""
        return False

    def has_change_permission(self, request, obj=None):
        """Não permite editar manualmente"""
        return False

    def tipo_operacao_badge(self, obj):
        """Exibe tipo de operação com cor"""
        cores = {
            'AUTH': '#6f42c1',
            'CREATE': '#28a745',
            'UPDATE': '#ffc107',
            'DELETE': '#dc3545',
            'VIEW': '#17a2b8',
            'DOWNLOAD': '#fd7e14',
            'UPLOAD': '#20c997',
            'SEARCH': '#6c757d',
            'EXPORT': '#6610f2',
            'BACKUP': '#e83e8c',
            'RESTORE': '#d63384',
            'SECURITY': '#dc3545',
            'SYSTEM': '#6c757d'
        }

        cor = cores.get(obj.tipo_operacao, '#6c757d')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 2px 6px; '
            'border-radius: 3px; font-size: 11px;">{}</span>',
            cor,
            obj.get_tipo_operacao_display()
        )
    tipo_operacao_badge.short_description = 'Operação'

    def nivel_severidade_badge(self, obj):
        """Exibe nível de severidade com cor"""
        cores = {
            'DEBUG': '#6c757d',
            'INFO': '#17a2b8',
            'WARNING': '#ffc107',
            'ERROR': '#dc3545',
            'CRITICAL': '#6f42c1'
        }

        cor = cores.get(obj.nivel_severidade, '#6c757d')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 2px 6px; '
            'border-radius: 3px; font-size: 11px;">{}</span>',
            cor,
            obj.get_nivel_severidade_display()
        )
    nivel_severidade_badge.short_description = 'Severidade'


@admin.register(AlertaSeguranca)
class AlertaSegurancaAdmin(admin.ModelAdmin):
    """
    Interface para alertas de segurança
    """

    list_display = [
        'timestamp', 'tipo_alerta_badge', 'nivel_alerta_badge',
        'usuario_info', 'ip_address', 'titulo', 'visualizado_badge'
    ]

    list_filter = [
        'timestamp', 'tipo_alerta', 'nivel_alerta', 'visualizado'
    ]

    search_fields = [
        'usuario__username', 'ip_address', 'titulo', 'descricao'
    ]

    date_hierarchy = 'timestamp'
    ordering = ['-timestamp']

    readonly_fields = [
        'timestamp', 'tipo_alerta', 'nivel_alerta', 'usuario',
        'ip_address', 'dados_adicionais_formatado', 'logs_relacionados'
    ]

    actions = [
        'marcar_como_visualizado', 'marcar_como_nao_visualizado',
        'exportar_alertas'
    ]

    def tipo_alerta_badge(self, obj):
        """Exibe tipo de alerta com cor"""
        cores = {
            'MULTIPLAS_FALHAS_LOGIN': '#dc3545',
            'ACESSO_NEGADO': '#dc3545',
            'ATIVIDADE_SUSPEITA': '#ffc107',
            'ALTERACAO_MASSIVA': '#fd7e14',
            'HORARIO_INCOMUM': '#17a2b8',
            'IP_SUSPEITO': '#dc3545'
        }

        cor = cores.get(obj.tipo_alerta, '#6c757d')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 2px 6px; '
            'border-radius: 3px; font-size: 11px;">{}</span>',
            cor,
            obj.get_tipo_alerta_display()
        )
    tipo_alerta_badge.short_description = 'Tipo'

    def nivel_alerta_badge(self, obj):
        """Exibe nível de alerta com cor"""
        cores = {
            'BAIXO': '#28a745',
            'MEDIO': '#ffc107',
            'ALTO': '#fd7e14',
            'CRITICO': '#dc3545'
        }

        cor = cores.get(obj.nivel_alerta, '#6c757d')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 2px 6px; '
            'border-radius: 3px; font-size: 11px;">{}</span>',
            cor,
            obj.get_nivel_alerta_display()
        )
    nivel_alerta_badge.short_description = 'Nível'

    def usuario_info(self, obj):
        """Exibe informações do usuário"""
        if obj.usuario:
            return format_html(
                '<strong>{}</strong><br><small>{}</small>',
                obj.usuario.get_username(),
                obj.usuario.get_full_name() or obj.usuario.email
            )
        return 'Sistema'
    usuario_info.short_description = 'Usuário'

    def visualizado_badge(self, obj):
        """Exibe status de visualização"""
        if obj.visualizado:
            return format_html(
                '<span style="color: #28a745;">✓ Visualizado</span>'
            )
        return format_html(
            '<span style="color: #6c757d;">○ Não visualizado</span>'
        )
    visualizado_badge.short_description = 'Status'

    def dados_adicionais_formatado(self, obj):
        """Formata dados adicionais para exibição"""
        if not obj.dados_adicionais:
            return 'Nenhum dado adicional'

        return format_html(
            '<pre style="background: #f8f9fa; padding: 10px; border-radius: 4px; '
            'max-height: 200px; overflow-y: auto;">{}</pre>',
            json.dumps(obj.dados_adicionais, indent=2, ensure_ascii=False)
        )
    dados_adicionais_formatado.short_description = 'Dados Adicionais'

    def marcar_como_visualizado(self, request, queryset):
        """Marca alertas como visualizados"""
        count = queryset.filter(visualizado=False).update(
            visualizado=True,
            visualizado_em=timezone.now(),
            visualizado_por=request.user
        )
        self.message_user(request, f'{count} alertas marcados como visualizados.')
    marcar_como_visualizado.short_description = 'Marcar como visualizado'

    def marcar_como_nao_visualizado(self, request, queryset):
        """Marca alertas como não visualizados"""
        count = queryset.filter(visualizado=True).update(
            visualizado=False,
            visualizado_em=None,
            visualizado_por=None
        )
        self.message_user(request, f'{count} alertas marcados como não visualizados.')
    marcar_como_nao_visualizado.short_description = 'Marcar como não visualizado'
