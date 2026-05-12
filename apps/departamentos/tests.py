from datetime import date
import shutil
import tempfile

from django.contrib.auth.models import Permission, User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from apps.departamentos.models import Departamento
from apps.documentos.models import Documento, TipoDocumento


TEST_MEDIA_ROOT = tempfile.mkdtemp()


@override_settings(MEDIA_ROOT=TEST_MEDIA_ROOT)
class DepartamentoViewsTests(TestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(TEST_MEDIA_ROOT, ignore_errors=True)

    def setUp(self):
        self.user = User.objects.create_user(username="arquivador", password="senha")
        permissions = Permission.objects.filter(
            content_type__app_label="departamentos",
            codename__in=[
                "view_departamento",
                "add_departamento",
                "change_departamento",
                "delete_departamento",
            ],
        )
        self.user.user_permissions.set(permissions)
        self.client.force_login(self.user)

        self.departamento = Departamento.objects.create(nome="Arquivo")
        self.tipo = TipoDocumento.objects.create(nome="Memorando")

    def test_excluir_departamento_mantem_documento_sem_departamento(self):
        documento = Documento.objects.create(
            nome="Memorando 003/2025",
            assunto="Teste",
            tipo_documento=self.tipo,
            departamento=self.departamento,
            numero_documento="003/2025",
            data_documento=date(2025, 1, 1),
            arquivo_pdf=SimpleUploadedFile("teste.pdf", b"%PDF-1.4\n", content_type="application/pdf"),
        )

        response = self.client.post(reverse("departamentos:excluir", args=[self.departamento.id]))

        self.assertRedirects(response, reverse("departamentos:listar"))
        self.assertFalse(Departamento.objects.filter(id=self.departamento.id).exists())
        documento.refresh_from_db()
        self.assertIsNone(documento.departamento)
