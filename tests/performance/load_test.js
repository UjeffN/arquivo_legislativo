import http from 'k6/http';
import { check, sleep } from 'k6';
import { parseHTML } from 'k6/html';

const BASE_URL = __ENV.BASE_URL || 'http://localhost:8000/arquivo';
const USERNAME = __ENV.USERNAME || 'admin';
const PASSWORD = __ENV.PASSWORD || 'admin';

export const options = {
  scenarios: {
    navegacao_nominal: {
      executor: 'ramping-arrival-rate',
      startRate: 2,
      timeUnit: '1s',
      preAllocatedVUs: 15,
      maxVUs: 80,
      stages: [
        { target: 5, duration: '1m' },
        { target: 15, duration: '3m' },
        { target: 15, duration: '2m' },
        { target: 0, duration: '1m' },
      ],
    },
  },
  thresholds: {
    http_req_failed: ['rate<0.01'],
    http_req_duration: ['p(95)<800', 'p(99)<1500'],
    checks: ['rate>0.99'],
  },
};

function extrairCsrfToken(body) {
  const doc = parseHTML(body);
  return doc.find('input[name=csrfmiddlewaretoken]').first().attr('value');
}

function autenticar() {
  const loginPage = http.get(`${BASE_URL}/accounts/login/`);
  check(loginPage, {
    'login page status 200': (r) => r.status === 200,
  });

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
    'login redirect 302/303': (r) => r.status === 302 || r.status === 303,
  });
}

export default function () {
  autenticar();

  const respostas = http.batch([
    ['GET', `${BASE_URL}/dashboard/`],
    ['GET', `${BASE_URL}/documentos/`],
    ['GET', `${BASE_URL}/caixas/`],
    ['GET', `${BASE_URL}/caixas/historico-movimentacoes/`],
  ]);

  check(respostas[0], { 'dashboard ok': (r) => r.status === 200 });
  check(respostas[1], { 'documentos ok': (r) => r.status === 200 });
  check(respostas[2], { 'caixas ok': (r) => r.status === 200 });
  check(respostas[3], { 'historico ok': (r) => r.status === 200 });

  sleep(1);
}
