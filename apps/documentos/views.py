"""
Views do app Documentos
"""
import logging
import os
import re
import tempfile
from urllib.parse import urlencode
from datetime import datetime
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, Http404, FileResponse
from django.core.exceptions import PermissionDenied
from django.urls import reverse
from django.conf import settings
from django.db import transaction
from django.db import models
from django.db.models import Q
from django.views.decorators.clickjacking import xframe_options_exempt

from apps.core.pagination import paginate_with_show_all
from .models import Documento, TipoDocumento, LogAuditoria
from apps.departamentos.models import Departamento
from apps.caixas.models import Caixa
from .forms import DocumentoOCRForm, DocumentoConfirmacaoForm
from services.ocr import ocr_processor

logger = logging.getLogger(__name__)


def _require_perm(request, perm):
    if not request.user.has_perm(perm):
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
                        'Falha ao remover arquivo temporário após download: %s',
                        self._delete_path,
                        exc_info=True,
                    )


def _aplicar_busca_documentos(queryset, termo_busca):
    """Aplica busca textual em metadados + OCR, termo a termo."""
    if not termo_busca:
        return queryset

    termos = [t for t in re.split(r"\s+", termo_busca.strip()) if t]
    if not termos:
        return queryset

    # Cada termo precisa aparecer em algum campo, tornando a busca
    # mais flexível para textos longos extraídos por OCR.
    for termo in termos:
        queryset = queryset.filter(
            Q(texto_extraido__icontains=termo) |
            Q(nome__icontains=termo) |
            Q(assunto__icontains=termo) |
            Q(numero_documento__icontains=termo) |
            Q(palavra_chave__icontains=termo) |
            Q(observacao__icontains=termo) |
            Q(tipo_documento__nome__icontains=termo) |
            Q(departamento__nome__icontains=termo)
        )

    return queryset


@login_required
def upload_documento(request):
    """View inicial de upload com processamento OCR"""
    is_ajax = request.headers.get('x-requested-with') == 'XMLHttpRequest'
    documento_editando = request.session.get('documento_editando', False)
    documento_editando_id = request.session.get('documento_editando_id', None)
    if documento_editando:
        _require_perm(request, 'documentos.change_documento')
    else:
        _require_perm(request, 'documentos.add_documento')

    # LIMPEZA SEGURA: Limpar apenas dados de documentos, mantendo autenticação
    path_info = request.path_info
    if path_info == '/documentos/upload/':
        # Se está acessando upload diretamente, limpar apenas dados específicos
        logger.debug('Limpando dados temporários de documentos no upload direto.')
        keys_to_remove = [
            'documento_editando',
            'documento_editando_id',
            'dados_documento',
            'arquivo_pdf_base64',
            'arquivo_pdf_temp_path',
            'arquivo_pdf_documento_id',
            'dados_documento_confirmados'
        ]
        _cleanup_temp_upload(request.session.get('arquivo_pdf_temp_path'))
        for key in keys_to_remove:
            request.session.pop(key, None)
        # NÃO usar request.session.clear() para manter login

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
                            messages.warning(request, f"Categoria '{informacoes['tipo_documento']}' não encontrada. Selecione manualmente.")

                # Redirecionar para confirmação
                request.session['dados_documento'] = dados_iniciais
                _cleanup_temp_upload(request.session.get('arquivo_pdf_temp_path'))
                request.session['arquivo_pdf_temp_path'] = temp_path
                request.session['arquivo_pdf_documento_id'] = None

                if is_ajax:
                    return JsonResponse({
                        'success': True,
                        'redirect_url': reverse('documentos:confirmar_upload')
                    })
                return redirect('documentos:confirmar_upload')

            except Exception as e:
                logger.exception('Erro ao processar upload OCR.')
                if is_ajax:
                    return JsonResponse({
                        'success': False,
                        'message': f'Erro ao processar arquivo: {str(e)}'
                    }, status=400)
                messages.error(request, f'Erro ao processar arquivo: {str(e)}')
                if 'temp_path' in locals() and os.path.exists(temp_path):
                    os.unlink(temp_path)
        else:
            if is_ajax:
                return JsonResponse({
                    'success': False,
                    'message': 'Por favor, corrija os erros no formulário.',
                    'errors': form.errors.get_json_data()
                }, status=400)
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

    return render(request, 'documentos/upload.html', context)


@login_required
def confirmar_upload(request):
    """View de confirmação dos dados extraídos pelo OCR"""

    # Recuperar dados da sessão
    dados_documento = request.session.get('dados_documento', {})
    arquivo_temp_path = request.session.get('arquivo_pdf_temp_path', '')
    arquivo_documento_id = request.session.get('arquivo_pdf_documento_id')
    documento_editando = request.session.get('documento_editando', False)
    documento_editando_id = request.session.get('documento_editando_id', None)

    if documento_editando:
        _require_perm(request, 'documentos.change_documento')
    else:
        _require_perm(request, 'documentos.add_documento')

    arquivo_disponivel = bool(arquivo_temp_path) or bool(arquivo_documento_id)
    if not dados_documento or not arquivo_disponivel:
        messages.error(request, 'Sessão expirada. Por favor, faça o upload novamente.')
        return redirect('documentos:upload')

    if request.method == 'POST':
        form = DocumentoConfirmacaoForm(request.POST)

        if form.is_valid():
            try:
                # Salvar dados confirmados na sessão
                dados_confirmados = form.cleaned_data.copy()
                # Preserva dados técnicos do OCR, pois nem todos os campos
                # são renderizados/submetidos no formulário de confirmação.
                dados_confirmados['texto_extraido'] = dados_documento.get('texto_extraido', '')
                dados_confirmados['confianca_ocr'] = dados_documento.get('confianca_ocr', 0)
                dados_confirmados['arquivo_original_name'] = dados_documento.get('arquivo_original_name', '')
                dados_confirmados['ocr_preenchido'] = dados_documento.get('ocr_preenchido', False)

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
                logger.exception('Erro ao processar confirmação de upload.')
    else:
        # Preencher formulário com dados da sessão
        form = DocumentoConfirmacaoForm(initial=dados_documento)

        # Adicionar arquivo base64 ao formulário se necessário
        form.fields['arquivo_pdf'].required = False

    return render(request, 'documentos/confirmar_upload.html', {
        'form': form,
        'dados_documento': dados_documento,
        'arquivo_preview': reverse('documentos:preview_upload_pdf'),
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

    if documento_editando:
        _require_perm(request, 'documentos.change_documento')
    else:
        _require_perm(request, 'documentos.add_documento')

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

                # Se houver novo arquivo temporário, atualizar
                arquivo_temp_path = request.session.get('arquivo_pdf_temp_path', '')
                if arquivo_temp_path and os.path.exists(arquivo_temp_path):
                    arquivo_file = _arquivo_temp_para_content_file(
                        arquivo_temp_path,
                        os.path.basename(documento.arquivo_pdf.name) if documento.arquivo_pdf else f"{documento.numero_documento}.pdf"
                    )
                    documento.arquivo_pdf.save(arquivo_file.name, arquivo_file, save=False)

                documento.save()

                # Registrar log
                LogAuditoria.objects.create(
                    documento=documento,
                    usuario=request.user,
                    acao=LogAuditoria.Acao.ATUALIZADO,
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
                arquivo_temp_path = request.session.get('arquivo_pdf_temp_path', '')
                if arquivo_temp_path and os.path.exists(arquivo_temp_path):
                    nome_arquivo = f"{documento.numero_documento}_{documento.nome.replace(' ', '_')}.pdf"
                    arquivo_file = _arquivo_temp_para_content_file(arquivo_temp_path, nome_arquivo)
                    documento.arquivo_pdf.save(arquivo_file.name, arquivo_file, save=True)

                # Registrar log
                LogAuditoria.objects.create(
                    documento=documento,
                    usuario=request.user,
                    acao=LogAuditoria.Acao.CRIADO,
                    descricao=f'Documento "{documento.nome}" criado com sucesso',
                    ip_address=_get_client_ip(request)
                )

                messages.success(request, f'Documento "{documento.nome}" salvo com sucesso!')

            # Limpar dados da sessão
            request.session.pop('dados_documento', None)
            request.session.pop('dados_documento_confirmados', None)
            request.session.pop('arquivo_pdf_base64', None)
            request.session.pop('arquivo_pdf_documento_id', None)
            _cleanup_temp_upload(request.session.get('arquivo_pdf_temp_path'))
            request.session.pop('arquivo_pdf_temp_path', None)

            # Limpar flags de edição se for upload novo
            if not documento_editando:
                request.session.pop('documento_editando', None)
                request.session.pop('documento_editando_id', None)

            return redirect('documentos:detalhe', documento_id=documento.id)

    except Exception as e:
        messages.error(request, f'Erro ao salvar documento: {str(e)}')
        logger.exception('Erro ao salvar documento em caixa.')
        return redirect('documentos:confirmar_upload')


@login_required
def editar_documento(request, documento_id):
    """View para editar documento - redireciona para confirmação com dados preenchidos"""
    _require_perm(request, 'documentos.change_documento')

    documento = get_object_or_404(Documento, id=documento_id)

    # Registrar log de visualização
    LogAuditoria.objects.create(
        documento=documento,
        usuario=request.user,
        acao=LogAuditoria.Acao.EDITAR,
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

        # Referenciar arquivo existente para prévia sem carregar em base64 na sessão
        _cleanup_temp_upload(request.session.get('arquivo_pdf_temp_path'))
        request.session['arquivo_pdf_temp_path'] = ''
        request.session['arquivo_pdf_documento_id'] = documento.id

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
    _require_perm(request, 'documentos.view_documento')

    documento = get_object_or_404(Documento, id=documento_id)

    # Registrar log de visualização
    LogAuditoria.objects.create(
        documento=documento,
        usuario=request.user,
        acao=LogAuditoria.Acao.VISUALIZADO,
        descricao='Documento visualizado',
        ip_address=_get_client_ip(request)
    )

    context = {
        'documento': documento,
        'titulo': f'Detalhes do Documento: {documento}',
        'pode_editar': True,  # Verificar permissões
        'pode_excluir': True,  # Verificar permissões
    }

    return render(request, 'documentos/detalhe.html', context)


@login_required
def listar_documentos(request):
    """View para listagem de documentos com filtros"""
    _require_perm(request, 'documentos.view_documento')
    if request.method == 'POST':
        acao_lote = request.POST.get('acao_lote', '').strip()
        ids_selecionados = request.POST.getlist('selected_documentos')

        filtros_post = {
            'search': request.POST.get('search', '').strip(),
            'tipo': request.POST.get('tipo', '').strip(),
            'departamento': request.POST.get('departamento', '').strip(),
            'caixa': request.POST.get('caixa', '').strip(),
            'ano': request.POST.get('ano', '').strip(),
            'per_page': request.POST.get('per_page', '').strip(),
            'page': request.POST.get('page', '').strip(),
        }
        filtros_post = {k: v for k, v in filtros_post.items() if v}
        redirect_url = reverse('documentos:listar')
        if filtros_post:
            redirect_url = f"{redirect_url}?{urlencode(filtros_post)}"

        if not ids_selecionados:
            messages.error(request, 'Selecione ao menos um documento para executar a ação em lote.')
            return redirect(redirect_url)

        documentos_selecionados = list(
            Documento.objects.filter(id__in=ids_selecionados).select_related('caixa')
        )

        if not documentos_selecionados:
            messages.error(request, 'Nenhum documento válido foi encontrado para a ação solicitada.')
            return redirect(redirect_url)

        if acao_lote == 'excluir':
            _require_perm(request, 'documentos.delete_documento')
            total = len(documentos_selecionados)
            with transaction.atomic():
                for documento in documentos_selecionados:
                    LogAuditoria.objects.create(
                        documento=documento,
                        usuario=request.user,
                        acao=LogAuditoria.Acao.EXCLUIDO,
                        descricao='Documento excluído em ação em lote.',
                        ip_address=_get_client_ip(request)
                    )
                Documento.objects.filter(id__in=[d.id for d in documentos_selecionados]).delete()
            messages.success(request, f'{total} documento(s) excluído(s) com sucesso.')
            return redirect(redirect_url)

        if acao_lote == 'download_lote':
            _require_perm(request, 'documentos.view_documento')
            # Redirecionar para interface de download avançado
            ids_param = ','.join(map(str, ids_selecionados))
            return redirect(f'{reverse("documentos:download_lote_avancado")}?ids={ids_param}')

        if acao_lote not in ('adicionar_caixa', 'mover_caixa'):
            messages.error(request, 'Ação em lote inválida.')
            return redirect(redirect_url)

        _require_perm(request, 'documentos.change_documento')

        caixa_destino_id = request.POST.get('caixa_destino', '').strip()
        if not caixa_destino_id:
            messages.error(request, 'Selecione a caixa de destino para continuar.')
            return redirect(redirect_url)

        try:
            caixa_destino = Caixa.objects.get(id=caixa_destino_id)
        except Caixa.DoesNotExist:
            messages.error(request, 'A caixa de destino selecionada não existe.')
            return redirect(redirect_url)

        if acao_lote == 'adicionar_caixa':
            elegiveis = [d for d in documentos_selecionados if d.caixa_id is None]
            ignorados = len(documentos_selecionados) - len(elegiveis)
        else:
            elegiveis = [d for d in documentos_selecionados if d.caixa_id and d.caixa_id != caixa_destino.id]
            ignorados = len(documentos_selecionados) - len(elegiveis)

        vagas_disponiveis = max(caixa_destino.vagas_disponiveis, 0)
        documentos_para_atualizar = elegiveis[:vagas_disponiveis]
        sem_vaga = max(len(elegiveis) - len(documentos_para_atualizar), 0)

        atualizados = 0
        with transaction.atomic():
            for documento in documentos_para_atualizar:
                caixa_origem_nome = documento.caixa.nome if documento.caixa else 'SEM CAIXA'
                caixa_destino_nome = caixa_destino.nome
                documento.caixa = caixa_destino
                documento.save(update_fields=['caixa', 'atualizado_em'])
                LogAuditoria.objects.create(
                    documento=documento,
                    usuario=request.user,
                    acao=LogAuditoria.Acao.ATUALIZADO,
                    descricao=(
                        f'TRANSFERÊNCIA: "{caixa_origem_nome}" -> "{caixa_destino_nome}" '
                        f'(ação em lote: {acao_lote}).'
                    ),
                    ip_address=_get_client_ip(request)
                )
                atualizados += 1

        if atualizados:
            if acao_lote == 'adicionar_caixa':
                messages.success(
                    request,
                    f'{atualizados} documento(s) adicionado(s) à caixa "{caixa_destino.nome}".'
                )
            else:
                messages.success(
                    request,
                    f'{atualizados} documento(s) movido(s) para a caixa "{caixa_destino.nome}".'
                )
        if ignorados:
            if acao_lote == 'adicionar_caixa':
                messages.warning(
                    request,
                    f'{ignorados} documento(s) já possuíam caixa e foram ignorados.'
                )
            else:
                messages.warning(
                    request,
                    f'{ignorados} documento(s) não tinham caixa ou já estavam na caixa de destino e foram ignorados.'
                )
        if sem_vaga:
            messages.warning(
                request,
                f'{sem_vaga} documento(s) não foram processados por falta de capacidade na caixa de destino.'
            )

        return redirect(redirect_url)

    documentos_list = Documento.objects.select_related(
        'tipo_documento', 'departamento', 'caixa'
    ).order_by('-data_upload')  # Ordenar por upload para mostrar novos primeiro

    # Filtros
    search = request.GET.get('search', '')
    tipo = request.GET.get('tipo', '')
    departamento = request.GET.get('departamento', '')
    caixa = request.GET.get('caixa', '')
    ano = request.GET.get('ano', '')

    if search:
        documentos_list = _aplicar_busca_documentos(documentos_list, search)

    if tipo:
        documentos_list = documentos_list.filter(tipo_documento_id=tipo)

    if departamento:
        documentos_list = documentos_list.filter(departamento_id=departamento)

    if caixa:
        documentos_list = documentos_list.filter(caixa_id=caixa)

    if ano:
        documentos_list = documentos_list.filter(data_documento__year=ano)

    # Paginação
    documentos, pagination_state = paginate_with_show_all(
        request,
        documentos_list,
        default_per_page=20,
        allowed_per_page=(10, 20, 50, 100),
        item_label='documentos',
    )

    context = {
        'documentos': documentos,
        'titulo': 'Listagem de Documentos',
        'tipos_documento': TipoDocumento.objects.all(),
        'departamentos': Departamento.objects.all(),
        'caixas': Caixa.objects.all().order_by('nome', 'numero'),
        'historico_transferencias': LogAuditoria.objects.filter(
            descricao__startswith='TRANSFERÊNCIA:'
        ).select_related('documento', 'usuario')[:15],
        'filtros': {
            'search': search,
            'tipo': tipo,
            'departamento': departamento,
            'caixa': caixa,
            'ano': ano,
            'per_page': pagination_state['per_page'],
        },
        'pagination_state': pagination_state,
    }

    return render(request, 'documentos/listar.html', context)


@login_required
def download_documento(request, documento_id):
    """View para download do documento PDF"""
    _require_perm(request, 'documentos.view_documento')

    documento = get_object_or_404(Documento, id=documento_id)

    if not documento.arquivo_pdf:
        raise Http404('Arquivo não encontrado')

    # Registrar log de download
    LogAuditoria.objects.create(
        documento=documento,
        usuario=request.user,
        acao=LogAuditoria.Acao.BAIXADO,
        descricao=f'Documento baixado: {documento.arquivo_pdf.name}',
        ip_address=_get_client_ip(request)
    )

    # Retornar arquivo
    try:
        arquivo = documento.arquivo_pdf.open('rb')
    except Exception:
        raise Http404('Arquivo não encontrado')
    return FileResponse(
        arquivo,
        as_attachment=True,
        filename=f'{documento.numero_formatado}.pdf',
        content_type='application/pdf',
    )


# Funções auxiliares
def _gerar_nome_documento(informacoes):
    """Gera nome do documento baseado nas informações extraídas"""
    tipo = informacoes.get('tipo_documento') or 'Documento'
    numero = informacoes.get('numero_documento', '')
    ano = informacoes.get('ano_documento', '')

    if numero and ano:
        return f"{tipo} {numero}/{ano}".strip()
    if numero:
        return f"{tipo} {numero}".strip()
    return tipo.strip()


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


def _arquivo_temp_para_content_file(temp_path, nome_original):
    """Converte arquivo temporário do sistema para ContentFile Django"""
    from django.core.files.base import ContentFile
    with open(temp_path, 'rb') as temp_file:
        return ContentFile(temp_file.read(), name=nome_original)


def _cleanup_temp_upload(temp_path):
    """Remove arquivo temporário de upload, se existir"""
    if temp_path and os.path.exists(temp_path):
        try:
            os.unlink(temp_path)
        except OSError:
            pass


@login_required
@xframe_options_exempt
def preview_upload_pdf(request):
    """Retorna PDF para prévia na tela de confirmação sem base64 em sessão"""
    _require_perm(request, 'documentos.view_documento')
    temp_path = request.session.get('arquivo_pdf_temp_path')
    documento_id = request.session.get('arquivo_pdf_documento_id')

    if temp_path and os.path.exists(temp_path):
        return FileResponse(open(temp_path, 'rb'), content_type='application/pdf')

    if documento_id:
        documento = get_object_or_404(Documento, id=documento_id)
        if documento.arquivo_pdf:
            return FileResponse(documento.arquivo_pdf.open('rb'), content_type='application/pdf')

    raise Http404('Arquivo de prévia não encontrado.')


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
    """View autocomplete para departamentos por nome."""
    _require_perm(request, 'documentos.view_documento')
    term = request.GET.get('term', '')

    if len(term) < 2:
        return JsonResponse({'results': []})

    departamentos = Departamento.objects.filter(ativo=True, nome__icontains=term)[:10]

    results = []
    for depto in departamentos:
        results.append({
            'id': depto.id,
            'text': depto.nome,
            'nome': depto.nome
        })

    return JsonResponse({'results': results})


@login_required
def pesquisar_documentos(request):
    """View para pesquisar documentos por texto extraído via OCR e metadados"""
    _require_perm(request, 'documentos.view_documento')

    query = request.GET.get('q', '').strip()
    tipo_id = request.GET.get('tipo', '')
    depto_id = request.GET.get('departamento', '')
    data_inicio = request.GET.get('data_inicio', '')
    data_fim = request.GET.get('data_fim', '')

    documentos = Documento.objects.all().select_related('tipo_documento', 'departamento', 'caixa')

    if query:
        documentos = _aplicar_busca_documentos(documentos, query)

    if tipo_id:
        documentos = documentos.filter(tipo_documento_id=tipo_id)

    if depto_id:
        documentos = documentos.filter(departamento_id=depto_id)

    if data_inicio:
        documentos = documentos.filter(data_documento__gte=data_inicio)

    if data_fim:
        documentos = documentos.filter(data_documento__lte=data_fim)

    documentos = documentos.order_by('-data_upload')

    # Paginação
    page_obj, pagination_state = paginate_with_show_all(
        request,
        documentos,
        default_per_page=20,
        item_label='documentos',
    )

    context = {
        'titulo': 'Pesquisa de Documentos',
        'documentos': page_obj,
        'page_obj': page_obj,  # Template usa page_obj para paginação
        'is_paginated': page_obj.has_other_pages(),
        'pagination_state': pagination_state,
        'query': query,
        'total_resultados': documentos.count(),
        'tipos_documento': TipoDocumento.objects.all(),
        'departamentos': Departamento.objects.all(),
    }

    return render(request, 'documentos/pesquisar.html', context)


# Views de Download em Lote
@login_required
def download_lote_documentos(request):
    """View para download em lote de documentos"""
    _require_perm(request, 'documentos.view_documento')

    if request.method == 'POST':
        ids_selecionados = request.POST.getlist('selected_documentos')
        nome_arquivo = request.POST.get('nome_arquivo', 'documentos_selecionados')

        if not ids_selecionados:
            messages.error(request, 'Selecione ao menos um documento para download.')
            return redirect('documentos:listar')

        # Buscar documentos
        documentos = Documento.objects.filter(id__in=ids_selecionados)

        # Verificar se todos têm arquivos
        documentos_com_arquivo = []
        for doc in documentos:
            if doc.arquivo_pdf and os.path.exists(doc.arquivo_pdf.path):
                documentos_com_arquivo.append(doc)

        if not documentos_com_arquivo:
            messages.error(request, 'Nenhum arquivo encontrado para download.')
            return redirect('documentos:listar')

        # Criar ZIP
        from .services import DownloadLoteService
        download_service = DownloadLoteService()

        try:
            stats = download_service.criar_zip_documentos(
                documentos_com_arquivo,
                nome_arquivo,
                request.user,
            )
            if not stats.get('sucesso'):
                raise ValueError('Nenhum arquivo válido foi incluído no ZIP.')
            caminho_zip = stats['caminho_zip']
            nome_zip = stats['nome_zip']

            # Registrar log
            for doc in documentos_com_arquivo:
                LogAuditoria.objects.create(
                    documento=doc,
                    usuario=request.user,
                    acao=LogAuditoria.Acao.BAIXADO_LOTE,
                    descricao=f'Documento incluído em download em lote: {nome_zip}',
                    ip_address=_get_client_ip(request)
                )

            # Retornar arquivo ZIP
            zip_file = open(caminho_zip, 'rb')
            response = AutoDeleteFileResponse(
                zip_file,
                as_attachment=True,
                filename=nome_zip,
                content_type='application/zip',
                delete_path=caminho_zip,
            )

            messages.success(request, f'Download criado com {len(documentos_com_arquivo)} documentos!')

            return response

        except Exception as e:
            messages.error(request, f'Erro ao criar arquivo ZIP: {str(e)}')
            return redirect('documentos:listar')

    # Se for GET, mostrar página de download
    return render(request, 'documentos/download_lote.html')


@login_required
def preview_download_lote(request):
    """View AJAX para preview do download em lote"""
    _require_perm(request, 'documentos.view_documento')

    ids_selecionados = request.GET.getlist('ids[]')

    if not ids_selecionados:
        return JsonResponse({'error': 'Nenhum documento selecionado'})

    # Buscar documentos
    documentos = Documento.objects.filter(id__in=ids_selecionados)

    # Gerar resumo
    from .services import DownloadLoteService
    download_service = DownloadLoteService()
    resumo = download_service.gerar_resumo_download(documentos)

    return JsonResponse(resumo)


@login_required
def download_por_tipo(request, tipo_id):
    """View para download de todos os documentos de um tipo"""
    _require_perm(request, 'documentos.view_documento')

    tipo = get_object_or_404(TipoDocumento, id=tipo_id)
    documentos = Documento.objects.filter(tipo_documento=tipo)

    # Filtrar apenas documentos com arquivos
    documentos_com_arquivo = []
    for doc in documentos:
        if doc.arquivo_pdf and os.path.exists(doc.arquivo_pdf.path):
            documentos_com_arquivo.append(doc)

    if not documentos_com_arquivo:
        messages.error(request, f'Nenhum arquivo encontrado para a categoria "{tipo.nome}".')
        return redirect('documentos:listar')

    # Criar ZIP
    from .services import DownloadLoteService
    download_service = DownloadLoteService()

    try:
        stats = download_service.criar_zip_documentos(
            documentos_com_arquivo,
            f"documentos_{tipo.nome.lower().replace(' ', '_')}",
            request.user,
        )
        if not stats.get('sucesso'):
            raise ValueError('Nenhum arquivo válido foi incluído no ZIP.')
        caminho_zip = stats['caminho_zip']
        nome_zip = stats['nome_zip']

        # Registrar log
        for doc in documentos_com_arquivo:
            LogAuditoria.objects.create(
                documento=doc,
                usuario=request.user,
                acao=LogAuditoria.Acao.BAIXADO_POR_TIPO,
                descricao=f'Download por categoria "{tipo.nome}": {nome_zip}',
                ip_address=_get_client_ip(request)
            )

        # Retornar arquivo ZIP
        zip_file = open(caminho_zip, 'rb')
        response = AutoDeleteFileResponse(
            zip_file,
            as_attachment=True,
            filename=nome_zip,
            content_type='application/zip',
            delete_path=caminho_zip,
        )

        messages.success(request, f'Download criado com {len(documentos_com_arquivo)} documentos da categoria "{tipo.nome}"!')

        return response

    except Exception as e:
        messages.error(request, f'Erro ao criar arquivo ZIP: {str(e)}')
        return redirect('documentos:listar')


@login_required
def download_por_departamento(request, depto_id):
    """View para download de todos os documentos de um departamento"""
    _require_perm(request, 'documentos.view_documento')

    departamento = get_object_or_404(Departamento, id=depto_id)
    documentos = Documento.objects.filter(departamento=departamento)

    # Filtrar apenas documentos com arquivos
    documentos_com_arquivo = []
    for doc in documentos:
        if doc.arquivo_pdf and os.path.exists(doc.arquivo_pdf.path):
            documentos_com_arquivo.append(doc)

    if not documentos_com_arquivo:
        messages.error(request, f'Nenhum arquivo encontrado para o departamento "{departamento.nome}".')
        return redirect('documentos:listar')

    # Criar ZIP
    from .services import DownloadLoteService
    download_service = DownloadLoteService()

    try:
        stats = download_service.criar_zip_documentos(
            documentos_com_arquivo,
            f"documentos_{departamento.nome.lower().replace(' ', '_')}",
            request.user,
        )
        if not stats.get('sucesso'):
            raise ValueError('Nenhum arquivo válido foi incluído no ZIP.')
        caminho_zip = stats['caminho_zip']
        nome_zip = stats['nome_zip']

        # Registrar log
        for doc in documentos_com_arquivo:
            LogAuditoria.objects.create(
                documento=doc,
                usuario=request.user,
                acao=LogAuditoria.Acao.BAIXADO_POR_DEPARTAMENTO,
                descricao=f'Download por departamento "{departamento.nome}": {nome_zip}',
                ip_address=_get_client_ip(request)
            )

        # Retornar arquivo ZIP
        zip_file = open(caminho_zip, 'rb')
        response = AutoDeleteFileResponse(
            zip_file,
            as_attachment=True,
            filename=nome_zip,
            content_type='application/zip',
            delete_path=caminho_zip,
        )

        messages.success(request, f'Download criado com {len(documentos_com_arquivo)} documentos do departamento "{departamento.nome}"!')

        return response

    except Exception as e:
        messages.error(request, f'Erro ao criar arquivo ZIP: {str(e)}')
        return redirect('documentos:listar')
