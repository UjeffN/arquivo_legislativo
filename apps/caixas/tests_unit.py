from django.test import RequestFactory, SimpleTestCase

from apps.caixas.views import _get_client_ip


class ClienteIpUnitTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()

    def test_get_client_ip_com_x_forwarded_for(self):
        request = self.factory.get('/', HTTP_X_FORWARDED_FOR='203.0.113.10, 10.0.0.1')
        self.assertEqual(_get_client_ip(request), '203.0.113.10')

    def test_get_client_ip_com_remote_addr(self):
        request = self.factory.get('/', REMOTE_ADDR='192.168.0.77')
        self.assertEqual(_get_client_ip(request), '192.168.0.77')

    def test_get_client_ip_sem_headers(self):
        request = self.factory.get('/')
        self.assertEqual(_get_client_ip(request), '127.0.0.1')
