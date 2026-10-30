#!/usr/bin/env python3
"""Grava o inglês fixo do app com uma voz neural natural (Kokoro-82M, licença Apache 2.0).

Lê ferramentas/textos_ingles.txt (gerado por extrair_ingles.js) e cria, pra cada voz:
  dados/<pasta>/<x>/<id>.mp3   um áudio por frase
  dados/<pasta>/indice.js      a lista de ids que o app consulta antes de tocar
Vozes: brenda (americana, pasta "voz") e jarvis (mordomo britânico com efeito de IA, pasta "voz-jarvis").

O id é o hash cyrb53 do texto normalizado, igual ao que o app calcula em idVoz().
Só grava o que ainda não existe e apaga os áudios de frases que saíram do app.

Precisa de:
  pip install kokoro-onnx misaki num2words spacy  (+ o modelo en_core_web_sm do spaCy)
  ffmpeg com libmp3lame
  kokoro-v1.0.onnx e voices-v1.0.bin de
  https://github.com/thewh1teagle/kokoro-onnx/releases/tag/model-files-v1.0

Uso: python3 ferramentas/gerar_voz.py --modelo PASTA_DO_MODELO [--voz brenda|jarvis] [--processos 4]
"""
import argparse
import multiprocessing as mp
import os
import re
import subprocess
import sys
import time
import unicodedata
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
TEXTOS = RAIZ / "ferramentas" / "textos_ingles.txt"
TAXA = 24000
VELOCIDADE = 0.92  # um pouco mais devagar que o normal: soa natural e fica fácil de entender
KBPS = 40

VOZES = {
    "brenda": {"voz": "af_heart", "britanico": False, "pasta": "voz", "efeito": None,  # a americana mais natural do Kokoro
               "titulo": "Voz em inglês da Brenda", "detalhe": "voz af_heart"},
    # estilo mordomo de IA: voz masculina britânica grave (a mais clara no reconhecedor) e um efeito leve,
    # dois ecos curtinhos (brilho de "sala de computador") e presença; não é a voz de nenhum ator
    "jarvis": {"voz": "bm_lewis", "britanico": True, "pasta": "voz-jarvis",
               "efeito": "highpass=f=75,equalizer=f=220:t=q:w=1:g=-1.5,equalizer=f=3500:t=q:w=1.2:g=2.5,"
                         "aecho=1.0:0.9:16|29:0.16|0.1,volume=0.9,alimiter=limit=0.89:level=false",
               "titulo": "Voz em inglês no estilo mordomo de IA", "detalhe": "voz bm_lewis com um efeito leve de eco"},
}
CONFIG = VOZES["brenda"]
VOZ, SAIDA = CONFIG["voz"], RAIZ / "dados" / CONFIG["pasta"]


def configurar(nome):
    """Escolhe a voz: muda a pasta de saída e o sotaque."""
    global CONFIG, VOZ, SAIDA
    CONFIG = VOZES[nome]
    VOZ, SAIDA = CONFIG["voz"], RAIZ / "dados" / CONFIG["pasta"]


# Onde o leitor de fonemas erra: letras faladas pelo nome (americano, britânico)
FONEMAS_FIXOS = {
    "a, e, i, o, u": ("ˈA, ˈi, ˈI, ˈO, jˈu", "ˈA, ˈiː, ˈI, ˈQ, jˈuː"),
    "ye": ("jˈi", "jˈiː"),  # "you" antigo: o leitor de fonemas não conhece
}
# Palavra solta sai pior sem nada antes ("fish" vira "vish", "slap" vira "is lap"): grava "Oh... fish." de uma vez
# e corta o "Oh..." no silêncio da pausa. Se a pausa não aparecer ou o corte pegar só um pedaço da palavra,
# tenta o próximo apoio; se nenhum der certo, fica a gravação simples. (No britânico o "Oh" muda: sai do leitor.)
APOIOS = ("ˈO... ", "ˈO?! ", "ˈO. ", "ˈɑ... ")
SONS_SOPRADOS = set("fvθðszʃʒ")  # com "h" a gravação simples já sai certa
# Textos que precisam ser lidos de outro jeito (telefone se fala número por número)
TEXTOS_FIXOS = {
    "in case of fire, dial 119.": "In case of fire, dial one one nine.",
}

LICENCA = """{titulo}

Os áudios desta pasta foram gerados com o Kokoro-82M (https://github.com/hexgrad/kokoro),
{detalhe}, licença Apache 2.0, usando o kokoro-onnx (MIT) e o misaki (MIT) para a pronúncia.
"""


def chave(texto):
    """Igual a chaveVoz() no app."""
    t = unicodedata.normalize("NFC", texto)
    t = re.sub(r"[’‘`´]", "'", t)
    t = re.sub(r"[“”\"]", "", t)
    return re.sub(r"\s+", " ", t).strip().lower()


def _imul(a, b):
    return ((a & 0xFFFFFFFF) * (b & 0xFFFFFFFF)) & 0xFFFFFFFF


def cyrb53(texto, semente=0):
    """Hash de 53 bits, igual ao cyrb53() do app (percorre unidades UTF-16, como o JavaScript)."""
    h1 = (0xDEADBEEF ^ semente) & 0xFFFFFFFF
    h2 = (0x41C6CE57 ^ semente) & 0xFFFFFFFF
    dados = texto.encode("utf-16-le")
    for i in range(0, len(dados), 2):
        c = dados[i] | (dados[i + 1] << 8)
        h1 = _imul(h1 ^ c, 2654435761)
        h2 = _imul(h2 ^ c, 1597334677)
    h1 = _imul(h1 ^ (h1 >> 16), 2246822507)
    h1 ^= _imul(h2 ^ (h2 >> 13), 3266489909)
    h2 = _imul(h2 ^ (h2 >> 16), 2246822507)
    h2 ^= _imul(h1 ^ (h1 >> 13), 3266489909)
    return 4294967296 * (2097151 & h2) + (h1 & 0xFFFFFFFF)


def base36(n):
    digitos = "0123456789abcdefghijklmnopqrstuvwxyz"
    s = ""
    while True:
        n, r = divmod(n, 36)
        s = digitos[r] + s
        if not n:
            return s


def id_voz(texto):
    """Igual a idVoz() no app."""
    return base36(cyrb53(chave(texto))).rjust(11, "0")[:10]


def arquivo(i):
    return SAIDA / i[0] / f"{i}.mp3"


# ---------- trabalho de cada processo ----------
_kokoro = _g2p = _cache = None


def _fixos(texto):
    """Fonemas escritos à mão pra esse texto (no sotaque da voz), ou None."""
    par = FONEMAS_FIXOS.get(chave(texto))
    return par[CONFIG["britanico"]] if par else None


def _iniciar(modelo, cache=None, voz="brenda"):
    global _kokoro, _g2p, _cache, APOIOS
    configurar(voz)
    _cache = Path(cache) if cache else None
    import onnxruntime as rt
    from kokoro_onnx import Kokoro
    from misaki import en, espeak

    opcoes = rt.SessionOptions()
    opcoes.intra_op_num_threads = 1  # vários processos de 1 thread rendem mais que 1 processo com várias
    opcoes.inter_op_num_threads = 1
    sessao = rt.InferenceSession(str(Path(modelo) / "kokoro-v1.0.onnx"), opcoes, providers=["CPUExecutionProvider"])
    _kokoro = Kokoro.from_session(sessao, str(Path(modelo) / "voices-v1.0.bin"))
    britanico = CONFIG["britanico"]
    _g2p = en.G2P(trf=False, british=britanico, fallback=espeak.EspeakFallback(british=britanico))
    if britanico:
        oh, ah = (_g2p(p)[0].strip(" .") for p in ("Oh", "Ah"))
        APOIOS = (f"{oh}... ", f"{oh}?! ", f"{oh}. ", f"{ah}... ")


def _precisa_apoio(texto, fonemas):
    palavras, inicio = texto.split(), fonemas.lstrip("ˈˌ")[:1]
    return (len(palavras) == 1 and inicio != "h") or (len(palavras) <= 3 and inicio in SONS_SOPRADOS)


def _duracao_fala(audio):
    import numpy as np

    acima = np.flatnonzero(np.abs(np.asarray(audio)) > 0.0003)
    return (acima[-1] - acima[0]) / TAXA if acima.size else 0


def _com_apoio(fonemas, simples):
    """Grava "Oh... palavra" numa passada só (o create() separaria as frases) e devolve só a palavra, ou None."""
    import numpy as np

    alvo = _duracao_fala(simples)
    if fonemas[-1] not in ".!?…":
        fonemas += "."
    q = TAXA // 200  # 5 ms
    soprado = fonemas.lstrip("ˈˌ")[:1] in SONS_SOPRADOS
    for apoio in APOIOS:
        tokens = _kokoro.tokenizer.tokenize(apoio + fonemas)
        audio, _ = _kokoro._infer(tokens, _kokoro._style_for(_kokoro.voices[VOZ], len(tokens)), VELOCIDADE)
        audio = np.asarray(audio, dtype=np.float32)
        n = len(audio) // q
        blocos = audio[: n * q].reshape(n, q)
        rms = np.sqrt(np.mean(blocos ** 2, axis=1))
        fala = np.flatnonzero(rms > 0.05)
        if not fala.size:
            continue
        cortes = []
        if soprado:
            # a vogal do "Oh" vira chiado (f, s, sh, th): a energia cai e o sinal passa a cruzar o zero o tempo todo
            zcr = np.mean(np.abs(np.diff(np.sign(blocos), axis=1)) > 0, axis=1)
            pico = rms[fala[0] : fala[0] + 40].max()
            for k in range(fala[0] + 10, min(n, fala[0] + 120)):
                if zcr[k] > 0.25 and zcr[k - 1] <= 0.25 and rms[k] < 0.35 * pico:
                    cortes.append(max(0, k - 2) * q)
                    break
        i = fala[0] + 10  # passa do começo do "Oh"
        while i < n and rms[i] > 0.003:  # até o "Oh" acabar
            i += 1
        j = i
        while j < n and rms[j] < 0.003:  # a pausa
            j += 1
        if j - i >= 8 and j < n:  # 40 ms de silêncio e a palavra depois
            cortes.append(max(i, j - 16) * q)  # até 80 ms antes da palavra: o resto da pausa vira atraso
        for corte in cortes:
            palavra = audio[corte:]
            # o corte pode ter caído no fechamento de um "p" ou "t" de dentro da palavra: aí sobra só um pedaço
            if alvo and 0.85 <= _duracao_fala(palavra) / alvo <= 1.3:
                return palavra
    return None


def _comeco_do_chiado(audio):
    """Começa no chiado (f, th, s, sh): tira o restinho do "Oh" que às vezes sobra antes dele."""
    import numpy as np

    q = TAXA // 200
    n = min(len(audio) // q, 60)  # só nos primeiros 300 ms
    blocos = np.asarray(audio[: n * q], dtype=np.float32).reshape(n, q)
    rms = np.sqrt(np.mean(blocos ** 2, axis=1))
    zcr = np.mean(np.abs(np.diff(np.sign(blocos), axis=1)) > 0, axis=1)
    for k in range(n - 3):
        if rms[k] > 0.001 and (zcr[k : k + 4] > 0.35).all():  # 20 ms seguidos de chiado de verdade
            return audio[k * q :]
    return audio


def _limpar_audio(audio):
    import numpy as np

    audio = np.asarray(audio, dtype=np.float32)
    # corta o silêncio das pontas pelo nível a cada 5 ms: o ruído de fundo da voz fica em ~0,0002 e o fim de
    # "fish", "stuff" e "ship" (baixinho, mas não pode sumir) fica acima de 0,001 até quase acabar
    q = TAXA // 200
    n = audio.size // q
    if n:
        rms = np.sqrt(np.mean(audio[: n * q].reshape(n, q) ** 2, axis=1))
        comeco, final = np.flatnonzero(rms > 0.0005), np.flatnonzero(rms > 0.001)
        if comeco.size and final.size:
            audio = audio[max(0, comeco[0] * q - int(0.03 * TAXA)) : min(audio.size, (final[-1] + 1) * q + int(0.08 * TAXA))]
    pico = float(np.max(np.abs(audio))) if audio.size else 0
    if pico > 0:
        audio = audio * (0.89 / pico)  # -1 dBFS: todas no mesmo volume
    rampa = min(audio.size // 2, int(0.005 * TAXA))
    if rampa:
        audio[:rampa] *= np.linspace(0, 1, rampa, dtype=np.float32)
        audio[-rampa:] *= np.linspace(1, 0, rampa, dtype=np.float32)
    return audio


def _gravar(item):
    import numpy as np

    i, texto = item
    try:
        fonemas = _fixos(texto)
        if not fonemas:
            fonemas, _ = _g2p(TEXTOS_FIXOS.get(chave(texto), texto))
        fonemas = "".join(c for c in fonemas if c in _kokoro.tokenizer.vocab).strip()
        if not fonemas:
            return i, texto, "sem fonemas"
        guardado = _cache / f"{i}.npy" if _cache else None
        if guardado and guardado.exists():
            audio = np.load(guardado)
        else:
            simples, taxa = _kokoro.create(fonemas, voice=VOZ, speed=VELOCIDADE, is_phonemes=True)
            assert taxa == TAXA
            audio = _com_apoio(fonemas, simples) if _precisa_apoio(texto, fonemas) else None
            audio = np.asarray(simples if audio is None else audio, dtype=np.float32)
            if guardado:
                np.save(guardado, audio)
        if fonemas.lstrip("ˈˌ")[:1] in "fθsʃ":
            audio = _comeco_do_chiado(audio)
        audio = _limpar_audio(audio)
        mp3 = subprocess.run(
            ["ffmpeg", "-loglevel", "error", "-f", "f32le", "-ar", str(TAXA), "-ac", "1", "-i", "pipe:0",
             *(["-af", CONFIG["efeito"]] if CONFIG["efeito"] else []), "-c:a", "libmp3lame", "-b:a", f"{KBPS}k", "-map_metadata", "-1", "-id3v2_version", "0", "-f", "mp3", "pipe:1"],
            input=audio.tobytes(), capture_output=True, check=True,
        ).stdout
        destino = arquivo(i)
        destino.parent.mkdir(parents=True, exist_ok=True)
        temporario = destino.with_suffix(".tmp")
        temporario.write_bytes(mp3)
        temporario.replace(destino)
        return i, texto, None
    except Exception as e:  # um texto ruim não pode derrubar o resto
        return i, texto, repr(e)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--modelo", required=True, help="pasta com kokoro-v1.0.onnx e voices-v1.0.bin")
    ap.add_argument("--voz", choices=sorted(VOZES), default="brenda")
    ap.add_argument("--processos", type=int, default=os.cpu_count() or 2)
    ap.add_argument("--limite", type=int, default=0, help="grava só os N primeiros (pra testar)")
    ap.add_argument("--refazer-apoio", action="store_true", help="regrava as palavras soltas e frases curtas que usam o apoio")
    ap.add_argument("--cache", help="pasta pra guardar o áudio cru (aí mudar o corte não exige gravar de novo)")
    args = ap.parse_args()
    configurar(args.voz)

    textos = [t for t in TEXTOS.read_text(encoding="utf-8").splitlines() if t.strip()]
    por_id = {}
    for t in textos:
        i = id_voz(t)
        if i in por_id and chave(por_id[i]) != chave(t):
            sys.exit(f"Colisão de hash entre {por_id[i]!r} e {t!r}: mude o tamanho do id no app e aqui.")
        por_id.setdefault(i, t)
    if args.refazer_apoio:
        import espeakng_loader
        from misaki import en, espeak
        from phonemizer.backend.espeak.wrapper import EspeakWrapper

        EspeakWrapper.set_library(espeakng_loader.get_library_path())
        EspeakWrapper.set_data_path(espeakng_loader.get_data_path())
        britanico = CONFIG["britanico"]
        g2p = en.G2P(trf=False, british=britanico, fallback=espeak.EspeakFallback(british=britanico))
        apagados = 0
        for i, t in por_id.items():
            fonemas = _fixos(t) or g2p(TEXTOS_FIXOS.get(chave(t), t))[0] or ""
            inicio = fonemas.lstrip("ˈˌ")[:1] if fonemas else ""
            palavras = len(t.split())
            # o que usava apoio antes (inclusive palavras com "h", que agora voltam pra gravação simples)
            if fonemas and (palavras == 1 or (palavras <= 3 and inicio in SONS_SOPRADOS | {"h"})) and arquivo(i).exists():
                arquivo(i).unlink()
                apagados += 1
        print(f"{apagados} áudios apagados pra regravar com o apoio", flush=True)
    faltando = [(i, t) for i, t in por_id.items() if not arquivo(i).exists()]
    if args.limite:
        faltando = faltando[: args.limite]
    print(f"{len(por_id)} frases; {len(faltando)} pra gravar com {args.processos} processos", flush=True)

    erros = []
    inicio = time.time()
    if faltando:
        if args.cache:
            Path(args.cache).mkdir(parents=True, exist_ok=True)
        with mp.get_context("spawn").Pool(args.processos, initializer=_iniciar, initargs=(args.modelo, args.cache, args.voz)) as pool:
            for n, (i, texto, erro) in enumerate(pool.imap_unordered(_gravar, faltando, chunksize=8), 1):
                if erro:
                    erros.append((texto, erro))
                if n % 200 == 0 or n == len(faltando):
                    passou = time.time() - inicio
                    print(f"  {n}/{len(faltando)} em {passou / 60:.1f} min (falta ~{passou / n * (len(faltando) - n) / 60:.0f} min)", flush=True)

    # índice com o que existe; apaga áudios de frases que saíram do app
    if not args.limite:
        for velho in SAIDA.glob("*/*.mp3"):
            if velho.stem not in por_id:
                velho.unlink()
    ids = sorted(i for i in por_id if arquivo(i).exists())
    SAIDA.mkdir(parents=True, exist_ok=True)
    (SAIDA / "indice.js").write_text(
        f'(window.SFE_DATA = window.SFE_DATA || {{}})["{CONFIG["pasta"]}/indice"] = "' + " ".join(ids) + '";\n', encoding="utf-8")
    (SAIDA / "LICENCA.txt").write_text(LICENCA.format(**CONFIG), encoding="utf-8")
    tamanho = sum(f.stat().st_size for f in SAIDA.glob("*/*.mp3"))
    print(f"{len(ids)} áudios, {tamanho / 1e6:.1f} MB; {len(erros)} erro(s)")
    for texto, erro in erros[:20]:
        print(f"  ERRO {texto!r}: {erro}")


if __name__ == "__main__":
    main()
