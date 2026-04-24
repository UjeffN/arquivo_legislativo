"""
Configuração do app Departamentos
"""
from django.apps import AppConfig


class DepartamentosConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.departamentos'
    verbose_name = 'Departamentos'
