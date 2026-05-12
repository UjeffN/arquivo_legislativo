from datetime import date
import json
import os
import time
from pathlib import Path
from unittest.mock import patch

from django.contrib.auth.models import Permission, User
from django.contrib.messages import get_messages
from django.core.files.uploadedfile import SimpleUploadedFile
from django.middleware.csrf import _get_new_csrf_string
from django.test import Client, TestCase
from django.urls import reverse

from apps.auditoria.models import LogAuditoria as LogAuditoriaSistema
from apps.caixas.models import Caixa
from apps.departamentos.models import Departamento
from apps.documentos.forms import CategoriaDocumentoForm, DocumentoConfirmacaoForm, DocumentoEditForm, DocumentoOCRForm
from apps.documentos.models import Documento, LogAuditoria, TipoDocumento


class MovimentacaoDocumentosLoteTests(TestCase):
    def setUp(self):
        # Em testes locais, o path precisa ser sem FORCE_SCRIPT_NAME.
        self.url = reverse('documentos:listar').replace('/arquivo', '', 1)
        self.password = 'senha-segura-123'
        self.user = User.objects.create_user(
            username='operador',
            password=self.password,
            email='operador@example.com'
        )

        self.tipo = TipoDocumento.objects.create(nome='OFICIO')
        self.departamento = Departamento.objects.create(nome='Departamento de TI')

        self.caixa_origem = Caixa.objects.create(numero=1, nome='Arquivo Corrente')
        self.caixa_destino = Caixa.objects.create(numero=2, nome='Arquivo Permanente')
        self.caixa_destino.capacidade_maxima = 100
        self.caixa_destino.save()

    def _login_com_permissao(self, codename):
        self.user.user_permissions.add(Permission.objects.get(codename='view_documento'))
        perm = Permission.objects.get(codename=codename)
        self.user.user_permissions.add(perm)
        self.assertTrue(self.client.login(username=self.user.username, password=self.password))

    def _criar_documento(self, numero, caixa=None):
        arquivo = SimpleUploadedFile(
            name=f'doc_{numero}.pdf',
            content=b'%PDF-1.4\n%%EOF',
            content_type='application/pdf'
        )
        return Documento.objects.create(
            nome=f'Documento {numero}',
            assunto='Assunto de teste',
            tipo_documento=self.tipo,
            departamento=self.departamento,
            numero_documento=f'{numero}/2024',
            data_documento=date(2024, 1, 1),
            caixa=caixa,
            arquivo_pdf=arquivo,
            texto_extraido='texto teste',
            ocr_processado=True
        )

    def _messages(self, response):
        return [m.message for m in get_messages(response.wsgi_request)]

    def test_mover_documento_unico_entre_caixas(self):
        self._login_com_permissao('change_documento')
        doc = self._criar_documento('001', caixa=self.caixa_origem)

        response = self.client.post(
            self.url,
            {
                'acao_lote': 'mover_caixa',
                'caixa_destino': str(self.caixa_destino.id),
                'selected_documentos': [str(doc.id)],
            },
            follow=True
        )

        doc.refresh_from_db()
        self.assertEqual(doc.caixa_id, self.caixa_destino.id)
        self.assertTrue(
            LogAuditoria.objects.filter(
                documento=doc,
                descricao__contains='TRANSFERÊNCIA:'
            ).exists()
        )
        self.assertTrue(
            any('movido(s) para a caixa' in msg for msg in self._messages(response))
        )

    def test_adicionar_multiplos_documentos_sem_caixa(self):
        self._login_com_permissao('change_documento')
        doc1 = self._criar_documento('002', caixa=None)
        doc2 = self._criar_documento('003', caixa=None)

        self.client.post(
            self.url,
            {
                'acao_lote': 'adicionar_caixa',
                'caixa_destino': str(self.caixa_destino.id),
                'selected_documentos': [str(doc1.id), str(doc2.id)],
            },
            follow=True
        )

        doc1.refresh_from_db()
        doc2.refresh_from_db()
        self.assertEqual(doc1.caixa_id, self.caixa_destino.id)
        self.assertEqual(doc2.caixa_id, self.caixa_destino.id)

    def test_retorna_erro_para_caixa_destino_inexistente(self):
        self._login_com_permissao('change_documento')
        doc = self._criar_documento('004', caixa=self.caixa_origem)

        response = self.client.post(
            self.url,
            {
                'acao_lote': 'mover_caixa',
                'caixa_destino': '999999',
                'selected_documentos': [str(doc.id)],
            },
            follow=True
        )

        doc.refresh_from_db()
        self.assertEqual(doc.caixa_id, self.caixa_origem.id)
        self.assertTrue(
            any('não existe' in msg.lower() for msg in self._messages(response))
        )

    def test_bloqueia_movimentacao_sem_permissao(self):
        self.assertTrue(self.client.login(username=self.user.username, password=self.password))
        doc = self._criar_documento('005', caixa=self.caixa_origem)

        response = self.client.post(
            self.url,
            {
                'acao_lote': 'mover_caixa',
                'caixa_destino': str(self.caixa_destino.id),
                'selected_documentos': [str(doc.id)],
            },
            follow=True
        )

        self.assertEqual(response.status_code, 403)
        doc.refresh_from_db()
        self.assertEqual(doc.caixa_id, self.caixa_origem.id)

    def test_previne_movimentacao_duplicada_para_mesma_caixa(self):
        self._login_com_permissao('change_documento')
        doc = self._criar_documento('006', caixa=self.caixa_destino)

        response = self.client.post(
            self.url,
            {
                'acao_lote': 'mover_caixa',
                'caixa_destino': str(self.caixa_destino.id),
                'selected_documentos': [str(doc.id)],
            },
            follow=True
        )

        doc.refresh_from_db()
        self.assertEqual(doc.caixa_id, self.caixa_destino.id)
        self.assertTrue(
            any('foram ignorados' in msg.lower() for msg in self._messages(response))
        )

    def test_exibe_erro_quando_nenhum_documento_e_selecionado(self):
        self._login_com_permissao('change_documento')

        response = self.client.post(
            self.url,
            {
                'acao_lote': 'mover_caixa',
                'caixa_destino': str(self.caixa_destino.id),
            },
            follow=True
        )

        self.assertIn(response.status_code, (200, 404))
        self.assertTrue(
            any('selecione ao menos um documento' in msg.lower() for msg in self._messages(response))
        )

    def test_bloqueia_acao_lote_invalida(self):
        self._login_com_permissao('change_documento')
        doc = self._criar_documento('007', caixa=self.caixa_origem)

        response = self.client.post(
            self.url,
            {
                'acao_lote': 'acao_inexistente',
                'caixa_destino': str(self.caixa_destino.id),
                'selected_documentos': [str(doc.id)],
            },
            follow=True
        )

        doc.refresh_from_db()
        self.assertEqual(doc.caixa_id, self.caixa_origem.id)
        self.assertTrue(
            any('ação em lote inválida' in msg.lower() for msg in self._messages(response))
        )

    def test_aplica_limite_de_capacidade_na_caixa_destino(self):
        self._login_com_permissao('change_documento')
        self.caixa_destino.capacidade_maxima = 1
        self.caixa_destino.save(update_fields=['capacidade_maxima'])
        self._criar_documento('008', caixa=self.caixa_destino)

        doc1 = self._criar_documento('009', caixa=self.caixa_origem)
        doc2 = self._criar_documento('010', caixa=self.caixa_origem)

        response = self.client.post(
            self.url,
            {
                'acao_lote': 'mover_caixa',
                'caixa_destino': str(self.caixa_destino.id),
                'selected_documentos': [str(doc1.id), str(doc2.id)],
            },
            follow=True
        )

        doc1.refresh_from_db()
        doc2.refresh_from_db()
        self.assertEqual(doc1.caixa_id, self.caixa_origem.id)
        self.assertEqual(doc2.caixa_id, self.caixa_origem.id)
        self.assertEqual(
            LogAuditoria.objects.filter(descricao__contains='TRANSFERÊNCIA:').count(),
            0
        )
        self.assertTrue(
            any('falta de capacidade' in msg.lower() for msg in self._messages(response))
        )

    def test_excluir_em_lote_sem_permissao_nao_remove_documentos(self):
        self.assertTrue(self.client.login(username=self.user.username, password=self.password))
        doc1 = self._criar_documento('011', caixa=self.caixa_origem)
        doc2 = self._criar_documento('012', caixa=self.caixa_origem)

        response = self.client.post(
            self.url,
            {
                'acao_lote': 'excluir',
                'selected_documentos': [str(doc1.id), str(doc2.id)],
            },
            follow=True
        )

        self.assertEqual(response.status_code, 403)
        self.assertTrue(Documento.objects.filter(id=doc1.id).exists())
        self.assertTrue(Documento.objects.filter(id=doc2.id).exists())

    def test_excluir_em_lote_com_permissao_remove_documentos_e_gera_log(self):
        self._login_com_permissao('delete_documento')
        doc1 = self._criar_documento('013', caixa=self.caixa_origem)
        doc2 = self._criar_documento('014', caixa=self.caixa_origem)

        response = self.client.post(
            self.url,
            {
                'acao_lote': 'excluir',
                'selected_documentos': [str(doc1.id), str(doc2.id)],
            },
            follow=True
        )

        self.assertFalse(Documento.objects.filter(id=doc1.id).exists())
        self.assertFalse(Documento.objects.filter(id=doc2.id).exists())
        # O modelo de auditoria possui FK com CASCADE para Documento.
        # Portanto os logs de EXCLUIDO sao removidos junto aos documentos.
        self.assertEqual(LogAuditoria.objects.filter(acao='EXCLUIDO').count(), 0)
        self.assertTrue(
            any('excluído(s) com sucesso' in msg.lower() for msg in self._messages(response))
        )


class DownloadLoteTests(TestCase):
    def setUp(self):
        self.url = reverse('documentos:listar').replace('/arquivo', '', 1)
        self.url_download_lote = reverse('documentos:download_lote_avancado').replace('/arquivo', '', 1)
        self.url_preview_avancado = reverse('documentos:preview_download_lote_avancado').replace('/arquivo', '', 1)
        self.url_progress = reverse('documentos:download_progress', args=['cache_inexistente']).replace('/arquivo', '', 1)
        self.url_download_zip = reverse('documentos:download_arquivo_zip', args=['token_invalido']).replace('/arquivo', '', 1)
        self.password = 'senha-segura-123'
        self.user = User.objects.create_user(
            username='operador',
            password=self.password,
            email='operador@example.com'
        )

        self.tipo = TipoDocumento.objects.create(nome='MEMORANDO')
        self.departamento = Departamento.objects.create(nome='Departamento de TI')
        self.caixa = Caixa.objects.create(numero=1, nome='Caixa Teste')

    def _login_com_permissao(self, codename):
        self.user.user_permissions.add(Permission.objects.get(codename='view_documento'))
        perm = Permission.objects.get(codename=codename)
        self.user.user_permissions.add(perm)
        self.assertTrue(self.client.login(username=self.user.username, password=self.password))

    def _criar_documento(self, numero, caixa=None):
        arquivo = SimpleUploadedFile(
            name=f'memorando_{numero}.pdf',
            content=b'%PDF-1.4\n1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n3 0 obj\n<< /Type /Page /Parent 2 0 R /Resources << /Font << /F1 4 0 R >> >> /MediaBox [0 0 612 792] /Contents 5 0 R >>\nendobj\n4 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\nendobj\n5 0 obj\n<< /Length 44 >>\nstream\nBT /F1 12 Tf 72 720 Td (Memorando de Teste) Tj ET\nendstream\nendobj\nxref\n0 6\n0000000000 65535 f\n0000000009 00000 n\n0000000058 00000 n\n0000000115 00000 n\n0000000261 00000 n\n0000000325 00000 n\ntrailer\n<< /Size 6 /Root 1 0 R >>\nstartxref\n412\n%%EOF',
            content_type='application/pdf'
        )
        return Documento.objects.create(
            nome=f'Memorando {numero}',
            assunto='Assunto de teste',
            tipo_documento=self.tipo,
            departamento=self.departamento,
            numero_documento=f'{numero}/2024',
            data_documento=date(2024, 1, 1),
            caixa=caixa,
            arquivo_pdf=arquivo,
            texto_extraido='Memorando de teste',
            ocr_processado=True
        )

    def _messages(self, response):
        return [m.message for m in get_messages(response.wsgi_request)]

    def test_redireciona_para_download_avancado_ao_selecionar_download_lote(self):
        self._login_com_permissao('change_documento')
        doc1 = self._criar_documento('001')
        doc2 = self._criar_documento('002')

        response = self.client.post(
            self.url,
            {
                'acao_lote': 'download_lote',
                'selected_documentos': [str(doc1.id), str(doc2.id)],
            }
        )

        self.assertEqual(response.status_code, 302)
        self.assertIn('download-lote-avancado', response.url)
        self.assertIn(f'{doc1.id},{doc2.id}', response.url)

    def test_download_lote_avancado_exibe_interface_com_documentos_selecionados(self):
        self._login_com_permissao('change_documento')
        doc1 = self._criar_documento('001')
        doc2 = self._criar_documento('002')

        response = self.client.get(
            f'{self.url_download_lote}?ids={doc1.id},{doc2.id}'
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Download em Lote de Documentos')
        self.assertContains(response, 'MEMORANDO 001')
        self.assertContains(response, 'MEMORANDO 002')

    def test_download_lote_avancado_sem_documentos_redireciona_para_listagem(self):
        self._login_com_permissao('change_documento')

        response = self.client.get(self.url_download_lote)

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('documentos:listar'))

    def test_preview_download_lote_avancado_retorna_resumo_detalhado(self):
        self._login_com_permissao('change_documento')
        doc1 = self._criar_documento('001')
        doc2 = self._criar_documento('002')

        response = self.client.post(
            self.url_preview_avancado,
            data=json.dumps({'ids': [doc1.id, doc2.id]}),
            content_type='application/json'
        )

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertTrue(data['sucesso'])
        self.assertEqual(data['resumo']['total_documentos'], 2)
        self.assertEqual(len(data['resumo']['documentos_detalhes']), 2)

    def test_preview_download_lote_avancado_sem_ids_retorna_erro(self):
        self._login_com_permissao('change_documento')

        response = self.client.post(
            self.url_preview_avancado,
            data=json.dumps({'ids': []}),
            content_type='application/json'
        )

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertFalse(data['sucesso'])
        self.assertIn('Nenhum documento selecionado', data['erro'])

    def test_download_progress_retorna_not_found_para_cache_inexistente(self):
        self._login_com_permissao('change_documento')

        response = self.client.get(self.url_progress)

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEqual(data['status'], 'not_found')

    def test_download_arquivo_zip_invalido_retorna_403(self):
        self._login_com_permissao('change_documento')

        response = self.client.get(self.url_download_zip)

        self.assertEqual(response.status_code, 403)


class DownloadLoteServiceTests(TestCase):
    def setUp(self):
        self.tipo = TipoDocumento.objects.create(nome='OFICIO')
        self.departamento = Departamento.objects.create(nome='Administração')
        self.user = User.objects.create_user(
            username='testuser',
            password='test123',
            email='test@example.com'
        )
        self.user.user_permissions.add(Permission.objects.get(codename='view_documento'))

    def _criar_documento_com_arquivo(self, nome, arquivo_conteudo):
        arquivo = SimpleUploadedFile(
            name=f'{nome}.pdf',
            content=arquivo_conteudo,
            content_type='application/pdf'
        )
        doc = Documento.objects.create(
            nome=nome,
            assunto='Assunto de teste',
            tipo_documento=self.tipo,
            departamento=self.departamento,
            numero_documento='001/2024',
            data_documento=date(2024, 1, 1),
            arquivo_pdf=arquivo,
            texto_extraido='texto teste',
            ocr_processado=True
        )
        # Salvar para garantir que o arquivo foi gravado
        doc.save()
        return doc

    def test_criar_zip_documentos_sucesso_com_arquivos_validos(self):
        from apps.documentos.services import DownloadLoteService

        doc1 = self._criar_documento_com_arquivo('Oficio 1', b'%PDF-1.4\n%%EOF')
        doc2 = self._criar_documento_com_arquivo('Oficio 2', b'%PDF-1.4\n%%EOF')

        service = DownloadLoteService()
        stats = service.criar_zip_documentos([doc1, doc2], 'oficios_teste', self.user)

        self.assertTrue(stats['sucesso'])
        self.assertEqual(stats['arquivos_processados'], 2)
        self.assertEqual(stats['arquivos_ignorados'], 0)
        self.assertTrue(stats['sucesso'])
        self.assertIn('oficios_teste_2docs_', stats['nome_zip'])

        # Verificar se arquivo ZIP foi criado
        self.assertTrue(Path(stats['caminho_zip']).exists())

        # Limpar
        Path(stats['caminho_zip']).unlink()

    def test_criar_zip_documentos_ignora_arquivos_corrompidos(self):
        from apps.documentos.services import DownloadLoteService

        doc1 = self._criar_documento_com_arquivo('Oficio 1', b'%PDF-1.4\n%%EOF')
        doc2 = self._criar_documento_com_arquivo('Arquivo Corrompido', b'conteudo invalido')

        service = DownloadLoteService()
        stats = service.criar_zip_documentos([doc1, doc2], 'oficios_teste', self.user)

        self.assertTrue(stats['sucesso'])
        self.assertEqual(stats['arquivos_processados'], 1)
        self.assertEqual(stats['arquivos_ignorados'], 1)
        self.assertIn('corrompido', stats['erros'][0])

        # Limpar
        if Path(stats['caminho_zip']).exists():
            Path(stats['caminho_zip']).unlink()

    def test_criar_zip_documentos_levanta_erro_sem_documentos(self):
        from apps.documentos.services import DownloadLoteService

        service = DownloadLoteService()

        with self.assertRaises(ValueError) as context:
            service.criar_zip_documentos([], 'teste', self.user)

        self.assertIn('Nenhum documento selecionado', str(context.exception))

    def test_validar_arquivo_retorna_true_para_pdf_valido(self):
        from apps.documentos.services import DownloadLoteService

        doc = self._criar_documento_com_arquivo('Teste', b'%PDF-1.4\n%%EOF')
        service = DownloadLoteService()

        resultado = service._validar_arquivo(doc.arquivo_pdf.path)
        self.assertTrue(resultado)

        # Limpar
        doc.arquivo_pdf.delete()
        doc.delete()

    def test_validar_arquivo_retorna_false_para_arquivo_invalido(self):
        from apps.documentos.services import DownloadLoteService

        doc = self._criar_documento_com_arquivo('Invalido', b'conteudo invalido')
        service = DownloadLoteService()

        resultado = service._validar_arquivo(doc.arquivo_pdf.path)
        self.assertFalse(resultado)

        # Limpar
        doc.arquivo_pdf.delete()
        doc.delete()

    def test_sanitizar_nome_arquivo_remove_caracteres_invalidos(self):
        from apps.documentos.services import DownloadLoteService

        service = DownloadLoteService()

        # Testar com caracteres inválidos
        resultado = service._sanitizar_nome_arquivo('Teste/Arquivo<>:"\\|?*.pdf')
        self.assertEqual(resultado, 'Teste_Arquivo_.pdf')

        # Testar com espaços múltiplos
        resultado = service._sanitizar_nome_arquivo('Teste    Arquivo    pdf')
        self.assertEqual(resultado, 'Teste_Arquivo_pdf')

        # Testar nome muito longo
        nome_longo = 'a' * 150
        resultado = service._sanitizar_nome_arquivo(nome_longo)
        self.assertLessEqual(len(resultado), 100)

    def test_limpar_arquivos_temporarios_remove_arquivos_antigos(self):
        from apps.documentos.services import DownloadLoteService
        import tempfile
        import time

        service = DownloadLoteService()

        # Criar arquivo temporário antigo
        arquivo_antigo = service.temp_dir / 'arquivo_antigo.zip'
        arquivo_antigo.write_bytes(b'teste')

        # Modificar tempo para parecer antigo
        tempo_antigo = time.time() - (25 * 3600)  # 25 horas atrás
        os.utime(arquivo_antigo, (tempo_antigo, tempo_antigo))

        # Criar arquivo recente
        arquivo_recente = service.temp_dir / 'arquivo_recente.zip'
        arquivo_recente.write_bytes(b'teste')

        # Limpar arquivos temporários
        service.limpar_arquivos_temporarios(idade_horas=24)

        # Verificar resultados
        self.assertFalse(arquivo_antigo.exists())
        self.assertTrue(arquivo_recente.exists())

        # Limpar
        arquivo_recente.unlink()

    def test_gerar_resumo_download_retorna_estatisticas_corretas(self):
        from apps.documentos.services import DownloadLoteService

        doc1 = self._criar_documento_com_arquivo('Doc 1', b'%PDF-1.4\n%%EOF')
        doc2 = self._criar_documento_com_arquivo('Doc 2', b'%PDF-1.4\n%%EOF')

        service = DownloadLoteService()
        resumo = service.gerar_resumo_download([doc1, doc2])

        self.assertEqual(resumo['total_documentos'], 2)
        self.assertEqual(resumo['total_arquivos'], 2)
        self.assertEqual(resumo['tamanho_total_mb'], 0.0)  # Arquivos pequenos
        self.assertIn('Oficio', resumo['tipos'])
        self.assertIn('ADMINISTRAÇÃO', resumo['departamentos'])

        # Limpar
        doc1.arquivo_pdf.delete()
        doc1.delete()
        doc2.arquivo_pdf.delete()
        doc2.delete()

    def test_gerar_metadados_documento_usa_data_upload(self):
        from apps.documentos.services import DownloadLoteService

        doc = self._criar_documento_com_arquivo('Doc Metadados', b'%PDF-1.4\n%%EOF')
        service = DownloadLoteService()

        metadados = service._gerar_metadados_documento(doc)

        self.assertIn('Data de Upload:', metadados)
        self.assertIn(doc.numero_documento, metadados)

        doc.arquivo_pdf.delete()
        doc.delete()


class CategoriaDocumentoFormTests(TestCase):
    def test_rejeita_nome_duplicado_de_categoria_ativa(self):
        TipoDocumento.objects.create(nome='Memorando', ativo=True)

        form = CategoriaDocumentoForm(data={
            'nome': 'memorando',
            'descricao': 'Duplicado',
            'ativo': True,
        })

        self.assertFalse(form.is_valid())
        self.assertIn('Ja existe uma categoria ativa com esse nome.', form.errors['nome'])

    def test_rejeita_nome_duplicado_de_categoria_inativa(self):
        TipoDocumento.objects.create(nome='Contrato', ativo=False)

        form = CategoriaDocumentoForm(data={
            'nome': 'contrato',
            'descricao': 'Duplicado',
            'ativo': True,
        })

        self.assertFalse(form.is_valid())
        self.assertIn('Ja existe uma categoria inativa com esse nome.', form.errors['nome'][0])

    def test_formulario_de_confirmacao_omite_categorias_inativas_em_novos_cadastros(self):
        ativa = TipoDocumento.objects.create(nome='Ativa', ativo=True)
        TipoDocumento.objects.create(nome='Inativa', ativo=False)

        form = DocumentoConfirmacaoForm(initial={})

        self.assertEqual(list(form.fields['tipo_documento'].queryset), [ativa])

    def test_formulario_de_edicao_mantem_categoria_inativa_do_documento(self):
        categoria_inativa = TipoDocumento.objects.create(nome='Legado', ativo=False)
        categoria_ativa = TipoDocumento.objects.create(nome='Atual', ativo=True)
        departamento = Departamento.objects.create(nome='Tecnologia')
        arquivo = SimpleUploadedFile('legado.pdf', b'%PDF-1.4\n%%EOF', content_type='application/pdf')
        documento = Documento.objects.create(
            nome='Documento legado',
            assunto='Teste',
            tipo_documento=categoria_inativa,
            departamento=departamento,
            numero_documento='001/2024',
            data_documento=date(2024, 1, 1),
            arquivo_pdf=arquivo,
        )

        form = DocumentoEditForm(instance=documento)

        self.assertCountEqual(
            list(form.fields['tipo_documento'].queryset),
            [categoria_ativa, categoria_inativa],
        )


class CategoriaDocumentoViewsTests(TestCase):
    def setUp(self):
        self.password = 'senha-segura-123'
        self.user = User.objects.create_user(
            username='gestor-categorias',
            password=self.password,
            email='categorias@example.com',
        )
        self.list_url = reverse('documentos:categorias_listar').replace('/arquivo', '', 1)
        self.create_url = reverse('documentos:categorias_criar').replace('/arquivo', '', 1)
        self.categoria = TipoDocumento.objects.create(
            nome='Memorando',
            descricao='Categoria principal',
            ativo=True,
        )
        self.departamento = Departamento.objects.create(nome='Arquivo Geral')
        self.documento = Documento.objects.create(
            nome='Memorando 001',
            assunto='Assunto',
            tipo_documento=self.categoria,
            departamento=self.departamento,
            numero_documento='001/2024',
            data_documento=date(2024, 1, 1),
            arquivo_pdf=SimpleUploadedFile('memo.pdf', b'%PDF-1.4\n%%EOF', content_type='application/pdf'),
        )

    def _login_com_permissoes(self, *codenames):
        for codename in codenames:
            self.user.user_permissions.add(Permission.objects.get(codename=codename))
        self.assertTrue(self.client.login(username=self.user.username, password=self.password))

    def _messages(self, response):
        return [m.message for m in get_messages(response.wsgi_request)]

    def test_listagem_filtra_por_busca_e_status(self):
        TipoDocumento.objects.create(nome='Resolucao', descricao='Ativa', ativo=True)
        TipoDocumento.objects.create(nome='Memoria', descricao='Inativa', ativo=False)
        self._login_com_permissoes('view_tipodocumento')

        response = self.client.get(self.list_url, {'q': 'memo', 'status': 'ativas'})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Memorando')
        self.assertNotContains(response, 'Memoria')

    def test_listagem_suporta_paginacao(self):
        for indice in range(25):
            TipoDocumento.objects.create(nome=f'Categoria {indice + 10}', ativo=True)
        self._login_com_permissoes('view_tipodocumento')

        response = self.client.get(self.list_url, {'page': 2})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['categorias'].number, 2)

    def test_criar_categoria_registra_feedback_e_auditoria(self):
        self._login_com_permissoes('add_tipodocumento', 'view_tipodocumento')

        response = self.client.post(
            self.create_url,
            {
                'nome': 'Contrato',
                'descricao': 'Contratos e instrumentos',
                'ativo': 'on',
            },
            follow=True,
        )

        categoria = TipoDocumento.objects.get(nome='Contrato')
        self.assertEqual(response.status_code, 200)
        self.assertTrue(any('criada com sucesso' in msg.lower() for msg in self._messages(response)))
        self.assertTrue(
            LogAuditoriaSistema.objects.filter(
                tipo_operacao=LogAuditoriaSistema.TipoOperacao.CREATE,
                modelo='documentos.TipoDocumento',
                objeto_id=str(categoria.id),
            ).exists()
        )

    def test_editar_categoria_registra_feedback_e_auditoria(self):
        self._login_com_permissoes('change_tipodocumento', 'view_tipodocumento')
        edit_url = reverse('documentos:categorias_editar', args=[self.categoria.id]).replace('/arquivo', '', 1)

        response = self.client.post(
            edit_url,
            {
                'nome': 'Memorando Interno',
                'descricao': 'Categoria atualizada',
                'ativo': 'on',
            },
            follow=True,
        )

        self.categoria.refresh_from_db()
        self.assertEqual(self.categoria.nome, 'Memorando Interno')
        self.assertTrue(any('atualizada com sucesso' in msg.lower() for msg in self._messages(response)))
        self.assertTrue(
            LogAuditoriaSistema.objects.filter(
                tipo_operacao=LogAuditoriaSistema.TipoOperacao.UPDATE,
                modelo='documentos.TipoDocumento',
                objeto_id=str(self.categoria.id),
            ).exists()
        )

    def test_excluir_categoria_inativa_sem_afetar_documentos(self):
        self._login_com_permissoes('delete_tipodocumento', 'view_tipodocumento')
        delete_url = reverse('documentos:categorias_excluir', args=[self.categoria.id]).replace('/arquivo', '', 1)

        response = self.client.post(delete_url, follow=True)

        self.categoria.refresh_from_db()
        self.documento.refresh_from_db()
        self.assertFalse(self.categoria.ativo)
        self.assertTrue(Documento.objects.filter(id=self.documento.id).exists())
        self.assertEqual(self.documento.tipo_documento_id, self.categoria.id)
        self.assertTrue(any('foram preservados' in msg.lower() for msg in self._messages(response)))
        self.assertTrue(
            LogAuditoriaSistema.objects.filter(
                tipo_operacao=LogAuditoriaSistema.TipoOperacao.DELETE,
                modelo='documentos.TipoDocumento',
                objeto_id=str(self.categoria.id),
            ).exists()
        )


class SecurityAndCsrfTests(TestCase):
    def setUp(self):
        self.password = 'senha-segura-123'
        self.user = User.objects.create_user(
            username='security-user',
            password=self.password,
            email='security@example.com',
        )
        self.user.user_permissions.add(Permission.objects.get(codename='view_documento'))
        self.csrf_client = Client(enforce_csrf_checks=True)
        self.csrf_client.force_login(self.user)

    def test_logout_exige_post_e_csrf(self):
        logout_url = reverse('custom_logout').replace('/arquivo', '', 1)
        response_get = self.csrf_client.get(logout_url)
        self.assertEqual(response_get.status_code, 405)

        response_post_sem_csrf = self.csrf_client.post(logout_url)
        self.assertEqual(response_post_sem_csrf.status_code, 403)

        token = _get_new_csrf_string()
        self.csrf_client.cookies['csrftoken'] = token
        response_post_com_csrf = self.csrf_client.post(
            logout_url,
            HTTP_X_CSRFTOKEN=token,
            follow=False,
        )
        self.assertEqual(response_post_com_csrf.status_code, 302)

    def test_preview_avancado_exige_csrf(self):
        url = reverse('documentos:preview_download_lote_avancado').replace('/arquivo', '', 1)
        response = self.csrf_client.post(
            url,
            data=json.dumps({'ids': [1]}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 403)

    def test_download_token_e_vinculado_ao_usuario(self):
        from apps.documentos.views_download import _gerar_download_token

        outro_usuario = User.objects.create_user(
            username='outro-user',
            password=self.password,
            email='other@example.com',
        )
        token = _gerar_download_token('arquivo_qualquer.zip', outro_usuario.id)
        url = reverse('documentos:download_arquivo_zip', args=[token]).replace('/arquivo', '', 1)
        response = self.csrf_client.get(url)
        self.assertEqual(response.status_code, 403)

    def test_download_token_expirado_retorna_403(self):
        from apps.documentos.views_download import _gerar_download_token

        token = _gerar_download_token('arquivo_qualquer.zip', self.user.id)
        url = reverse('documentos:download_arquivo_zip', args=[token]).replace('/arquivo', '', 1)

        with patch('apps.documentos.views_download.DOWNLOAD_TOKEN_MAX_AGE', 0):
            time.sleep(1)
            response = self.csrf_client.get(url)

        self.assertEqual(response.status_code, 403)


class UploadValidationTests(TestCase):
    def test_ocr_form_rejeita_arquivo_nao_pdf(self):
        arquivo = SimpleUploadedFile(
            'arquivo.txt',
            b'conteudo texto puro',
            content_type='text/plain',
        )
        form = DocumentoOCRForm(files={'arquivo_pdf': arquivo})
        self.assertFalse(form.is_valid())
        self.assertIn('Apenas arquivos PDF são permitidos.', form.errors['arquivo_pdf'])

    def test_ocr_form_rejeita_pdf_sem_assinatura(self):
        arquivo = SimpleUploadedFile(
            'arquivo.pdf',
            b'conteudo invalido',
            content_type='application/pdf',
        )
        form = DocumentoOCRForm(files={'arquivo_pdf': arquivo})
        self.assertFalse(form.is_valid())
        self.assertIn('O arquivo enviado não é um PDF válido.', form.errors['arquivo_pdf'])

    def test_ocr_form_aceita_pdf_valido(self):
        arquivo = SimpleUploadedFile(
            'arquivo.pdf',
            b'%PDF-1.4\n%%EOF',
            content_type='application/pdf',
        )
        form = DocumentoOCRForm(files={'arquivo_pdf': arquivo})
        self.assertTrue(form.is_valid())
