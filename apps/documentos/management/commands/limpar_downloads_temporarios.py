from django.core.management.base import BaseCommand, CommandError

from apps.documentos.services import DownloadLoteService


class Command(BaseCommand):
    help = 'Remove arquivos ZIP temporários de download com base em TTL.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--idade-horas',
            type=int,
            default=24,
            help='Remove arquivos mais antigos que N horas (padrão: 24).',
        )

    def handle(self, *args, **options):
        idade_horas = options['idade_horas']
        if idade_horas < 0:
            raise CommandError('O valor de --idade-horas deve ser maior ou igual a zero.')

        service = DownloadLoteService()
        resultado = service.limpar_arquivos_temporarios(idade_horas=idade_horas)
        self.stdout.write(
            self.style.SUCCESS(
                f"Expurgo concluído. Removidos: {resultado['removidos']} | Erros: {resultado['erros']}"
            )
        )
