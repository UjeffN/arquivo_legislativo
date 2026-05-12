"""
Configuração do app de auditoria
"""

from django.apps import AppConfig


class AuditoriaConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.auditoria'
    verbose_name = 'Auditoria e Segurança'

    def ready(self):
        """
        Configurações iniciais quando o app é carregado
        """
        # Importar sinais para registrar listeners
        try:
            from . import signals
        except ImportError:
            pass

        # Configurar logger personalizado
        import logging
        from django.conf import settings

        # Criar logger para auditoria
        logger = logging.getLogger('auditoria')
        logger.setLevel(logging.INFO)

        # Evitar duplicação de handlers
        if not logger.handlers:
            # Handler para arquivo
            handler = logging.FileHandler(
                settings.BASE_DIR / 'logs' / 'auditoria.log',
                encoding='utf-8'
            )
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            logger.addHandler(handler)

        # Criar configurações padrão de retenção se não existirem
        from .models import ConfiguracaoRetencao

        configs_padrao = [
            ('AUTH', 90),      # Logs de autenticação: 90 dias
            ('CREATE', 365),   # Logs de criação: 1 ano
            ('UPDATE', 365),   # Logs de atualização: 1 ano
            ('DELETE', 1825),  # Logs de exclusão: 5 anos
            ('VIEW', 30),      # Logs de visualização: 30 dias
            ('DOWNLOAD', 365), # Logs de download: 1 ano
            ('UPLOAD', 365),   # Logs de upload: 1 ano
            ('SEARCH', 30),    # Logs de busca: 30 dias
            ('EXPORT', 365),   # Logs de exportação: 1 ano
            ('BACKUP', 1825),  # Logs de backup: 5 anos
            ('RESTORE', 1825), # Logs de restauração: 5 anos
            ('SECURITY', 1825),# Logs de segurança: 5 anos
            ('SYSTEM', 90),    # Logs de sistema: 90 dias
        ]

        # Criar configurações de forma assíncrona para não bloquear startup
        from django.db import transaction

        def criar_configs_padrao():
            try:
                with transaction.atomic():
                    for tipo_operacao, dias in configs_padrao:
                        ConfiguracaoRetencao.objects.get_or_create(
                            tipo_operacao=tipo_operacao,
                            defaults={'dias_retencao': dias}
                        )
            except Exception:
                # Silenciar erros durante startup para não quebrar a aplicação
                pass

        # Agendar criação para após a inicialização completa
        from concurrent.futures import ThreadPoolExecutor
        executor = ThreadPoolExecutor(max_workers=1)
        executor.submit(criar_configs_padrao)
        executor.shutdown(wait=False)
