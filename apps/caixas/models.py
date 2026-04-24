"""
Modelos de Caixas - Sistema de Arquivo Digital
"""
import os
import calendar
from django.db import models
from django.core.exceptions import ValidationError


class Caixa(models.Model):
    """Modelo para caixas de arquivo físico como coleções organizadas"""
    
    numero = models.PositiveIntegerField(
        unique=True,
        verbose_name="Número da Caixa",
        help_text="Número automático e único da caixa"
    )
    
    nome = models.CharField(
        max_length=100,
        blank=True,
        verbose_name="Nome da Caixa",
        help_text="Nome/descrição da caixa (será o mesmo do número por padrão)"
    )
    
    descricao = models.TextField(
        blank=True,
        verbose_name="Descrição",
        help_text="Descrição detalhada do conteúdo da caixa"
    )
    
    localizacao_fisica = models.CharField(
        max_length=100,
        blank=True,
        verbose_name="Localização Física",
        help_text="Onde a caixa está fisicamente armazenada"
    )
    
    capacidade_maxima = models.PositiveIntegerField(
        default=100,
        verbose_name="Capacidade Máxima",
        help_text="Número máximo de documentos na caixa (definido pelo cliente)"
    )
    
    class Meta:
        verbose_name = "Caixa"
        verbose_name_plural = "Caixas"
        ordering = ['numero']
    
    criado_em = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Criado em"
    )
    
    atualizado_em = models.DateTimeField(
        auto_now=True,
        verbose_name="Atualizado em"
    )
    
    class Meta:
        verbose_name = "Caixa"
        verbose_name_plural = "Caixas"
        ordering = ['numero']
    
    def __str__(self):
        return f"Caixa {self.numero:04d} - {self.nome}"
    
    def save(self, *args, **kwargs):
        """Gera número automaticamente antes de salvar"""
        if not self.numero:
            self.numero = self.gerar_proximo_numero()
        if not self.nome:
            self.nome = f"Caixa {self.numero}"
        super().save(*args, **kwargs)
    
    def gerar_proximo_numero(self):
        """Gera o próximo número de caixa automaticamente"""
        ultima_caixa = Caixa.objects.all().order_by('-numero').first()
        if ultima_caixa:
            return ultima_caixa.numero + 1
        return 1
    
    @property
    def quantidade_documentos(self):
        """Retorna a quantidade de documentos na caixa"""
        return self.documento_set.count()
    
    @property
    def esta_cheia(self):
        """Verifica se a caixa está cheia"""
        return self.quantidade_documentos >= self.capacidade_maxima
    
    @property
    def percentual_ocupacao(self):
        """Retorna percentual de ocupação da caixa"""
        if self.capacidade_maxima > 0:
            return (self.quantidade_documentos / self.capacidade_maxima) * 100
        return 0
    
    @property
    def vagas_disponiveis(self):
        """Retorna número de vagas disponíveis na caixa"""
        if self.capacidade_maxima:
            return self.capacidade_maxima - self.quantidade_documentos
        return 0
    
    @property
    def descricao_completa(self):
        """Retorna descrição completa da caixa"""
        descricao = f"Caixa {self.numero}"
        if self.nome:
            descricao += f" - {self.nome}"
        if self.localizacao_fisica:
            descricao += f" ({self.localizacao_fisica})"
        return descricao
    
    @property
    def codigo_barras(self):
        """Retorna o código de barras formatado"""
        return f"CX{self.numero:06d}"
