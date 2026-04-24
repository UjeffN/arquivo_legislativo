"""
Modelos de Departamentos - Sistema de Arquivo Digital
"""
from django.db import models
from django.utils.text import slugify


class Departamento(models.Model):
    """Modelo para departamentos da Câmara Municipal"""
    
    sigla = models.CharField(
        max_length=10, 
        unique=True,
        verbose_name="Sigla",
        help_text="Sigla do departamento (ex: GAB, SECAD, SEFIN)"
    )
    
    nome = models.CharField(
        max_length=100,
        unique=True,
        verbose_name="Nome do Departamento",
        help_text="Nome completo do departamento"
    )
    
    ativo = models.BooleanField(
        default=True,
        verbose_name="Ativo",
        help_text="Indica se o departamento está ativo"
    )
    
    criado_em = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Criado em"
    )
    
    atualizado_em = models.DateTimeField(
        auto_now=True,
        verbose_name="Atualizado em"
    )
    
    class Meta:
        verbose_name = "Departamento"
        verbose_name_plural = "Departamentos"
        ordering = ['sigla']
    
    def __str__(self):
        return f"{self.sigla} - {self.nome}"
    
    def save(self, *args, **kwargs):
        self.sigla = self.sigla.upper()
        self.nome = self.nome.upper()
        super().save(*args, **kwargs)
