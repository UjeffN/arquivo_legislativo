from datetime import date

from django.contrib.auth.models import Permission, User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from apps.caixas.models import Caixa
from apps.departamentos.models import Departamento
from apps.documentos.models import Documento, LogAuditoria, TipoDocumento


class ExclusaoCaixaComDesvinculacaoTests(TestCase):
    def setUp(self):
        self.password = 'senha-segura-123'
        self.user = User.objects.create_user(username='gestor', password=self.password)
        self.user.user_permissions.add(Permission.objects.get(codename='delete_caixa'))
        self.user.user_permissions.add(Permission.objects.get(codename='view_caixa'))

        self.url_listar = reverse('caixas:listar_caixas').replace('/arquivo', '', 1)
        self.url_historico = reverse('caixas:historico_movimentacoes').replace('/arquivo', '', 1)

        self.tipo = TipoDocumento.objects.create(nome='OFICIO')
        self.departamento = Departamento.objects.create(nome='Departamento de Protocolo')

        self.caixa = Caixa.objects.create(numero=100, nome='Caixa Teste')
        self.doc1 = self._criar_documento('001', self.caixa)
        self.doc2 = self._criar_documento('002', self.caixa)

    def _criar_documento(self, numero, caixa):
        arquivo = SimpleUploadedFile(
            name=f'doc_{numero}.pdf',
            content=b'%PDF-1.4\n%%EOF',
            content_type='application/pdf'
        )
        return Documento.objects.create(
            nome=f'Documento {numero}',
            assunto='Assunto',
            tipo_documento=self.tipo,
            departamento=self.departamento,
            numero_documento=f'{numero}/2024',
            data_documento=date(2024, 1, 1),
            caixa=caixa,
            arquivo_pdf=arquivo,
            texto_extraido='texto',
            ocr_processado=True
        )

    def test_tela_confirmacao_lista_documentos(self):
        self.assertTrue(self.client.login(username=self.user.username, password=self.password))
        url_excluir = reverse('caixas:excluir_caixa', kwargs={'pk': self.caixa.pk}).replace('/arquivo', '', 1)
        response = self.client.get(url_excluir)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.doc1.nome)
        self.assertContains(response, self.doc2.nome)

    def test_exclusao_desvincula_documentos_sem_perder_registros(self):
        self.assertTrue(self.client.login(username=self.user.username, password=self.password))
        url_excluir = reverse('caixas:excluir_caixa', kwargs={'pk': self.caixa.pk}).replace('/arquivo', '', 1)

        response = self.client.post(url_excluir, {'confirmar_exclusao': '1'}, follow=True)

        self.assertIn(response.status_code, (200, 404))
        self.assertFalse(Caixa.objects.filter(pk=self.caixa.pk).exists())

        self.doc1.refresh_from_db()
        self.doc2.refresh_from_db()
        self.assertIsNone(self.doc1.caixa_id)
        self.assertIsNone(self.doc2.caixa_id)

        # Documentos continuam acessíveis por consultas independentes
        self.assertTrue(Documento.objects.filter(id=self.doc1.id).exists())
        self.assertTrue(Documento.objects.filter(numero_documento='001/2024').exists())

        logs = LogAuditoria.objects.filter(descricao__startswith='DESVINCULACAO_CAIXA:')
        self.assertEqual(logs.count(), 2)
        self.assertTrue(logs.filter(documento=self.doc1).exists())
        self.assertTrue(logs.filter(documento=self.doc2).exists())

    def test_cancelamento_nao_altera_caixa_nem_documentos(self):
        self.assertTrue(self.client.login(username=self.user.username, password=self.password))
        url_excluir = reverse('caixas:excluir_caixa', kwargs={'pk': self.caixa.pk}).replace('/arquivo', '', 1)

        self.client.post(url_excluir, {}, follow=True)

        self.assertTrue(Caixa.objects.filter(pk=self.caixa.pk).exists())
        self.doc1.refresh_from_db()
        self.doc2.refresh_from_db()
        self.assertEqual(self.doc1.caixa_id, self.caixa.id)
        self.assertEqual(self.doc2.caixa_id, self.caixa.id)

    def test_historico_movimentacoes_exibe_desvinculacoes(self):
        self.assertTrue(self.client.login(username=self.user.username, password=self.password))
        url_excluir = reverse('caixas:excluir_caixa', kwargs={'pk': self.caixa.pk}).replace('/arquivo', '', 1)
        self.client.post(url_excluir, {'confirmar_exclusao': '1'}, follow=True)

        response = self.client.get(self.url_historico)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'DESVINCULACAO_CAIXA')

    def test_bloqueia_exclusao_quando_usuario_nao_tem_permissao(self):
        usuario_sem_perm = User.objects.create_user(username='sem-permissao', password=self.password)
        self.assertTrue(self.client.login(username=usuario_sem_perm.username, password=self.password))
        url_excluir = reverse('caixas:excluir_caixa', kwargs={'pk': self.caixa.pk}).replace('/arquivo', '', 1)

        response = self.client.post(url_excluir, {'confirmar_exclusao': '1'}, follow=True)

        self.assertEqual(response.status_code, 403)
        self.assertTrue(Caixa.objects.filter(pk=self.caixa.pk).exists())
        self.doc1.refresh_from_db()
        self.doc2.refresh_from_db()
        self.assertEqual(self.doc1.caixa_id, self.caixa.id)
        self.assertEqual(self.doc2.caixa_id, self.caixa.id)

    def test_log_de_desvinculacao_contem_metadados_esperados(self):
        self.assertTrue(self.client.login(username=self.user.username, password=self.password))
        url_excluir = reverse('caixas:excluir_caixa', kwargs={'pk': self.caixa.pk}).replace('/arquivo', '', 1)
        self.client.post(url_excluir, {'confirmar_exclusao': '1'}, follow=True)

        logs = LogAuditoria.objects.filter(descricao__startswith='DESVINCULACAO_CAIXA:').order_by('id')
        self.assertEqual(logs.count(), 2)

        descricao = logs.first().descricao
        self.assertIn(f'caixa_id={self.caixa.id}', descricao)
        self.assertIn(f'caixa_nome="{self.caixa.nome}"', descricao)
        self.assertIn('documentos_afetados=', descricao)
