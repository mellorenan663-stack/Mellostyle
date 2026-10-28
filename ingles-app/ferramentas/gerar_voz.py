#!/usr/bin/env python3
"""Grava o inglês fixo do app com uma voz neural natural (Kokoro-82M, licença Apache 2.0).

Lê ferramentas/textos_ingles.txt (gerado por extrair_ingles.js) e cria:
  dados/voz/<x>/<id>.mp3   um áudio por frase
  dados/voz/indice.js      a lista de ids que o app consulta antes de tocar

O id é o hash cyrb53 do texto normalizado, igual ao que o app calcula em idVoz().
Só grava o que ainda não existe e apaga os áudios de frases que saíram do app.

Precisa de:
  pip install kokoro-onnx misaki num2words spacy  (+ o modelo en_core_web_sm do spaCy)
  ffmpeg com libmp3lame
  kokoro-v1.0.onnx e voices-v1.0.bin de
  https://github.com/thewh1teagle/kokoro-onnx/releases/tag/model-files-v1.0

Uso: python3 ferramentas/gerar_voz.py --modelo PASTA_DO_MODELO [--processos 4]
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
SAIDA = RAIZ / "dados" / "voz"
TAXA = 24000

VOZ = "af_heart"  # a voz americana mais natural do Kokoro
VELOCIDADE = 0.92  # um pouco mais devagar que o normal: soa natural e fica fácil de entender
KBPS = 40

# Onde o leitor de fonemas erra: letras faladas pelo nome
FONEMAS_FIXOS = {
    "a, e, i, o, u": "ˈA, ˈi, ˈI, ˈO, jˈu",
}
# Textos que precisam ser lidos de outro jeito (telefone se fala número por número)
TEXTOS_FIXOS = {
    "in case of fire, dial 119.": "In case of fire, dial one one nine.",
}

LICENCA = """Voz em inglês da Brenda

Os áudios desta pasta foram gerados com o Kokoro-82M (https://github.com/hexgrad/kokoro),
voz af_heart, licença Apache 2.0, usando o kokoro-onnx (MIT) e o misaki (MIT) para a pronúncia.
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
_kokoro = _g2p = None


def _iniciar(modelo):
    global _kokoro, _g2p
    import onnxruntime as rt
    from kokoro_onnx import Kokoro
    from misaki import en, espeak

    opcoes = rt.SessionOptions()
    opcoes.intra_op_num_threads = 1  # vários processos de 1 thread rendem mais que 1 processo com várias
    opcoes.inter_op_num_threads = 1
    sessao = rt.InferenceSession(str(Path(modelo) / "kokoro-v1.0.onnx"), opcoes, providers=["CPUExecutionProvider"])
    _kokoro = Kokoro.from_session(sessao, str(Path(modelo) / "voices-v1.0.bin"))
    _g2p = en.G2P(trf=False, british=False, fallback=espeak.EspeakFallback(british=False))


def _limpar_audio(audio):
    import numpy as np

    audio = np.asarray(audio, dtype=np.float32)
    acima = np.flatnonzero(np.abs(audio) > 0.004)
    if acima.size:
        ini = max(0, acima[0] - int(0.05 * TAXA))
        fim = min(audio.size, acima[-1] + int(0.08 * TAXA))
        audio = audio[ini:fim]
    pico = float(np.max(np.abs(audio))) if audio.size else 0
    if pico > 0:
        audio = audio * (0.89 / pico)  # -1 dBFS: todas no mesmo volume
    rampa = min(audio.size // 2, int(0.005 * TAXA))
    if rampa:
        audio[:rampa] *= np.linspace(0, 1, rampa, dtype=np.float32)
        audio[-rampa:] *= np.linspace(1, 0, rampa, dtype=np.float32)
    return audio


def _gravar(item):
    i, texto = item
    try:
        fonemas = FONEMAS_FIXOS.get(chave(texto))
        if not fonemas:
            fonemas, _ = _g2p(TEXTOS_FIXOS.get(chave(texto), texto))
        fonemas = "".join(c for c in fonemas if c in _kokoro.tokenizer.vocab).strip()
        if not fonemas:
            return i, texto, "sem fonemas"
        audio, taxa = _kokoro.create(fonemas, voice=VOZ, speed=VELOCIDADE, is_phonemes=True)
        assert taxa == TAXA
        audio = _limpar_audio(audio)
        mp3 = subprocess.run(
            ["ffmpeg", "-loglevel", "error", "-f", "f32le", "-ar", str(TAXA), "-ac", "1", "-i", "pipe:0",
             "-c:a", "libmp3lame", "-b:a", f"{KBPS}k", "-map_metadata", "-1", "-id3v2_version", "0", "-f", "mp3", "pipe:1"],
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
    ap.add_argument("--processos", type=int, default=os.cpu_count() or 2)
    ap.add_argument("--limite", type=int, default=0, help="grava só os N primeiros (pra testar)")
    args = ap.parse_args()

    textos = [t for t in TEXTOS.read_text(encoding="utf-8").splitlines() if t.strip()]
    por_id = {}
    for t in textos:
        i = id_voz(t)
        if i in por_id and chave(por_id[i]) != chave(t):
            sys.exit(f"Colisão de hash entre {por_id[i]!r} e {t!r}: mude o tamanho do id no app e aqui.")
        por_id.setdefault(i, t)
    faltando = [(i, t) for i, t in por_id.items() if not arquivo(i).exists()]
    if args.limite:
        faltando = faltando[: args.limite]
    print(f"{len(por_id)} frases; {len(faltando)} pra gravar com {args.processos} processos", flush=True)

    erros = []
    inicio = time.time()
    if faltando:
        with mp.get_context("spawn").Pool(args.processos, initializer=_iniciar, initargs=(args.modelo,)) as pool:
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
        '(window.SFE_DATA = window.SFE_DATA || {})["voz/indice"] = "' + " ".join(ids) + '";\n', encoding="utf-8")
    (SAIDA / "LICENCA.txt").write_text(LICENCA, encoding="utf-8")
    tamanho = sum(f.stat().st_size for f in SAIDA.glob("*/*.mp3"))
    print(f"{len(ids)} áudios, {tamanho / 1e6:.1f} MB; {len(erros)} erro(s)")
    for texto, erro in erros[:20]:
        print(f"  ERRO {texto!r}: {erro}")


if __name__ == "__main__":
    main()
