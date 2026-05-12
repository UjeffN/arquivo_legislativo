"""
Modelos de Documentos - Sistema de Arquivo Digital
"""
from django.db import models
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.conf import settings


class TipoDocumento(models.Model):
    """Modelo para tipos de documento"""

    nome = models.CharField(
        max_length=50,
        unique=True,
        verbose_name="Tipo de Documento",
        help_text="Nome do tipo de documento (ex: Lei, Portaria, Ofício)"
    )

    descricao = models.TextField(
        blank=True,
        verbose_name="Descrição",
        help_text="Descrição do tipo de documento"
    )

    ativo = models.BooleanField(
        default=True,
        verbose_name="Ativo",
        help_text="Indica se o tipo está ativo"
    )

    criado_em = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Criado em"
    )

    class Meta:
        verbose_name = "Tipo de Documento"
        verbose_name_plural = "Tipos de Documento"
        ordering = ['nome']

    def __str__(self):
        return self.nome

    def save(self, *args, **kwargs):
        self.nome = self.nome.title()
        super().save(*args, **kwargs)


class Documento(models.Model):
    """Modelo principal para documentos"""

    nome = models.CharField(
        max_length=200,
        verbose_name="Nome do Documento",
        help_text="Nome completo do documento"
    )

    assunto = models.TextField(
        verbose_name="Assunto",
        help_text="Assunto ou resumo do documento"
    )

    tipo_documento = models.ForeignKey(
        TipoDocumento,
        on_delete=models.PROTECT,
        verbose_name="Tipo de Documento",
        help_text="Tipo do documento"
    )

    departamento = models.ForeignKey(
        'departamentos.Departamento',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Departamento",
        help_text="Departamento de origem (opcional se o departamento foi removido)"
    )

    numero_documento = models.CharField(
        max_length=50,
        verbose_name="Número do Documento",
        help_text="Número do documento (ex: 404/2024)"
    )

    data_documento = models.DateField(
        verbose_name="Data do Documento",
        help_text="Data de emissão do documento"
    )

    caixa = models.ForeignKey(
        'caixas.Caixa',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        verbose_name="Caixa",
        help_text="Caixa onde o documento está armazenado (opcional)"
    )

    arquivo_pdf = models.FileField(
        upload_to='documentos/',
        verbose_name="Arquivo PDF",
        help_text="Arquivo PDF do documento digitalizado"
    )

    texto_extraido = models.TextField(
        blank=True,
        verbose_name="Texto Extraído (OCR)",
        help_text="Texto extraído do documento via OCR"
    )

    ocr_processado = models.BooleanField(
        default=False,
        verbose_name="OCR Processado",
        help_text="Indica se o OCR já foi processado"
    )

    palavra_chave = models.CharField(
        max_length=200,
        blank=True,
        verbose_name="Palavra-chave",
        help_text="Palavras-chave para busca"
    )

    observacao = models.TextField(
        blank=True,
        verbose_name="Observação",
        help_text="Observações adicionais sobre o documento"
    )

    data_upload = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Data de Upload"
    )

    atualizado_em = models.DateTimeField(
        auto_now=True,
        verbose_name="Atualizado em"
    )

    class Meta:
        verbose_name = "Documento"
        verbose_name_plural = "Documentos"
        ordering = ['-data_documento', 'numero_documento']
        indexes = [
            models.Index(fields=['numero_documento']),
            models.Index(fields=['tipo_documento']),
            models.Index(fields=['departamento']),
            models.Index(fields=['caixa']),
            models.Index(fields=['data_documento']),
        ]

    def __str__(self):
        return f"{self.tipo_documento.nome} {self.numero_documento}/{self.data_documento.year}"

    def clean(self):
        """Validação personalizada"""

        # Validações básicas
        if self.data_documento and self.data_documento > timezone.now().date():
            raise ValidationError('Data do documento não pode ser futura')

        # Validações da caixa (se existir)
        if hasattr(self, 'caixa') and self.caixa:
            # Verificar capacidade da caixa
            if self.caixa.esta_cheia:
                raise ValidationError('Esta caixa já atingiu sua capacidade máxima')

    @property
    def numero_formatado(self):
        """Retorna o número formatado do documento"""
        return f"{self.numero_documento}/{self.data_documento.year}"

    @property
    def tamanho_arquivo(self):
        """Retorna o tamanho do arquivo em MB"""
        if self.arquivo_pdf:
            return self.arquivo_pdf.size / (1024 * 1024)
        return 0

    def save(self, *args, **kwargs):
        # Salvar o nome e assunto em maiúsculas
        self.nome = self.nome.upper()
        self.assunto = self.assunto.upper()
        self.numero_documento = self.numero_documento.upper()
        self.palavra_chave = self.palavra_chave.upper() if self.palavra_chave else ""

        super().save(*args, **kwargs)


class LogAuditoria(models.Model):
    """Modelo para auditoria de alterações em documentos"""

    class Acao(models.TextChoices):
        CRIADO = 'CRIADO', 'Documento Criado'
        ATUALIZADO = 'ATUALIZADO', 'Documento Atualizado'
        EXCLUIDO = 'EXCLUIDO', 'Documento Excluído'
        EDITAR = 'EDITAR', 'Acesso à Edição'
        VISUALIZADO = 'VISUALIZADO', 'Documento Visualizado'
        BAIXADO = 'BAIXADO', 'Documento Baixado'
        BAIXADO_LOTE = 'BAIXADO_LOTE', 'Documento Baixado em Lote'
        BAIXADO_POR_TIPO = 'BAIXADO_POR_TIPO', 'Download por Tipo'
        BAIXADO_POR_DEPARTAMENTO = 'BAIXADO_POR_DEPARTAMENTO', 'Download por Departamento'
        ACESSO_NEGADO_DOWNLOAD = 'ACESSO_NEGADO_DOWNLOAD', 'Acesso Negado no Download'

    documento = models.ForeignKey(
        Documento,
        on_delete=models.CASCADE,
        verbose_name="Documento"
    )

    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        verbose_name="Usuário"
    )

    acao = models.CharField(
        max_length=50,
        choices=Acao.choices,
        verbose_name="Ação"
    )

    descricao = models.TextField(
        verbose_name="Descrição",
        help_text="Descrição detalhada da ação"
    )

    data_hora = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Data e Hora"
    )

    ip_address = models.GenericIPAddressField(
        null=True,
        blank=True,
        verbose_name="Endereço IP"
    )

    class Meta:
        verbose_name = "Log de Auditoria"
        verbose_name_plural = "Logs de Auditoria"
        ordering = ['-data_hora']

    def __str__(self):
        return f"{self.documento} - {self.acao} - {self.data_hora}"
