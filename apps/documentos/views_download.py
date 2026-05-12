"""
Views de Download em Lote - Sistema de Arquivo Digital
Implementação profissional com progress bar, validações e tratamento de erros
"""

import os
import json
import time
import logging
from pathlib import Path
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse, Http404, FileResponse
from django.core.exceptions import PermissionDenied
from django.views.decorators.http import require_http_methods
from django.core.cache import cache
from django.core import signing
from django.urls import reverse

from .models import Documento, LogAuditoria
from .services import DownloadLoteService

logger = logging.getLogger(__name__)
DOWNLOAD_TOKEN_SALT = 'documentos.download.zip'
DOWNLOAD_TOKEN_MAX_AGE = 3600  # 1 hora


class TimeoutError(Exception):
    """Exceção personalizada para timeout de processamento"""
    pass


def _require_perm(request, perm):
    if not request.user.has_perm(perm):
        raise PermissionDenied


def _gerar_download_token(nome_zip, user_id):
    return signing.dumps({'zip': nome_zip, 'uid': user_id}, salt=DOWNLOAD_TOKEN_SALT)


def _ler_download_token(token):
    return signing.loads(token, salt=DOWNLOAD_TOKEN_SALT, max_age=DOWNLOAD_TOKEN_MAX_AGE)


def _validar_nome_zip(nome_zip):
    if not nome_zip or Path(nome_zip).name != nome_zip or not nome_zip.lower().endswith('.zip'):
        raise PermissionDenied


class AutoDeleteFileResponse(FileResponse):
    """FileResponse com remoção opcional do arquivo ao finalizar a resposta."""

    def __init__(self, *args, delete_path=None, **kwargs):
        self._delete_path = delete_path
        super().__init__(*args, **kwargs)

    def close(self):
        try:
            super().close()
        finally:
            if self._delete_path and os.path.exists(self._delete_path):
                try:
                    os.unlink(self._delete_path)
                except OSError:
                    logger.warning(
                        'Falha ao remover ZIP temporário após download: %s',
                        self._delete_path,
                        exc_info=True,
                    )


class DownloadProcess:
    """Classe para gerenciar processo de download com timeout"""

    def __init__(self, request):
        self.request = request
        self.usuario = request.user
        self.start_time = time.time()
        self.timeout = 300  # 5 minutos
        self.download_service = DownloadLoteService()

    def _check_timeout(self):
        """Verifica se o timeout foi atingido"""
        if time.time() - self.start_time > self.timeout:
            raise TimeoutError("Tempo limite de processamento excedido")

    def processar_download_lote(self, ids_documentos, nome_arquivo=None):
        """
        Processa download em lote com validações e tratamento de erros

        Args:
            ids_documentos: Lista de IDs dos documentos
            nome_arquivo: Nome personalizado para o arquivo ZIP

        Returns:
            dict: Resultado do processamento
        """
        try:
            # Validar IDs
            if not ids_documentos:
                return {
                    'sucesso': False,
                    'erro': 'Nenhum documento selecionado',
                    'erros': ['Nenhum documento selecionado']
                }

            # Buscar documentos com validação de permissões
            documentos = Documento.objects.filter(id__in=ids_documentos).select_related(
                'tipo_documento', 'departamento', 'caixa'
            )

            if not documentos:
                return {
                    'sucesso': False,
                    'erro': 'Nenhum documento encontrado',
                    'erros': ['Nenhum documento encontrado']
                }

            # Verificar timeout
            self._check_timeout()

            # Processar download
            stats = self.download_service.criar_zip_documentos(
                documentos,
                nome_arquivo,
                self.usuario
            )

            # Verificar timeout
            self._check_timeout()

            # Registrar logs de auditoria
            self._registrar_logs_auditoria(documentos, stats)

            return stats

        except TimeoutError as e:
            return {
                'sucesso': False,
                'erro': str(e),
                'erros': [str(e)]
            }
        except Exception as e:
            return {
                'sucesso': False,
                'erro': f'Erro no processamento: {str(e)}',
                'erros': [str(e)]
            }

    def _registrar_logs_auditoria(self, documentos, stats):
        """Registra logs de auditoria para o download"""
        try:
            for documento in documentos:
                LogAuditoria.objects.create(
                    documento=documento,
                    usuario=self.usuario,
                    acao=LogAuditoria.Acao.BAIXADO_LOTE,
                    descricao=f'Download em lote: {stats.get("nome_zip", "desconhecido")}',
                    ip_address=self._get_client_ip()
                )
        except Exception:
            pass  # Não falhar o download se o log falhar

    def _get_client_ip(self):
        """Obtém IP do cliente"""
        x_forwarded_for = self.request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = self.request.META.get('REMOTE_ADDR')
        return ip or '0.0.0.0'


@login_required
@require_http_methods(["GET", "POST"])
def download_lote_avancado(request):
    """
    View principal para download em lote com interface avançada
    """
    _require_perm(request, 'documentos.view_documento')
    if request.method == 'POST':
        return _processar_download_post(request)
    else:
        return _exibir_interface_download(request)


def _processar_download_post(request):
    """Processa requisição POST de download"""
    try:
        # Obter dados da requisição
        data = json.loads(request.body) if request.content_type == 'application/json' else request.POST

        ids_documentos = data.get('ids_documentos', [])
        nome_arquivo = data.get('nome_arquivo', 'documentos_selecionados')

        # Validar entrada
        if not ids_documentos:
            return JsonResponse({
                'sucesso': False,
                'erro': 'Nenhum documento selecionado',
                'erros': ['Nenhum documento selecionado']
            })

        # Iniciar processamento
        processo = DownloadProcess(request)

        # Processar em background (simulado com cache)
        cache_key = f"download_progress_{request.user.id}_{int(time.time())}"

        # Status inicial
        cache.set(cache_key, {
            'status': 'processing',
            'progress': 0,
            'message': 'Iniciando processamento...',
            'total_documentos': len(ids_documentos)
        }, timeout=600)  # 10 minutos

        # Processar assincronamente (simulação)
        try:
            stats = processo.processar_download_lote(ids_documentos, nome_arquivo)

            # Atualizar cache com resultado
            cache.set(cache_key, {
                'status': 'completed' if stats['sucesso'] else 'error',
                'progress': 100,
                'message': 'Processamento concluído' if stats['sucesso'] else 'Erro no processamento',
                'stats': stats,
                'download_url': (
                    reverse(
                        'documentos:download_arquivo_zip',
                        args=[_gerar_download_token(stats['nome_zip'], request.user.id)],
                    ) if stats['sucesso'] else None
                )
            }, timeout=600)

            return JsonResponse({
                'sucesso': True,
                'cache_key': cache_key,
                'message': 'Processamento iniciado'
            })

        except Exception as e:
            cache.set(cache_key, {
                'status': 'error',
                'progress': 0,
                'message': f'Erro: {str(e)}',
                'stats': None
            }, timeout=600)

            return JsonResponse({
                'sucesso': False,
                'erro': str(e)
            })

    except json.JSONDecodeError:
        return JsonResponse({
            'sucesso': False,
            'erro': 'Dados inválidos'
        }, status=400)
    except Exception as e:
        return JsonResponse({
            'sucesso': False,
            'erro': f'Erro interno: {str(e)}'
        }, status=500)


def _exibir_interface_download(request):
    """Exibe interface de download"""
    # Obter IDs dos documentos da query string
    ids_documentos = request.GET.get('ids', '').split(',')
    ids_documentos = [int(id.strip()) for id in ids_documentos if id.strip().isdigit()]

    if not ids_documentos:
        messages.error(request, 'Nenhum documento selecionado')
        return redirect('documentos:listar')

    # Buscar documentos para preview
    documentos = Documento.objects.filter(id__in=ids_documentos).select_related(
        'tipo_documento', 'departamento'
    )

    # Gerar resumo
    download_service = DownloadLoteService()
    resumo = download_service.gerar_resumo_download(documentos)

    context = {
        'documentos': documentos,
        'resumo': resumo,
        'ids_documentos': ids_documentos,
        'titulo': 'Download em Lote de Documentos'
    }

    return render(request, 'documentos/download_lote_avancado.html', context)


@login_required
@require_http_methods(["GET"])
def download_progress(request, cache_key):
    """
    View AJAX para verificar progresso do download
    """
    _require_perm(request, 'documentos.view_documento')
    progress_data = cache.get(cache_key)

    if not progress_data:
        return JsonResponse({
            'status': 'not_found',
            'message': 'Processamento não encontrado'
        })

    return JsonResponse(progress_data)


@login_required
@require_http_methods(["GET"])
def download_arquivo_zip(request, token):
    """
    View para download do arquivo ZIP gerado
    """
    _require_perm(request, 'documentos.view_documento')
    try:
        payload = _ler_download_token(token)
        if payload.get('uid') != request.user.id:
            raise PermissionDenied
        nome_zip = payload.get('zip')
        _validar_nome_zip(nome_zip)

        download_service = DownloadLoteService()
        caminho_zip = (download_service.temp_dir / nome_zip).resolve()
        temp_dir_resolved = download_service.temp_dir.resolve()
        if temp_dir_resolved not in caminho_zip.parents:
            raise PermissionDenied
        if not caminho_zip.exists():
            raise Http404('Arquivo não encontrado')

        download_service.limpar_arquivos_temporarios(idade_horas=1)
        zip_file = open(caminho_zip, 'rb')
        return AutoDeleteFileResponse(
            zip_file,
            as_attachment=True,
            filename=nome_zip,
            content_type='application/zip',
            delete_path=str(caminho_zip),
        )

    except signing.SignatureExpired:
        raise PermissionDenied
    except signing.BadSignature:
        raise PermissionDenied
    except PermissionDenied:
        raise
    except Http404:
        raise
    except Exception as e:
        messages.error(request, f'Erro ao baixar arquivo: {str(e)}')
        return redirect('documentos:listar')


@login_required
@require_http_methods(["POST"])
def preview_download_lote_avancado(request):
    """
    View AJAX para preview avançado do download
    """
    _require_perm(request, 'documentos.view_documento')
    try:
        data = json.loads(request.body)
        ids_documentos = data.get('ids', [])

        if not ids_documentos:
            return JsonResponse({
                'sucesso': False,
                'erro': 'Nenhum documento selecionado'
            })

        # Buscar documentos
        documentos = Documento.objects.filter(id__in=ids_documentos).select_related(
            'tipo_documento', 'departamento'
        )

        # Gerar resumo detalhado
        download_service = DownloadLoteService()
        resumo = download_service.gerar_resumo_download(documentos)

        # Adicionar informações adicionais
        resumo['documentos_detalhes'] = [
            {
                'id': doc.id,
                'nome': doc.nome,
                'tipo': doc.tipo_documento.nome,
                'departamento': doc.departamento.nome if doc.departamento else 'Sem departamento',
                'data': doc.data_documento.strftime('%d/%m/%Y'),
                'tem_arquivo': bool(doc.arquivo_pdf)
            }
            for doc in documentos
        ]

        return JsonResponse({
            'sucesso': True,
            'resumo': resumo
        })

    except Exception as e:
        return JsonResponse({
            'sucesso': False,
            'erro': str(e)
        }, status=500)
