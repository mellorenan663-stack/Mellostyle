/**
 * FinanceAI — Webhook WhatsApp (Evolution API → Firebase)
 * ------------------------------------------------------------
 * Recebe mensagens do seu WhatsApp via Evolution API, interpreta
 * comandos em linguagem simples e grava lançamentos no Firestore,
 * respondendo automaticamente no WhatsApp.
 *
 * Comandos suportados (envie pelo WhatsApp):
 *   despesa 45.90 alimentacao mercado do mes
 *   receita 1500 salario pagamento
 *   gastei 20 transporte uber           (alias de despesa)
 *   recebi 500 freelance projeto x       (alias de receita)
 *   meta viagem 200                      (adiciona aporte a uma meta)
 *   saldo                                (consulta saldo do mes)
 *   resumo                               (resumo mensal)
 *   extrato                              (ultimas 10 transacoes)
 *   ajuda                                (lista de comandos)
 */

import express from "express";
import admin from "firebase-admin";
import axios from "axios";

/* ─────────────────────────── CONFIG ─────────────────────────── */
const PORT = process.env.PORT || 3000;

// Evolution API
const EVOLUTION_URL = process.env.EVOLUTION_URL;          // ex: https://sua-evolution.com
const EVOLUTION_INSTANCE = process.env.EVOLUTION_INSTANCE; // ex: financeai
const EVOLUTION_APIKEY = process.env.EVOLUTION_APIKEY;     // API key da instancia

// Segredo opcional para validar o webhook
const WEBHOOK_SECRET = process.env.WEBHOOK_SECRET || "";

// Mapeia o numero do WhatsApp -> UID do usuario no Firebase.
// Formato da env: "5511999999999=uidDoFirebase,5511888888888=outroUid"
const USER_MAP = {};
(process.env.USER_MAP || "").split(",").filter(Boolean).forEach(pair => {
  const [phone, uid] = pair.split("=");
  if (phone && uid) USER_MAP[phone.trim().replace(/\D/g, "")] = uid.trim();
});

/* ─────────────────────── FIREBASE ADMIN ─────────────────────── */
// A service account vem na env FIREBASE_SERVICE_ACCOUNT (JSON em uma linha)
let serviceAccount;
try {
  serviceAccount = JSON.parse(process.env.FIREBASE_SERVICE_ACCOUNT);
} catch {
  console.error("❌ FIREBASE_SERVICE_ACCOUNT inválido ou ausente. Defina a env com o JSON da service account.");
  process.exit(1);
}
admin.initializeApp({ credential: admin.credential.cert(serviceAccount) });
const db = admin.firestore();
const { Timestamp } = admin.firestore;

/* ─────────────────────────── CATEGORIAS ─────────────────────── */
const CATEGORIES = {
  income: ["salario", "freelance", "investimento", "bonus", "aluguel_rec", "outros_rec"],
  expense: ["alimentacao", "transporte", "moradia", "saude", "lazer", "educacao",
            "roupas", "tecnologia", "assinaturas", "cartao", "outros_desp"],
};
// Apelidos comuns -> categoria oficial
const CAT_ALIASES = {
  comida: "alimentacao", mercado: "alimentacao", restaurante: "alimentacao", lanche: "alimentacao",
  uber: "transporte", gasolina: "transporte", onibus: "transporte", carro: "transporte",
  aluguel: "moradia", casa: "moradia", luz: "moradia", agua: "moradia", internet: "moradia",
  remedio: "saude", farmacia: "saude", medico: "saude", academia: "saude",
  cinema: "lazer", jogo: "lazer", viagem: "lazer", festa: "lazer",
  curso: "educacao", livro: "educacao", escola: "educacao",
  roupa: "roupas", celular: "tecnologia", eletronico: "tecnologia",
  netflix: "assinaturas", spotify: "assinaturas", assinatura: "assinaturas",
  salario: "salario", trabalho: "salario", freela: "freelance",
};

function resolveCategory(word, type) {
  if (!word) return type === "income" ? "outros_rec" : "outros_desp";
  const w = word.toLowerCase().normalize("NFD").replace(/[\u0300-\u036f]/g, "");
  if (CATEGORIES[type].includes(w)) return w;
  if (CAT_ALIASES[w]) return CAT_ALIASES[w];
  return type === "income" ? "outros_rec" : "outros_desp";
}

const CAT_LABELS = {
  salario: "Salário", freelance: "Freelance", investimento: "Investimento", bonus: "Bônus",
  aluguel_rec: "Aluguel Recebido", outros_rec: "Outros", alimentacao: "Alimentação",
  transporte: "Transporte", moradia: "Moradia", saude: "Saúde", lazer: "Lazer",
  educacao: "Educação", roupas: "Roupas", tecnologia: "Tecnologia", assinaturas: "Assinaturas",
  cartao: "Cartão", outros_desp: "Outros",
};
const fmt = v => Number(v || 0).toLocaleString("pt-BR", { style: "currency", currency: "BRL" });

/* ─────────────────────── PARSER DE MENSAGEM ──────────────────── */
function parseMessage(text) {
  const raw = text.trim();
  const lower = raw.toLowerCase();
  const parts = raw.split(/\s+/);
  const cmd = parts[0].toLowerCase().normalize("NFD").replace(/[\u0300-\u036f]/g, "");

  // Comandos de consulta
  if (["saldo", "resumo", "extrato", "ajuda", "help", "metas", "orcamento"].includes(cmd)) {
    return { kind: "query", query: cmd };
  }

  // Lançamentos: despesa/gastei  e  receita/recebi
  const expenseCmds = ["despesa", "gastei", "gasto", "paguei", "saiu"];
  const incomeCmds = ["receita", "recebi", "ganhei", "entrou"];
  let type = null;
  if (expenseCmds.includes(cmd)) type = "expense";
  else if (incomeCmds.includes(cmd)) type = "income";

  if (type) {
    // valor = primeiro numero encontrado (aceita 45,90 e 45.90)
    const amountMatch = raw.match(/(\d+[.,]?\d*)/);
    if (!amountMatch) return { kind: "error", msg: "Não encontrei o valor. Ex: *despesa 45,90 alimentacao mercado*" };
    const amount = parseFloat(amountMatch[1].replace(".", "").replace(",", "."));
    // remove comando e valor para descobrir categoria + descricao
    const rest = raw.slice(cmd.length).replace(amountMatch[1], "").trim();
    const restParts = rest.split(/\s+/).filter(Boolean);
    const category = resolveCategory(restParts[0], type);
    // se a 1a palavra virou categoria conhecida, descricao = resto; senao tudo eh descricao
    const firstIsCat = restParts[0] &&
      (CATEGORIES[type].includes(restParts[0].toLowerCase()) || CAT_ALIASES[restParts[0].toLowerCase()]);
    const description = (firstIsCat ? restParts.slice(1) : restParts).join(" ") || CAT_LABELS[category];
    return { kind: "transaction", type, amount, category, description };
  }

  // Meta: "meta viagem 200"
  if (cmd === "meta" || cmd === "guardar" || cmd === "aporte") {
    const amountMatch = raw.match(/(\d+[.,]?\d*)/);
    if (!amountMatch) return { kind: "error", msg: "Ex: *meta viagem 200*" };
    const amount = parseFloat(amountMatch[1].replace(".", "").replace(",", "."));
    const name = raw.slice(cmd.length).replace(amountMatch[1], "").trim();
    return { kind: "goal", name, amount };
  }

  return { kind: "unknown" };
}

/* ─────────────────────── AÇÕES NO FIREBASE ───────────────────── */
function monthKey(d = new Date()) {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;
}

async function addTransaction(uid, { type, amount, category, description }) {
  await db.collection("users").doc(uid).collection("transactions").add({
    type, amount, category, description,
    account: "principal", notes: "via WhatsApp",
    date: Timestamp.now(), createdAt: Timestamp.now(),
  });
}

async function addGoalDeposit(uid, name, amount) {
  const snap = await db.collection("users").doc(uid).collection("goals").get();
  const target = snap.docs.find(d => {
    const n = (d.data().name || "").toLowerCase();
    return n.includes(name.toLowerCase()) || name.toLowerCase().includes(n);
  });
  if (!target) return null;
  const g = target.data();
  const newCurrent = Math.min((g.current || 0) + amount, g.target);
  await target.ref.update({ current: newCurrent });
  return { name: g.name, current: newCurrent, total: g.target };
}

async function getMonthTx(uid) {
  const snap = await db.collection("users").doc(uid).collection("transactions").get();
  const mk = monthKey();
  return snap.docs
    .map(d => ({ ...d.data(), date: d.data().date?.toDate?.() ?? new Date() }))
    .filter(t => monthKey(t.date) === mk);
}

async function buildQueryReply(uid, query) {
  if (query === "ajuda" || query === "help") {
    return `🤖 *FinanceAI — Comandos*\n\n` +
      `💸 *despesa 45,90 alimentacao mercado*\n` +
      `💰 *receita 1500 salario pagamento*\n` +
      `🏆 *meta viagem 200* (aporte numa meta)\n` +
      `📊 *saldo* — saldo do mês\n` +
      `📆 *resumo* — resumo mensal\n` +
      `📋 *extrato* — últimas transações\n\n` +
      `_Você também pode usar: gastei, recebi, paguei, ganhei._`;
  }

  const tx = await getMonthTx(uid);
  const income = tx.filter(t => t.type === "income").reduce((s, t) => s + t.amount, 0);
  const expense = tx.filter(t => t.type === "expense").reduce((s, t) => s + t.amount, 0);
  const balance = income - expense;
  const saving = income > 0 ? (balance / income) * 100 : 0;

  if (query === "saldo") {
    return `💙 *Saldo do mês*\n\n✅ Receitas: ${fmt(income)}\n🔴 Despesas: ${fmt(expense)}\n━━━━━━━━━\n💰 Saldo: *${fmt(balance)}*\n📈 Economia: ${saving.toFixed(1)}%`;
  }
  if (query === "resumo") {
    const byCat = {};
    tx.filter(t => t.type === "expense").forEach(t => { byCat[t.category] = (byCat[t.category] || 0) + t.amount; });
    const top = Object.entries(byCat).sort((a, b) => b[1] - a[1]).slice(0, 3);
    return `📆 *Resumo do mês*\n\n💚 Receitas: ${fmt(income)}\n❤️ Despesas: ${fmt(expense)}\n💙 Saldo: ${fmt(balance)}\n📈 Economia: ${saving.toFixed(1)}%\n\n*Top gastos:*\n${top.map(([c, v], i) => `${i + 1}. ${CAT_LABELS[c] || c}: ${fmt(v)}`).join("\n") || "—"}`;
  }
  if (query === "extrato") {
    const last = [...tx].sort((a, b) => b.date - a.date).slice(0, 10);
    const lines = last.map(t => `${t.type === "income" ? "✅" : "🔴"} ${t.description}: ${t.type === "income" ? "+" : "-"}${fmt(t.amount)}`).join("\n");
    return `📋 *Extrato (mês)*\n\n${lines || "Nenhuma transação ainda."}`;
  }
  if (query === "metas") {
    const snap = await db.collection("users").doc(uid).collection("goals").get();
    if (snap.empty) return "🏆 Você não tem metas cadastradas.";
    return `🏆 *Suas metas*\n\n` + snap.docs.map(d => {
      const g = d.data();
      const pct = ((g.current || 0) / (g.target || 1) * 100).toFixed(0);
      return `${g.emoji || "🎯"} ${g.name}: ${pct}% (${fmt(g.current || 0)}/${fmt(g.target)})`;
    }).join("\n");
  }
  if (query === "orcamento") {
    const snap = await db.collection("users").doc(uid).collection("budgets").get();
    if (snap.empty) return "🎯 Nenhum orçamento definido.";
    const byCat = {};
    tx.filter(t => t.type === "expense").forEach(t => { byCat[t.category] = (byCat[t.category] || 0) + t.amount; });
    return `🎯 *Orçamento do mês*\n\n` + snap.docs.map(d => {
      const b = d.data(); const spent = byCat[d.id] || 0;
      const p = (spent / b.limit * 100).toFixed(0);
      const icon = spent > b.limit ? "🚨" : p >= (b.alertAt || 80) ? "⚠️" : "✅";
      return `${icon} ${CAT_LABELS[d.id] || d.id}: ${fmt(spent)}/${fmt(b.limit)} (${p}%)`;
    }).join("\n");
  }
  return "🤔 Não entendi. Envie *ajuda* para ver os comandos.";
}

/* ─────────────────────── ENVIAR WHATSAPP ─────────────────────── */
async function sendWhatsApp(phone, text) {
  if (!EVOLUTION_URL || !EVOLUTION_INSTANCE || !EVOLUTION_APIKEY) {
    console.warn("⚠️ Evolution API não configurada — pulei o envio. Resposta seria:\n", text);
    return;
  }
  try {
    await axios.post(
      `${EVOLUTION_URL}/message/sendText/${EVOLUTION_INSTANCE}`,
      { number: phone, text },
      { headers: { apikey: EVOLUTION_APIKEY, "Content-Type": "application/json" } }
    );
  } catch (e) {
    console.error("❌ Erro ao enviar WhatsApp:", e.response?.data || e.message);
  }
}

/* ─────────────────────────── SERVER ─────────────────────────── */
const app = express();
app.use(express.json({ limit: "2mb" }));

app.get("/", (_req, res) => res.send("FinanceAI WhatsApp webhook online ✅"));
app.get("/health", (_req, res) => res.json({ ok: true }));

app.post("/webhook", async (req, res) => {
  // Validação opcional por querystring ?secret=
  if (WEBHOOK_SECRET && req.query.secret !== WEBHOOK_SECRET) {
    return res.status(401).json({ error: "unauthorized" });
  }
  res.sendStatus(200); // responde rápido; processa depois

  try {
    const body = req.body || {};
    // Evolution API envia em messages.upsert
    const data = body.data || body;
    // ignora mensagens enviadas por nós mesmos
    if (data?.key?.fromMe) return;

    const remoteJid = data?.key?.remoteJid || "";
    const phone = remoteJid.replace(/@.*/, "").replace(/\D/g, "");
    if (!phone) return;

    const msg = data?.message;
    const text = msg?.conversation
      || msg?.extendedTextMessage?.text
      || msg?.imageMessage?.caption
      || "";
    if (!text.trim()) return;

    // Descobre o usuário Firebase
    const uid = USER_MAP[phone];
    if (!uid) {
      await sendWhatsApp(phone, "👋 Seu número ainda não está vinculado ao FinanceAI. Cadastre-o no painel (env USER_MAP).");
      return;
    }

    const parsed = parseMessage(text);
    let reply = "";

    if (parsed.kind === "transaction") {
      await addTransaction(uid, parsed);
      const emoji = parsed.type === "income" ? "💰" : "💸";
      reply = `${emoji} *${parsed.type === "income" ? "Receita" : "Despesa"} registrada!*\n\n` +
        `${fmt(parsed.amount)} — ${parsed.description}\n` +
        `📂 ${CAT_LABELS[parsed.category] || parsed.category}\n\n` +
        `_Envie *saldo* para ver seu mês._`;
    } else if (parsed.kind === "goal") {
      const r = await addGoalDeposit(uid, parsed.name, parsed.amount);
      reply = r
        ? `🏆 *Aporte registrado!*\n\n${fmt(parsed.amount)} → ${r.name}\nProgresso: ${fmt(r.current)} / ${fmt(r.total)} (${(r.current / r.total * 100).toFixed(0)}%)`
        : `🤔 Não encontrei a meta "${parsed.name}". Crie-a no painel primeiro.`;
    } else if (parsed.kind === "query") {
      reply = await buildQueryReply(uid, parsed.query);
    } else if (parsed.kind === "error") {
      reply = "⚠️ " + parsed.msg;
    } else {
      reply = "🤔 Não entendi. Envie *ajuda* para ver os comandos disponíveis.";
    }

    await sendWhatsApp(phone, reply);
  } catch (e) {
    console.error("❌ Erro no webhook:", e);
  }
});

app.listen(PORT, () => console.log(`🚀 FinanceAI WhatsApp webhook rodando na porta ${PORT}`));
