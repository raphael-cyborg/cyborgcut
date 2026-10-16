"""Conferência do vídeo pronto: o que a gente não enxerga olhando por cima.

    python scripts/conferir.py <projeto> [--video saida/x.mp4]

- retranscreve o vídeo final e confere, fala por fala, se a primeira e a última palavra do
  plano estão lá, na ordem (palavra comida no corte aparece aqui);
- procura quadro escuro e piscada de um quadro (erro de montagem clássico);
- mede o volume integrado (alvo das redes: -14 LUFS, tolerância 2);
- escreve `saida/conferencia.md` com tudo e devolve 1 se algo reprovou.

    python scripts/conferir.py <projeto> --comparar referencia.mp4

Monta `saida/lado-a-lado-*.mp4`, a referência à esquerda e o nosso à direita, uma cópia com o
som de cada um (não dá pra tocar os dois juntos).
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import plano as pl  # noqa: E402
import transcrever  # noqa: E402
import util  # noqa: E402


def ultimo_video(projeto: Path) -> Path:
    saida = projeto / "saida"
    vids = sorted((p for p in saida.glob("*.mp4") if not p.name.startswith("lado-a-lado")), key=lambda p: p.stat().st_mtime)
    if not vids:
        raise util.Falha(f"nada em {saida}; rode montar primeiro")
    return vids[-1]


def brilho_por_quadro(video: Path, ate: float | None = None) -> np.ndarray:
    cmd = ["ffmpeg", "-nostdin", "-v", "error", "-i", str(video)]
    if ate:
        cmd += ["-t", f"{ate:.3f}"]
    cmd += ["-vf", "scale=32:56,format=gray", "-f", "rawvideo", "-"]
    raw = subprocess.run(cmd, capture_output=True).stdout
    a = np.frombuffer(raw, np.uint8)
    n = len(a) // (32 * 56)
    return a[: n * 32 * 56].reshape(n, -1).mean(1)


def loudness(video: Path) -> float:
    r = subprocess.run(["ffmpeg", "-nostdin", "-i", str(video), "-af", "ebur128=framelog=quiet", "-f", "null", "-"],
                       capture_output=True, text=True)
    m = re.search(r"I:\s+(-?[\d.]+) LUFS", r.stderr)
    return float(m.group(1)) if m else float("nan")


def conferir(projeto: Path, video: Path | None = None) -> int:
    projeto = Path(projeto)
    video = video or ultimo_video(projeto)
    p = pl.carregar(projeto / "plano.json", projeto / "trabalho")
    linhas = [f"# Conferência de `{video.name}`", ""]
    reprovou = 0

    # 1. fala inteira? Cada fala tem um trecho conhecido na saída (t0..t1): a primeira palavra
    # tem que aparecer no começo dele e a última no fim. Buscar em sequência no texto inteiro
    # errava com palavra curta ("e", "a") que aparece em todo lugar.
    util.esperar_maquina()
    p.resolver_falas()
    p.linha_do_tempo()
    tr = transcrever.em_subprocesso([(video, projeto / "trabalho" / "render" / "retranscricao.json")], p.idioma)[0]
    palavras = p.corrigir(tr["palavras"])

    def parecido(a, b):
        import difflib
        if a == b:
            return True
        r = difflib.SequenceMatcher(None, a, b).ratio()
        return (len(b) >= 4 and r >= 0.8) or (len(b) == 3 and r >= 0.66)

    faltas = []
    for f in p.falas:
        janela = [w for w in palavras if w["fim"] > f.t0 - 0.3 and w["inicio"] < f.t1 + 0.3]
        txt = [pl.limpa(w["texto"]) for w in janela]
        de, ate = pl.limpa(f.de), pl.limpa(f.ate)
        ok_de = any(parecido(x, de) for x in txt[:4])
        ok_ate = any(parecido(x, ate) for x in txt[-4:])
        if not (ok_de and ok_ate):
            # segunda chance: o transcritor engole palavra na emenda de frase; isolado, acerta
            trecho = projeto / "trabalho" / "render" / f"trecho-{f.id}.wav"
            util.ffmpeg(["-ss", f"{max(0, f.t0 - 0.2):.3f}", "-t", f"{f.t1 - f.t0 + 0.5:.3f}", "-i", video, "-vn", "-ac", "1", "-ar", "16000", trecho])
            tr2 = transcrever.em_subprocesso([(trecho, trecho.with_suffix(".json"))], p.idioma)[0]
            txt2 = [pl.limpa(w["texto"]) for w in p.corrigir(tr2["palavras"])]
            ok_de = ok_de or any(parecido(x, de) for x in txt2[:4])
            ok_ate = ok_ate or any(parecido(x, ate) for x in txt2[-4:])
            if ok_de and ok_ate:
                janela = p.corrigir(tr2["palavras"])
        if not (ok_de and ok_ate):
            reprovou += 1
            faltas.append(f"fala `{f.id}` ({f.t0:.1f}s a {f.t1:.1f}s): esperava começar em `{f.de}` e terminar em `{f.ate}`; "
                          f"ouvido: {' '.join(w['texto'] for w in janela)}")
    linhas += ["## Fala", ""]
    if faltas:
        linhas += [f"- ⚠ {x}" for x in faltas]
    else:
        linhas.append(f"- ok: as {len(p.falas)} falas começam e terminam na palavra certa")
    (projeto / "saida" / "retranscricao.txt").write_text(tr["texto"] + "\n", encoding="utf-8")
    linhas += ["", "Retranscrição completa em `saida/retranscricao.txt`.", ""]

    # 2. imagem
    dur = util.duracao(video)
    cartao = float(p.cartao_final.get("duracao", 3.2))
    m = brilho_por_quadro(video, ate=max(1.0, dur - cartao - 0.2))
    escuros = [int(i) for i in np.where(m < 25)[0]]
    pisc = [i for i in range(1, len(m) - 1) if abs(m[i] - m[i - 1]) > 25 and abs(m[i] - m[i + 1]) > 25 and abs(m[i - 1] - m[i + 1]) < 12]
    linhas += ["## Imagem", ""]
    if escuros:
        reprovou += 1
        grupos = np.split(np.array(escuros), np.where(np.diff(escuros) > 1)[0] + 1)
        for g in grupos:
            linhas.append(f"- ⚠ quadro escuro de {g[0] / p.fps:.2f}s a {g[-1] / p.fps:.2f}s ({len(g)} quadros)")
    if pisc:
        reprovou += 1
        linhas.append(f"- ⚠ piscada de um quadro em: {', '.join(f'{i / p.fps:.2f}s' for i in pisc)}")
    if not escuros and not pisc:
        linhas.append(f"- ok: {len(m)} quadros, nenhum escuro, nenhuma piscada")

    # 3. volume
    lufs = loudness(video)
    linhas += ["", "## Volume", ""]
    if abs(lufs + 14) > 2:
        reprovou += 1
        linhas.append(f"- ⚠ {lufs:.1f} LUFS (alvo -14)")
    else:
        linhas.append(f"- ok: {lufs:.1f} LUFS (alvo -14)")

    linhas += ["", "## Veredito", "", "APROVADO" if not reprovou else f"REPROVADO ({reprovou} problema(s))", ""]
    out = projeto / "saida" / "conferencia.md"
    out.write_text("\n".join(linhas), encoding="utf-8")
    print("\n".join(linhas))
    return 0 if not reprovou else 1


def comparar(projeto: Path, referencia: Path, video: Path | None = None):
    """Lado a lado: referência à esquerda, nosso à direita, uma cópia com cada som."""
    projeto = Path(projeto)
    video = video or ultimo_video(projeto)
    from PIL import Image, ImageDraw, ImageFont

    w = 1100
    f = ImageFont.truetype(str(util.FONTE_TITULO), 34)
    f.set_variation_by_axes([800])
    im = Image.new("RGB", (w, 1040), (18, 18, 22))
    d = ImageDraw.Draw(im)
    for x, t in ((270, "REFERÊNCIA"), (830, "CYBORGCUT")):
        d.text((x - f.getlength(t) / 2, 22), t, font=f, fill=(245, 185, 66))
    mold = projeto / "trabalho" / "moldura.png"
    im.save(mold)
    dur = max(util.duracao(referencia), util.duracao(video)) + 0.5
    for som, idx in (("referencia", 1), ("cyborgcut", 2)):
        out = projeto / "saida" / f"lado-a-lado-som-{som}.mp4"
        util.ffmpeg(["-loop", "1", "-i", mold, "-i", referencia, "-i", video, "-filter_complex",
                     "[1:v]scale=540:960:force_original_aspect_ratio=decrease,pad=540:960:(ow-iw)/2:(oh-ih)/2,setsar=1,tpad=stop_mode=clone:stop_duration=10[e];"
                     "[2:v]scale=540:960:force_original_aspect_ratio=decrease,pad=540:960:(ow-iw)/2:(oh-ih)/2,setsar=1,tpad=stop_mode=clone:stop_duration=10[i];"
                     f"[0:v][e]overlay=0:72:shortest=0[a];[a][i]overlay=560:72[v];[{idx}:a]apad[s]",
                     "-map", "[v]", "-map", "[s]", "-t", f"{dur:.2f}", "-r", "30", "-c:v", "libx264", "-preset", "fast",
                     "-crf", "23", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart", out],
                    erro="lado a lado falhou")
        print(out)


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("projeto", type=Path)
    ap.add_argument("--video", type=Path)
    ap.add_argument("--comparar", type=Path)
    a = ap.parse_args()
    if a.comparar:
        comparar(a.projeto, a.comparar, a.video)
    else:
        sys.exit(conferir(a.projeto, a.video))
