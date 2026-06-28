# FinanceAI — Backend WhatsApp (Evolution API)

Webhook que recebe mensagens do seu WhatsApp via **Evolution API**, interpreta
comandos simples e grava lançamentos no **Firebase** — os mesmos dados que aparecem
no painel `financeiro.html`.

```
WhatsApp  ──►  Evolution API  ──►  este webhook  ──►  Firebase Firestore  ──►  Painel FinanceAI
   ▲                                                                              
   └──────────────── resposta automática ◄──────────────────────────────────────
```

---

## ✅ Passo a passo completo

### 1. Subir a Evolution API
A Evolution API é o "motor" que conecta ao seu WhatsApp. Você pode subir em:

- **Railway** (mais fácil): https://railway.app → New Project → Deploy Evolution API (tem template pronto)
- **VPS/Docker**:
  ```bash
  docker run -d --name evolution -p 8080:8080 \
    -e AUTHENTICATION_API_KEY=minha-chave-forte \
    atendai/evolution-api:latest
  ```

Anote:
- `EVOLUTION_URL` → a URL pública (ex: `https://evolution-production.up.railway.app`)
- `EVOLUTION_APIKEY` → a chave que você definiu

### 2. Criar a instância e conectar seu WhatsApp
```bash
# cria a instância
curl -X POST "$EVOLUTION_URL/instance/create" \
  -H "apikey: SUA_APIKEY" -H "Content-Type: application/json" \
  -d '{"instanceName":"financeai","integration":"WHATSAPP-BAILEYS","qrcode":true}'
```
Abra o painel da Evolution (ou o endpoint do QR Code) e **escaneie o QR Code com seu WhatsApp**
(Aparelhos conectados). Pronto, seu número está conectado.

### 3. Pegar a Service Account do Firebase
1. [Firebase Console](https://console.firebase.google.com) → projeto `producao-saas`
2. ⚙️ Configurações do projeto → aba **Contas de serviço**
3. **Gerar nova chave privada** → baixa um arquivo `.json`
4. Transforme o conteúdo em **uma única linha** (use https://www.text-utils.com/json-minify ou `cat arquivo.json | jq -c .`) e cole na env `FIREBASE_SERVICE_ACCOUNT`.

### 4. Pegar seu UID do Firebase
- Firebase Console → **Authentication** → aba Users → copie o **User UID** da sua conta.
- Monte a env: `USER_MAP=5511999999999=SEU_UID` (número com DDI 55, só dígitos).

### 5. Deploy deste webhook
**Opção A — Railway (recomendado):**
1. Suba esta pasta `whatsapp-backend/` para um repositório.
2. Railway → New Project → Deploy from GitHub → selecione a pasta.
3. Em **Variables**, cole todas as variáveis do `.env.example`.
4. Railway te dá uma URL pública, ex: `https://financeai-wh.up.railway.app`.

**Opção B — Docker:**
```bash
cd whatsapp-backend
cp .env.example .env   # preencha tudo
docker build -t financeai-wh .
docker run -d -p 3000:3000 --env-file .env financeai-wh
```

**Opção C — Local (teste):**
```bash
npm install
# preencha as variáveis no shell ou use um .env loader
npm start
```

### 6. Apontar a Evolution para este webhook
```bash
curl -X POST "$EVOLUTION_URL/webhook/set/financeai" \
  -H "apikey: SUA_APIKEY" -H "Content-Type: application/json" \
  -d '{
    "webhook": {
      "enabled": true,
      "url": "https://SEU-WEBHOOK.up.railway.app/webhook?secret=SEU_WEBHOOK_SECRET",
      "events": ["MESSAGES_UPSERT"]
    }
  }'
```

### 7. Testar 🎉
Mande uma mensagem **para o próprio número conectado** (ou peça para alguém mandar):

```
despesa 45,90 alimentacao almoço
```

Você recebe de volta:
```
💸 Despesa registrada!
R$ 45,90 — almoço
📂 Alimentação
```
E o lançamento já aparece no painel `financeiro.html`. ✅

---

## 💬 Comandos disponíveis

| Mensagem | O que faz |
|----------|-----------|
| `despesa 45,90 alimentacao mercado` | registra uma despesa |
| `gastei 20 transporte uber` | idem (alias) |
| `receita 1500 salario pagamento` | registra uma receita |
| `recebi 500 freelance projeto` | idem (alias) |
| `meta viagem 200` | adiciona R$200 à meta "viagem" |
| `saldo` | saldo do mês |
| `resumo` | resumo mensal + top gastos |
| `extrato` | últimas 10 transações |
| `metas` | status das metas |
| `orcamento` | status dos orçamentos |
| `ajuda` | lista de comandos |

> A categoria é opcional e aceita apelidos (uber → transporte, netflix → assinaturas, etc.).
> Se não informar, vai para "Outros". Valores aceitam vírgula ou ponto.

---

## 🔐 Segurança
- Nunca suba o `.env` nem a service account para o Git (`.gitignore` já cuida disso).
- Use `WEBHOOK_SECRET` para impedir que terceiros chamem seu webhook.
- O `USER_MAP` garante que só números autorizados gravam dados.

## 🛠 Variáveis de ambiente
Veja `.env.example` — todas estão documentadas lá.
