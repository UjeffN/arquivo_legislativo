import http from 'k6/http';
import { check, sleep } from 'k6';
import { parseHTML } from 'k6/html';

const BASE_URL = __ENV.BASE_URL || 'http://localhost:8000/arquivo';
const USERNAME = __ENV.USERNAME || 'admin';
const PASSWORD = __ENV.PASSWORD || 'admin';

export const options = {
  scenarios: {
    pico_progressivo: {
      executor: 'ramping-vus',
      stages: [
        { duration: '2m', target: 20 },
        { duration: '3m', target: 60 },
        { duration: '4m', target: 120 },
        { duration: '4m', target: 180 },
        { duration: '2m', target: 220 },
        { duration: '3m', target: 0 },
      ],
      gracefulRampDown: '30s',
    },
  },
  thresholds: {
    http_req_failed: ['rate<0.03'],
    http_req_duration: ['p(95)<1500', 'p(99)<3000'],
    checks: ['rate>0.95'],
  },
};

function extrairCsrfToken(body) {
  const doc = parseHTML(body);
  return doc.find('input[name=csrfmiddlewaretoken]').first().attr('value');
}

function autenticar() {
  const loginPage = http.get(`${BASE_URL}/accounts/login/`);
  const csrfToken = extrairCsrfToken(loginPage.body);
  const cookies = loginPage.cookies.csrftoken;
  const csrfCookie = cookies && cookies.length > 0 ? cookies[0].value : '';

  const payload = {
    username: USERNAME,
    password: PASSWORD,
    csrfmiddlewaretoken: csrfToken,
  };

  const loginRes = http.post(`${BASE_URL}/accounts/login/`, payload, {
    headers: {
      Referer: `${BASE_URL}/accounts/login/`,
      'Content-Type': 'application/x-www-form-urlencoded',
      'X-CSRFToken': csrfCookie,
    },
  });

  check(loginRes, {
    'login realizado': (r) => r.status === 302 || r.status === 303,
  });
}

export default function () {
  autenticar();

  const respDocumentos = http.get(`${BASE_URL}/documentos/?search=teste&page=1`);
  const respCaixas = http.get(`${BASE_URL}/caixas/?status=ativa`);
  const respHistorico = http.get(`${BASE_URL}/caixas/historico-movimentacoes/?page=1`);

  check(respDocumentos, { 'documentos responde': (r) => r.status === 200 });
  check(respCaixas, { 'caixas responde': (r) => r.status === 200 });
  check(respHistorico, { 'historico responde': (r) => r.status === 200 });

  sleep(0.5);
}
