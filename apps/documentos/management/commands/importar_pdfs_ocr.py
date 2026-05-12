import csv
import os
from datetime import date, datetime
from typing import Optional

from django.core.files import File
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from apps.caixas.models import Caixa
from apps.departamentos.models import Departamento
from apps.documentos.models import Documento, TipoDocumento
from services.ocr import ocr_processor


class Command(BaseCommand):
    help = 'Importa PDFs existentes do servidor, executa OCR e preenche campos mínimos (assunto/data) + defaults.'

    def add_arguments(self, parser):
        parser.add_argument('--root', required=True, help='Pasta raiz contendo PDFs para importação.')
        parser.add_argument('--recursive', action='store_true', help='Varre subpastas recursivamente.')
        parser.add_argument('--dry-run', action='store_true', help='Não grava no banco nem salva arquivos (apenas simula).')
        parser.add_argument('--offset', type=int, default=0, help='Pula os N primeiros arquivos (após ordenação).')
        parser.add_argument('--limit', type=int, default=0, help='Limita quantidade de arquivos processados (0 = sem limite).')
        parser.add_argument(
            '--csv-relatorio',
            default='relatorio_importacao_documentos.csv',
            help='Caminho do CSV de relatório (padrão: relatorio_importacao_documentos.csv).',
        )
        parser.add_argument(
            '--caixa-numero',
            type=int,
            default=1,
            help='Número da caixa default (padrão: 1 -> caixa 0001).',
        )
        parser.add_argument(
            '--tipo-nome',
            default='IMPORTADO',
            help='Nome do TipoDocumento default para documentos importados.',
        )
        parser.add_argument(
            '--departamento-nome',
            default='IMPORTACAO',
            help='Nome do Departamento default para documentos importados.',
        )
        parser.add_argument(
            '--numero-documento',
            default='001',
            help='Valor placeholder para numero_documento (padrão: 001).',
        )
        parser.add_argument(
            '--data-fallback',
            choices=['today', 'mtime'],
            default='mtime',
            help='Se OCR não extrair data, usar a data de hoje ou a data de modificação do arquivo (padrão: mtime).',
        )

    def handle(self, *args, **options):
        root = options['root']
        recursive = options['recursive']
        dry_run = options['dry_run']
        offset = options['offset']
        limit = options['limit']
        csv_relatorio = options['csv_relatorio']

        if not os.path.isdir(root):
            raise CommandError(f'Pasta não encontrada: {root}')

        caixa = self._get_or_create_caixa(options['caixa_numero'], dry_run=dry_run)
        tipo = self._get_or_create_tipo(options['tipo_nome'], dry_run=dry_run)
        departamento = self._get_or_create_departamento(
            nome=options['departamento_nome'],
            dry_run=dry_run,
        )

        arquivos = self._listar_pdfs(root, recursive=recursive)
        if offset and offset > 0:
            arquivos = arquivos[offset:]
        if limit and limit > 0:
            arquivos = arquivos[:limit]

        self.stdout.write(self.style.NOTICE(f'Encontrados {len(arquivos)} PDF(s) para processar.'))

        total_ok = 0
        total_erro = 0

        with open(csv_relatorio, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(
                f,
                fieldnames=['arquivo', 'status', 'documento_id', 'erro', 'ocr_chars'],
            )
            writer.writeheader()

            for idx, caminho in enumerate(arquivos, start=1):
                try:
                    documento_id, ocr_chars = self._importar_arquivo(
                        caminho=caminho,
                        caixa=caixa,
                        tipo=tipo,
                        departamento=departamento,
                        numero_documento=options['numero_documento'],
                        data_fallback=options['data_fallback'],
                        dry_run=dry_run,
                    )
                    total_ok += 1
                    writer.writerow(
                        {
                            'arquivo': caminho,
                            'status': 'OK',
                            'documento_id': documento_id or '',
                            'erro': '',
                            'ocr_chars': ocr_chars,
                        }
                    )
                    if idx % 25 == 0:
                        self.stdout.write(self.style.NOTICE(f'Processados {idx}/{len(arquivos)}...'))
                except Exception as e:
                    total_erro += 1
                    writer.writerow(
                        {
                            'arquivo': caminho,
                            'status': 'ERRO',
                            'documento_id': '',
                            'erro': str(e),
                            'ocr_chars': 0,
                        }
                    )

        self.stdout.write(self.style.SUCCESS('Importação concluída.'))
        self.stdout.write(f'OK: {total_ok} | Erros: {total_erro} | Dry-run: {dry_run} | CSV: {csv_relatorio}')

    def _listar_pdfs(self, root: str, recursive: bool):
        pdfs = []
        if recursive:
            for base, _, files in os.walk(root):
                for name in files:
                    if name.lower().endswith('.pdf'):
                        pdfs.append(os.path.join(base, name))
        else:
            for name in os.listdir(root):
                if name.lower().endswith('.pdf'):
                    pdfs.append(os.path.join(root, name))
        pdfs.sort()
        return pdfs

    def _importar_arquivo(
        self,
        *,
        caminho: str,
        caixa: Caixa,
        tipo: TipoDocumento,
        departamento: Departamento,
        numero_documento: str,
        data_fallback: str,
        dry_run: bool,
    ):
        if not os.path.isfile(caminho):
            raise CommandError(f'Arquivo não encontrado: {caminho}')

        texto_extraido = ocr_processor.extrair_texto_pdf(caminho)
        informacoes = ocr_processor.analisar_documento(texto_extraido or '')

        assunto = self._montar_assunto(informacoes.get('assunto'), texto_extraido)
        data_documento = self._montar_data(informacoes.get('data_documento'), caminho, data_fallback=data_fallback)

        nome_arquivo = os.path.basename(caminho)
        nome = os.path.splitext(nome_arquivo)[0] or nome_arquivo

        if dry_run:
            return None, len(texto_extraido or '')

        with transaction.atomic():
            documento = Documento.objects.create(
                nome=nome,
                assunto=assunto,
                tipo_documento=tipo,
                departamento=departamento,
                numero_documento=numero_documento,
                data_documento=data_documento,
                caixa=caixa,
                texto_extraido=texto_extraido or '',
                ocr_processado=True,
                palavra_chave='',
                observacao='IMPORTADO EM LOTE (OCR)',
                arquivo_pdf='',
            )

            with open(caminho, 'rb') as f:
                documento.arquivo_pdf.save(os.path.basename(caminho), File(f), save=True)

            return documento.id, len(texto_extraido or '')

    def _montar_assunto(self, assunto_ocr: Optional[str], texto: Optional[str]) -> str:
        assunto_ocr = (assunto_ocr or '').strip()
        if assunto_ocr:
            return assunto_ocr[:200]

        texto = (texto or '').strip()
        if not texto:
            return 'SEM TEXTO OCR'

        linhas = [ln.strip() for ln in texto.splitlines() if ln.strip()]
        if not linhas:
            return texto[:200]

        return ' '.join(linhas[:3])[:200]

    def _montar_data(self, data_ocr: Optional[str], caminho: str, *, data_fallback: str) -> date:
        data_ocr = (data_ocr or '').strip()

        if data_ocr:
            for fmt in ('%d/%m/%Y', '%Y-%m-%d'):
                try:
                    return datetime.strptime(data_ocr, fmt).date()
                except ValueError:
                    pass

        if data_fallback == 'today':
            return timezone.now().date()

        ts = os.path.getmtime(caminho)
        return datetime.fromtimestamp(ts).date()

    def _get_or_create_caixa(self, numero: int, *, dry_run: bool) -> Caixa:
        caixa = Caixa.objects.filter(numero=numero).first()
        if caixa:
            return caixa
        if dry_run:
            return Caixa(numero=numero, nome=f'Caixa {numero}')
        return Caixa.objects.create(numero=numero, nome=f'Caixa {numero}', capacidade_maxima=1000000)

    def _get_or_create_tipo(self, nome: str, *, dry_run: bool) -> TipoDocumento:
        nome = (nome or '').strip() or 'IMPORTADO'
        tipo = TipoDocumento.objects.filter(nome__iexact=nome).first()
        if tipo:
            return tipo
        if dry_run:
            return TipoDocumento(nome=nome)
        return TipoDocumento.objects.create(nome=nome)

    def _get_or_create_departamento(self, *, nome: str, dry_run: bool) -> Departamento:
        nome = (nome or '').strip() or 'IMPORTACAO'

        departamento = Departamento.objects.filter(nome__iexact=nome).first()
        if departamento:
            return departamento
        if dry_run:
            return Departamento(nome=nome)
        return Departamento.objects.create(nome=nome)
