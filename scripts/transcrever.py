"""Transcrição com tempo por palavra, no backend que a máquina tiver.

    python scripts/transcrever.py audio.wav -o saida.json [--backend auto|mlx|faster|cli] [--idioma pt]
    python scripts/transcrever.py --lote pares.json [--backend ...]   # vários arquivos, modelo carregado uma vez

Saída, sempre no mesmo formato, seja qual for o backend:

    {"idioma": "pt", "duracao": 9.5, "texto": "...", "backend": "mlx",
     "palavras": [{"texto": "Essa", "inicio": 0.94, "fim": 1.48}, ...]}

Backends, na ordem em que o `auto` tenta:
- `mlx`    mlx-whisper, Apple Silicon, roda no chip de vídeo. Rápido. Modelo large-v3-turbo (1,6 GB).
- `faster` faster-whisper, qualquer máquina. Usa CUDA se tiver, senão o processador. large-v3.
- `cli`    whisper-cli (whisper.cpp do Homebrew), com o modelo em ~/.cache/whisper-cpp/.

Na primeira vez o modelo é baixado e fica em cache. Os outros scripts chamam este como
subprocesso: quando ele acaba, a memória do modelo é devolvida à máquina.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import util  # noqa: E402

MODELO_HF = os.environ.get("CYBORGCUT_FASTER_MODEL", "large-v3")
MODELO_MLX = os.environ.get("CYBORGCUT_MLX_MODEL", "mlx-community/whisper-large-v3-turbo")


def _wav16k(entrada: Path) -> Path:
    """Os três backends querem mono 16 kHz."""
    tmp = Path(tempfile.mkdtemp(prefix="cyborgcut-")) / "a16k.wav"
    util.ffmpeg(["-i", entrada, "-vn", "-ac", "1", "-ar", "16000", tmp], erro="não consegui extrair o áudio")
    return tmp


# ---------------------------------------------------------------- backends
# Cada backend devolve uma função `(wav, idioma) -> dict` com o modelo já carregado.
def carrega_mlx():
    import mlx_whisper  # type: ignore

    def f(wav, idioma):
        r = mlx_whisper.transcribe(str(wav), path_or_hf_repo=MODELO_MLX, language=idioma, word_timestamps=True,
                                   condition_on_previous_text=False)
        palavras = []
        for seg in r.get("segments", []):
            for w in seg.get("words", []):
                t = w["word"].strip()
                if t:
                    palavras.append(dict(texto=t, inicio=round(float(w["start"]), 3), fim=round(float(w["end"]), 3)))
        return dict(idioma=r.get("language", idioma), texto=r.get("text", "").strip(), palavras=palavras)

    return f


def carrega_faster():
    from faster_whisper import WhisperModel  # type: ignore

    dispositivo, compute = "cpu", "int8"
    try:
        import ctranslate2  # type: ignore

        if ctranslate2.get_cuda_device_count() > 0:
            dispositivo, compute = "cuda", "float16"
    except Exception:
        pass
    modelo = WhisperModel(MODELO_HF, device=dispositivo, compute_type=compute, cpu_threads=int(util.THREADS))

    def f(wav, idioma):
        segs, info = modelo.transcribe(str(wav), language=idioma, word_timestamps=True, vad_filter=True,
                                       condition_on_previous_text=False)
        palavras, texto = [], []
        for s in segs:
            texto.append(s.text.strip())
            for w in s.words or []:
                t = w.word.strip()
                if t:
                    palavras.append(dict(texto=t, inicio=round(w.start, 3), fim=round(w.end, 3)))
        return dict(idioma=info.language, texto=" ".join(texto), palavras=palavras)

    return f


def _modelo_cli() -> Path | None:
    env = os.environ.get("CYBORGCUT_WHISPER_CLI_MODEL")
    if env and Path(env).exists():
        return Path(env)
    pasta = Path.home() / ".cache" / "whisper-cpp"
    if pasta.exists():
        for nome in ("ggml-large-v3-turbo.bin", "ggml-large-v3-turbo-q5_0.bin", "ggml-large-v3.bin", "ggml-large-v3-q5_0.bin"):
            if (pasta / nome).exists():
                return pasta / nome
        bins = sorted(pasta.glob("ggml-*.bin"))
        if bins:
            return bins[0]
    return None


def carrega_cli():
    modelo = _modelo_cli()
    if modelo is None:
        raise util.Falha("whisper-cli sem modelo: ponha um ggml-*.bin em ~/.cache/whisper-cpp/ ou CYBORGCUT_WHISPER_CLI_MODEL")

    def f(wav, idioma):
        saida = wav.with_suffix("")
        cmd = ["whisper-cli", "-m", modelo, "-l", idioma, "-f", wav, "-ojf", "-of", saida, "-np", "-sow", "-t", util.THREADS]
        nome = modelo.name
        if "large-v3-turbo" in nome:
            cmd += ["--dtw", "large.v3.turbo"]
        elif "large-v3" in nome:
            cmd += ["--dtw", "large.v3"]
        util.run(cmd, erro="whisper-cli falhou")
        d = json.loads(Path(str(saida) + ".json").read_text(encoding="utf-8"))
        palavras, texto = [], []
        for seg in d.get("transcription", []):
            texto.append(seg.get("text", "").strip())
            atual = None
            for tok in seg.get("tokens", []):
                t = tok.get("text", "")
                if t.startswith("[_") or not t.strip():
                    continue
                ini = tok.get("t_dtw", -1)
                ini = ini / 100 if ini and ini > 0 else tok["offsets"]["from"] / 1000
                fim = tok["offsets"]["to"] / 1000
                if t.startswith(" ") or atual is None:
                    if atual:
                        palavras.append(atual)
                    atual = dict(texto=t.strip(), inicio=round(ini, 3), fim=round(fim, 3))
                else:
                    atual["texto"] += t
                    atual["fim"] = round(fim, 3)
            if atual:
                palavras.append(atual)
        return dict(idioma=idioma, texto=" ".join(texto), palavras=palavras)

    return f


CARREGA = {"mlx": carrega_mlx, "faster": carrega_faster, "cli": carrega_cli}


def disponiveis() -> list[str]:
    out = []
    if util.apple_silicon():
        try:
            import mlx_whisper  # noqa: F401

            out.append("mlx")
        except Exception:
            pass
    try:
        import faster_whisper  # noqa: F401

        out.append("faster")
    except Exception:
        pass
    if util.tem("whisper-cli") and _modelo_cli():
        out.append("cli")
    return out


def escolhe(backend: str) -> str:
    if backend != "auto":
        return backend
    ops = disponiveis()
    if not ops:
        raise util.Falha("nenhum transcritor instalado. Mac: `uv pip install -e '.[mac]'`. "
                         "Outros: `uv pip install -e '.[cpu]'`. Ou `brew install whisper-cpp` + modelo.")
    return ops[0]


def _e_palavra(txt: str) -> bool:
    """O Whisper alucina em ruído de loja: "...", "Amém", "Se inscreva no canal". Pontuação
    solta sai aqui; o resto é marcado pela densidade de fala no `_arruma`."""
    return any(ch.isalnum() for ch in txt)


def _arruma(r: dict, entrada: Path, wav: Path, backend: str) -> dict:
    r["duracao"] = round(util.duracao(wav), 3)
    r["backend"] = backend
    r["arquivo"] = str(entrada)
    r["palavras"] = [w for w in r["palavras"] if _e_palavra(w["texto"])]
    t = 0.0
    for w in r["palavras"]:  # tempos monotônicos
        w["inicio"] = max(w["inicio"], t)
        w["fim"] = max(w["fim"], w["inicio"] + 0.02)
        t = w["fim"]
    # Fala de verdade tem umas 2 a 3 palavras por segundo. Meia palavra por segundo num take
    # de 10 s é barulho que o modelo "entendeu": imagem de apoio.
    dens = len(r["palavras"]) / max(r["duracao"], 1e-3)
    r["tem_fala"] = len(r["palavras"]) >= 4 and dens >= 0.6
    r["texto"] = " ".join(w["texto"] for w in r["palavras"]) if r["tem_fala"] else ""
    return r


def transcrever_varios(pares: list[tuple[Path, Path]], idioma="pt", backend="auto") -> list[dict]:
    """Carrega o modelo uma vez e transcreve todos. Escreve cada JSON de saída."""
    backend = escolhe(backend)
    f = CARREGA[backend]()
    out = []
    for entrada, saida in pares:
        wav = _wav16k(Path(entrada))
        r = _arruma(f(wav, idioma), Path(entrada), wav, backend)
        Path(saida).parent.mkdir(parents=True, exist_ok=True)
        Path(saida).write_text(json.dumps(r, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"  {Path(saida).name}  ({len(r['palavras'])} palavras, {r['duracao']:.1f}s, {backend})", flush=True)
        out.append(r)
    return out


def transcrever(entrada: Path, idioma="pt", backend="auto") -> dict:
    return transcrever_varios([(Path(entrada), Path(tempfile.mkdtemp(prefix="cyborgcut-")) / "t.json")], idioma, backend)[0]


def em_subprocesso(pares: list[tuple[Path, Path]], idioma="pt", backend="auto") -> list[dict]:
    """Roda este script num processo à parte: o modelo some da memória quando acaba."""
    lote = Path(tempfile.mkdtemp(prefix="cyborgcut-")) / "lote.json"
    lote.write_text(json.dumps([[str(a), str(b)] for a, b in pares]), encoding="utf-8")
    r = subprocess.run([sys.executable, str(Path(__file__).resolve()), "--lote", str(lote), "--idioma", idioma, "--backend", backend],
                       capture_output=True, text=True)
    if r.returncode:
        raise util.Falha("transcrição falhou:\n" + (r.stderr or r.stdout)[-1500:])
    for linha in r.stdout.splitlines():
        if linha.strip():
            print(linha, flush=True)
    return [json.loads(Path(b).read_text(encoding="utf-8")) for _, b in pares]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("entrada", type=Path, nargs="?")
    ap.add_argument("-o", "--saida", type=Path)
    ap.add_argument("--lote", type=Path, help="JSON com lista de [entrada, saida]")
    ap.add_argument("--idioma", default="pt")
    ap.add_argument("--backend", default="auto", choices=["auto", *CARREGA])
    a = ap.parse_args()
    if a.lote:
        pares = [(Path(x), Path(y)) for x, y in json.loads(a.lote.read_text(encoding="utf-8"))]
        transcrever_varios(pares, a.idioma, a.backend)
        return
    if not a.entrada:
        ap.error("passe um arquivo ou --lote")
    saida = a.saida or a.entrada.with_suffix(".json")
    transcrever_varios([(a.entrada, saida)], a.idioma, a.backend)


if __name__ == "__main__":
    main()
