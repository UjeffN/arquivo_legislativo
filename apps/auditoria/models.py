"""
Modelos de auditoria e logging para o Sistema de Arquivo Digital
"""

import json
import hashlib
from django.db import models
from django.contrib.auth import get_user_model
from django.core.serializers.json import DjangoJSONEncoder
from django.utils import timezone

User = get_user_model()


class LogAuditoria(models.Model):
    """
    Modelo principal para registro de logs de auditoria estruturados
    """

    class NivelSeveridade(models.TextChoices):
        DEBUG = 'DEBUG', 'Debug'
        INFO = 'INFO', 'Informação'
        WARNING = 'WARNING', 'Aviso'
        ERROR = 'ERROR', 'Erro'
        CRITICAL = 'CRITICAL', 'Crítico'

    class TipoOperacao(models.TextChoices):
        AUTENTICACAO = 'AUTH', 'Autenticação'
        CREATE = 'CREATE', 'Criação'
        UPDATE = 'UPDATE', 'Atualização'
        DELETE = 'DELETE', 'Exclusão'
        VIEW = 'VIEW', 'Visualização'
        DOWNLOAD = 'DOWNLOAD', 'Download'
        UPLOAD = 'UPLOAD', 'Upload'
        SEARCH = 'SEARCH', 'Busca'
        EXPORT = 'EXPORT', 'Exportação'
        BACKUP = 'BACKUP', 'Backup'
        RESTORE = 'RESTORE', 'Restauração'
        SECURITY = 'SECURITY', 'Segurança'
        SYSTEM = 'SYSTEM', 'Sistema'

    # Campos principais
    id = models.BigAutoField(primary_key=True)
    timestamp = models.DateTimeField(default=timezone.now, db_index=True)
    nivel_severidade = models.CharField(
        max_length=10,
        choices=NivelSeveridade.choices,
        default=NivelSeveridade.INFO,
        db_index=True
    )
    tipo_operacao = models.CharField(
        max_length=20,
        choices=TipoOperacao.choices,
        db_index=True
    )

    # Informações do usuário
    usuario = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='logs_auditoria'
    )
    nome_usuario = models.CharField(max_length=150, blank=True)  # Backup caso usuário seja deletado
    ip_address = models.GenericIPAddressField(null=True, blank=True, db_index=True)
    user_agent = models.TextField(blank=True)

    # Informações do recurso
    modulo = models.CharField(max_length=100, db_index=True)  # app responsável
    modelo = models.CharField(max_length=100, blank=True)  # modelo Django
    objeto_id = models.CharField(max_length=50, blank=True, db_index=True)
    objeto_repr = models.CharField(max_length=255, blank=True)

    # Descrição e detalhes
    acao = models.CharField(max_length=255)  # descrição curta da ação
    descricao = models.TextField(blank=True)  # descrição detalhada

    # Dados estruturados (JSON)
    dados_antes = models.JSONField(
        default=dict,
        blank=True,
        encoder=DjangoJSONEncoder
    )
    dados_depois = models.JSONField(
        default=dict,
        blank=True,
        encoder=DjangoJSONEncoder
    )
    metadados = models.JSONField(
        default=dict,
        blank=True,
        encoder=DjangoJSONEncoder
    )

    # Campos de segurança e integridade
    hash_dados = models.CharField(max_length=64, unique=True)  # SHA-256 para integridade
    checksum_verificado = models.BooleanField(default=False)

    # Campos de controle
    sessao_id = models.CharField(max_length=100, blank=True, db_index=True)
    request_id = models.CharField(max_length=100, blank=True, db_index=True)
    duracao_ms = models.IntegerField(null=True, blank=True)  # duração da operação em ms

    # Status da operação
    sucesso = models.BooleanField(default=True)
    erro_msg = models.TextField(blank=True)

    class Meta:
        db_table = 'auditoria_log'
        verbose_name = 'Log de Auditoria'
        verbose_name_plural = 'Logs de Auditoria'
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['timestamp', 'nivel_severidade']),
            models.Index(fields=['usuario', 'timestamp']),
            models.Index(fields=['modulo', 'tipo_operacao']),
            models.Index(fields=['ip_address', 'timestamp']),
        ]

    def __str__(self):
        return f"{self.timestamp} - {self.usuario} - {self.acao}"

    def save(self, *args, **kwargs):
        # Gerar hash dos dados para integridade
        dados_json = json.dumps({
            'dados_antes': self.dados_antes,
            'dados_depois': self.dados_depois,
            'metadados': self.metadados,
            'acao': self.acao,
            'timestamp': self.timestamp.isoformat() if self.timestamp else None,
        }, sort_keys=True, cls=DjangoJSONEncoder)

        self.hash_dados = hashlib.sha256(dados_json.encode()).hexdigest()

        # Salvar nome do usuário como backup
        if self.usuario and not self.nome_usuario:
            self.nome_usuario = self.usuario.get_username()

        super().save(*args, **kwargs)

    def verificar_integridade(self):
        """Verifica se os dados não foram alterados"""
        dados_json = json.dumps({
            'dados_antes': self.dados_antes,
            'dados_depois': self.dados_depois,
            'metadados': self.metadados,
            'acao': self.acao,
            'timestamp': self.timestamp.isoformat() if self.timestamp else None,
        }, sort_keys=True, cls=DjangoJSONEncoder)

        hash_calculado = hashlib.sha256(dados_json.encode()).hexdigest()
        return hash_calculado == self.hash_dados


class ConfiguracaoRetencao(models.Model):
    """
    Configurações de retenção de logs por tipo de operação
    """

    tipo_operacao = models.CharField(
        max_length=20,
        choices=LogAuditoria.TipoOperacao.choices,
        unique=True
    )
    dias_retencao = models.IntegerField(default=365)  # dias para manter
    nivel_severidade_minimo = models.CharField(
        max_length=10,
        choices=LogAuditoria.NivelSeveridade.choices,
        default=LogAuditoria.NivelSeveridade.DEBUG
    )
    ativo = models.BooleanField(default=True)

    class Meta:
        db_table = 'auditoria_configuracao_retencao'
        verbose_name = 'Configuração de Retenção'
        verbose_name_plural = 'Configurações de Retenção'

    def __str__(self):
        return f"{self.get_tipo_operacao_display()} - {self.dias_retencao} dias"


class EstatisticaAuditoria(models.Model):
    """
    Estatísticas agregadas de auditoria para relatórios
    """

    data = models.DateField(db_index=True)
    tipo_operacao = models.CharField(
        max_length=20,
        choices=LogAuditoria.TipoOperacao.choices
    )
    nivel_severidade = models.CharField(
        max_length=10,
        choices=LogAuditoria.NivelSeveridade.choices
    )
    total_registros = models.IntegerField(default=0)
    usuarios_unicos = models.IntegerField(default=0)
    ip_unicos = models.IntegerField(default=0)
    falhas = models.IntegerField(default=0)

    class Meta:
        db_table = 'auditoria_estatisticas'
        verbose_name = 'Estatística de Auditoria'
        verbose_name_plural = 'Estatísticas de Auditoria'
        unique_together = ['data', 'tipo_operacao', 'nivel_severidade']
        ordering = ['-data', 'tipo_operacao']

    def __str__(self):
        return f"{self.data} - {self.get_tipo_operacao_display()} - {self.total_registros}"


class AlertaSeguranca(models.Model):
    """
    Alertas de segurança gerados automaticamente
    """

    class TipoAlerta(models.TextChoices):
        MULTIPLAS_FALHAS_LOGIN = 'MULTIPLAS_FALHAS_LOGIN', 'Múltiplas falhas de login'
        ACESSO_NEGADO = 'ACESSO_NEGADO', 'Acesso negado recorrente'
        ATIVIDADE_SUSPEITA = 'ATIVIDADE_SUSPEITA', 'Atividade suspeita'
        ALTERACAO_MASSIVA = 'ALTERACAO_MASSIVA', 'Alteração massiva de dados'
        HORARIO_INCOMUM = 'HORARIO_INCOMUM', 'Acesso em horário incomum'
        IP_SUSPEITO = 'IP_SUSPEITO', 'Acesso de IP suspeito'

    class NivelAlerta(models.TextChoices):
        BAIXO = 'BAIXO', 'Baixo'
        MEDIO = 'MEDIO', 'Médio'
        ALTO = 'ALTO', 'Alto'
        CRITICO = 'CRITICO', 'Crítico'

    timestamp = models.DateTimeField(default=timezone.now)
    tipo_alerta = models.CharField(max_length=30, choices=TipoAlerta.choices)
    nivel_alerta = models.CharField(max_length=10, choices=NivelAlerta.choices)

    # Informações relacionadas
    usuario = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    ip_address = models.GenericIPAddressField(null=True, blank=True)

    # Detalhes do alerta
    titulo = models.CharField(max_length=255)
    descricao = models.TextField()
    dados_adicionais = models.JSONField(default=dict, blank=True)

    # Controle do alerta
    visualizado = models.BooleanField(default=False)
    visualizado_em = models.DateTimeField(null=True, blank=True)
    visualizado_por = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='alertas_visualizados'
    )

    # Logs relacionados
    logs_relacionados = models.ManyToManyField(
        LogAuditoria,
        blank=True,
        related_name='alertas'
    )

    class Meta:
        db_table = 'auditoria_alerta_seguranca'
        verbose_name = 'Alerta de Segurança'
        verbose_name_plural = 'Alertas de Segurança'
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['timestamp', 'nivel_alerta']),
            models.Index(fields=['visualizado', 'timestamp']),
        ]

    def __str__(self):
        return f"{self.timestamp} - {self.titulo}"
