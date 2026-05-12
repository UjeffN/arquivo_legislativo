"""
Modelos de Departamentos - Sistema de Arquivo Digital
"""
from django.db import models


class Departamento(models.Model):
    """Modelo para departamentos da Câmara Municipal"""

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
        ordering = ['nome']

    def __str__(self):
        return self.nome

    def save(self, *args, **kwargs):
        self.nome = self.nome.upper()
        super().save(*args, **kwargs)
