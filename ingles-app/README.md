# Sem Frescura English

App para aprender inglês com a **Brenda**, uma gata professora sem filtro, do zero (A1) até nível nativo (C2).
Não usa IA nem precisa de chave: todo o conteúdo vem dentro do app. É grátis e funciona até sem internet.

## Como usar
Abra o `index.html` no navegador (Chrome recomendado, por causa do microfone) ou publique a pasta inteira no Netlify.
A pasta `dados` precisa ficar junto do `index.html`, porque é nela que está o dicionário.

- **Início:** a Brenda te recebe. Dá para conversar com ela ("como se diz borboleta?", "o que significa went?"), pedir palavra, quiz, piada, dica ou palavrão, e fazer carinho.
- **Dicionário:** inglês ↔ português com 61 mil palavras e expressões em inglês e 48 mil em português. Traz pronúncia, sentidos, definições, exemplos e sinônimos, e reconhece formas como *went → go* e *falou → falar*.
- **Trilha:** 35 aulas do A1 ao C2, com explicação falada e exercícios.
- **Cartões:** flashcards com repetição espaçada, incluindo as 3.000 palavras mais usadas do inglês com tradução revisada e frase de exemplo.
- **Frases:** busca em 23 mil frases reais traduzidas, mais frases prontas por situação.

## Personalidades
- 🔥 **Sem filtro:** palavrão liberado (sem ofensa preconceituosa). Conteúdo adulto.
- 😏 **Debochada:** zoeira leve.
- 😇 **Educada:** sem palavrão.

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
