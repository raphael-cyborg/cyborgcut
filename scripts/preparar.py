"""Prepara o bruto pro agente planejar: cor, voz limpa, transcrição e folha de cada take.

    python scripts/preparar.py <projeto> [--idioma pt] [--backend auto] [--refazer]

`<projeto>` é a pasta com `bruto/` dentro (os arquivos de vídeo). Sai em `<projeto>/trabalho/`:

    sdr/<take>.mp4           vídeo em cor normal e em pé (HDR do celular convertido)
    limpo/<take>.wav         voz sem o ruído de fundo (RNNoise), mono 48 kHz
    transcricoes/<take>.json tempo por palavra
    transcricoes/<take>.txt  a fala, legível, com o segundo de cada frase
    folhas/<take>.jpg        um quadro por segundo, com o segundo escrito
    catalogo.md              o que tem em cada take: duração, tamanho, primeiras palavras
    tempos.tsv               quanto cada etapa levou

É isso que o agente lê antes de escrever o plano. Só refaz o que falta.
"""
from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, str(Path(__file__).resolve().parent))
import transcrever  # noqa: E402
import util  # noqa: E402

HDR = {"arib-std-b67", "smpte2084"}


# ---------------------------------------------------------------- cor
def modo_cor() -> str:
    """Como esta máquina converte HDR pra cor normal."""
    if util.so() == "mac" and util.tem("avconvert"):
        return "avconvert"
    if util.tem_filtro("zscale") and util.tem_filtro("tonemap"):
        return "zscale"
    return "colorspace"


def converter_cor(origem: Path, destino: Path, info: dict, modo: str):
    """HDR (HLG ou PQ) do celular vira cor normal (BT.709). Três caminhos, do melhor pro pior:

    - avconvert (Mac): a conversão da própria Apple, a mais fiel pro HDR do iPhone.
    - zscale + tonemap (ffmpeg do Linux e do Windows): testado lado a lado com o da Apple, igual.
    - colorspace (qualquer ffmpeg): não faz tone mapping, só troca as primárias; fica mais
      lavado, e uma curva em S compensa um pouco. Avisa.
    """
    destino.parent.mkdir(parents=True, exist_ok=True)
    if modo == "avconvert":
        util.run(["avconvert", "-s", origem, "-p", "PresetHighestQuality", "-o", destino, "--replace"],
                 erro=f"avconvert falhou em {origem.name}")
        return
    if modo == "zscale":
        hlg = info["transferencia"] == "arib-std-b67"
        vf = (f"zscale=t=linear:npl={1000 if hlg else 10000},format=gbrpf32le,zscale=p=bt709,"
              f"tonemap=tonemap=hable:desat=0:peak={'10' if hlg else '100'},"
              f"zscale=t=bt709:m=bt709:r=tv,format=yuv420p")
    else:
        util.aviso(f"{origem.name}: ffmpeg sem zscale, cor convertida por aproximação (instale um ffmpeg completo pra ficar fiel)")
        itrc = "arib-std-b67" if info["transferencia"] == "arib-std-b67" else "smpte2084"
        vf = (f"colorspace=all=bt709:iall=bt2020:itrc={itrc}:fast=0,format=yuv420p,"
              "curves=all='0/0 0.25/0.21 0.5/0.5 0.75/0.79 1/1',eq=saturation=1.05")
    util.ffmpeg(["-i", origem, "-vf", vf, "-c:v", "libx264", "-preset", "medium", "-crf", "16",
                 "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", destino],
                erro=f"conversão de cor falhou em {origem.name}")


def normalizar(origem: Path, destino: Path, info: dict):
    """SDR que só precisa ficar em pé (rotação do celular) ou nem isso."""
    destino.parent.mkdir(parents=True, exist_ok=True)
    if info["rotacao"] % 360 == 0 and origem.suffix.lower() == ".mp4":
        util.hardlink_ou_copia(origem.resolve(), destino)
        return
    util.ffmpeg(["-i", origem, "-c:v", "libx264", "-preset", "medium", "-crf", "16", "-c:a", "aac", "-b:a", "192k",
                 "-movflags", "+faststart", destino], erro=f"não consegui reescrever {origem.name}")


# ---------------------------------------------------------------- voz
def limpar_voz(video: Path, destino: Path):
    """Mono 48 kHz, grave de ar cortado, RNNoise com o modelo `sh` (fala de gravação)."""
    destino.parent.mkdir(parents=True, exist_ok=True)
    util.ffmpeg(["-i", video, "-vn", "-ac", "1", "-ar", "48000",
                 "-af", f"highpass=f=80,arnndn=m='{util.caminho_filtro(util.RNNOISE)}'", destino],
                erro=f"limpeza de voz falhou em {video.name}")


# ---------------------------------------------------------------- folhas e catálogo
def folha(video: Path, destino: Path):
    """Um quadro por segundo, 12 por linha, com o segundo escrito no canto (desenhado em Python:
    o ffmpeg do Homebrew vem sem drawtext)."""
    destino.parent.mkdir(parents=True, exist_ok=True)
    tmp = Path(tempfile.mkdtemp(prefix="cyborgcut-folha-"))
    util.ffmpeg(["-i", video, "-vf", "fps=1,scale=160:-2", "-q:v", "4", tmp / "%04d.jpg"], erro=f"quadros falharam em {video.name}")
    quadros = sorted(tmp.glob("*.jpg"))
    if not quadros:
        return
    ims = [Image.open(q).convert("RGB") for q in quadros]
    w, h = ims[0].size
    cols = min(12, len(ims))
    rows = -(-len(ims) // cols)
    f = ImageFont.truetype(str(util.FONTE_MONO), 15)
    out = Image.new("RGB", (cols * (w + 2), rows * (h + 2)), "black")
    for i, im in enumerate(ims):
        d = ImageDraw.Draw(im)
        d.rectangle((0, 0, 44, 20), fill=(0, 0, 0))
        d.text((4, 3), f"{i}s", font=f, fill=(255, 220, 0))
        out.paste(im, ((i % cols) * (w + 2), (i // cols) * (h + 2)))
    out.save(destino, quality=82)


def txt_legivel(tr: dict) -> str:
    """A fala em frases, cada uma com o segundo em que começa."""
    linhas, atual, t0 = [], [], None
    for w in tr["palavras"]:
        if t0 is None:
            t0 = w["inicio"]
        atual.append(w["texto"])
        if w["texto"][-1:] in ".?!" or len(atual) >= 18:
            linhas.append(f"[{t0:6.2f}s] {' '.join(atual)}")
            atual, t0 = [], None
    if atual:
        linhas.append(f"[{t0:6.2f}s] {' '.join(atual)}")
    return "\n".join(linhas) + "\n"


def catalogo(itens: list[dict], modo: str, backend: str) -> str:
    md = ["# Catálogo do bruto", "",
          "Um take por linha. `folhas/<take>.jpg` mostra um quadro por segundo; `transcricoes/<take>.txt` tem a fala com os segundos.", "",
          "| take | duração | quadro | fala | começa dizendo |", "|---|---|---|---|---|"]
    for it in itens:
        fala = "sim" if it["tem_fala"] else "não (imagem de apoio)"
        md.append(f"| `{it['take']}` | {it['duracao']:.1f} s | {it['largura']}x{it['altura']} | {fala} | {it['inicio'] if it['tem_fala'] else '-'} |")
    md += ["", f"Cor convertida por: `{modo}`. Transcritor: `{backend}`.", ""]
    return "\n".join(md)


# ---------------------------------------------------------------- principal
def preparar(projeto: Path, idioma="pt", backend="auto", so_faltantes=True) -> Path:
    projeto = Path(projeto)
    bruto = projeto / "bruto"
    if not bruto.is_dir():
        raise util.Falha(f"não achei {bruto}. O projeto precisa de uma pasta `bruto/` com os vídeos.")
    videos = util.videos_em(bruto)
    if not videos:
        raise util.Falha(f"{bruto} está vazia")
    trab = projeto / "trabalho"
    trab.mkdir(exist_ok=True)
    crono = util.Cronometro(trab / "tempos.tsv")
    modo = modo_cor()
    util.esperar_maquina()
    print(f"{len(videos)} arquivos em {bruto} (cor: {modo}; transcritor: {backend})")
    infos = {}
    a_transcrever = []
    for v in videos:
        take = v.stem
        info = util.info_video(v)
        infos[take] = info
        sdr = trab / "sdr" / f"{take}.mp4"
        limpo = trab / "limpo" / f"{take}.wav"
        tr_json = trab / "transcricoes" / f"{take}.json"
        fol = trab / "folhas" / f"{take}.jpg"
        if not (so_faltantes and sdr.exists()):
            with crono.etapa(f"cor: {take}"):
                if info["transferencia"] in HDR:
                    converter_cor(v, sdr, info, modo)
                else:
                    normalizar(v, sdr, info)
        if info["tem_audio"] and not (so_faltantes and limpo.exists()):
            with crono.etapa(f"voz limpa: {take}"):
                limpar_voz(sdr, limpo)
        if info["tem_audio"] and not (so_faltantes and tr_json.exists()):
            a_transcrever.append((limpo, tr_json))
        if not (so_faltantes and fol.exists()):
            with crono.etapa(f"folha: {take}"):
                folha(sdr, fol)
    if a_transcrever:
        with crono.etapa(f"transcrição de {len(a_transcrever)} takes"):
            transcrever.em_subprocesso(a_transcrever, idioma, backend)
            for _, tr_json in a_transcrever:
                tr = json.loads(tr_json.read_text(encoding="utf-8"))
                tr_json.with_suffix(".txt").write_text(txt_legivel(tr), encoding="utf-8")
    itens, usado = [], backend
    for v in videos:
        take = v.stem
        tr_json = trab / "transcricoes" / f"{take}.json"
        tr = json.loads(tr_json.read_text(encoding="utf-8")) if tr_json.exists() else {"palavras": [], "backend": "-"}
        usado = tr.get("backend", usado)
        info_sdr = util.info_video(trab / "sdr" / f"{take}.mp4")
        dens = len(tr["palavras"]) / max(infos[take]["duracao"], 1e-3)
        itens.append(dict(take=take, duracao=infos[take]["duracao"], largura=info_sdr["largura"], altura=info_sdr["altura"],
                          palavras=len(tr["palavras"]), tem_fala=tr.get("tem_fala", len(tr["palavras"]) >= 4 and dens >= 0.6),
                          inicio=" ".join(w["texto"] for w in tr["palavras"][:8]) + ("…" if len(tr["palavras"]) > 8 else "")))
    (trab / "catalogo.md").write_text(catalogo(itens, modo, usado), encoding="utf-8")
    print(f"pronto: {trab / 'catalogo.md'}")
    return trab


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("projeto", type=Path)
    ap.add_argument("--idioma", default="pt")
    ap.add_argument("--backend", default="auto")
    ap.add_argument("--refazer", action="store_true", help="refaz mesmo o que já existe em trabalho/")
    a = ap.parse_args()
    preparar(a.projeto, a.idioma, a.backend, so_faltantes=not a.refazer)


if __name__ == "__main__":
    main()
