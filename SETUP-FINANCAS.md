# Mello Finanças — como colocar no ar

Controle financeiro pessoal (pessoa física) com o mesmo visual do sistema principal:
contas, cartões de crédito com fatura, lançamentos (parcelados e fixos), orçamento por
categoria, metas de guardar dinheiro, relatório para imprimir/PDF, backup e lixeira.

Tudo fica em **um arquivo só**: `financas.html`.

---

## Antes de tudo: dá para testar sem configurar nada

Abra o `financas.html` (ou publique no Netlify, passo 7) e:

- clique em **Ver com dados de exemplo** para ver o sistema com seis meses de dados inventados; ou
- crie uma conta de teste.

Nesse **modo de teste** os dados ficam guardados **só naquele aparelho/navegador**
(aparece "MODO DE TESTE" no topo). Para usar de verdade — cada pessoa com o seu login,
no celular e no computador ao mesmo tempo — siga os passos abaixo para ligar o Firebase.

> **Importante:** use um projeto Firebase **novo, só para o Mello Finanças**.
> Não reaproveite o projeto do sistema da fábrica (`producao-saas`): as regras de lá
> deixam qualquer pessoa logada ler os dados de lá, e aqui cada cliente precisa
> enxergar só o que é dele.

---

## Passo 1 — Criar o projeto
1. Acesse https://console.firebase.google.com
2. **Adicionar projeto** → nome sugerido: `mello-financas` → avançar (pode desativar o Google Analytics).

## Passo 2 — Ligar o login por e-mail e senha
1. Menu **Criação → Authentication → Começar**.
2. Aba **Sign-in method** → **E-mail/senha** → **Ativar** → salvar.
3. (Para o "Esqueci minha senha") em **Authentication → Templates**, dá para trocar o
   idioma do e-mail para **Português (Brasil)**.

## Passo 3 — Criar o banco (Firestore)
1. Menu **Criação → Firestore Database → Criar banco de dados**.
2. Escolha **Modo de produção**.
3. Região: **southamerica-east1 (São Paulo)** → ativar.

## Passo 4 — Regras de segurança (cada pessoa só vê o que é dela)
Em **Firestore → Regras**, apague o que estiver lá, cole o texto abaixo e clique em **Publicar**:

```
rules_version = '2';
service cloud.firestore {
  match /databases/{database}/documents {
    // Tudo de uma pessoa fica dentro de usuarios/{uid dela}:
    // perfil, contas, cartões, categorias, lançamentos, contas fixas, metas.
    // Só a própria pessoa, logada, lê e grava ali. O resto do banco é fechado.
    match /usuarios/{uid}/{documento=**} {
      allow read, write: if request.auth != null && request.auth.uid == uid;
    }
  }
}
```

## Passo 5 — Registrar o app Web e copiar a configuração
1. **Configurações do projeto** (engrenagem) → aba **Geral**.
2. Em **Seus apps**, clique no ícone **Web `</>`** → apelido `financas-web` → registrar.
3. Copie o objeto `firebaseConfig` que aparece (apiKey, authDomain, projectId…).

## Passo 6 — Colar a configuração no sistema
No `financas.html`, perto da **linha 890**, está este bloco:

```js
const FIREBASE_CONFIG={
  apiKey:"",
  authDomain:"",
  projectId:"",
  storageBucket:"",
  messagingSenderId:"",
  appId:""
};
```

Preencha com os valores copiados, por exemplo:

```js
const FIREBASE_CONFIG={
  apiKey:"AIza...",
  authDomain:"mello-financas.firebaseapp.com",
  projectId:"mello-financas",
  storageBucket:"mello-financas.firebasestorage.app",
  messagingSenderId:"1234567890",
  appId:"1:1234567890:web:abc123"
};
```

Salve o arquivo. Pronto: o aviso de "modo de teste" some e a tela de login passa a
criar contas de verdade.

## Passo 7 — Publicar online (Netlify)
- **Mais simples:** arraste o `financas.html` para https://app.netlify.com/drop.
  Para o endereço ficar "limpo" (sem `/financas.html` no fim), renomeie para
  `index.html` antes de arrastar.
- Depois, no Firebase → **Authentication → Settings → Domínios autorizados**, adicione o
  endereço do site publicado (ex.: `mello-financas.netlify.app`).

## Passo 8 — Primeiro acesso
1. Abra o site → **Ainda não tenho conta — criar agora**.
2. Cada pessoa cria o próprio login. O sistema já vem com as categorias prontas e uma
   conta "Carteira"; o painel mostra os **Primeiros passos** (cadastrar contas, cartões,
   contas fixas e tetos de gasto).

---

## Como o sistema faz as contas (para conferir)
- **Dinheiro em centavos inteiros:** R$ 1.234,56 é guardado como `123456`, então a soma
  das linhas sempre bate com o total (sem erro de arredondamento).
- **Cartão:** compra feita **a partir do dia do fechamento** entra na fatura seguinte.
  A compra conta como despesa **no mês em que a fatura vence**. Pagar a fatura tira o
  dinheiro da conta, mas **não conta de novo como despesa**.
- **Parcelado:** os centavos que sobram da divisão vão na 1ª parcela
  (R$ 100,00 em 3x = 33,34 + 33,33 + 33,33). A compra ocupa o limite inteiro e libera
  conforme as faturas são pagas.
- **Contas fixas:** aparecem todo mês como **previstas** até serem marcadas como pagas.
  Se o valor mudar (aumento do aluguel), edite e escolha "a partir de qual mês".
- **Saldo de hoje** = saldo inicial + tudo marcado como pago/recebido.
  **Previsto** = saldo de hoje + o que falta pagar e receber até a data − faturas que
  vencem até a data.
- **Transferência, pagamento de fatura e ajuste de saldo** não são receita nem despesa.
- **Teto por categoria:** abaixo de 85% "Controlado", de 85% até o teto "Atenção",
  passou do teto "Acima do teto" (mesmas faixas do sistema principal).

## Observações
- **Backup:** em **Ajustes & Backup** dá para baixar tudo (arquivo `.json`), restaurar
  em qualquer conta e baixar uma planilha (`.csv`, abre no Excel) com todos os lançamentos.
- **Lixeira:** o que for excluído fica 30 dias na lixeira e pode ser restaurado.
- **Celular e computador juntos:** com o Firebase ligado, o que for lançado num aparelho
  aparece no outro em segundos, sozinho, sem recarregar a página.
- **Sem internet:** com o Firebase ligado, o app abre com os dados que já estavam no
  aparelho; o que for lançado sem conexão fica guardado e é enviado sozinho quando a
  internet voltar.
- **Limite do plano gratuito do Firebase:** cada vez que alguém abre o app, o banco lê
  todos os registros daquela pessoa (cerca de 1.500 por ano de uso). O plano gratuito
  permite 50 mil leituras por dia no total — sobra para uso pessoal e de algumas pessoas.
  Para muitos usuários, ative o plano **Blaze** (paga só o que usar; o custo das leituras
  é de poucos centavos por dia).
- **Cobrança/assinatura:** esta versão não cobra dos usuários. Para vender por assinatura,
  o próximo passo é ligar um meio de pagamento (ex.: Mercado Pago ou Stripe).
