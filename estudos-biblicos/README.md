# Lâmpada Bíblica

Aplicativo web de estudos bíblicos, em português, que funciona direto no navegador e não precisa de servidor nem de instalação.

## O que tem

- **Bíblia completa**: os 66 livros e 31.104 versículos da Bíblia Livre. Tem busca por palavra ou referência (`Jo 3:16`), destaques em quatro cores, anotações e marcação de capítulos lidos.
- **Palavras no original**: 117 termos em hebraico e grego, com transliteração, número de Strong, sentido e comentário de estudiosos. No leitor, essas palavras aparecem sublinhadas e abrem a explicação com um toque.
- **Introdução aos 66 livros**: autor, data, contexto, tema, estrutura, como o livro aponta para Cristo e o que disseram os intérpretes.
- **23 estudos aprofundados** de passagens-chave, como Gênesis 1, Isaías 53, João 1, Romanos 8 e 1 Coríntios 13. Cada um traz notas versículo a versículo, palavras no original, a visão dos teólogos e perguntas para refletir.
- **33 teólogos**, de Ireneu a Keller, com ideias principais, obras e uma citação com a fonte indicada.
- **12 doutrinas**: textos-base, como a doutrina se formou e as posições de cada tradição.
- **História**: linha do tempo, impérios, grupos do tempo de Jesus e como o texto bíblico chegou até nós.
- **Como estudar**: método em nove passos, gêneros literários, erros comuns e escolas de interpretação.
- **Planos de leitura**: Panorama em 40 dias, Evangelhos em 30 dias, NT em 90 dias, Salmos em 30 dias e Bíblia em 1 ano.
- **Pergunte ao professor**: explicação de qualquer versículo e conversa livre sobre teologia, feitas pelo Claude. Só funciona quando a página está aberta como Artifact no claude.ai.

## Como abrir

Abra o `index.html` no navegador. Os dados ficam em `dados/`. As notas, os destaques e o progresso ficam salvos no `localStorage` do próprio navegador.

## Fontes e licença do texto bíblico

O texto bíblico é da **Bíblia Livre (BLIVRE)**, publicada sob a licença Creative Commons Atribuição 3.0 Brasil e obtida via [scrollmapper/bible_databases](https://github.com/scrollmapper/bible_databases). Os demais conteúdos (introduções, léxico, estudos e perfis) foram escritos para este app. Neles, as ideias dos teólogos aparecem resumidas, e as citações diretas indicam a obra de origem.
