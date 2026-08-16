# Módulo Financeiro — Mello Style / FacçãoOS

Gestor financeiro integrado ao sistema: contas bancárias, extrato, conciliação,
contas a pagar/receber e fluxo de caixa. Tudo dentro do mesmo arquivo
`index_minimalista_20.html`, no mesmo padrão visual e com os mesmos dados do
Firebase que o resto do app já usa.

## Telas

Uma seção **Financeiro** foi adicionada ao menu lateral, com três telas:

| Tela | O que faz |
|---|---|
| **Painel Financeiro** | Saldo consolidado, entradas e saídas do mês, resultado, contas a pagar e a receber, gráfico de fluxo de caixa dos últimos 6 meses, próximos vencimentos e para onde o dinheiro foi por categoria. |
| **Contas Bancárias** | Cadastro de cada conta (banco, agência, conta, tipo, saldo inicial). O saldo atual é calculado a partir dos lançamentos, nunca digitado. |
| **Extrato & Conciliação** | Importação do extrato do banco, lançamento manual, filtros, conciliação e exportação para CSV. |

O acesso segue os perfis já existentes: `admin`, `gerente` e `financeiro` veem
as telas; `operador` não.

## Como funciona a conexão com o banco

O caminho que funciona hoje é a **importação do extrato em OFX** — o mesmo
arquivo que Itaú, Bradesco, Caixa, Banco do Brasil, Nubank, Inter, Sicoob,
Sicredi, C6, Santander e praticamente todo banco brasileiro disponibiliza no
internet banking. Também aceita CSV.

O fluxo é: baixar o extrato do período → escolher a conta de destino →
selecionar o arquivo → conferir a prévia → importar.

O que o módulo faz sozinho:

- Lê **OFX 1.x** (SGML, tags de folha sem fechamento) e **OFX 2.x** (XML).
- Lê **CSV** em formatos variados: separador `;`, `,` ou tab; valor único
  assinado ou colunas separadas de crédito/débito; coluna `D`/`C`; datas em
  `DD/MM/AAAA`, `AAAA-MM-DD` ou `DD/MM/AA`; números em `1.234,56` ou `1234.56`;
  negativos entre parênteses; prefixo `R$`.
- **Não duplica.** Cada transação é identificada pelo `FITID` do OFX dentro da
  conta. Sem FITID, usa uma chave de data + valor + descrição normalizada.
  Reimportar o mesmo extrato, ou um período que se sobrepõe ao anterior, não
  gera lançamento repetido — as duplicatas aparecem marcadas e desmarcadas na
  prévia.
- **Classifica sozinho** pela descrição do extrato: folha, aluguel, energia,
  internet, impostos, tarifas bancárias, empréstimo, frete, manutenção, Pix
  recebido, rendimento. É um chute inicial, sempre editável.
- Mostra o **saldo do extrato** (`LEDGERBAL`) para conferir contra o saldo
  calculado pelo sistema.

### Por que não tem conexão automática e contínua

Conectar direto no banco, sem baixar arquivo, exige um **servidor próprio**.
Não é limitação de esforço — é impedimento técnico e regulatório:

- **Open Finance Brasil** exige ser instituição autorizada pelo Banco Central,
  com registro no diretório de participantes, certificados ICP-Brasil e mTLS,
  e autenticação FAPI. Nada disso roda em navegador.
- **API direta do banco** (Inter, Itaú, Sicoob, BB, Bradesco) exige certificado
  cliente mTLS e `client_secret`. Uma chave dessas colocada em página web fica
  legível para qualquer pessoa que abrir o código-fonte.
- **Agregadores** (Pluggy, Belvo, Klavi) resolvem a parte regulatória, mas a
  chave de API deles também é de servidor. O widget no navegador só funciona
  com um token de curta duração emitido pelo seu backend.

Ou seja: qualquer um dos três caminhos precisa de backend. Enquanto ele não
existe, o OFX entrega o mesmo resultado prático — o extrato inteiro entra no
sistema sem digitação — com a diferença de ser você quem baixa o arquivo.

### Onde plugar quando houver backend

O ponto de extensão é `finSincronizarConta(id)` no bloco `MÓDULO FINANCEIRO`.
Hoje ela orienta o usuário para a importação por arquivo. Com um backend, o
corpo passa a ser uma chamada autenticada que devolve transações no mesmo
formato que os parsers já produzem:

```js
{ data:"2026-08-05", descricao:"...", valor:4200.00, tipo:"saida"|"entrada", fitid:"..." }
```

A partir daí, a deduplicação (`finChaveDedupe`), a categorização
(`finCategoriaAutomatica`) e a gravação já existentes são reaproveitadas sem
alteração. O campo `conexao` de cada conta (`{tipo, provedor, ultimaSync}`) já
está reservado para guardar o provedor e a data da última sincronização.

## Integração com o resto do sistema

Uma saída do extrato pode ser enviada para o módulo de **Gastos** com o botão
💸, entrando no cálculo de lucro e no DRE que já existiam. O lançamento fica
marcado como conciliado e guarda o `gastoId`, para não ser enviado duas vezes.

Lançamentos marcados como **Previsto** não entram no saldo — são contas a pagar
e a receber, e aparecem em "Próximos vencimentos" no painel, com destaque
para os vencidos. O botão ✓ confirma o pagamento e aí sim afeta o caixa.

## Dados no Firestore

Duas coleções novas, seguindo o mesmo padrão de `ownerId` das demais:

**`contasBancarias`** — `nome`, `codigoBanco` (COMPE), `banco`, `tipo`,
`agencia`, `conta`, `saldoInicial`, `dataSaldoInicial`, `ativa`,
`conexao:{tipo,provedor,ultimaSync}`.

**`lancamentos`** — `contaId`, `data` (`AAAA-MM-DD`), `descricao`, `valor`
(sempre positivo), `tipo` (`entrada`/`saida`), `categoria`, `status`
(`realizado`/`previsto`), `competencia`, `conciliado`, `origem`
(`manual`/`ofx`/`csv`), `fitid`, `gastoId`.

O saldo de uma conta é sempre `saldoInicial` mais entradas realizadas menos
saídas realizadas. Nunca é gravado — assim não há como o saldo divergir dos
lançamentos.

> **Regras do Firestore:** as duas coleções novas precisam entrar nas regras de
> segurança do projeto, no mesmo modelo das existentes (leitura e escrita
> apenas para `request.auth.uid == resource.data.ownerId`). Sem isso a
> importação falha com erro de permissão.

## Testes

Os parsers e o fluxo completo foram testados:

- **33 testes de parser** cobrindo OFX 1.x e 2.x, CSV em cinco variações,
  deduplicação por FITID e por hash, e conversão de datas e números.
- **17 verificações ponta a ponta** em Chromium com o Firebase substituído por
  stubs em memória: cadastro de conta, lançamento manual, importação de OFX,
  deduplicação na reimportação, saldo consolidado e envio para o DRE.
- As telas já existentes (Dashboard, Gastos, Lotes, Produção, Relatório,
  Faturamento por Cliente, Funcionários, Histórico) continuam navegáveis sem
  erro de JavaScript.
