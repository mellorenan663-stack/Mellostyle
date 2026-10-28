// Lista todo o inglês fixo que a Brenda fala (aulas, frases, cartões, papo, palavras mais usadas),
// do jeito que o app manda pra voz. Saída: ferramentas/textos_ingles.txt (um texto por linha).
// Uso (na pasta do repositório, com Playwright instalado): node ingles-app/ferramentas/extrair_ingles.js
const { chromium } = require("playwright");
const fs = require("fs");
const path = require("path");

(async () => {
  const pasta = path.resolve(__dirname, "..");
  const browser = await chromium.launch();
  const page = await browser.newPage();
  await page.addInitScript(() => localStorage.setItem("sfe:setup", "true"));
  await page.goto("file://" + path.join(pasta, "index.html"));
  const textos = await page.evaluate(async () => {
    const vistos = new Map();
    const add = (t) => {
      if (t == null) return;
      t = textoFalado(String(t), true);
      if (!t || !/[a-z]/i.test(t) || t.includes("${")) return;
      const k = t.toLowerCase();
      if (!vistos.has(k)) vistos.set(k, t);
    };
    const colchetes = (s) => { for (const m of String(s).matchAll(/\[\[(.+?)\]\]/g)) add(m[1]); };
    const varre = (x) => {
      if (typeof x === "string") colchetes(x);
      else if (Array.isArray(x)) x.forEach(varre);
      else if (x && typeof x === "object") Object.values(x).forEach(varre);
    };
    for (const l of LESSONS) for (const st of l.steps) {
      varre([st.text, st.q, st.why]);
      if (st.t === "speak" || st.t === "order") add(st.en);
    }
    for (const [en] of Object.values(PHRASES).flat()) add(en);
    for (const c of allCards()) { add(c.en); add(c.ex); }
    varre(CHAT);
    for (const [en] of CHAT.swears) add(en);
    for (const p of DICT) add(p.en);
    varre([VIBE, TOQUES, DICA_TIPO, REGRAS_INGLES.map((r) => r[1]), INTRO_VIVO]);
    for (const p of PAPO) { add(p.q); add(p.exemplo); }
    for (const q of ["Do", "Can", "Are", "Have", "Did", "Will"]) { add(respostaCurta(q + " you", false)); add(respostaCurta(q + " you", true)); }
    for (let n = 1; n <= 100; n++) add(`I'm ${n} years old.`);
    ["Purr... meow!", "Stop it!", "Hi! How are you doing today?", "hello, how are you?"].forEach(add);
    const b = await dadosBase();
    for (const [en, , ex] of b.top) { add(en); add(ex); }
    return [...vistos.values()];
  });
  fs.writeFileSync(path.join(__dirname, "textos_ingles.txt"), textos.join("\n") + "\n");
  console.log(`${textos.length} textos em inglês`);
  await browser.close();
})();
