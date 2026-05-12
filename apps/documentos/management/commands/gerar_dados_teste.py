import random
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.caixas.models import Caixa
from apps.departamentos.models import Departamento
from apps.documentos.models import Documento, TipoDocumento


class Command(BaseCommand):
    help = 'Gera dados simulados para testes funcionais, carga e estresse.'

    def add_arguments(self, parser):
        parser.add_argument('--usuarios', type=int, default=10, help='Quantidade de usuários de teste.')
        parser.add_argument('--caixas', type=int, default=50, help='Quantidade de caixas de teste.')
        parser.add_argument('--documentos', type=int, default=1000, help='Quantidade de documentos de teste.')
        parser.add_argument(
            '--seed',
            type=int,
            default=42,
            help='Seed para geração determinística de dados.',
        )

    def handle(self, *args, **options):
        random.seed(options['seed'])
        total_usuarios = max(options['usuarios'], 0)
        total_caixas = max(options['caixas'], 0)
        total_documentos = max(options['documentos'], 0)

        self.stdout.write(self.style.NOTICE('Iniciando geração de dados simulados...'))
        usuarios = self._criar_usuarios(total_usuarios)
        tipos = self._garantir_tipos_documento()
        departamentos = self._garantir_departamentos()
        caixas = self._criar_caixas(total_caixas)
        documentos = self._criar_documentos(total_documentos, tipos, departamentos, caixas)

        self.stdout.write(self.style.SUCCESS('Geração concluída com sucesso.'))
        self.stdout.write(f'Usuários criados: {usuarios}')
        self.stdout.write(f'Caixas criadas: {caixas}')
        self.stdout.write(f'Documentos criados: {documentos}')

    def _criar_usuarios(self, total):
        user_model = get_user_model()
        criados = 0
        for i in range(total):
            username = f'teste_user_{i:03d}'
            email = f'{username}@example.com'
            _, created = user_model.objects.get_or_create(
                username=username,
                defaults={'email': email},
            )
            if created:
                criados += 1
        return criados

    def _garantir_tipos_documento(self):
        nomes = ['OFICIO', 'PORTARIA', 'ATA', 'MEMORANDO', 'CONTRATO']
        tipos = []
        for nome in nomes:
            # TipoDocumento normaliza o nome no save(), entao a busca precisa
            # ser case-insensitive para evitar conflito de unique.
            tipo = TipoDocumento.objects.filter(nome__iexact=nome).first()
            if not tipo:
                tipo = TipoDocumento.objects.create(nome=nome)
            tipos.append(tipo)
        return tipos

    def _garantir_departamentos(self):
        base = [
            'Gabinete',
            'Financas',
            'Administracao',
            'Juridico',
            'Tecnologia da Informacao',
        ]
        departamentos = []
        for nome in base:
            departamento = Departamento.objects.filter(nome__iexact=nome).first()
            if not departamento:
                departamento = Departamento.objects.create(nome=nome)
            departamentos.append(departamento)
        return departamentos

    def _criar_caixas(self, total):
        criadas = 0
        ultimo_numero = Caixa.objects.order_by('-numero').values_list('numero', flat=True).first() or 0
        for i in range(total):
            numero = ultimo_numero + i + 1
            _, created = Caixa.objects.get_or_create(
                numero=numero,
                defaults={
                    'nome': f'Caixa Teste {numero:04d}',
                    'descricao': 'Massa simulada para testes de performance.',
                    'capacidade_maxima': random.choice([100, 200, 300]),
                },
            )
            if created:
                criadas += 1
        return criadas

    def _criar_documentos(self, total, tipos, departamentos, caixas):
        if not tipos or not departamentos:
            return 0

        # Mesmo sem criar novas caixas nesta execucao, pode haver caixas
        # existentes no banco que devem ser consideradas.
        caixa_ids = list(Caixa.objects.values_list('id', flat=True))
        criados = 0
        hoje = timezone.now().date()

        for i in range(total):
            numero = f'{100000 + i}/2026'
            data_documento = hoje - timedelta(days=random.randint(0, 3650))
            caixa_id = random.choice(caixa_ids) if caixa_ids and random.random() < 0.8 else None
            tipo = random.choice(tipos)
            departamento = random.choice(departamentos)
            assunto = f'ASSUNTO TESTE {i:05d}'
            nome = f'{tipo.nome} {numero}'
            texto_extraido = (
                f'Registro simulado {i:05d}. Texto para validar busca OCR, '
                f'com departamento {departamento.nome} e tipo {tipo.nome}.'
            )

            documento = Documento(
                nome=nome,
                assunto=assunto,
                tipo_documento=tipo,
                departamento=departamento,
                numero_documento=numero,
                data_documento=data_documento,
                caixa_id=caixa_id,
                texto_extraido=texto_extraido,
                ocr_processado=True,
                palavra_chave='TESTE, CARGA, ESTRESSE',
                observacao='GERADO AUTOMATICAMENTE PARA TESTES',
            )
            documento.arquivo_pdf.save(
                f'documento_simulado_{i:05d}.pdf',
                ContentFile(b'%PDF-1.4\n%%EOF'),
                save=False,
            )
            documento.save()
            criados += 1

        return criados
