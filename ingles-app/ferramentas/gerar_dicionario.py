#!/usr/bin/env python3
"""Gera os dados do dicionário do app (pasta ../dados) a partir de fontes abertas.

Uso:  python3 gerar_dicionario.py [--cache PASTA]

Fontes (baixadas automaticamente para a pasta de cache):
- WordNet 3.0 (Universidade de Princeton), via pacotes npm WNdb 3.0.1 e wndb-with-exceptions 3.0.2
- OpenWN-PT, o WordNet em português (repositório omwn/omw-data)
- FreeDict inglês-português e português-inglês (repositório freedict/fd-dictionaries)
- FrequencyWords, frequência de palavras em legendas de filmes (repositório hermitdave/FrequencyWords)
- Frases do Tatoeba (conjunto de teste eng-por do repositório Helsinki-NLP/Tatoeba-Challenge)

Saída: arquivos .js que o app carrega sob demanda (funcionam abrindo o index.html direto ou no Netlify).
"""
import argparse
import io
import json
import os
import re
import sys
import tarfile
import tempfile
import unicodedata
import urllib.request
import xml.etree.ElementTree as ET
from collections import defaultdict

AQUI = os.path.dirname(os.path.abspath(__file__))
SAIDA = os.path.join(AQUI, "..", "dados")
RAW = "https://raw.githubusercontent.com"
FONTES = {
    "WNdb-3.0.1.tgz": "https://registry.npmjs.org/WNdb/-/WNdb-3.0.1.tgz",
    "wndb-with-exceptions-3.0.2.tgz": "https://registry.npmjs.org/wndb-with-exceptions/-/wndb-with-exceptions-3.0.2.tgz",
    "wn-data-por.tab": f"{RAW}/omwn/omw-data/main/wns/por/wn-data-por.tab",
    "eng-por.tei": f"{RAW}/freedict/fd-dictionaries/master/eng-por/eng-por.tei",
    "por-eng.tei": f"{RAW}/freedict/fd-dictionaries/master/por-eng/por-eng.tei",
    "en_50k.txt": f"{RAW}/hermitdave/FrequencyWords/master/content/2018/en/en_50k.txt",
    "pt_br_50k.txt": f"{RAW}/hermitdave/FrequencyWords/master/content/2018/pt_br/pt_br_50k.txt",
    "tatoeba-eng-por.txt": f"{RAW}/Helsinki-NLP/Tatoeba-Challenge/master/data/test/eng-por/test.txt",
}

# Limites para o dicionário caber bem no celular: (sentidos, exemplos, sinônimos, traduções)
LIMITES_COMUM = (8, 2, 5, 6)    # entre as 20 mil palavras mais usadas
LIMITES_MEDIA = (4, 1, 4, 5)    # entre 20 mil e 50 mil
LIMITES_RARA = (2, 1, 4, 4)     # fora das 50 mil (só entra se tiver tradução)
MAX_DEF = 180
MAX_GLOSA_PT = 70
TAMANHO_PEDACO = 450_000        # bytes por arquivo de dados
TOP_PALAVRAS = 3000


def baixar(cache):
    os.makedirs(cache, exist_ok=True)
    for nome, url in FONTES.items():
        destino = os.path.join(cache, nome)
        if os.path.exists(destino):
            continue
        print("baixando", url)
        with urllib.request.urlopen(url, timeout=120) as r, open(destino + ".tmp", "wb") as f:
            f.write(r.read())
        os.replace(destino + ".tmp", destino)


def sem_acento(s):
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")


def chave_pt(s):
    return re.sub(r"\s+", " ", sem_acento(s.lower())).strip()


def chave_en(s):
    return re.sub(r"\s+", " ", s.lower().replace("’", "'")).strip()


def letra(chave):
    c = chave[:1]
    return c if "a" <= c <= "z" else "0"


def cortar(texto, limite):
    if len(texto) <= limite:
        return texto
    corte = texto[:limite].rsplit(" ", 1)[0]
    return corte.rstrip(",;:") + "…"


# ---------------------------------------------------------------- WordNet 3.0
POS_ARQ = {"n": "noun", "v": "verb", "a": "adj", "r": "adv"}


def ler_wordnet(cache):
    with tarfile.open(os.path.join(cache, "WNdb-3.0.1.tgz")) as t:
        interno = t.extractfile("package/WNdb-3.0.tar.gz").read()
    arquivos = {}
    with tarfile.open(fileobj=io.BytesIO(interno)) as t:
        for m in t.getmembers():
            nome = os.path.basename(m.name)
            if nome.startswith(("data.", "index.")) and nome != "index.sense":
                arquivos[nome] = t.extractfile(m).read().decode("utf-8", "replace")

    synsets = {}
    for p, nome in POS_ARQ.items():
        for linha in arquivos["data." + nome].splitlines():
            if not linha or linha.startswith("  "):
                continue
            campos, _, glosa = linha.partition(" | ")
            f = campos.split()
            n = int(f[3], 16)
            palavras = []
            for i in range(n):
                w = re.sub(r"\([a-z]+\)$", "", f[4 + 2 * i]).replace("_", " ")
                if w not in palavras:
                    palavras.append(w)
            glosa = glosa.strip()
            definicao = re.split(r';\s*"', glosa, maxsplit=1)[0].strip().rstrip(";").strip()
            exemplos = re.findall(r'"([^"]+)"', glosa[len(definicao):])
            synsets[f"{f[0]}-{p}"] = {"pos": p, "w": palavras, "d": definicao, "ex": exemplos}

    # índice: lema -> [(pos, contagem de uso, [synsets em ordem de frequência])]
    indice = defaultdict(list)
    for p, nome in POS_ARQ.items():
        for linha in arquivos["index." + nome].splitlines():
            if not linha or linha.startswith("  "):
                continue
            f = linha.split()
            lema = f[0].replace("_", " ")
            n_syn, n_ptr = int(f[2]), int(f[3])
            uso = int(f[5 + n_ptr])
            offs = f[6 + n_ptr: 6 + n_ptr + n_syn]
            indice[lema].append((p, uso, [f"{o}-{p}" for o in offs]))

    excecoes = {}
    with tarfile.open(os.path.join(cache, "wndb-with-exceptions-3.0.2.tgz")) as t:
        for m in t.getmembers():
            if m.name.endswith(".exc"):
                for linha in t.extractfile(m).read().decode().splitlines():
                    f = linha.split()
                    if len(f) >= 2:
                        forma = f[0].replace("_", " ")
                        excecoes.setdefault(forma, [])
                        for base in f[1:]:
                            base = base.replace("_", " ")
                            if base not in excecoes[forma]:
                                excecoes[forma].append(base)
    return synsets, indice, excecoes


# ---------------------------------------------------------------- OpenWN-PT
def limpar_pt(lemas):
    """Tira variações repetidas ("Bancos" quando já tem "banco") e põe em minúscula o que não é nome próprio."""
    chaves = {chave_pt(w) for w in lemas}
    saida, vistas = [], set()
    for w in lemas:
        k = chave_pt(w)
        if w[:1].isupper() and (k in chaves or len(lemas) > 1):
            w = w[0].lower() + w[1:]
        if k in vistas or (k.endswith("s") and k[:-1] in chaves) or (k.endswith("es") and k[:-2] in chaves):
            continue
        vistas.add(k)
        saida.append(w)
    return saida


def ler_omw(cache):
    por_synset = defaultdict(list)
    for linha in open(os.path.join(cache, "wn-data-por.tab"), encoding="utf-8"):
        if linha.startswith("#"):
            continue
        f = linha.rstrip("\n").split("\t")
        if len(f) < 3 or f[1] != "lemma":
            continue
        off, p = f[0].split("-")
        p = "a" if p == "s" else p
        lema = f[2].strip().replace("_", " ")
        if lema and lema not in por_synset[f"{off}-{p}"]:
            por_synset[f"{off}-{p}"].append(lema)
    return {s: limpar_pt(lemas) for s, lemas in por_synset.items()}


# ---------------------------------------------------------------- FreeDict
TEI = "{http://www.tei-c.org/ns/1.0}"
POS_FD = {"s": "n", "adj": "a", "adjt": "a", "vt": "v", "vi": "v", "vi)": "v", "v": "v", "adv": "r", "ad": "r",
          "pron": "o", "prep": "o", "conj": "o", "art": "o", "num": "o"}


def ler_freedict(caminho):
    """Retorna {cabeçalho: {"ipa": str, "sentidos": [[pos, [traduções]]]}}"""
    raiz = ET.parse(caminho).getroot()
    saida = {}
    for entrada in raiz.iter(TEI + "entry"):
        form = entrada.find(TEI + "form")
        orths = [o.text.strip() for o in form.findall(TEI + "orth") if o.text and o.text.strip()]
        pron = form.find(TEI + "pron")
        ipa = pron.text.strip() if pron is not None and pron.text else ""
        pos_atual = ""
        sentidos = []
        for filho in entrada:
            if filho.tag == TEI + "gramGrp":
                p = filho.find(TEI + "pos")
                pos_atual = POS_FD.get((p.text or "").strip(), "") if p is not None else ""
            elif filho.tag == TEI + "sense":
                trad = []
                for cit in filho.iter(TEI + "cit"):
                    if cit.get("type") == "trans":
                        q = cit.find(TEI + "quote")
                        if q is not None and q.text and q.text.strip() and q.text.strip() not in trad:
                            trad.append(q.text.strip())
                if trad:
                    sentidos.append([pos_atual, trad])
        # gramGrp depois do 1º sentido costuma valer para a entrada toda
        if pos_atual:
            for s in sentidos:
                s[0] = s[0] or pos_atual
        for o in orths:
            item = saida.setdefault(o, {"ipa": ipa, "sentidos": []})
            item["ipa"] = item["ipa"] or ipa
            item["sentidos"].extend(sentidos)
    return saida


# ---------------------------------------------------------------- Frequência e frases
def ler_frequencia(caminho):
    rank = {}
    for i, linha in enumerate(open(caminho, encoding="utf-8"), 1):
        w = linha.split(" ")[0].strip().lower()
        if w and w not in rank:
            rank[w] = i
    return rank


def ler_tatoeba(caminho):
    pares, vistos = [], set()
    for linha in open(caminho, encoding="utf-8"):
        f = linha.rstrip("\n").split("\t")
        if len(f) < 4:
            continue
        en, pt = f[2].strip(), f[3].strip()
        if not en or not pt or "\t" in en + pt:
            continue
        chave = (en.lower(), pt.lower())
        if chave in vistos:
            continue
        vistos.add(chave)
        pares.append((en, pt))
    pares.sort(key=lambda p: (len(p[0]), p[0]))
    return pares


LICENCAS = """Dados do dicionário do app Sem Frescura English
Gerados por ferramentas/gerar_dicionario.py a partir destas fontes abertas.
Os arquivos desta pasta são obras derivadas e seguem as licenças abaixo.

1. WordNet 3.0 (definições, exemplos e sinônimos em inglês)
   WordNet 3.0 Copyright 2006 by Princeton University. All rights reserved.
   Licença WordNet: https://wordnet.princeton.edu/license-and-commercial-use
   THIS SOFTWARE AND DATABASE IS PROVIDED "AS IS" AND PRINCETON UNIVERSITY MAKES NO
   REPRESENTATIONS OR WARRANTIES, EXPRESS OR IMPLIED.

2. OpenWN-PT, o WordNet em português (traduções inglês <-> português)
   de Paiva, Valeria e Rademaker, Alexandre. "Revisiting a Brazilian WordNet", GWC 2012.
   Distribuído pela Open Multilingual Wordnet (https://github.com/omwn/omw-data).
   Licença: Creative Commons Atribuição-CompartilhaIgual 3.0 (CC BY-SA 3.0).

3. FreeDict English-Portuguese e Portuguese-English (traduções e pronúncia IPA)
   https://freedict.org | https://github.com/freedict/fd-dictionaries
   Licença: GNU General Public License versão 2 ou posterior.

4. Tatoeba (frases reais com tradução)
   https://tatoeba.org, via Tatoeba Challenge (https://github.com/Helsinki-NLP/Tatoeba-Challenge).
   Licença: Creative Commons Atribuição 2.0 França (CC BY 2.0 FR).

5. FrequencyWords, de Hermit Dave (frequência das palavras em legendas do OpenSubtitles 2018)
   https://github.com/hermitdave/FrequencyWords
   Licença do conteúdo: Creative Commons Atribuição-CompartilhaIgual 4.0 (CC BY-SA 4.0).

As traduções das 3.000 palavras mais usadas (ferramentas/traducoes_manuais.tsv) foram
revisadas à mão para este app.
"""


# ---------------------------------------------------------------- Lematização do inglês (como o "morphy" do WordNet)
REGRAS_EN = [("s", ""), ("ses", "s"), ("xes", "x"), ("zes", "z"), ("ches", "ch"), ("shes", "sh"), ("men", "man"),
             ("ies", "y"), ("es", "e"), ("es", ""), ("ed", "e"), ("ed", ""), ("ing", "e"), ("ing", ""),
             ("er", ""), ("est", ""), ("er", "e"), ("est", "e")]


def lematizar_en(palavra, existe, excecoes):
    """Formas-base possíveis de uma palavra em inglês (went -> go, dogs -> dog)."""
    saida = [palavra] if existe(palavra) else []
    for base in excecoes.get(palavra, []):
        if existe(base) and base not in saida:
            saida.append(base)
    if saida:
        return saida
    for suf, troca in REGRAS_EN:
        if palavra.endswith(suf):
            base = palavra[: len(palavra) - len(suf)] + troca
            if base and existe(base) and base not in saida:
                saida.append(base)
    return saida


def ler_manuais():
    """traducoes_manuais.tsv: palavra em inglês <TAB> tradução.
    "-" tira a palavra da lista das mais usadas; "=base" diz que a palavra é uma forma de outra (saw -> =see)."""
    manuais = {}
    caminho = os.path.join(AQUI, "traducoes_manuais.tsv")
    if os.path.exists(caminho):
        for linha in open(caminho, encoding="utf-8"):
            if linha.strip() and not linha.startswith("#"):
                en, _, pt = linha.rstrip("\n").partition("\t")
                manuais[en.strip().lower()] = pt.strip()
    return manuais


def gravar(nome, conteudo):
    with open(os.path.join(SAIDA, nome + ".js"), "w", encoding="utf-8") as f:
        f.write(f'SFE_DATA["{nome}"]=' + json.dumps(conteudo, ensure_ascii=False, separators=(",", ":")) + ";\n")


def gravar_pedacos(prefixo, itens):
    """Divide as entradas (já em ordem) em arquivos de ~TAMANHO_PEDACO; devolve a 1ª chave de cada um."""
    pedacos, inicios, atual, tam = [], [], {}, 0
    for k, v in itens:
        t = len(json.dumps(v, ensure_ascii=False, separators=(",", ":")).encode()) + len(k.encode()) + 4
        if atual and tam + t > TAMANHO_PEDACO:
            pedacos.append(atual)
            atual, tam = {}, 0
        if not atual:
            inicios.append(k)
        atual[k] = v
        tam += t
    if atual:
        pedacos.append(atual)
    for i, p in enumerate(pedacos):
        gravar(f"{prefixo}-{i:03d}", p)
    return inicios


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cache", default=os.path.join(tempfile.gettempdir(), "sfe-dicionario-cache"))
    ap.add_argument("--revisar", help="grava aqui a lista das mais usadas com as alternativas, para revisão")
    args = ap.parse_args()
    baixar(args.cache)
    c = lambda n: os.path.join(args.cache, n)

    synsets, indice, excecoes = ler_wordnet(args.cache)
    omw = ler_omw(args.cache)
    fd_en = ler_freedict(c("eng-por.tei"))
    fd_pt = ler_freedict(c("por-eng.tei"))
    rank_en = ler_frequencia(c("en_50k.txt"))
    rank_pt = ler_frequencia(c("pt_br_50k.txt"))
    frases = ler_tatoeba(c("tatoeba-eng-por.txt"))
    manuais = ler_manuais()
    print(f"WordNet: {len(synsets)} synsets, {len(indice)} lemas | OpenWN-PT: {len(omw)} synsets com português")
    print(f"FreeDict: {len(fd_en)} en→pt, {len(fd_pt)} pt→en | Tatoeba: {len(frases)} frases | manuais: {len(manuais)}")

    rpt = lambda w: rank_pt.get(w.lower(), 99999)
    ren = lambda w: rank_en.get(w.lower(), 99999)

    # ------------------------------------------------------------ inglês: [exibição, ipa, rank, sentidos, freedict]
    # sentido: [classe, definição, [exemplos], [sinônimos], [traduções]]
    en = {}
    for lema, por_pos in indice.items():
        chave = chave_en(lema)
        r = rank_en.get(chave, 0)
        tem_pt = any(omw.get(s) for _, _, ss in por_pos for s in ss)
        formas = [w for _, _, ss in por_pos for s in ss for w in synsets[s]["w"] if w.lower() == lema]
        proprio = bool(formas) and all(w[:1].isupper() for w in formas)
        if not r and (not tem_pt or proprio) and lema not in fd_en:
            continue
        n_sent, n_ex, n_sin, n_pt = LIMITES_COMUM if r and r <= 20000 else LIMITES_MEDIA if r else LIMITES_RARA
        if not r and " " in lema:
            n_sent = 1
        # intercala as classes gramaticais: 1º sentido de cada uma, depois o 2º...
        filas = [list(ss) for _, _, ss in sorted(por_pos, key=lambda x: -x[1])]
        ordem = []
        while len(ordem) < n_sent and any(filas):
            for f in filas:
                if f and len(ordem) < n_sent:
                    ordem.append(f.pop(0))
        exibicao = lema if (lema in formas or not formas) else formas[0]
        sentidos = []
        for s in ordem:
            syn = synsets[s]
            outros = [w for w in syn["w"] if w.lower() != lema][:n_sin]
            pts = sorted(omw.get(s, []), key=rpt)[:n_pt]
            sentidos.append([syn["pos"], cortar(syn["d"], MAX_DEF), [cortar(e, 110) for e in syn["ex"][:n_ex]], outros, pts])
        en[chave] = [exibicao, "", r, sentidos, []]

    for cab, item in fd_en.items():
        chave = chave_en(cab)
        e = en.setdefault(chave, [cab, "", rank_en.get(chave, 0), [], []])
        e[1] = e[1] or item["ipa"]
        for p, trad in item["sentidos"][:6]:
            e[4].append([p, trad[:6]])

    # ------------------------------------------------------------ português: [exibição, rank, sentidos, freedict, reverso]
    # sentido: [classe, [palavras em inglês], glosa curta (só quando as palavras em inglês são raras)]
    pt = defaultdict(dict)

    def entrada_pt(w):
        w = w.strip()
        return pt[chave_pt(w)].setdefault(w, [w, rank_pt.get(w.lower(), 0), [], [], []])

    for s, lemas in omw.items():
        syn = synsets.get(s)
        if not syn:
            continue
        ens = sorted(syn["w"], key=ren)[:4]
        melhor = min(ren(w) for w in syn["w"])
        sentido = [syn["pos"], ens] + ([cortar(syn["d"], MAX_GLOSA_PT)] if melhor > 20000 else [])
        for lema in lemas:
            entrada_pt(lema)[2].append((melhor, sentido))
    for cab, item in fd_pt.items():
        e = entrada_pt(cab)
        for _, trad in item["sentidos"]:
            for t in trad:
                if t not in e[3]:
                    e[3].append(t)
        e[3] = e[3][:8]

    reverso = defaultdict(list)
    for cab, item in fd_en.items():
        for _, trad in item["sentidos"]:
            for t in trad:
                t = t.strip()
                if t and "(" not in t and len(t.split()) <= 3 and cab not in reverso[t]:
                    reverso[t].append(cab)
    for t, cabs in reverso.items():
        entrada_pt(t)[4] = sorted(cabs, key=ren)[:8]

    # sentidos em ordem: primeiro os que batem com a tradução do FreeDict, depois os de palavras mais comuns
    for k in pt:
        for e in pt[k].values():
            fd = {w.lower() for w in e[3] + e[4]}
            e[2] = [x for _, x in sorted(e[2], key=lambda m: (not any(w.lower() in fd for w in m[1][1]), m[0]))[:8]]

    # ------------------------------------------------------------ frases: índice de palavras para achar exemplos
    indice_frases = defaultdict(list)
    for i, (fen, _) in enumerate(frases):
        for w in set(re.findall(r"[a-z]+(?:'[a-z]+)?", fen.lower())):
            indice_frases[w].append(i)
    nomes = re.compile(r"\b(Tom|Mary|John|Alice|Bob|Jack|Ken|Bill|Jim|Mike|Lucy|Mr|Mrs)\b")

    def exemplo(lema, formas_palavra):
        """Frase curta do Tatoeba com a palavra (de preferência na forma básica e sem nomes próprios)."""
        melhores = []
        for f in formas_palavra:
            for i in indice_frases.get(f, [])[:400]:
                fen = frases[i][0]
                n = len(fen.split())
                if 3 <= n <= 10:
                    melhores.append((abs(n - 6) + 5 * len(nomes.findall(fen)) + (2 if f != lema else 0), i))
        if not melhores:
            return "", ""
        return frases[min(melhores)[1]]

    formas_de = defaultdict(set)
    for forma, bases in excecoes.items():
        for b in bases:
            formas_de[b].add(forma)

    # ------------------------------------------------------------ as palavras mais usadas (para os cartões)
    def traducao_auto(lema):
        e = en.get(lema)
        if not e:
            return "", []
        cands = []
        for i, (_, trad) in enumerate(e[4][:2]):
            cands += [(t, i) for t in trad[:4]]
        for j, s in enumerate(e[3][:2]):
            cands += [(t, 1 + j) for t in s[4][:4]]
        vistos, ordenados = set(), []
        for t, pen in sorted(cands, key=lambda c: max(rpt(w) for w in chave_pt(c[0]).split() or ["?"]) * (1 + c[1] * 0.6)):
            if chave_pt(t) not in vistos:
                vistos.add(chave_pt(t))
                ordenados.append(t)
        return (ordenados[0] if ordenados else ""), ordenados

    existe = lambda w: w in en or (w in manuais and not manuais[w].startswith("="))
    classes = defaultdict(set)
    for k, pp in indice.items():
        for p, _, _ in pp:
            classes[k].add(p)

    def tem_traducao(w):
        e = en.get(w)
        return bool(e and (any(x[4] for x in e[3] if x[0] in "an") or e[4]))

    def lema_da_lista(token):
        """Forma-base para a lista das mais usadas: saw -> see, hands -> hand, going -> go.
        Mantém adjetivos e substantivos próprios (married, boring, building, teacher)."""
        if token in manuais:
            return manuais[token][1:] if manuais[token].startswith("=") else token
        comum = lambda b: b != token and existe(b) and b in rank_en and rank_en[b] < rank_en.get(token, 99999) * 4
        for b in excecoes.get(token, []):            # irregulares: saw, men, better...
            if comum(b):
                return b
        if len(token) >= 4 and not token.endswith("ss"):  # plural ou 3ª pessoa
            for suf, troca in (("ies", "y"), ("ses", "s"), ("xes", "x"), ("ches", "ch"), ("shes", "sh"), ("es", "e"), ("es", ""), ("s", "")):
                base = token[: len(token) - len(suf)] + troca
                if token.endswith(suf) and comum(base) and classes[base] & {"n", "v"}:
                    return base
        if not tem_traducao(token):                  # -ing e -ed de verbos
            for suf, troca in (("ying", "ie"), ("ing", "e"), ("ing", ""), ("ied", "y"), ("ed", "e"), ("ed", "")):
                base = token[: len(token) - len(suf)] + troca
                if token.endswith(suf) and comum(base) and "v" in classes[base]:
                    return base
        if existe(token):
            return token
        lemas = lematizar_en(token, existe, excecoes)
        return lemas[0] if lemas else token

    contracoes = {"don", "didn", "doesn", "isn", "wasn", "aren", "weren", "couldn", "wouldn", "shouldn", "haven",
                  "hasn", "hadn", "won", "ain", "mustn", "needn", "ll", "ve", "re"}
    top, vistos, revisao = [], set(), []
    for token, r in sorted(rank_en.items(), key=lambda x: x[1]):
        if len(top) >= TOP_PALAVRAS:
            break
        if not re.fullmatch(r"[a-z]+(?:-[a-z]+)?", token) or (len(token) == 1 and token not in ("i", "a")):
            continue
        if token in contracoes and token not in manuais:
            continue
        lema = lema_da_lista(token)
        if lema in vistos:
            continue
        vistos.add(lema)
        auto, alternativas = traducao_auto(lema)
        trad = manuais.get(lema, auto)
        revisao.append(f"{len(top) + 1}\t{token}\t{lema}\t{trad}\t{' | '.join(alternativas[:6])}\t{'M' if lema in manuais else ''}")
        if not trad or trad == "-":
            continue
        formas = {lema, token} | formas_de.get(lema, set())
        if len(lema) >= 3:
            formas |= {lema + "s", lema + "ed", lema + "ing"}
        ex_en, ex_pt = exemplo(lema, formas)
        exib = "I" if lema == "i" else lema if (lema in manuais or lema not in en) else en[lema][0]
        top.append([exib, trad, ex_en, ex_pt])
    if args.revisar:
        open(args.revisar, "w", encoding="utf-8").write("\n".join(revisao) + "\n")

    # ------------------------------------------------------------ gravar
    os.makedirs(SAIDA, exist_ok=True)
    for nome in os.listdir(SAIDA):
        if re.fullmatch(r"(en|pt)-\d{3}\.js|base\.js|frases\.js", nome):
            os.remove(os.path.join(SAIDA, nome))
    ini_en = gravar_pedacos("en", sorted(en.items()))
    ini_pt = gravar_pedacos("pt", sorted((k, list(v.values())) for k, v in pt.items()))
    exc = {f: "|".join(b for b in bs if b in en) for f, bs in excecoes.items() if f not in en and any(b in en for b in bs)}
    total_pt = sum(len(v) for v in pt.values())
    gravar("frases", "\n".join(f"{a}\t{b}" for a, b in frases))
    gravar("base", {
        "pedacos": {"en": ini_en, "pt": ini_pt},
        "exc": exc,
        "top": top,
        "total": {"en": len(en), "pt": total_pt, "frases": len(frases)},
    })
    with open(os.path.join(SAIDA, "LICENCAS.txt"), "w", encoding="utf-8") as f:
        f.write(LICENCAS)
    tamanho = sum(os.path.getsize(os.path.join(SAIDA, n)) for n in os.listdir(SAIDA))
    print(f"inglês: {len(en)} entradas em {len(ini_en)} arquivos | português: {total_pt} em {len(ini_pt)} arquivos")
    print(f"mais usadas: {len(top)} | exceções: {len(exc)} | total gravado: {tamanho / 1e6:.1f} MB")


if __name__ == "__main__":
    main()
