"""
Serviços de auditoria e logging para o Sistema de Arquivo Digital
"""

import json
import logging
import time
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone
from django.conf import settings
from django.http import HttpRequest
from .models import LogAuditoria, ConfiguracaoRetencao, AlertaSeguranca

User = get_user_model()


class AuditoriaService:
    """
    Serviço principal para gerenciamento de auditoria e logging
    """

    def __init__(self):
        self.logger = logging.getLogger('auditoria')

    def registrar_log(
        self,
        acao: str,
        tipo_operacao: str,
        nivel_severidade: str = LogAuditoria.NivelSeveridade.INFO,
        usuario: Optional[User] = None,
        ip_address: Optional[str] = None,
        user_agent: str = '',
        modulo: str = '',
        modelo: str = '',
        objeto_id: str = '',
        objeto_repr: str = '',
        descricao: str = '',
        dados_antes: Optional[Dict[str, Any]] = None,
        dados_depois: Optional[Dict[str, Any]] = None,
        metadados: Optional[Dict[str, Any]] = None,
        sessao_id: str = '',
        request_id: str = '',
        sucesso: bool = True,
        erro_msg: str = '',
        duracao_ms: Optional[int] = None
    ) -> LogAuditoria:
        """
        Registra um log de auditoria com todos os parâmetros estruturados
        """
        try:
            log = LogAuditoria.objects.create(
                acao=acao,
                tipo_operacao=tipo_operacao,
                nivel_severidade=nivel_severidade,
                usuario=usuario,
                ip_address=ip_address,
                user_agent=user_agent,
                modulo=modulo,
                modelo=modelo,
                objeto_id=objeto_id,
                objeto_repr=objeto_repr,
                descricao=descricao,
                dados_antes=dados_antes or {},
                dados_depois=dados_depois or {},
                metadados=metadados or {},
                sessao_id=sessao_id,
                request_id=request_id,
                sucesso=sucesso,
                erro_msg=erro_msg,
                duracao_ms=duracao_ms
            )

            # Verificar se gera alerta de segurança
            self._verificar_alertas(log)

            return log

        except Exception as e:
            self.logger.error(f"Erro ao registrar log de auditoria: {str(e)}")
            raise

    def registrar_autenticacao(
        self,
        usuario: Optional[User],
        ip_address: str,
        user_agent: str,
        sucesso: bool,
        erro_msg: str = ''
    ) -> LogAuditoria:
        """
        Registra tentativas de autenticação
        """
        return self.registrar_log(
            acao=f"Autenticação {'bem-sucedida' if sucesso else 'falha'}",
            tipo_operacao=LogAuditoria.TipoOperacao.AUTENTICACAO,
            nivel_severidade=LogAuditoria.NivelSeveridade.INFO if sucesso else LogAuditoria.NivelSeveridade.WARNING,
            usuario=usuario,
            ip_address=ip_address,
            user_agent=user_agent,
            modulo='auth',
            descricao=f"Tentativa de autenticação {'bem-sucedida' if sucesso else 'falha'} para usuário {usuario.get_username() if usuario else 'desconhecido'}",
            sucesso=sucesso,
            erro_msg=erro_msg
        )

    def registrar_operacao_crud(
        self,
        acao: str,
        tipo_operacao: str,
        usuario: User,
        request: HttpRequest,
        modelo: str,
        objeto_id: str,
        objeto_repr: str,
        dados_antes: Optional[Dict[str, Any]] = None,
        dados_depois: Optional[Dict[str, Any]] = None,
        sucesso: bool = True,
        erro_msg: str = ''
    ) -> LogAuditoria:
        """
        Registra operações CRUD
        """
        return self.registrar_log(
            acao=acao,
            tipo_operacao=tipo_operacao,
            usuario=usuario,
            ip_address=self._get_client_ip(request),
            user_agent=request.META.get('HTTP_USER_AGENT', ''),
            modulo=self._get_module_name(request),
            modelo=modelo,
            objeto_id=objeto_id,
            objeto_repr=objeto_repr,
            dados_antes=dados_antes,
            dados_depois=dados_depois,
            sessao_id=request.session.session_key or '',
            sucesso=sucesso,
            erro_msg=erro_msg
        )

    def registrar_acesso_recurso(
        self,
        usuario: User,
        request: HttpRequest,
        recurso: str,
        objeto_id: str = '',
        sucesso: bool = True,
        erro_msg: str = ''
    ) -> LogAuditoria:
        """
        Registra acesso a recursos sensíveis
        """
        return self.registrar_log(
            acao=f"Acesso ao recurso: {recurso}",
            tipo_operacao=LogAuditoria.TipoOperacao.VIEW,
            nivel_severidade=LogAuditoria.NivelSeveridade.INFO,
            usuario=usuario,
            ip_address=self._get_client_ip(request),
            user_agent=request.META.get('HTTP_USER_AGENT', ''),
            modulo=self._get_module_name(request),
            objeto_id=objeto_id,
            objeto_repr=recurso,
            descricao=f"Usuário acessou recurso sensível: {recurso}",
            sucesso=sucesso,
            erro_msg=erro_msg
        )

    def limpar_logs_antigos(self):
        """
        Limpa logs antigos baseado nas configurações de retenção
        """
        configs = ConfiguracaoRetencao.objects.filter(ativo=True)
        total_removidos = 0

        for config in configs:
            data_limite = timezone.now() - timedelta(days=config.dias_retencao)

            # Filtrar por nível de severidade mínimo
            niveis_acima = [
                choice[0] for choice in LogAuditoria.NivelSeveridade.choices
                if choice[0] >= config.nivel_severidade_minimo
            ]

            removidos, _ = LogAuditoria.objects.filter(
                tipo_operacao=config.tipo_operacao,
                nivel_severidade__in=niveis_acima,
                timestamp__lt=data_limite
            ).delete()

            total_removidos += removidos

        return total_removidos

    def exportar_logs(
        self,
        data_inicio: datetime,
        data_fim: datetime,
        tipo_operacao: Optional[str] = None,
        usuario: Optional[User] = None,
        nivel_severidade: Optional[str] = None,
        formato: str = 'json'
    ) -> str:
        """
        Exporta logs filtrados para CSV ou JSON
        """
        queryset = LogAuditoria.objects.filter(
            timestamp__gte=data_inicio,
            timestamp__lte=data_fim
        )

        if tipo_operacao:
            queryset = queryset.filter(tipo_operacao=tipo_operacao)

        if usuario:
            queryset = queryset.filter(usuario=usuario)

        if nivel_severidade:
            queryset = queryset.filter(nivel_severidade=nivel_severidade)

        if formato.lower() == 'csv':
            return self._exportar_csv(queryset)
        else:
            return self._exportar_json(queryset)

    def _verificar_alertas(self, log: LogAuditoria):
        """
        Verifica se o log deve gerar algum alerta de segurança
        """
        # Múltiplas falhas de login
        if (log.tipo_operacao == LogAuditoria.TipoOperacao.AUTENTICACAO and
            not log.sucesso):
            self._verificar_multiplas_falhas_login(log)

        # Acesso em horário incomum
        if log.timestamp.hour < 6 or log.timestamp.hour > 22:
            self._verificar_horario_incomum(log)

        # Atividade suspeita (muitas operações em pouco tempo)
        self._verificar_atividade_suspeita(log)

    def _verificar_multiplas_falhas_login(self, log: LogAuditoria):
        """
        Verifica múltiplas falhas de login do mesmo IP
        """
        uma_hora_atras = timezone.now() - timedelta(hours=1)

        falhas_recentes = LogAuditoria.objects.filter(
            tipo_operacao=LogAuditoria.TipoOperacao.AUTENTICACAO,
            ip_address=log.ip_address,
            sucesso=False,
            timestamp__gte=uma_hora_atras
        ).count()

        if falhas_recentes >= 5:  # Limiar configurável
            AlertaSeguranca.objects.create(
                tipo_alerta=AlertaSeguranca.TipoAlerta.MULTIPLAS_FALHAS_LOGIN,
                nivel_alerta=AlertaSeguranca.NivelAlerta.ALTO,
                ip_address=log.ip_address,
                titulo="Múltiplas falhas de login detectadas",
                descricao=f"Foram detectadas {falhas_recentes} tentativas de login falhas na última hora do IP {log.ip_address}",
                dados_adicionais={
                    'total_falhas': falhas_recentes,
                    'periodo_horas': 1
                }
            )

    def _verificar_horario_incomum(self, log: LogAuditoria):
        """
        Verifica acesso em horários incomuns
        """
        if log.usuario:
            # Verificar se é padrão do usuário acessar neste horário
            acessos_anteriores = LogAuditoria.objects.filter(
                usuario=log.usuario,
                timestamp__hour__gte=log.timestamp.hour - 1,
                timestamp__hour__lte=log.timestamp.hour + 1
            ).exclude(id=log.id).count()

            if acessos_anteriores < 3:  # Primeiro acesso ou raro neste horário
                AlertaSeguranca.objects.create(
                    tipo_alerta=AlertaSeguranca.TipoAlerta.HORARIO_INCOMUM,
                    nivel_alerta=AlertaSeguranca.NivelAlerta.MEDIO,
                    usuario=log.usuario,
                    ip_address=log.ip_address,
                    titulo="Acesso em horário incomum",
                    descricao=f"Usuário {log.usuario.get_username()} acessou o sistema às {log.timestamp.strftime('%H:%M')}",
                    dados_adicionais={
                        'hora_acesso': log.timestamp.hour,
                        'acessos_similares': acessos_anteriores
                    }
                )

    def _verificar_atividade_suspeita(self, log: LogAuditoria):
        """
        Verifica atividade suspeita (muitas operações em pouco tempo)
        """
        if not log.usuario:
            return

        cinco_minutos_atras = timezone.now() - timedelta(minutes=5)

        operacoes_recentes = LogAuditoria.objects.filter(
            usuario=log.usuario,
            timestamp__gte=cinco_minutos_atras
        ).exclude(id=log.id).count()

        if operacoes_recentes >= 50:  # Limiar configurável
            AlertaSeguranca.objects.create(
                tipo_alerta=AlertaSeguranca.TipoAlerta.ATIVIDADE_SUSPEITA,
                nivel_alerta=AlertaSeguranca.NivelAlerta.ALTO,
                usuario=log.usuario,
                ip_address=log.ip_address,
                titulo="Atividade suspeita detectada",
                descricao=f"Usuário {log.usuario.get_username()} realizou {operacoes_recentes} operações nos últimos 5 minutos",
                dados_adicionais={
                    'total_operacoes': operacoes_recentes,
                    'periodo_minutos': 5
                }
            )

    def _get_client_ip(self, request: HttpRequest) -> str:
        """
        Obtém o IP real do cliente considerando proxies
        """
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0].strip()
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip or '0.0.0.0'

    def _get_module_name(self, request: HttpRequest) -> str:
        """
        Obtém o nome do módulo baseado na URL
        """
        path = str(getattr(request, 'path', '') or '')
        parts = path.strip('/').split('/')
        return parts[0] if parts else 'unknown'

    def _exportar_csv(self, queryset) -> str:
        """
        Exporta logs para formato CSV
        """
        import csv
        import io

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

        return output.getvalue()

    def _exportar_json(self, queryset) -> str:
        """
        Exporta logs para formato JSON
        """
        logs_data = []

        for log in queryset:
            logs_data.append({
                'id': log.id,
                'timestamp': log.timestamp.isoformat(),
                'nivel_severidade': log.get_nivel_severidade_display(),
                'tipo_operacao': log.get_tipo_operacao_display(),
                'usuario': log.usuario.get_username() if log.usuario else log.nome_usuario,
                'ip_address': log.ip_address,
                'modulo': log.modulo,
                'modelo': log.modelo,
                'objeto_id': log.objeto_id,
                'objeto_repr': log.objeto_repr,
                'acao': log.acao,
                'descricao': log.descricao,
                'dados_antes': log.dados_antes,
                'dados_depois': log.dados_depois,
                'metadados': log.metadados,
                'sucesso': log.sucesso,
                'erro_msg': log.erro_msg,
                'duracao_ms': log.duracao_ms
            })

        return json.dumps(logs_data, indent=2, ensure_ascii=False)


class DecoradoresAuditoria:
    """
    Decoradores para automação de auditoria
    """

    @staticmethod
    def auditar_operacao(
        tipo_operacao: str,
        acao: str = '',
        nivel_severidade: str = LogAuditoria.NivelSeveridade.INFO
    ):
        """
        Decorador para auditar automaticamente operações de views
        """
        def decorator(view_func):
            def wrapper(request, *args, **kwargs):
                auditoria = AuditoriaService()
                inicio = time.time()

                try:
                    # Executar a view original
                    response = view_func(request, *args, **kwargs)
                    sucesso = True
                    erro_msg = ''
                except Exception as e:
                    sucesso = False
                    erro_msg = str(e)
                    raise
                finally:
                    # Registrar log
                    duracao_ms = int((time.time() - inicio) * 1000)

                    auditoria.registrar_log(
                        acao=acao or f"Operação {tipo_operacao}",
                        tipo_operacao=tipo_operacao,
                        nivel_severidade=nivel_severidade,
                        usuario=request.user if request.user.is_authenticated else None,
                        ip_address=auditoria._get_client_ip(request),
                        user_agent=request.META.get('HTTP_USER_AGENT', ''),
                        modulo=auditoria._get_module_name(request),
                        sucesso=sucesso,
                        erro_msg=erro_msg,
                        duracao_ms=duracao_ms
                    )

                return response

            return wrapper
        return decorator


# Instância global do serviço
auditoria_service = AuditoriaService()
