# Configuração — JV Confecção

Guia para deixar o sistema com o **banco de dados próprio do cliente** (Firebase).
Enquanto isso não for feito, os dados vão para o projeto compartilhado `producao-saas`
(serve só para testes — **não usar em produção do cliente**).

> Onde fica a config no código: arquivo `index_minimalista_20.html`, perto da **linha 15**,
> dentro do bloco comentado `CONFIGURAÇÃO DO FIREBASE — JV Confecção`.

---

## Pré-requisito
Uma conta Google (de preferência do próprio cliente, para ele ser o dono dos dados).

## Passo 1 — Criar o projeto
1. Acesse https://console.firebase.google.com
2. **Adicionar projeto** → nome sugerido: `jv-confeccao` → avançar (pode desativar o Google Analytics).

## Passo 2 — Ativar o login por e-mail/senha
1. Menu **Criação → Authentication → Começar**.
2. Aba **Sign-in method** → **E-mail/senha** → **Ativar** → salvar.

## Passo 3 — Criar o banco (Firestore)
1. Menu **Criação → Firestore Database → Criar banco de dados**.
2. Escolha **Modo de produção**.
3. Região: **southamerica-east1 (São Paulo)** (mais perto do Brasil) → ativar.

## Passo 4 — Regras de segurança
Em **Firestore → Regras**, cole o conteúdo abaixo e **Publicar**.
Assim cada usuário só enxerga e edita os próprios dados:

```
rules_version = '2';
service cloud.firestore {
  match /databases/{database}/documents {

    // Configuração (1 documento por usuário, id = uid)
    match /configuracoes/{uid} {
      allow read, write: if request.auth != null && request.auth.uid == uid;
    }

    // Demais coleções: cada documento tem ownerId = uid do dono
    match /{colecao}/{docId} {
      allow read, delete: if request.auth != null
                          && resource.data.ownerId == request.auth.uid;
      allow create: if request.auth != null
                    && request.resource.data.ownerId == request.auth.uid;
      allow update: if request.auth != null
                    && resource.data.ownerId == request.auth.uid
                    && request.resource.data.ownerId == request.auth.uid;
    }
  }
}
```

## Passo 5 — Registrar o app Web e copiar a config
1. **Configurações do projeto** (engrenagem) → aba **Geral**.
2. Em **Seus apps**, clique no ícone **Web `</>`** → apelido `jv-web` → registrar.
3. Copie o objeto `firebaseConfig` que aparece (apiKey, authDomain, projectId, etc.).

## Passo 6 — Colar a config no sistema
No `index_minimalista_20.html` (perto da **linha 15**), substitua o objeto:

```js
const firebaseConfig={apiKey:"...",authDomain:"jv-confeccao.firebaseapp.com",
  projectId:"jv-confeccao",storageBucket:"jv-confeccao.appspot.com",
  messagingSenderId:"...",appId:"..."};
```

Salve o arquivo.

## Passo 7 — Criar o primeiro acesso
1. Abra o sistema, na tela de login clique em **Criar conta**.
2. Cadastre o e-mail/senha do cliente. Pronto — esse usuário vira o dono dos dados.

## Passo 8 (opcional) — Publicar online
- **Mais simples:** arraste o `index_minimalista_20.html` para https://app.netlify.com/drop
  (gera um link na hora).
- **Ou** Firebase Hosting: `firebase init hosting` + `firebase deploy`.
- Depois, no Firebase → Authentication → **Settings → Authorized domains**, adicione o
  domínio do site publicado.

---

## Observações
- **Logo:** o sistema usa hoje um brasão SVG provisório "JV". Quando enviar o logo oficial
  (PNG/SVG), ele é aplicado nos 3 pontos (login, topo, menu).
- **Backup:** a tela **Backup & Config** exporta/importa os dados em JSON.
- **Imposto:** alíquota fixa de 7% (havia um banner que foi removido por duplicar o
  faturamento líquido); o cálculo permanece disponível internamente se precisar reativar.
