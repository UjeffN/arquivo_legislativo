from datetime import date

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase, TestCase

from apps.departamentos.models import Departamento
from apps.documentos.models import Documento, TipoDocumento
from apps.documentos.views import (
    _aplicar_busca_documentos,
    _converter_data,
    _converter_data_para_string,
    _gerar_nome_documento,
)


class HelpersDocumentosUnitTests(SimpleTestCase):
    def test_gerar_nome_documento_com_numero_e_ano(self):
        nome = _gerar_nome_documento(
            {'tipo_documento': 'Ofício', 'numero_documento': '123', 'ano_documento': '2026'}
        )
        self.assertEqual(nome, 'Ofício 123/2026')

    def test_gerar_nome_documento_com_numero_sem_ano(self):
        nome = _gerar_nome_documento({'tipo_documento': 'Portaria', 'numero_documento': '77'})
        self.assertEqual(nome, 'Portaria 77')

    def test_converter_data_para_string_aceita_formatos_esperados(self):
        self.assertEqual(_converter_data_para_string('31/01/2026'), '2026-01-31')
        self.assertEqual(_converter_data_para_string('2026-01-31'), '2026-01-31')

    def test_converter_data_para_string_retorna_none_em_data_invalida(self):
        self.assertIsNone(_converter_data_para_string('31-31-2026'))
        self.assertIsNone(_converter_data_para_string(''))
        self.assertIsNone(_converter_data_para_string(None))

    def test_converter_data_aceita_formatos_esperados(self):
        self.assertEqual(_converter_data('31/01/2026'), date(2026, 1, 31))
        self.assertEqual(_converter_data('2026-01-31'), date(2026, 1, 31))

    def test_converter_data_retorna_none_em_data_invalida(self):
        self.assertIsNone(_converter_data('31-31-2026'))
        self.assertIsNone(_converter_data(''))
        self.assertIsNone(_converter_data(None))


class BuscaDocumentosUnitTests(TestCase):
    def setUp(self):
        self.tipo = TipoDocumento.objects.create(nome='OFICIO')
        self.departamento = Departamento.objects.create(nome='Departamento de TI')

        self.doc_ocr = self._criar_documento(
            numero='001',
            nome='Relatório Financeiro',
            assunto='Resumo Mensal',
            texto_extraido='Despesas e receitas da camara municipal',
            palavra_chave='orcamento balanco',
            observacao='urgente'
        )
        self._criar_documento(
            numero='002',
            nome='Ata de Reunião',
            assunto='Comissão de Obras',
            texto_extraido='Pauta de infraestrutura',
            palavra_chave='obras',
            observacao='arquivado'
        )

    def _criar_documento(self, numero, nome, assunto, texto_extraido, palavra_chave, observacao):
        arquivo = SimpleUploadedFile(
            name=f'doc_{numero}.pdf',
            content=b'%PDF-1.4\n%%EOF',
            content_type='application/pdf',
        )
        return Documento.objects.create(
            nome=nome,
            assunto=assunto,
            tipo_documento=self.tipo,
            departamento=self.departamento,
            numero_documento=f'{numero}/2026',
            data_documento=date(2026, 1, 1),
            arquivo_pdf=arquivo,
            texto_extraido=texto_extraido,
            ocr_processado=True,
            palavra_chave=palavra_chave,
            observacao=observacao,
        )

    def test_busca_encontra_por_texto_extraido(self):
        qs = _aplicar_busca_documentos(Documento.objects.all(), 'receitas camara')
        self.assertEqual(list(qs.values_list('id', flat=True)), [self.doc_ocr.id])

    def test_busca_multitermo_exige_todos_os_termos(self):
        qs = _aplicar_busca_documentos(Documento.objects.all(), 'receitas infraestrutura')
        self.assertEqual(qs.count(), 0)

    def test_busca_vazia_retorna_queryset_original(self):
        qs_original = Documento.objects.all().order_by('id')
        qs_resultado = _aplicar_busca_documentos(qs_original, '')
        self.assertEqual(
            list(qs_resultado.values_list('id', flat=True)),
            list(qs_original.values_list('id', flat=True)),
        )
