"""
Sinais para automação de auditoria no Sistema de Arquivo Digital
"""

from django.db.models.signals import post_save, post_delete, pre_save
from django.contrib.auth.signals import user_logged_in, user_logged_out, user_login_failed
from django.dispatch import receiver
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.db import transaction
from django.core.cache import cache
from threading import local

from .models import LogAuditoria, EstatisticaAuditoria
from .services import auditoria_service

User = get_user_model()
_thread_locals = local()


@receiver(user_logged_in)
def log_login_sucesso(sender, request, user, **kwargs):
    """
    Registra login bem-sucedido
    """
    auditoria_service.registrar_autenticacao(
        usuario=user,
        ip_address=auditoria_service._get_client_ip(request),
        user_agent=request.META.get('HTTP_USER_AGENT', ''),
        sucesso=True
    )


@receiver(user_logged_out)
def log_logout(sender, request, user, **kwargs):
    """
    Registra logout do usuário
    """
    auditoria_service.registrar_log(
        acao="Logout do usuário",
        tipo_operacao=LogAuditoria.TipoOperacao.AUTENTICACAO,
        usuario=user,
        ip_address=auditoria_service._get_client_ip(request),
        user_agent=request.META.get('HTTP_USER_AGENT', ''),
        modulo='auth',
        descricao=f"Usuário {user.get_username()} fez logout do sistema"
    )


@receiver(user_login_failed)
def log_login_falha(sender, credentials, request, **kwargs):
    """
    Registra tentativa de login falha
    """
    username = credentials.get('username', 'desconhecido')

    # Tentar encontrar o usuário
    try:
        user = User.objects.get(username=username)
    except User.DoesNotExist:
        user = None

    auditoria_service.registrar_autenticacao(
        usuario=user,
        ip_address=auditoria_service._get_client_ip(request),
        user_agent=request.META.get('HTTP_USER_AGENT', ''),
        sucesso=False,
        erro_msg="Credenciais inválidas"
    )


@receiver(pre_save)
def log_pre_save(sender, instance, **kwargs):
    """
    Captura estado anterior do objeto antes de salvar
    """
    # Ignorar modelos de auditoria para evitar recursão infinita
    if sender._meta.app_label == 'auditoria':
        return

    # Ignorar se é um novo objeto
    if instance.pk is None:
        return

    try:
        # Obter estado anterior
        modelo_anterior = sender.objects.get(pk=instance.pk)

        # Armazenar dados anteriores no cache para uso no post_save
        cache_key = f"auditoria_pre_save_{sender.__name__}_{instance.pk}"
        dados_anteriores = {}

        # Capturar todos os campos do modelo
        for field in instance._meta.fields:
            field_name = field.name
            valor_anterior = getattr(modelo_anterior, field_name)
            valor_atual = getattr(instance, field_name)

            # Comparar valores
            if valor_anterior != valor_atual:
                dados_anteriores[field_name] = {
                    'antes': str(valor_anterior) if valor_anterior is not None else None,
                    'depois': str(valor_atual) if valor_atual is not None else None,
                    'tipo': field.get_internal_type()
                }

        # Armazenar no cache por 5 minutos
        cache.set(cache_key, dados_anteriores, timeout=300)

    except sender.DoesNotExist:
        # Objeto novo, não há dados anteriores
        pass
    except Exception:
        # Silenciar erros para não quebrar a operação principal
        pass


@receiver(post_save)
def log_post_save(sender, instance, created, **kwargs):
    """
    Registra operações de criação e atualização
    """
    # Ignorar modelos de auditoria para evitar recursão infinita
    if sender._meta.app_label == 'auditoria':
        return

    # Obter usuário atual do thread local (definido em middleware)
    usuario_atual = getattr(_thread_locals, 'user', None)
    request_atual = getattr(_thread_locals, 'request', None)

    if not usuario_atual:
        return

    try:
        modelo_nome = f"{sender._meta.app_label}.{sender.__name__}"
        objeto_id = str(instance.pk)
        objeto_repr = str(instance)[:255]

        if created:
            # Log de criação
            auditoria_service.registrar_log(
                acao=f"Criado {modelo_nome}",
                tipo_operacao=LogAuditoria.TipoOperacao.CREATE,
                usuario=usuario_atual,
                ip_address=auditoria_service._get_client_ip(request_atual) if request_atual else None,
                user_agent=request_atual.META.get('HTTP_USER_AGENT', '') if request_atual else '',
                modulo=sender._meta.app_label,
                modelo=modelo_nome,
                objeto_id=objeto_id,
                objeto_repr=objeto_repr,
                descricao=f"Novo objeto criado: {objeto_repr}",
                dados_depois={
                    'pk': instance.pk,
                    'criado_em': instance._meta.get_field('created_at') and str(getattr(instance, 'created_at', '')) or timezone.now().isoformat()
                }
            )
        else:
            # Log de atualização
            cache_key = f"auditoria_pre_save_{sender.__name__}_{instance.pk}"
            dados_anteriores = cache.get(cache_key)

            if dados_anteriores:
                # Capturar dados atuais
                dados_atuais = {}
                for field_name in dados_anteriores.keys():
                    valor_atual = getattr(instance, field_name)
                    dados_atuais[field_name] = str(valor_atual) if valor_atual is not None else None

                auditoria_service.registrar_log(
                    acao=f"Atualizado {modelo_nome}",
                    tipo_operacao=LogAuditoria.TipoOperacao.UPDATE,
                    usuario=usuario_atual,
                    ip_address=auditoria_service._get_client_ip(request_atual) if request_atual else None,
                    user_agent=request_atual.META.get('HTTP_USER_AGENT', '') if request_atual else '',
                    modulo=sender._meta.app_label,
                    modelo=modelo_nome,
                    objeto_id=objeto_id,
                    objeto_repr=objeto_repr,
                    descricao=f"Objeto atualizado: {objeto_repr}",
                    dados_antes={k: v['antes'] for k, v in dados_anteriores.items()},
                    dados_depois=dados_atuais,
                    metadados={
                        'campos_alterados': list(dados_anteriores.keys())
                    }
                )

                # Limpar cache
                cache.delete(cache_key)

    except Exception:
        # Silenciar erros para não quebrar a operação principal
        pass


@receiver(post_delete)
def log_post_delete(sender, instance, **kwargs):
    """
    Registra operações de exclusão
    """
    # Ignorar modelos de auditoria para evitar recursão infinita
    if sender._meta.app_label == 'auditoria':
        return

    # Obter usuário atual do thread local
    usuario_atual = getattr(_thread_locals, 'user', None)
    request_atual = getattr(_thread_locals, 'request', None)

    if not usuario_atual:
        return

    try:
        modelo_nome = f"{sender._meta.app_label}.{sender.__name__}"
        objeto_id = str(instance.pk)
        objeto_repr = str(instance)[:255]

        # Capturar dados do objeto antes de excluir
        dados_objeto = {}
        for field in instance._meta.fields:
            field_name = field.name
            valor = getattr(instance, field_name)
            dados_objeto[field_name] = str(valor) if valor is not None else None

        auditoria_service.registrar_log(
            acao=f"Excluído {modelo_nome}",
            tipo_operacao=LogAuditoria.TipoOperacao.DELETE,
            usuario=usuario_atual,
            ip_address=auditoria_service._get_client_ip(request_atual) if request_atual else None,
            user_agent=request_atual.META.get('HTTP_USER_AGENT', '') if request_atual else '',
            modulo=sender._meta.app_label,
            modelo=modelo_nome,
            objeto_id=objeto_id,
            objeto_repr=objeto_repr,
            descricao=f"Objeto excluído: {objeto_repr}",
            dados_antes=dados_objeto,
            metadados={
                'excluido_em': timezone.now().isoformat()
            }
        )

    except Exception:
        # Silenciar erros para não quebrar a operação principal
        pass


# Middleware para capturar usuário e request atual
class AuditoriaMiddleware:
    """
    Middleware para capturar informações da requisição para auditoria
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Armazenar usuário e request no thread local
        _thread_locals.user = request.user if hasattr(request, 'user') else None
        _thread_locals.request = request

        # Registrar log de acesso se for usuário autenticado e não for página de admin
        if hasattr(request, 'user') and request.user.is_authenticated:
            # Não registrar logs para páginas do admin para evitar excesso
            if not request.path.startswith('/admin/'):
                try:
                    # Registrar acesso geral
                    auditoria_service.registrar_log(
                        acao=f"Acesso à rota: {request.path}",
                        tipo_operacao=LogAuditoria.TipoOperacao.VIEW,
                        usuario=request.user,
                        ip_address=auditoria_service._get_client_ip(request),
                        user_agent=request.META.get('HTTP_USER_AGENT', ''),
                        modulo=request.resolver_match.app_name if request.resolver_match else 'unknown',
                        descricao=f"Usuário acessou: {request.method} {request.path}",
                        metadados={
                            'method': request.method,
                            'path': request.path,
                            'query_params': dict(request.GET),
                            'content_type': request.content_type
                        }
                    )
                except Exception:
                    # Silenciar erros para não quebrar a requisição
                    pass

        response = self.get_response(request)

        # Limpar thread local
        _thread_locals.user = None
        _thread_locals.request = None

        return response


# Tarefa periódica para gerar estatísticas
def gerar_estatisticas_diarias():
    """
    Gera estatísticas diárias de auditoria
    """
    from django.db.models import Count

    try:
        hoje = timezone.now().date()
        ontens = hoje - timedelta(days=1)

        # Agrupar logs por tipo e nível
        logs_ontem = LogAuditoria.objects.filter(
            timestamp__date=ontens
        ).values(
            'tipo_operacao', 'nivel_severidade'
        ).annotate(
            total_registros=Count('id'),
            usuarios_unicos=Count('usuario', distinct=True),
            ip_unicos=Count('ip_address', distinct=True),
            falhas=Count('id', filter=Q(sucesso=False))
        )

        # Salvar estatísticas
        with transaction.atomic():
            for stat in logs_ontem:
                EstatisticaAuditoria.objects.update_or_create(
                    data=ontens,
                    tipo_operacao=stat['tipo_operacao'],
                    nivel_severidade=stat['nivel_severidade'],
                    defaults={
                        'total_registros': stat['total_registros'],
                        'usuarios_unicos': stat['usuarios_unicos'],
                        'ip_unicos': stat['ip_unicos'],
                        'falhas': stat['falhas']
                    }
                )

    except Exception as e:
        import logging
        logger = logging.getLogger('auditoria')
        logger.error(f"Erro ao gerar estatísticas diárias: {str(e)}")


# Tarefa periódica para limpeza de logs
def limpar_logs_antigos_tarefa():
    """
    Tarefa periódica para limpeza de logs antigos
    """
    try:
        total_removidos = auditoria_service.limpar_logs_antigos()

        import logging
        logger = logging.getLogger('auditoria')
        logger.info(f"Limpeza de logs concluída. {total_removidos} registros removidos.")

    except Exception as e:
        import logging
        logger = logging.getLogger('auditoria')
        logger.error(f"Erro na limpeza de logs: {str(e)}")
