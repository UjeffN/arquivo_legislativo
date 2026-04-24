"""
Views para seleção de pasta de destino - Simplificado
"""

import os
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.conf import settings
from django.db import transaction

from .models import Documento


@login_required
def selecionar_pasta(request):
    """View simplificada - redireciona direto para salvar"""
    
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
            
            # Salvar arquivo com estrutura profissional
            arquivo_base64 = request.session.get('arquivo_pdf_base64', '')
            if arquivo_base64:
                import base64
                
                try:
                    # Decodificar base64
                    if ',' in arquivo_base64:
                        arquivo_data = base64.b64decode(arquivo_base64.split(',')[1])
                    else:
                        arquivo_data = base64.b64decode(arquivo_base64)
                    
                    # Gerar nome único baseado em hash
                    hash_obj = hashlib.sha256()
                    hash_obj.update(arquivo_data)
                    hash_obj.update(str(time.time()).encode())
                    hash_obj.update(str(uuid.uuid4()).encode())
                    nome_unico = hash_obj.hexdigest()[:8] + '.pdf'
                    
                    # Gerar caminho profissional: documentos/YYYY/MM/
                    ano = data_documento.year
                    mes = data_documento.month
                    
                    caminho_relativo = f"documentos/{ano}/{mes:02d}/{nome_unico}"
                    caminho_completo = os.path.join(settings.MEDIA_ROOT, caminho_relativo)
                    
                    # Criar diretório se não existir
                    os.makedirs(os.path.dirname(caminho_completo), exist_ok=True)
                    
                    # Salvar arquivo
                    with open(caminho_completo, 'wb') as f:
                        f.write(arquivo_data)
                    
                    # Atualizar caminho no documento
                    documento.arquivo_pdf = caminho_relativo
                    documento.save()
                    
                    messages.success(request, f'Documento "{documento.nome}" salvo! Código: {nome_unico}')
                    
                except Exception as e:
                    messages.error(request, f'Erro ao salvar arquivo: {str(e)}')
                    return redirect('documentos:detalhe', documento_id=documento.id)
            
            # Registrar log
            LogAuditoria.objects.create(
                documento=documento,
                acao='CRIAÇÃO',
                descricao=f'Documento criado com estrutura profissional. Código: {nome_unico}',
                usuario=request.user
            )
            
            messages.success(request, f'Documento "{documento.nome}" arquivado com sucesso!')
            
            # Limpar sessão
            for key in ['dados_documento', 'dados_documento_confirmados', 'dados_documento_final', 'arquivo_pdf_base64']:
                if key in request.session:
                    del request.session[key]
            
            return redirect('documentos:detalhe', documento_id=documento.id)
            
    except Exception as e:
        messages.error(request, f'Erro ao salvar documento: {str(e)}')
        import traceback
        traceback.print_exc()
        return redirect('documentos:upload')
