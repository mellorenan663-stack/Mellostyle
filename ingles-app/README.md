# Sem Frescura English

App para aprender inglês com a **Brenda**, uma gata professora sem filtro, do zero (A1) até nível nativo (C2).
Não usa IA nem precisa de chave: todo o conteúdo vem dentro do app. É grátis e funciona até sem internet.

## Como usar
Abra o `index.html` no navegador (Chrome recomendado, por causa do microfone) ou publique a pasta inteira no Netlify.
A pasta `dados` precisa ficar junto do `index.html`, porque é nela que está o dicionário.

- **Início:** a Brenda te recebe. Dá para conversar com ela ("como se diz borboleta?", "o que significa went?"), pedir palavra, quiz, piada, dica ou palavrão, e fazer carinho. Igual ao Talking Tom, ela reage a toques no nariz, na bochecha, na barriga e no rabo.
- **🎙️ Conversa ao vivo:** ela fala, te escuta e diz na hora se você falou **correto** ou **errado**. Corrige, manda repetir e segue a conversa sem você precisar tocar em nada. Também repete o que você falou com voz de gatinha, igual ao Talking Tom. Tem 4 modos:
  - **Papo:** perguntas do A1 ao C2.
  - **Repete:** treino de pronúncia.
  - **Traduz:** ela fala em português e você responde em inglês.
  - **Imita:** você fala qualquer coisa, ela imita e aponta os erros.

  A correção usa regras para os erros que brasileiro mais comete ("I have 25 years", "he don't", "I'm agree"…). Não é IA.
- **A Brenda nunca sai da tela:** nas outras abas ela fica flutuando no canto. Tocar nela abre a conversa ao vivo.
- **Dicionário:** inglês ↔ português com 61 mil palavras e expressões em inglês e 48 mil em português. Traz pronúncia, sentidos, definições, exemplos e sinônimos, e reconhece formas como *went → go* e *falou → falar*.
- **Trilha:** 35 aulas do A1 ao C2, com explicação falada e exercícios.
- **Cartões:** flashcards com repetição espaçada, incluindo as 3.000 palavras mais usadas do inglês com tradução revisada e frase de exemplo.
- **Frases:** busca em 23 mil frases reais traduzidas, mais frases prontas por situação.

## Personalidades
- 🔥 **Sem filtro:** palavrão liberado (sem ofensa preconceituosa). Conteúdo adulto.
- 😏 **Debochada:** zoeira leve.
- 😇 **Educada:** sem palavrão.

## Voz e microfone
- A Brenda usa as vozes do próprio aparelho e escolhe sozinha as mais naturais: as vozes neurais do Microsoft Edge (grátis), as vozes "Melhorada"/"Premium" do iPhone e as vozes do Google no Chrome. Em ⚙️ dá para trocar a voz, deixar mais aguda e testar.
- Para ela te ouvir, use Chrome, Edge ou Safari e permita o microfone. No Chrome o reconhecimento de voz precisa de internet. Sem microfone, dá para digitar as respostas.

O progresso fica salvo no `localStorage` do navegador.

## Dicionário: de onde vêm os dados
A pasta `dados` é gerada por `ferramentas/gerar_dicionario.py`, que baixa e junta estas fontes abertas:

| Fonte | O que traz | Licença |
|---|---|---|
| WordNet 3.0 (Princeton) | definições, exemplos e sinônimos em inglês | licença WordNet |
| OpenWN-PT (Open Multilingual Wordnet) | ligação entre palavras em português e inglês | CC BY-SA 3.0 |
| FreeDict inglês ↔ português | traduções e pronúncia (IPA) | GPL 2.0+ |
| Tatoeba (via Tatoeba Challenge) | frases reais com tradução | CC BY 2.0 FR |
| FrequencyWords (OpenSubtitles 2018) | frequência das palavras | CC BY-SA 4.0 |

As traduções das 3.000 palavras mais usadas foram revisadas à mão e ficam em `ferramentas/traducoes_manuais.tsv`.
Os créditos completos estão em `dados/LICENCAS.txt` e na tela de ⚙️ configurações do app.

Para gerar os dados de novo (precisa de Python 3 e internet):

```
python3 ferramentas/gerar_dicionario.py
```
