"""
Views para gerenciamento de categorias de documentos.
"""
import logging

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render

from apps.core.pagination import paginate_with_show_all
from apps.auditoria.models import LogAuditoria as LogAuditoriaSistema
from apps.auditoria.services import auditoria_service

from .forms import CategoriaDocumentoForm
from .models import TipoDocumento

logger = logging.getLogger(__name__)


def _require_perm(request, perm):
    if not request.user.has_perm(perm):
        raise PermissionDenied


def _serializar_categoria(categoria):
    return {
        'id': categoria.id,
        'nome': categoria.nome,
        'descricao': categoria.descricao,
        'ativo': categoria.ativo,
        'criado_em': categoria.criado_em.isoformat() if categoria.criado_em else '',
    }


def _registrar_auditoria_categoria(request, categoria, tipo_operacao, acao, dados_antes=None, dados_depois=None):
    try:
        auditoria_service.registrar_operacao_crud(
            acao=acao,
            tipo_operacao=tipo_operacao,
            usuario=request.user,
            request=request,
            modelo='documentos.TipoDocumento',
            objeto_id=str(categoria.id),
            objeto_repr=str(categoria),
            dados_antes=dados_antes,
            dados_depois=dados_depois,
        )
    except Exception:
        logger.exception('Falha ao registrar auditoria da categoria %s.', categoria.id)


@login_required
def listar_categorias_documentos(request):
    _require_perm(request, 'documentos.view_tipodocumento')

    termo_busca = request.GET.get('q', '').strip()
    status = request.GET.get('status', '').strip()

    categorias = TipoDocumento.objects.annotate(
        total_documentos=Count('documento', distinct=True)
    ).order_by('nome')

    if termo_busca:
        categorias = categorias.filter(
            Q(nome__icontains=termo_busca) |
            Q(descricao__icontains=termo_busca)
        )

    if status == 'ativas':
        categorias = categorias.filter(ativo=True)
    elif status == 'inativas':
        categorias = categorias.filter(ativo=False)

    page_obj, pagination_state = paginate_with_show_all(
        request,
        categorias,
        default_per_page=20,
        item_label='categorias',
    )

    return render(request, 'documentos/categorias_listar.html', {
        'categorias': page_obj,
        'total_categorias': categorias.count(),
        'filtros': {
            'q': termo_busca,
            'status': status,
        },
        'pagination_state': pagination_state,
    })


@login_required
def criar_categoria_documento(request):
    _require_perm(request, 'documentos.add_tipodocumento')

    if request.method == 'POST':
        form = CategoriaDocumentoForm(request.POST)
        if form.is_valid():
            try:
                with transaction.atomic():
                    categoria = form.save()
                    _registrar_auditoria_categoria(
                        request,
                        categoria,
                        LogAuditoriaSistema.TipoOperacao.CREATE,
                        'Criacao de categoria de documento',
                        dados_depois=_serializar_categoria(categoria),
                    )
                messages.success(request, f'Categoria "{categoria.nome}" criada com sucesso.')
                return redirect('documentos:categorias_listar')
            except Exception:
                logger.exception('Erro ao criar categoria de documento.')
                messages.error(request, 'Nao foi possivel criar a categoria. Tente novamente.')
    else:
        form = CategoriaDocumentoForm(initial={'ativo': True})

    return render(request, 'documentos/categorias_form.html', {
        'form': form,
        'titulo': 'Nova Categoria de Documento',
        'subtitulo': 'Cadastre categorias para organizar a classificacao dos documentos.',
        'acao': 'Criar Categoria',
    })


@login_required
def editar_categoria_documento(request, categoria_id):
    _require_perm(request, 'documentos.change_tipodocumento')
    categoria = get_object_or_404(TipoDocumento, id=categoria_id)

    if request.method == 'POST':
        dados_antes = _serializar_categoria(categoria)
        form = CategoriaDocumentoForm(request.POST, instance=categoria)
        if form.is_valid():
            try:
                with transaction.atomic():
                    categoria = form.save()
                    _registrar_auditoria_categoria(
                        request,
                        categoria,
                        LogAuditoriaSistema.TipoOperacao.UPDATE,
                        'Atualizacao de categoria de documento',
                        dados_antes=dados_antes,
                        dados_depois=_serializar_categoria(categoria),
                    )
                messages.success(request, f'Categoria "{categoria.nome}" atualizada com sucesso.')
                return redirect('documentos:categorias_listar')
            except Exception:
                logger.exception('Erro ao atualizar categoria de documento %s.', categoria_id)
                messages.error(request, 'Nao foi possivel atualizar a categoria. Tente novamente.')
    else:
        form = CategoriaDocumentoForm(instance=categoria)

    return render(request, 'documentos/categorias_form.html', {
        'form': form,
        'categoria': categoria,
        'titulo': 'Editar Categoria de Documento',
        'subtitulo': 'Atualize as regras de classificacao da categoria selecionada.',
        'acao': 'Salvar Alteracoes',
    })


@login_required
def excluir_categoria_documento(request, categoria_id):
    _require_perm(request, 'documentos.delete_tipodocumento')
    categoria = get_object_or_404(
        TipoDocumento.objects.annotate(total_documentos=Count('documento', distinct=True)),
        id=categoria_id,
    )

    if request.method == 'POST':
        if not categoria.ativo:
            messages.info(request, f'A categoria "{categoria.nome}" ja esta inativa.')
            return redirect('documentos:categorias_listar')

        dados_antes = _serializar_categoria(categoria)
        try:
            with transaction.atomic():
                categoria.ativo = False
                categoria.save(update_fields=['ativo'])
                _registrar_auditoria_categoria(
                    request,
                    categoria,
                    LogAuditoriaSistema.TipoOperacao.DELETE,
                    'Inativacao de categoria de documento',
                    dados_antes=dados_antes,
                    dados_depois=_serializar_categoria(categoria),
                )
            messages.success(
                request,
                (
                    f'Categoria "{categoria.nome}" inativada com sucesso. '
                    f'Os {categoria.total_documentos} documento(s) vinculados foram preservados.'
                ),
            )
            return redirect('documentos:categorias_listar')
        except Exception:
            logger.exception('Erro ao inativar categoria de documento %s.', categoria_id)
            messages.error(request, 'Nao foi possivel inativar a categoria. Tente novamente.')
            return redirect('documentos:categorias_listar')

    return render(request, 'documentos/categorias_confirmar_exclusao.html', {
        'categoria': categoria,
        'documentos_afetados': categoria.total_documentos,
    })
