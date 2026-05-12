"""
Testes unitários para o módulo de auditoria
"""

import json
from datetime import datetime, timedelta
from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.utils import timezone
from django.urls import reverse
from unittest.mock import patch, MagicMock

from .models import (
    LogAuditoria, ConfiguracaoRetencao, EstatisticaAuditoria, AlertaSeguranca
)
from .services import AuditoriaService, DecoradoresAuditoria

User = get_user_model()


class LogAuditoriaModelTest(TestCase):
    """Testes para o modelo LogAuditoria"""

    def setUp(self):
        self.usuario = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )

    def test_criacao_log_basico(self):
        """Testa criação básica de log"""
        log = LogAuditoria.objects.create(
            acao='Teste de log',
            tipo_operacao=LogAuditoria.TipoOperacao.CREATE,
            usuario=self.usuario,
            ip_address='127.0.0.1',
            modulo='test',
            descricao='Descrição do teste'
        )

        self.assertEqual(log.acao, 'Teste de log')
        self.assertEqual(log.tipo_operacao, LogAuditoria.TipoOperacao.CREATE)
        self.assertEqual(log.usuario, self.usuario)
        self.assertEqual(log.ip_address, '127.0.0.1')
        self.assertTrue(log.sucesso)
        self.assertIsNotNone(log.hash_dados)

    def test_hash_dados_gerado_automaticamente(self):
        """Testa se hash dos dados é gerado automaticamente"""
        dados_teste = {'campo1': 'valor1', 'campo2': 'valor2'}

        log = LogAuditoria.objects.create(
            acao='Teste com dados',
            tipo_operacao=LogAuditoria.TipoOperacao.UPDATE,
            usuario=self.usuario,
            dados_depois=dados_teste
        )

        self.assertIsNotNone(log.hash_dados)
        self.assertEqual(len(log.hash_dados), 64)  # SHA-256

    def test_verificacao_integridade(self):
        """Testa verificação de integridade dos dados"""
        log = LogAuditoria.objects.create(
            acao='Teste integridade',
            tipo_operacao=LogAuditoria.TipoOperacao.CREATE,
            usuario=self.usuario
        )

        # Integridade deve ser válida
        self.assertTrue(log.verificar_integridade())

        # Alterar hash manualmente deve quebrar integridade
        hash_original = log.hash_dados
        log.hash_dados = 'hash_invalido'

        # Salvar sem gerar novo hash
        with patch.object(log, 'save'):
            LogAuditoria.objects.filter(pk=log.pk).update(hash_dados='hash_invalido')

        log.refresh_from_db()
        self.assertFalse(log.verificar_integridade())

    def test_salvar_nome_usuario_backup(self):
        """Testa se nome do usuário é salvo como backup"""
        log = LogAuditoria.objects.create(
            acao='Teste backup usuário',
            tipo_operacao=LogAuditoria.TipoOperacao.CREATE,
            usuario=self.usuario
        )

        self.assertEqual(log.nome_usuario, self.usuario.get_username())

        # Após deletar usuário, nome deve permanecer
        self.usuario.delete()
        log.refresh_from_db()
        self.assertEqual(log.nome_usuario, 'testuser')


class AuditoriaServiceTest(TestCase):
    """Testes para o serviço de auditoria"""

    def setUp(self):
        self.usuario = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.service = AuditoriaService()

    def test_registrar_log_simples(self):
        """Testa registro de log simples"""
        log = self.service.registrar_log(
            acao='Ação de teste',
            tipo_operacao=LogAuditoria.TipoOperacao.CREATE,
            usuario=self.usuario,
            ip_address='127.0.0.1'
        )

        self.assertIsInstance(log, LogAuditoria)
        self.assertEqual(log.acao, 'Ação de teste')
        self.assertEqual(log.usuario, self.usuario)
        self.assertEqual(log.ip_address, '127.0.0.1')

    def test_registrar_autenticacao_sucesso(self):
        """Testa registro de autenticação bem-sucedida"""
        log = self.service.registrar_autenticacao(
            usuario=self.usuario,
            ip_address='127.0.0.1',
            user_agent='Test Agent',
            sucesso=True
        )

        self.assertEqual(log.tipo_operacao, LogAuditoria.TipoOperacao.AUTENTICACAO)
        self.assertEqual(log.nivel_severidade, LogAuditoria.NivelSeveridade.INFO)
        self.assertTrue(log.sucesso)

    def test_registrar_autenticacao_falha(self):
        """Testa registro de autenticação falha"""
        log = self.service.registrar_autenticacao(
            usuario=None,
            ip_address='192.168.1.100',
            user_agent='Test Agent',
            sucesso=False,
            erro_msg='Senha inválida'
        )

        self.assertEqual(log.tipo_operacao, LogAuditoria.TipoOperacao.AUTENTICACAO)
        self.assertEqual(log.nivel_severidade, LogAuditoria.NivelSeveridade.WARNING)
        self.assertFalse(log.sucesso)
        self.assertEqual(log.erro_msg, 'Senha inválida')

    def test_registrar_operacao_crud(self):
        """Testa registro de operações CRUD"""
        # Mock request
        request = MagicMock()
        request.user = self.usuario
        request.META = {
            'REMOTE_ADDR': '127.0.0.1',
            'HTTP_USER_AGENT': 'Test Agent'
        }
        request.session.session_key = 'test_session'
        request.resolver_match.app_name = 'test_app'

        log = self.service.registrar_operacao_crud(
            acao='Criar documento',
            tipo_operacao=LogAuditoria.TipoOperacao.CREATE,
            usuario=self.usuario,
            request=request,
            modelo='Documento',
            objeto_id='1',
            objeto_repr='Documento #1',
            dados_depois={'titulo': 'Teste', 'conteudo': 'Conteúdo teste'}
        )

        self.assertEqual(log.tipo_operacao, LogAuditoria.TipoOperacao.CREATE)
        self.assertEqual(log.modelo, 'Documento')
        self.assertEqual(log.objeto_id, '1')
        self.assertEqual(log.sessao_id, 'test_session')

    @patch('apps.auditoria.services.AuditoriaService._verificar_multiplas_falhas_login')
    def test_verificar_alertas_chamado(self, mock_verificar):
        """Testa se verificação de alertas é chamada"""
        self.service._verificar_alertas = MagicMock()

        self.service.registrar_log(
            acao='Teste alerta',
            tipo_operacao=LogAuditoria.TipoOperacao.AUTENTICACAO,
            usuario=self.usuario,
            sucesso=False
        )

        self.service._verificar_alertas.assert_called_once()

    def test_exportar_logs_json(self):
        """Testa exportação de logs para JSON"""
        # Criar logs de teste
        log1 = LogAuditoria.objects.create(
            acao='Log 1',
            tipo_operacao=LogAuditoria.TipoOperacao.CREATE,
            usuario=self.usuario
        )

        log2 = LogAuditoria.objects.create(
            acao='Log 2',
            tipo_operacao=LogAuditoria.TipoOperacao.UPDATE,
            usuario=self.usuario
        )

        data_inicio = timezone.now() - timedelta(days=1)
        data_fim = timezone.now() + timedelta(days=1)

        json_export = self.service.exportar_logs(
            data_inicio=data_inicio,
            data_fim=data_fim,
            formato='json'
        )

        # Verificar se é JSON válido
        dados = json.loads(json_export)
        self.assertEqual(len(dados), 2)

        # Verificar se ambos os logs estão presentes (ordem pode variar)
        acoes = [log['acao'] for log in dados]
        self.assertIn('Log 1', acoes)
        self.assertIn('Log 2', acoes)

    def test_exportar_logs_csv(self):
        """Testa exportação de logs para CSV"""
        # Criar log de teste
        LogAuditoria.objects.create(
            acao='Log CSV',
            tipo_operacao=LogAuditoria.TipoOperacao.CREATE,
            usuario=self.usuario
        )

        data_inicio = timezone.now() - timedelta(days=1)
        data_fim = timezone.now() + timedelta(days=1)

        csv_export = self.service.exportar_logs(
            data_inicio=data_inicio,
            data_fim=data_fim,
            formato='csv'
        )

        # Verificar se contém cabeçalho e dados
        lines = csv_export.strip().split('\n')
        self.assertGreater(len(lines), 1)  # Pelo menos cabeçalho + 1 linha
        self.assertIn('ID', lines[0])  # Cabeçalho
        self.assertIn('Log CSV', csv_export)  # Dados


class ConfiguracaoRetencaoTest(TestCase):
    """Testes para ConfiguracaoRetencao"""

    def test_criacao_configuracao(self):
        """Testa criação de configuração de retenção"""
        config = ConfiguracaoRetencao.objects.create(
            tipo_operacao=LogAuditoria.TipoOperacao.CREATE,
            dias_retencao=365,
            nivel_severidade_minimo=LogAuditoria.NivelSeveridade.INFO
        )

        self.assertEqual(config.tipo_operacao, LogAuditoria.TipoOperacao.CREATE)
        self.assertEqual(config.dias_retencao, 365)
        self.assertTrue(config.ativo)

    def test_string_representation(self):
        """Testa representação string"""
        config = ConfiguracaoRetencao.objects.create(
            tipo_operacao=LogAuditoria.TipoOperacao.DELETE,
            dias_retencao=1825
        )

        expected = f"Exclusão - {config.dias_retencao} dias"
        self.assertEqual(str(config), expected)


class AlertaSegurancaTest(TestCase):
    """Testes para AlertaSeguranca"""

    def setUp(self):
        self.usuario = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )

    def test_criacao_alerta(self):
        """Testa criação de alerta de segurança"""
        alerta = AlertaSeguranca.objects.create(
            tipo_alerta=AlertaSeguranca.TipoAlerta.MULTIPLAS_FALHAS_LOGIN,
            nivel_alerta=AlertaSeguranca.NivelAlerta.ALTO,
            usuario=self.usuario,
            ip_address='192.168.1.100',
            titulo='Múltiplas falhas detectadas',
            descricao='5 tentativas de login falhas na última hora',
            dados_adicionais={'total': 5, 'periodo': 1}
        )

        self.assertEqual(alerta.tipo_alerta, AlertaSeguranca.TipoAlerta.MULTIPLAS_FALHAS_LOGIN)
        self.assertEqual(alerta.nivel_alerta, AlertaSeguranca.NivelAlerta.ALTO)
        self.assertFalse(alerta.visualizado)
        self.assertIsNone(alerta.visualizado_em)

    def test_confirmar_visualizacao(self):
        """Testa confirmação de visualização de alerta"""
        alerta = AlertaSeguranca.objects.create(
            tipo_alerta=AlertaSeguranca.TipoAlerta.HORARIO_INCOMUM,
            nivel_alerta=AlertaSeguranca.NivelAlerta.MEDIO,
            usuario=self.usuario,
            titulo='Acesso em horário incomum'
        )

        # Confirmar visualização
        alerta.visualizado = True
        alerta.visualizado_em = timezone.now()
        alerta.visualizado_por = self.usuario
        alerta.save()

        alerta.refresh_from_db()
        self.assertTrue(alerta.visualizado)
        self.assertEqual(alerta.visualizado_por, self.usuario)
        self.assertIsNotNone(alerta.visualizado_em)


class AuditoriaAdminTest(TestCase):
    """Testes para interface admin de auditoria"""

    def setUp(self):
        self.usuario = User.objects.create_user(
            username='adminuser',
            email='admin@example.com',
            password='adminpass123'
        )
        self.usuario.is_staff = True
        self.usuario.is_superuser = True
        self.usuario.save()

        self.client = Client()
        self.client.login(username='adminuser', password='adminpass123')

    def test_acesso_admin_logs(self):
        """Testa acesso à lista de logs no admin"""
        response = self.client.get('/admin/auditoria/logauditoria/')
        self.assertEqual(response.status_code, 200)

    def test_acesso_admin_configuracoes(self):
        """Testa acesso às configurações no admin"""
        response = self.client.get('/admin/auditoria/configuracaoretencao/')
        self.assertEqual(response.status_code, 200)

    def test_acesso_admin_alertas(self):
        """Testa acesso aos alertas no admin"""
        response = self.client.get('/admin/auditoria/alertaseguranca/')
        self.assertEqual(response.status_code, 200)

    def test_exportar_logs_action(self):
        """Testa ação de exportar logs"""
        # Criar logs de teste
        LogAuditoria.objects.create(
            acao='Log teste',
            tipo_operacao=LogAuditoria.TipoOperacao.CREATE,
            usuario=self.usuario
        )

        response = self.client.post(
            '/admin/auditoria/logauditoria/',
            {
                'action': 'exportar_selecionados_json',
                '_selected_action': [1]
            }
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/json')

    def test_verificar_integridade_action(self):
        """Testa ação de verificar integridade"""
        # Criar log de teste
        log = LogAuditoria.objects.create(
            acao='Log integridade',
            tipo_operacao=LogAuditoria.TipoOperacao.CREATE,
            usuario=self.usuario
        )

        response = self.client.post(
            '/admin/auditoria/logauditoria/',
            {
                'action': 'verificar_integridade_selecionados',
                '_selected_action': [log.id]
            },
            follow=True
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Verificação concluída')


class DecoradoresAuditoriaTest(TestCase):
    """Testes para decoradores de auditoria"""

    def setUp(self):
        self.usuario = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )

    def test_decorador_auditar_operacao(self):
        """Testa decorador de auditoria de operação"""
        # Mock request
        request = MagicMock()
        request.user = self.usuario
        request.META = {'REMOTE_ADDR': '127.0.0.1', 'HTTP_USER_AGENT': 'Test Agent'}
        request.resolver_match = MagicMock()
        request.resolver_match.app_name = 'test_app'

        # Função de teste
        @DecoradoresAuditoria.auditar_operacao(
            tipo_operacao=LogAuditoria.TipoOperacao.CREATE,
            acao='Operação decorada'
        )
        def funcao_teste(request):
            return 'resultado'

        # Executar função
        resultado = funcao_teste(request)

        # Verificar resultado
        self.assertEqual(resultado, 'resultado')

        # Verificar se log foi criado
        logs = LogAuditoria.objects.filter(acao='Operação decorada')
        self.assertEqual(logs.count(), 1)
