# Checklist de Revisão de Segurança (PR)

## 1) Controle de acesso
- [ ] Toda nova view/action exige autenticação quando necessário.
- [ ] Permissões Django (`view/add/change/delete`) são validadas por ação.
- [ ] Operações em lote validam permissões explicitamente.

## 2) CSRF e métodos HTTP
- [ ] Endpoints `POST/PUT/PATCH/DELETE` não usam `csrf_exempt` sem justificativa formal.
- [ ] Logout implementado apenas via `POST` com CSRF.
- [ ] Métodos HTTP estão restritos ao necessário (`require_POST`, `require_http_methods`).

## 3) Arquivos e I/O
- [ ] Upload valida extensão, assinatura do arquivo e limite de tamanho.
- [ ] Download de arquivos grandes usa streaming (`FileResponse`).
- [ ] Não há risco de path traversal em caminhos recebidos por parâmetro.
- [ ] Downloads temporários usam identificador seguro (token assinado) com expiração.

## 4) Segredos e configuração
- [ ] Nenhum segredo novo em código, template, teste ou log.
- [ ] Configurações sensíveis vêm de variáveis de ambiente.
- [ ] Sem fallback inseguro para `SECRET_KEY` ou credenciais.

## 5) Observabilidade e erro
- [ ] Sem `print()`/traceback cru em produção.
- [ ] Logs usam logger com nível adequado e sem dados sensíveis.
- [ ] Mensagens de erro para usuário não expõem detalhes internos.

## 6) Backup e restauração
- [ ] Rotas/ações de backup e restauração restritas a superusuário.
- [ ] Fluxo de restauração exige confirmação operacional explícita.
- [ ] Artefatos de backup não exibem segredos em texto claro no admin.

## 7) Testes mínimos
- [ ] Há teste para caso autorizado e não autorizado (`403`).
- [ ] Há teste de CSRF negativo e positivo nos fluxos críticos.
- [ ] Há teste para upload inválido/válido e download com token inválido/expirado.
