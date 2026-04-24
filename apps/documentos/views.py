"""
Views do app Documentos
"""
import os
import tempfile
from datetime import datetime
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, Http404, HttpResponse
from django.core.files.storage import default_storage
from django.urls import reverse
from django.conf import settings
from django.db import transaction
from django.db import models
from django.db.models import Q
from django.core.paginator import Paginator

from .models import Documento, TipoDocumento, LogAuditoria
from apps.departamentos.models import Departamento
from apps.caixas.models import Caixa
from .forms import DocumentoOCRForm, DocumentoConfirmacaoForm, DocumentoEditForm
from services.ocr import ocr_processor
from services.caixa_service import caixa_manager

# Importar views do arquivo separado
from . import views_pasta as pasta_views


@login_required
def upload_documento(request):
    """View inicial de upload com processamento OCR"""
    
    # LIMPEZA SEGURA: Limpar apenas dados de documentos, mantendo autenticação
    path_info = request.path_info
    if path_info == '/documentos/upload/':
        # Se está acessando upload diretamente, limpar apenas dados específicos
        print("DEBUG: Limpando dados de documentos - upload direto")
        keys_to_remove = [
            'documento_editando', 
            'documento_editando_id', 
            'dados_documento', 
            'arquivo_pdf_base64',
            'dados_documento_confirmados'
        ]
        for key in keys_to_remove:
            request.session.pop(key, None)
        # NÃO usar request.session.clear() para manter login
    
    # Verificar se é uma edição
    documento_editando = request.session.get('documento_editando', False)
    documento_editando_id = request.session.get('documento_editando_id', None)
    print(f"DEBUG: documento_editando: {documento_editando}")
    print(f"DEBUG: documento_editando_id: {documento_editando_id}")
    print(f"DEBUG: Usuário logado: {request.user.is_authenticated}")
    
    if request.method == 'POST':
        form = DocumentoOCRForm(request.POST, request.FILES)
        
        if form.is_valid():
            try:
                with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as temp_file:
                    for chunk in request.FILES['arquivo_pdf'].chunks():
                        temp_file.write(chunk)
                    temp_path = temp_file.name
                
                # Extrair texto com OCR
                texto_extraido = ocr_processor.extrair_texto_pdf(temp_path)
                
                # Analisar documento
                informacoes = ocr_processor.analisar_documento(texto_extraido)
                
                # Se for edição, manter alguns dados originais
                if documento_editando:
                    # Buscar documento original
                    documento_original = Documento.objects.get(id=documento_editando_id)
                    
                    # Mesclar dados: manter alguns originais, usar OCR para outros
                    dados_iniciais = {
                        'nome': documento_original.nome,
                        'assunto': documento_original.assunto,
                        'tipo_documento': documento_original.tipo_documento,
                        'departamento': documento_original.departamento,
                        'numero_documento': documento_original.numero_documento,
                        'data_documento': documento_original.data_documento.strftime('%Y-%m-%d'),
                        'caixa': documento_original.caixa,
                        'palavra_chave': documento_original.palavra_chave,
                        'observacao': documento_original.observacao,
                        'texto_extraido': documento_original.texto_extraido,
                        'confianca_ocr': 0,  # Editando, não usa OCR
                        'ocr_preenchido': False,
                        'arquivo_temp_path': temp_path,
                        'arquivo_original_name': request.FILES['arquivo_pdf'].name,
                        'documento_editando_id': documento_editando_id
                    }
                else:
                    # Upload normal - usa OCR
                    dados_iniciais = {
                        'nome': _gerar_nome_documento(informacoes),
                        'assunto': informacoes.get('assunto', ''),
                        'numero_documento': informacoes.get('numero_documento', ''),
                        'data_documento': _converter_data_para_string(informacoes.get('data_documento')),
                        'texto_extraido': texto_extraido,
                        'confianca_ocr': informacoes.get('confianca', 0),
                        'ocr_preenchido': True,
                        'arquivo_temp_path': temp_path,
                        'arquivo_original_name': request.FILES['arquivo_pdf'].name
                    }
                    
                    # Mapear tipo de documento
                    if informacoes.get('tipo_documento'):
                        try:
                            tipo_doc = TipoDocumento.objects.get(nome__iexact=informacoes['tipo_documento'])
                            dados_iniciais['tipo_documento'] = tipo_doc.id
                        except TipoDocumento.DoesNotExist:
                            messages.warning(request, f"Tipo '{informacoes['tipo_documento']}' não encontrado. Selecione manualmente.")
                
                # Limpar arquivo temporário
                os.unlink(temp_path)
                
                # Redirecionar para confirmação
                request.session['dados_documento'] = dados_iniciais
                request.session['arquivo_pdf_base64'] = _arquivo_para_base64(request.FILES['arquivo_pdf'])
                
                return redirect('documentos:confirmar_upload')
                
            except Exception as e:
                messages.error(request, f'Erro ao processar arquivo: {str(e)}')
                if 'temp_path' in locals() and os.path.exists(temp_path):
                    os.unlink(temp_path)
        else:
            messages.error(request, 'Por favor, corrija os erros no formulário.')
    else:
        if documento_editando:
            # Se for edição, preencher com dados do documento original
            documento_original = Documento.objects.get(id=documento_editando_id)
            form = DocumentoOCRForm(initial={
                'nome': documento_original.nome,
                'assunto': documento_original.assunto,
                'tipo_documento': documento_original.tipo_documento,
                'departamento': documento_original.departamento,
                'numero_documento': documento_original.numero_documento,
                'data_documento': documento_original.data_documento,
                'caixa': documento_original.caixa,
                'palavra_chave': documento_original.palavra_chave,
                'observacao': documento_original.observacao
            })
            
            # Adicionar arquivo original se existir
            if documento_original.arquivo_pdf:
                form.fields['arquivo_pdf'].required = False
                form.fields['arquivo_pdf'].help_text = "Deixe em branco para manter o mesmo arquivo ou selecione um novo"
        else:
            form = DocumentoOCRForm()
    
    context = {
        'form': form,
        'titulo': 'Upload de Documento',
        'etapa': 'upload',
        'editando': documento_editando,
        'documento_original': Documento.objects.get(id=documento_editando_id) if documento_editando else None
    }
    
    return render(request, 'documentos/upload_documento.html', context)


@login_required
def confirmar_upload(request):
    """View de confirmação dos dados extraídos pelo OCR"""
    
    # Recuperar dados da sessão
    dados_documento = request.session.get('dados_documento', {})
    arquivo_base64 = request.session.get('arquivo_pdf_base64', '')
    documento_editando = request.session.get('documento_editando', False)
    documento_editando_id = request.session.get('documento_editando_id', None)
    
    if not dados_documento or not arquivo_base64:
        messages.error(request, 'Sessão expirada. Por favor, faça o upload novamente.')
        return redirect('documentos:upload')
    
    if request.method == 'POST':
        form = DocumentoConfirmacaoForm(request.POST)
        
        if form.is_valid():
            try:
                # Salvar dados confirmados na sessão
                dados_confirmados = form.cleaned_data.copy()
                
                # Converter objetos para tipos serializáveis
                if 'tipo_documento' in dados_confirmados and dados_confirmados['tipo_documento']:
                    dados_confirmados['tipo_documento'] = dados_confirmados['tipo_documento'].id
                
                if 'departamento' in dados_confirmados and dados_confirmados['departamento']:
                    dados_confirmados['departamento'] = dados_confirmados['departamento'].id
                
                if 'caixa' in dados_confirmados and dados_confirmados['caixa']:
                    dados_confirmados['caixa'] = dados_confirmados['caixa'].id
                
                # Converter data para string
                if 'data_documento' in dados_confirmados and dados_confirmados['data_documento']:
                    dados_confirmados['data_documento'] = dados_confirmados['data_documento'].isoformat()
                
                request.session['dados_documento_confirmados'] = dados_confirmados
                
                # Verificar se selecionou caixa ou pasta
                caixa_selecionada = form.cleaned_data.get('caixa')
                
                if caixa_selecionada:
                    # Se selecionou caixa, salvar diretamente
                    return redirect('documentos:salvar_com_caixa')
                else:
                    # Se não selecionou caixa, redirecionar para escolher pasta
                    return redirect('documentos:selecionar_pasta')
                    
            except Exception as e:
                messages.error(request, f'Erro ao processar confirmação: {str(e)}')
                import traceback
                traceback.print_exc()
    else:
        # Preencher formulário com dados da sessão
        form = DocumentoConfirmacaoForm(initial=dados_documento)
        
        # Adicionar arquivo base64 ao formulário se necessário
        form.fields['arquivo_pdf'].required = False
    
    return render(request, 'documentos/confirmar_upload.html', {
        'form': form,
        'dados_documento': dados_documento,
        'arquivo_preview': arquivo_base64,
        'confianca_ocr': dados_documento.get('confianca_ocr', 0),
        'arquivo_original': dados_documento.get('arquivo_original_name', 'N/A'),
        'editando': documento_editando,
        'documento_original': Documento.objects.get(id=documento_editando_id) if documento_editando else None
    })


@login_required
def salvar_com_caixa(request):
    """View para salvar documento em caixa selecionada"""
    
    # Recuperar dados confirmados
    dados_documento = request.session.get('dados_documento_confirmados', {})
    documento_editando = request.session.get('documento_editando', False)
    documento_editando_id = request.session.get('documento_editando_id', None)
    
    if not dados_documento:
        messages.error(request, 'Sessão expirada. Por favor, faça o upload novamente.')
        return redirect('documentos:upload')
    
    try:
        with transaction.atomic():
            # Converter IDs para objetos
            if 'tipo_documento' in dados_documento:
                tipo_documento = TipoDocumento.objects.get(id=dados_documento['tipo_documento'])
            else:
                tipo_documento = None
                
            if 'departamento' in dados_documento:
                departamento = Departamento.objects.get(id=dados_documento['departamento'])
            else:
                departamento = None
            
            caixa = None
            if 'caixa' in dados_documento and dados_documento['caixa']:
                caixa = Caixa.objects.get(id=dados_documento['caixa'])
            
            # Converter data string para objeto date
            from datetime import datetime
            data_documento = datetime.strptime(dados_documento['data_documento'], '%Y-%m-%d').date()
            
            if documento_editando:
                # EDIÇÃO: atualizar documento existente
                documento = Documento.objects.get(id=documento_editando_id)
                
                # Atualizar campos
                documento.nome = dados_documento['nome']
                documento.assunto = dados_documento['assunto']
                documento.numero_documento = dados_documento['numero_documento']
                documento.data_documento = data_documento
                documento.palavra_chave = dados_documento.get('palavra_chave', '')
                documento.observacao = dados_documento.get('observacao', '')
                documento.departamento = departamento
                documento.tipo_documento = tipo_documento
                documento.caixa = caixa
                
                # Se houver novo arquivo, atualizar
                arquivo_base64 = request.session.get('arquivo_pdf_base64', '')
                if arquivo_base64 and arquivo_base64 != request.session.get('arquivo_original_base64', ''):
                    # Salvar novo arquivo
                    arquivo_file = _base64_para_arquivo(arquivo_base64.split(',')[1], documento.arquivo_pdf.name)
                    documento.arquivo_pdf = arquivo_file
                
                documento.save()
                
                # Registrar log
                LogAuditoria.objects.create(
                    documento=documento,
                    usuario=request.user,
                    acao='EDIÇÃO',
                    descricao=f'Documento "{documento.nome}" atualizado com sucesso',
                    ip_address=_get_client_ip(request)
                )
                
                messages.success(request, f'Documento "{documento.nome}" atualizado com sucesso!')
                
                # Limpar sessão de edição
                request.session.pop('documento_editando', None)
                request.session.pop('documento_editando_id', None)
                
            else:
                # UPLOAD NOVO: criar novo documento
                documento = Documento.objects.create(
                    nome=dados_documento['nome'],
                    assunto=dados_documento['assunto'],
                    numero_documento=dados_documento['numero_documento'],
                    data_documento=data_documento,
                    texto_extraido=dados_documento.get('texto_extraido', ''),
                    ocr_processado=dados_documento.get('ocr_preenchido', False),
                    palavra_chave=dados_documento.get('palavra_chave', ''),
                    observacao=dados_documento.get('observacao', ''),
                    departamento=departamento,
                    tipo_documento=tipo_documento,
                    caixa=caixa,
                    arquivo_pdf=''  # Será atualizado depois
                )
                
                # Salvar arquivo PDF
                arquivo_base64 = request.session.get('arquivo_pdf_base64', '')
                if arquivo_base64:
                    nome_arquivo = f"{documento.numero_documento}_{documento.nome.replace(' ', '_')}.pdf"
                    arquivo_file = _base64_para_arquivo(arquivo_base64.split(',')[1], nome_arquivo)
                    documento.arquivo_pdf = arquivo_file
                    documento.save()
                
                # Registrar log
                LogAuditoria.objects.create(
                    documento=documento,
                    usuario=request.user,
                    acao='CRIAÇÃO',
                    descricao=f'Documento "{documento.nome}" criado com sucesso',
                    ip_address=_get_client_ip(request)
                )
                
                messages.success(request, f'Documento "{documento.nome}" salvo com sucesso!')
            
            # Limpar dados da sessão
            request.session.pop('dados_documento', None)
            request.session.pop('dados_documento_confirmados', None)
            request.session.pop('arquivo_pdf_base64', None)
            
            # Limpar flags de edição se for upload novo
            if not documento_editando:
                request.session.pop('documento_editando', None)
                request.session.pop('documento_editando_id', None)
            
            return redirect('documentos:detalhe', documento_id=documento.id)
            
    except Exception as e:
        messages.error(request, f'Erro ao salvar documento: {str(e)}')
        import traceback
        traceback.print_exc()
        return redirect('documentos:confirmar_upload')


@login_required
def editar_documento(request, documento_id):
    """View para editar documento - redireciona para confirmação com dados preenchidos"""
    
    documento = get_object_or_404(Documento, id=documento_id)
    
    # Registrar log de visualização
    LogAuditoria.objects.create(
        documento=documento,
        usuario=request.user,
        acao='EDITAR',
        descricao='Acesso à edição de documento',
        ip_address=_get_client_ip(request)
    )
    
    try:
        # Preparar dados para o formulário de confirmação
        dados_documento = {
            'nome': documento.nome,
            'assunto': documento.assunto,
            'tipo_documento': documento.tipo_documento.id if documento.tipo_documento else None,
            'departamento': documento.departamento.id if documento.departamento else None,
            'numero_documento': documento.numero_documento,
            'data_documento': documento.data_documento.strftime('%Y-%m-%d'),
            'caixa': documento.caixa.id if documento.caixa else None,
            'palavra_chave': documento.palavra_chave,
            'observacao': documento.observacao,
            'texto_extraido': documento.texto_extraido,
            'confianca_ocr': 0,  # Editando, não usa OCR
            'ocr_preenchido': False,
            'arquivo_original_name': documento.arquivo_pdf.name if documento.arquivo_pdf else '',
            'documento_editando_id': documento.id  # Flag para identificar edição
        }
        
        # Se o documento tem arquivo, adicionar à sessão
        if documento.arquivo_pdf:
            try:
                # Ler o arquivo existente
                with open(documento.arquivo_pdf.path, 'rb') as f:
                    arquivo_bytes = f.read()
                
                # Converter para base64
                import base64
                arquivo_base64 = base64.b64encode(arquivo_bytes).decode('utf-8')
                data_url = f"data:application/pdf;base64,{arquivo_base64}"
                
                # Salvar na sessão
                request.session['arquivo_pdf_base64'] = data_url
                
            except Exception as e:
                messages.warning(request, f'Não foi possível carregar o arquivo PDF: {str(e)}')
        
        # Salvar dados na sessão
        request.session['dados_documento'] = dados_documento
        request.session['documento_editando'] = True  # Flag para edição
        request.session['documento_editando_id'] = documento.id
        
        messages.info(request, f'Editando documento: {documento.nome}')
        # REDIRECIONAR DIRETAMENTE PARA CONFIRMAÇÃO
        return redirect('documentos:confirmar_upload')
        
    except Exception as e:
        messages.error(request, f'Erro ao preparar edição: {str(e)}')
        return redirect('documentos:detalhe', documento_id=documento.id)


@login_required
def detalhe_documento(request, documento_id):
    """View para detalhes do documento"""
    
    documento = get_object_or_404(Documento, id=documento_id)
    
    # Registrar log de visualização
    LogAuditoria.objects.create(
        documento=documento,
        usuario=request.user,
        acao='VISUALIZADO',
        descricao='Documento visualizado',
        ip_address=_get_client_ip(request)
    )
    
    context = {
        'documento': documento,
        'titulo': f'Detalhes do Documento: {documento}',
        'pode_editar': True,  # Verificar permissões
        'pode_excluir': True,  # Verificar permissões
    }
    
    return render(request, 'documentos/detalhe_documento.html', context)


@login_required
def listar_documentos(request):
    """View para listagem de documentos com filtros"""
    
    documentos = Documento.objects.select_related(
        'tipo_documento', 'departamento', 'caixa'
    ).order_by('-data_documento')
    
    # Filtros
    search = request.GET.get('search', '')
    tipo = request.GET.get('tipo', '')
    departamento = request.GET.get('departamento', '')
    caixa = request.GET.get('caixa', '')
    ano = request.GET.get('ano', '')
    
    if search:
        documentos = documentos.filter(
            models.Q(nome__icontains=search) |
            models.Q(assunto__icontains=search) |
            models.Q(numero_documento__icontains=search) |
            models.Q(palavra_chave__icontains=search)
        )
    
    if tipo:
        documentos = documentos.filter(tipo_documento_id=tipo)
    
    if departamento:
        documentos = documentos.filter(departamento_id=departamento)
    
    if caixa:
        documentos = documentos.filter(caixa_id=caixa)
    
    if ano:
        documentos = documentos.filter(ano_documento=ano)
    
    context = {
        'documentos': documentos,
        'titulo': 'Listagem de Documentos',
        'tipos_documento': TipoDocumento.objects.all(),
        'departamentos': Departamento.objects.all(),
        'caixas': Caixa.objects.all(),
        'filtros': {
            'search': search,
            'tipo': tipo,
            'departamento': departamento,
            'caixa': caixa,
            'ano': ano
        }
    }
    
    return render(request, 'documentos/listar_documentos.html', context)


@login_required
def download_documento(request, documento_id):
    """View para download do documento PDF"""
    
    documento = get_object_or_404(Documento, id=documento_id)
    
    if not documento.arquivo_pdf:
        raise Http404('Arquivo não encontrado')
    
    # Registrar log de download
    LogAuditoria.objects.create(
        documento=documento,
        usuario=request.user,
        acao='BAIXADO',
        descricao=f'Documento baixado: {documento.arquivo_pdf.name}',
        ip_address=_get_client_ip(request)
    )
    
    # Retornar arquivo
    response = HttpResponse(documento.arquivo_pdf.read(), content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{documento.numero_formatado}.pdf"'
    response['Content-Length'] = documento.arquivo_pdf.size
    
    return response


# Funções auxiliares
def _gerar_nome_documento(informacoes):
    """Gera nome do documento baseado nas informações extraídas"""
    tipo = informacoes.get('tipo_documento', 'Documento')
    numero = informacoes.get('numero_documento', '')
    ano = informacoes.get('ano_documento', '')
    
    if numero and ano:
        return f"{tipo} {numero}/{ano}"
    elif numero:
        return f"{tipo} {numero}"
    else:
        return tipo


def _converter_data_para_string(data_str):
    """Converte string de data para formato YYYY-MM-DD para armazenar na sessão"""
    if not data_str:
        return None
    
    try:
        # Format: DD/MM/YYYY
        if '/' in data_str:
            data_obj = datetime.strptime(data_str, '%d/%m/%Y').date()
            return data_obj.strftime('%Y-%m-%d')
        # Format: YYYY-MM-DD
        elif '-' in data_str:
            data_obj = datetime.strptime(data_str, '%Y-%m-%d').date()
            return data_obj.strftime('%Y-%m-%d')
    except ValueError:
        pass
    
    return None


def _converter_data(data_str):
    """Converte string de data para objeto date"""
    if not data_str:
        return None
    
    try:
        # Format: DD/MM/YYYY
        if '/' in data_str:
            return datetime.strptime(data_str, '%d/%m/%Y').date()
        # Format: YYYY-MM-DD
        elif '-' in data_str:
            return datetime.strptime(data_str, '%Y-%m-%d').date()
    except ValueError:
        pass
    
    return None


def _arquivo_para_base64(arquivo):
    """Converte arquivo para base64 com data URL"""
    import base64
    
    # Ler arquivo em chunks
    chunks = []
    for chunk in arquivo.chunks():
        chunks.append(chunk)
    
    # Converter para base64
    arquivo_bytes = b''.join(chunks)
    arquivo_base64 = base64.b64encode(arquivo_bytes).decode('utf-8')
    
    # Adicionar prefixo data URL
    data_url = f"data:application/pdf;base64,{arquivo_base64}"
    
    return data_url


def _base64_para_arquivo(arquivo_base64, nome_original):
    """Converte base64 para arquivo Django"""
    import base64
    from django.core.files.base import ContentFile
    
    # Decodificar base64
    arquivo_bytes = base64.b64decode(arquivo_base64)
    
    # Criar arquivo Django
    arquivo = ContentFile(arquivo_bytes, name=nome_original)
    
    return arquivo


def _get_client_ip(request):
    """Obtém IP do cliente"""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip


@login_required
def departamento_autocomplete(request):
    """View autocomplete para departamentos - permite busca por nome ou sigla"""
    term = request.GET.get('term', '')
    
    if len(term) < 2:
        return JsonResponse({'results': []})
    
    departamentos = Departamento.objects.filter(ativo=True).filter(
        models.Q(sigla__icontains=term) | 
        models.Q(nome__icontains=term)
    )[:10]
    
    results = []
    for depto in departamentos:
        results.append({
            'id': depto.id,
            'text': f"{depto.sigla} - {depto.nome}",
            'sigla': depto.sigla,
            'nome': depto.nome
        })
    
    return JsonResponse({'results': results})


@login_required
def pesquisar_documentos(request):
    """View para pesquisar documentos por texto extraído via OCR"""
    
    query = request.GET.get('q', '').strip()
    documentos = Documento.objects.all()
    
    if query:
        documentos = documentos.filter(
            Q(texto_extraido__icontains=query) |
            Q(nome__icontains=query) |
            Q(numero_documento__icontains=query) |
            Q(tipo_documento__nome__icontains=query)
        ).select_related('tipo_documento', 'departamento', 'caixa')
    
    # Paginação
    paginator = Paginator(documentos, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'titulo': 'Pesquisa de Documentos',
        'documentos': page_obj,
        'query': query,
        'total_resultados': documentos.count() if query else 0,
    }
    
    return render(request, 'documentos/pesquisar.html', context)
