"""
Views para seleção de pasta de destino - Simplificado
"""

import logging
import os
from django.shortcuts import redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.core.files.base import ContentFile

from .models import Documento
from services.caixa_service import caixa_manager

logger = logging.getLogger(__name__)


def _require_perm(request, perm):
    if not request.user.has_perm(perm):
        raise PermissionDenied


@login_required
def selecionar_pasta(request):
    """View simplificada - redireciona direto para salvar"""
    _require_perm(request, 'documentos.add_documento')

    # Recuperar dados da sessão
    dados_documento = request.session.get('dados_documento_confirmados', {})

    if not dados_documento:
        messages.error(request, 'Sessão expirada. Por favor, faça o upload novamente.')
        return redirect('documentos:upload')

    # Passar direto para salvar final com estrutura profissional
    request.session['dados_documento_final'] = dados_documento

    messages.info(request, 'Usando estrutura profissional de armazenamento...')
    return redirect('documentos:salvar_final')


@login_required
def salvar_final(request):
    """View final para salvar o documento com estrutura profissional"""
    _require_perm(request, 'documentos.add_documento')

    # Importar modelos necessários
    from apps.documentos.models import LogAuditoria
    from apps.departamentos.models import Departamento
    from apps.documentos.models import TipoDocumento
    import hashlib
    import uuid
    import time

    # Recuperar dados finais
    dados_documento = request.session.get('dados_documento_final', {})

    if not dados_documento:
        messages.error(request, 'Sessão expirada. Por favor, faça o upload novamente.')
        return redirect('documentos:upload')

    try:
        with transaction.atomic():
            # Converter IDs para instâncias dos modelos
            depto_id = dados_documento.get('departamento')
            tipo_id = dados_documento.get('tipo_documento')
            caixa_id = dados_documento.get('caixa')

            # Buscar instâncias
            departamento = Departamento.objects.get(id=depto_id) if depto_id else None
            tipo_documento = TipoDocumento.objects.get(id=tipo_id) if tipo_id else None
            caixa = caixa_manager.get_caixa_by_id(caixa_id) if caixa_id else None

            # Converter data string para objeto date
            from datetime import datetime
            data_documento = datetime.strptime(dados_documento['data_documento'], '%Y-%m-%d').date()

            # Criar documento
            documento = Documento.objects.create(
                nome=dados_documento['nome'],
                assunto=dados_documento['assunto'],
                numero_documento=dados_documento['numero_documento'],
                data_documento=data_documento,
                texto_extraido=dados_documento.get('texto_extraido', ''),
                ocr_processado=True,
                palavra_chave=dados_documento.get('palavra_chave', ''),
                observacao=dados_documento.get('observacao', ''),
                departamento=departamento,
                tipo_documento=tipo_documento,
                caixa=caixa,
                arquivo_pdf=''  # Será atualizado depois
            )

            # Salvar arquivo com estrutura profissional (sem base64 em sessão)
            arquivo_temp_path = request.session.get('arquivo_pdf_temp_path', '')
            nome_unico = ''
            if arquivo_temp_path and os.path.exists(arquivo_temp_path):
                try:
                    with open(arquivo_temp_path, 'rb') as temp_file:
                        arquivo_data = temp_file.read()

                    # Gerar nome único baseado em hash
                    hash_obj = hashlib.sha256()
                    hash_obj.update(arquivo_data)
                    hash_obj.update(str(time.time()).encode())
                    hash_obj.update(str(uuid.uuid4()).encode())
                    nome_unico = hash_obj.hexdigest()[:8] + '.pdf'

                    ano = data_documento.year
                    mes = data_documento.month
                    caminho_relativo = f"documentos/{ano}/{mes:02d}/{nome_unico}"

                    documento.arquivo_pdf.save(
                        caminho_relativo,
                        ContentFile(arquivo_data),
                        save=True
                    )

                    messages.success(request, f'Documento "{documento.nome}" salvo! Código: {nome_unico}')
                except Exception as e:
                    messages.error(request, f'Erro ao salvar arquivo: {str(e)}')
                    return redirect('documentos:detalhe', documento_id=documento.id)

            # Registrar log
            LogAuditoria.objects.create(
                documento=documento,
                acao=LogAuditoria.Acao.CRIADO,
                descricao=f'Documento criado com estrutura profissional. Código: {nome_unico}',
                usuario=request.user
            )

            messages.success(request, f'Documento "{documento.nome}" arquivado com sucesso!')

            # Limpar sessão
            arquivo_temp_path = request.session.get('arquivo_pdf_temp_path')
            if arquivo_temp_path and os.path.exists(arquivo_temp_path):
                try:
                    os.unlink(arquivo_temp_path)
                except OSError:
                    pass

            for key in ['dados_documento', 'dados_documento_confirmados', 'dados_documento_final', 'arquivo_pdf_base64', 'arquivo_pdf_temp_path', 'arquivo_pdf_documento_id']:
                if key in request.session:
                    del request.session[key]

            return redirect('documentos:detalhe', documento_id=documento.id)

    except Exception as e:
        messages.error(request, f'Erro ao salvar documento: {str(e)}')
        logger.exception('Erro ao salvar documento na view de pasta final.')
        return redirect('documentos:upload')
