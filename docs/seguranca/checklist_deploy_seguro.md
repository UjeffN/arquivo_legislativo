# Checklist de Deploy Seguro

## 1) Segredos e variáveis de ambiente
- [ ] `SECRET_KEY` rotacionada antes do deploy.
- [ ] Credenciais expostas historicamente foram revogadas/rotacionadas.
- [ ] Variáveis obrigatórias definidas: `SECRET_KEY`, `ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS`.
- [ ] `DEBUG=False` no ambiente de produção.

## 2) Infraestrutura e transporte
- [ ] Aplicação atrás de proxy reverso HTTPS.
- [ ] Header `X-Forwarded-Proto` corretamente encaminhado.
- [ ] `SECURE_PROXY_SSL_HEADER` e `SECURE_SSL_REDIRECT` validados no ambiente.
- [ ] HSTS habilitado conforme política da organização.

## 3) Higiene de artefatos
- [ ] `media/`, `staticfiles/`, `temp/`, `logs/`, `.env*` e `venv/` não estão versionados.
- [ ] Não existem backups sensíveis versionados (ex.: `db.sqlite3.backup`).
- [ ] Nenhum arquivo temporário sensível foi incluído no pacote de release.

## 4) Verificações de aplicação
- [ ] `python manage.py check` executado com sucesso.
- [ ] Pipeline CI passou (lint fatal + testes críticos).
- [ ] Logout aceita apenas `POST` com CSRF.
- [ ] Endpoints críticos de documentos/caixas retornam `403` sem permissão.

## 5) Upload/Download e temporários
- [ ] Upload aceita apenas PDF válido (extensão + assinatura).
- [ ] Download em lote usa token assinado vinculado ao usuário e com expiração.
- [ ] Download é feito por streaming (`FileResponse`).
- [ ] Expurgo TTL configurado:
  `python manage.py limpar_downloads_temporarios --idade-horas 24`

## 6) Operação pós-deploy
- [ ] Logs de erro e auditoria monitorados nas primeiras 24 horas.
- [ ] Restauração de backup validada por superusuário em ambiente controlado.
- [ ] Plano de rollback testado e documentado.
