"""O motor: do plano ao mp4.

    python scripts/montar.py <projeto> [--plano plano.json] [--previa 1,5,9] [--nome saida.mp4]

Cadeia, em ordem:
1. plano → janela de cada fala no take (por palavra), corte medido no áudio limpo, linha do tempo;
2. voz: pedaços do áudio limpo emendados e tratados → `trabalho/render/voz.wav`;
3. a voz montada é transcrita de novo: é daí que saem as palavras no tempo de saída, pra legenda
   e pras âncoras das peças (transcrever os takes crus deixava a legenda até 0,4 s adiantada);
4. apoios e peças ganham tempo de saída;
5. duas camadas de imagem, A (quem fala) e B (apoio), cortadas por quadro;
6. trilha abafada sob a voz + efeitos sintetizados (se o estilo pede);
7. quadro a quadro: câmera, transição do apoio, acabamento, peças, legenda, assinatura, cartão
   final → mp4.

Tudo que é visual vem do `estilo` do plano (ver estilo.py): fonte, legenda, painel, tag,
assinatura, transição, câmera, entrada, acabamento, cartão final, som.
"""
from __future__ import annotations

import copy
import json
import re
import subprocess
import sys
from pathlib import Path

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
import pecas  # noqa: E402
import plano as pl  # noqa: E402
import transcrever  # noqa: E402
import util  # noqa: E402

# cor e contraste por acabamento, feitos no ffmpeg ao cortar as camadas (grão e vinheta são por quadro, em pecas.acabamento)
GRADES = {
    "grao-vinheta": "curves=all='0/0 0.25/0.20 0.5/0.47 0.75/0.77 1/1',eq=saturation=1.06,unsharp=5:5:0.30",
    "neutro": "null",
    "frio": "eq=saturation=0.74:contrast=1.04,colorbalance=rs=-0.04:bs=0.05:rm=-0.03:bm=0.04,curves=all='0/0.015 0.5/0.49 1/0.985'",
    "quente": "curves=all='0/0 0.25/0.19 0.5/0.48 0.75/0.79 1/1',eq=saturation=1.16:contrast=1.05,colorbalance=rs=0.05:gs=0.01:bs=-0.05:rm=0.03:bm=-0.03,unsharp=5:5:0.35",
}
GANHO_TRILHA = {"lofi-calma": -10.0, "groove-leve": -14.0}


# ================================================================ voz e som
def render_voz(p: pl.Plano, render: Path) -> Path:
    """Pedaços do áudio limpo com fade de 12 ms, nível acertado ANTES do compressor (senão ele
    espreme a voz e deixa o ruído onde está), presença, e -14 LUFS no fim."""
    partes, filtros, k = [], [], 0
    for f in p.falas:
        for a, b in p.pedacos(f):
            partes += ["-ss", f"{a:.3f}", "-t", f"{b - a:.3f}", "-i", p.limpo(f.take)]
            filtros.append(f"[{k}:a]afade=t=in:d=0.012,afade=t=out:st={max(0, b - a - 0.015):.3f}:d=0.015[a{k}]")
            k += 1
    cat = "".join(f"[a{i}]" for i in range(k))
    fc = (";".join(filtros) + f";{cat}concat=n={k}:v=0:a=1,loudnorm=I=-20:LRA=9:TP=-3,"
          "acompressor=threshold=-26dB:ratio=2.5:attack=10:release=150:makeup=2,"
          "equalizer=f=180:t=q:w=1:g=-2,equalizer=f=3500:t=q:w=1.2:g=3,loudnorm=I=-14:LRA=7:TP=-1.5[voz]")
    voz = render / "voz.wav"
    util.ffmpeg([*partes, "-filter_complex", fc, "-map", "[voz]", "-ar", "48000", "-ac", "2", voz], erro="montagem da voz falhou")
    return voz


def efeitos(cena, dur: float, render: Path) -> Path:
    """Efeitos discretos sintetizados: sopro nas entradas de apoio e no cartão, tique em item
    marcado, toque em etiqueta e no botão. Baixos de propósito."""
    sr = 48000
    out = np.zeros(int((dur + 1) * sr), np.float32)
    rng = np.random.default_rng(3)

    def coloca(t, sig):
        i = int(max(t, 0) * sr)
        j = min(len(out), i + len(sig))
        out[i:j] += sig[: j - i]

    def sopro(t, d=0.38, g=0.05):
        n = int(d * sr)
        ruido = rng.normal(0, 1, n).astype(np.float32)
        y = np.zeros(n, np.float32)
        a0 = np.linspace(0.02, 0.25, n)
        for i in range(1, n):
            y[i] = y[i - 1] + a0[i] * (ruido[i] - y[i - 1])
        coloca(t - d * 0.6, y * np.sin(np.pi * np.linspace(0, 1, n)) ** 2 * g * 3)

    def tique(t, f=1900, g=0.08):
        n = int(0.05 * sr)
        x = np.arange(n) / sr
        coloca(t, np.sin(2 * np.pi * f * x) * np.exp(-x * 90) * g)

    def toque(t, g=0.12):
        n = int(0.09 * sr)
        x = np.arange(n) / sr
        fr = 240 - 80 * x / x[-1]
        coloca(t, np.sin(2 * np.pi * np.cumsum(fr) / sr) * np.exp(-x * 38) * g)

    sopro(0.15, 0.5, 0.04)
    for a in cena.p.apoios:
        sopro(a.t0, 0.32, 0.035)
    for pc in cena.pecas:
        tipo = pc["tipo"]
        if tipo in ("checklist", "marcos"):
            for it in pc["itens"]:
                tique(it["t"])
        elif tipo == "etiquetas":
            for it in pc["itens"]:
                toque(it["t"])
        elif tipo == "barra":
            tique(pc["acende"], 1500, 0.05)
        elif tipo == "botao" and pc.get("toque"):
            tique(pc["toque"], 2300, 0.09)
            toque(pc["toque"], 0.08)
    sopro(cena.p.total + 0.45, 0.9, 0.05)
    tique(cena.p.total + 1.05, 1200, 0.05)
    import soundfile as sf

    out_p = render / "efeitos.wav"
    sf.write(out_p, np.stack([out, out], 1), sr)
    return out_p


def render_audio(cena, render: Path) -> Path:
    p = cena.p
    dur = p.total + cena.cartao
    voz = render / "voz.wav"
    if p.trilha:
        ganho = GANHO_TRILHA.get(p.trilha.stem, -12.0)
        fc = (f"[1:a]atrim=0:{dur:.2f},asetpts=N/SR/TB,volume={ganho}dB,afade=t=in:d=0.5,"
              f"afade=t=out:st={dur - 1.2:.2f}:d=1.2[tr];"
              f"[0:a]apad=whole_dur={dur:.2f},asplit[v1][v2];"
              f"[tr][v2]sidechaincompress=threshold=0.06:ratio=2.5:attack=30:release=400:makeup=1[trd];"
              f"[v1][trd]amix=inputs=2:duration=first:normalize=0[mix]")
        base = render / "voz_trilha.wav"
        util.ffmpeg(["-i", voz, "-stream_loop", "-1", "-i", p.trilha, "-filter_complex", fc, "-map", "[mix]", "-ar", "48000", base],
                    erro="mistura da trilha falhou")
    else:
        base = render / "voz_trilha.wav"
        util.ffmpeg(["-i", voz, "-af", f"apad=whole_dur={dur:.2f}", base])
    final = render / "audio.wav"
    if cena.e.som == "efeitos":
        fx = efeitos(cena, dur, render)
        util.ffmpeg(["-i", base, "-i", fx, "-filter_complex",
                     "[1:a]volume=0.9[fx];[0:a][fx]amix=inputs=2:duration=first:normalize=0,alimiter=limit=0.89[o]",
                     "-map", "[o]", "-ar", "48000", final], erro="mistura dos efeitos falhou")
    else:
        util.ffmpeg(["-i", base, "-af", "alimiter=limit=0.89", final])
    return final


# ================================================================ imagem
def vf_base(W, H, fps, centro=(0.5, 0.5)):
    """Preenche o quadro de saída e recorta o que sobra, centrado onde o plano disse que o
    falante está (um 16:9 virando 9:16 perde os lados: `centro` escolhe qual lado fica)."""
    cx, cy = centro
    return (f"scale={W}:{H}:force_original_aspect_ratio=increase,"
            f"crop={W}:{H}:(iw-{W})*{cx:.3f}:(ih-{H})*{cy:.3f},setsar=1,fps={fps}")


def fc_caixa(W, H, fps, largura, y, grade):
    """Vídeo deitado dentro de um reel: a imagem inteira numa caixa de `largura` px com o topo
    em `y`, e o próprio vídeo desfocado e escurecido preenchendo o resto. Sobra espaço em cima
    pras peças e embaixo pra legenda."""
    return (f"[0:v]split[a][b];"
            f"[a]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},boxblur=40:8,eq=brightness=-0.28:saturation=0.55[bg];"
            f"[b]scale={largura}:-2:flags=lanczos[fg];"
            f"[bg][fg]overlay=(W-w)/2:{y},setsar=1,fps={fps},{grade}")


def filtro_clipe(p: pl.Plano, grade: str, centro=(0.5, 0.5)) -> list[str]:
    if p.recorte == "caixa":
        return ["-filter_complex", fc_caixa(p.largura, p.altura, p.fps, p.caixa_largura, p.caixa_y, grade)]
    return ["-vf", f"{vf_base(p.largura, p.altura, p.fps, centro)},{grade}"]


class Leitor:
    def __init__(self, path, W, H):
        self.p = subprocess.Popen(["ffmpeg", "-nostdin", "-v", "error", "-i", str(path), "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
                                  stdout=subprocess.PIPE)
        self.n = W * H * 3
        self.W, self.H = W, H

    def proximo(self):
        buf = self.p.stdout.read(self.n)
        if len(buf) < self.n:
            return None
        return Image.frombuffer("RGB", (self.W, self.H), buf, "raw", "RGB", 0, 1)

    def fecha(self):
        try:
            self.p.stdout.close()
            self.p.wait(timeout=5)
        except Exception:
            self.p.kill()


def quadro_em(path, t, W, H, filtro: list[str] | None = None):
    """Um quadro de `path` no segundo `t`; com `filtro`, já recortado e tratado."""
    r = subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-ss", f"{t:.3f}", "-i", str(path), "-frames:v", "1",
                        *(filtro or []), "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], capture_output=True)
    if len(r.stdout) < W * H * 3:
        return Image.new("RGB", (W, H))
    return Image.frombuffer("RGB", (W, H), r.stdout[: W * H * 3], "raw", "RGB", 0, 1)


def zoom(img, z, cx, cy):
    W, H = img.size
    z = max(z, 1.0)
    cw, ch = W / z, H / z
    x = min(max(cx * W - cw / 2, 0), W - cw)
    y = min(max(cy * H - ch / 2, 0), H - ch)
    return img.resize((W, H), Image.BICUBIC, box=(x, y, x + cw, y + ch))


class Cena:
    """Tudo já resolvido em tempo de saída: tomadas, apoios, peças, capítulos, legenda."""

    def __init__(self, p: pl.Plano, projeto: Path):
        self.p = p
        self.projeto = projeto
        self.W, self.H, self.fps = p.largura, p.altura, p.fps
        self.cartao = float(p.cartao_final.get("duracao", 3.2))
        self.a_shots = self._tomadas()
        self.capitulos = [{**c, "t0": p.inicio_capitulo(c["fala"])} for c in p.capitulos]
        self.pecas = self._resolver_pecas()
        self.riscar = {pl.limpa(x) for x in p.bruto.get("riscar", [])}
        self.logo = self._logo()
        self._env = None
        self._ultimo_b = None
        self.vestir(p.estilo)

    def vestir(self, e):
        """Troca o estilo sem refazer corte, voz ou peças (o mural usa isso dezenas de vezes)."""
        self.e = e
        self.ctx = pecas.Ctx(self.W, self.H, pl.cor_hex(self.p.marca["destaque"]), self.p.marca, e,
                             y_pecas=int(self.p.bruto.get("pecas_y", 300)), total=self.p.total)
        self.blocos = pecas.blocos_legenda(self.p.palavras_saida, self.ctx)
        return self

    def com_estilo(self, e):
        return copy.copy(self).vestir(e)

    def _logo(self):
        lg = self.p.marca.get("logo")
        if not lg:
            return None
        q = (self.projeto / lg) if not Path(lg).is_absolute() else Path(lg)
        if not q.exists():
            raise util.Falha(f"logo `{lg}` não existe")
        return Image.open(q).convert("RGBA")

    def _tomadas(self):
        shots = []
        for f in self.p.falas:
            z = pl.ENQUADRAMENTOS[f.enquadramento]
            for a, b, t0 in f.segmentos:
                shots.append(dict(t0=t0, dur=b - a, src=self.p.take(f.take), ent=a, zoom=z, fala=f.id, centro=f.centro))
        for i in range(1, len(shots)):
            q, r = shots[i - 1], shots[i]
            if q["src"] == r["src"] and abs(q["ent"] + q["dur"] - r["ent"]) > 0.05 and q["zoom"] == r["zoom"]:
                esc, cx, cy = r["zoom"]
                r["zoom"] = (1.0, cx, .45) if esc > 1.05 else (1.13, cx, .40)
        return shots

    def _t(self, fid, palavra, n=1, fim=False):
        return self.p.quando(fid, palavra, n, fim)

    def _resolver_pecas(self):
        out = []
        p = self.p
        for raw in p.pecas:
            pc = dict(raw)
            tipo = pc.get("tipo")
            if tipo not in pecas.DESENHA:
                raise util.Falha(f"peça de tipo `{tipo}` não existe; os tipos: {', '.join(pecas.DESENHA)}")
            fid = pc.get("fala")
            if not fid:
                raise util.Falha(f"peça `{tipo}` sem `fala`")
            f = p.fala(fid)
            antecipa = float(pc.get("antecipa", 0.1))
            if pc.get("de"):
                pc["t0"] = self._t(fid, pc["de"], pc.get("n_de", 1)) - antecipa
            else:
                pc["t0"] = f.t0 + 0.05
            if pc.get("ate") in (None, "fim"):
                pc["t1"] = f.t1 - 0.1
            elif pc.get("ate") == "video":
                pc["t1"] = p.total
            else:
                pc["t1"] = self._t(fid, pc["ate"], pc.get("n_ate", 1), fim=True)
            if pc.get("duracao"):
                pc["t1"] = pc["t0"] + float(pc["duracao"])
            if tipo in ("etiquetas", "checklist", "marcos"):
                itens = []
                for it in pc["itens"]:
                    texto, palavra = it[0], it[1]
                    n = it[2] if len(it) > 2 else 1
                    itens.append(dict(texto=texto, t=self._t(fid, palavra, n)))
                pc["itens"] = itens
                if tipo == "checklist" and not pc.get("de"):
                    pc["t0"] = itens[0]["t"] - 0.6
            # peça nunca começa antes da própria fala (senão encosta na peça da fala anterior)
            pc["t0"] = max(pc["t0"], f.t0 + 0.02)
            if tipo == "barra":
                pc["acende"] = self._t(fid, pc["acende"])
            if tipo == "ondas":
                pc["t_a"] = self._t(fid, pc["palavra_a"])
                pc["t_b"] = self._t(fid, pc["palavra_b"])
                pc["une"] = self._t(fid, pc["une"])
            if tipo == "botao":
                pc["toque"] = self._t(fid, pc["toque"]) if pc.get("toque") else None
                if pc.get("ate") is None:
                    pc["t1"] = p.total
            if tipo == "pilula" and not pc.get("texto"):
                pc["texto"] = "AO VIVO"
            if tipo == "titulo" and pc.get("ate") is None and not pc.get("duracao"):
                pc["t1"] = f.t1 - 0.25
            out.append(pc)
        for a in p.apoios:
            if a.rotulo:
                out.append(dict(tipo="pilula", texto=a.rotulo, t0=a.t0 + 0.25, t1=a.t1 - 0.05))
        return out

    # ------------------------------------------------------------ voz pro desenho
    def env_em(self, t):
        if self._env is None:
            import soundfile as sf

            a, sr = sf.read(self.projeto / "trabalho" / "render" / "voz.wav")
            a = a.mean(1) if a.ndim > 1 else a
            h = sr // 100
            n = len(a) // h
            e = np.sqrt((a[:n * h].reshape(n, h) ** 2).mean(1))
            e = np.convolve(e, np.ones(4) / 4, mode="same")
            self._env = e / (np.percentile(e, 98) + 1e-9)
        i = int(t * 100)
        return float(self._env[i]) if 0 <= i < len(self._env) else 0.0

    # ------------------------------------------------------------ quadro
    def a_shot(self, t):
        f = round(t * self.fps)
        for s in self.a_shots:
            if round(s["t0"] * self.fps) <= f < round((s["t0"] + s["dur"]) * self.fps):
                return s
        return self.a_shots[-1]

    def apoio_em(self, t):
        f = round(t * self.fps)
        for k, a in enumerate(self.p.apoios):
            if round(a.t0 * self.fps) <= f < round(a.t1 * self.fps):
                return k, a
        return None, None

    def camera(self, t, fa):
        """Movimento de câmera do estilo sobre a camada A."""
        if self.p.recorte == "caixa":
            return fa  # a caixa já é o enquadramento; zoom aqui cortaria a moldura
        s = self.a_shot(t)
        esc, cx, cy = s["zoom"]
        cam = self.e.camera
        if cam == "avanco":
            prog = min(max((t - s["t0"]) / max(s["dur"], 1e-3), 0.0), 1.0)
            z = esc * (1 + 0.045 * prog)
        elif cam == "zoom-corte":
            z = esc * (1 + 0.06 * (1 - pecas.ease_out((t - s["t0"]) / 0.45)))
        else:
            z = esc
        return zoom(fa, z, cx, cy) if z > 1.001 else fa

    def base(self, t, fa, fb):
        img = self.camera(t, fa)
        k, a = self.apoio_em(t)
        if a is None:
            return img
        movimento = self.e.camera != "fixa" and self.p.recorte != "caixa"
        pb = min(max((t - a.t0) / max(a.t1 - a.t0, 1e-3), 0.0), 1.0)
        imb = zoom(fb, 1.02 + 0.06 * pb, 0.5, 0.5) if movimento else fb
        tr = self.e.transicao_apoio
        dur = {"mascara": 0.3, "deslize": 0.28, "fade": 0.22}.get(tr, 0.0)
        el = (t - a.t0) / dur if dur > 0 else 1.0
        if el >= 1:
            return imb
        anterior = self.p.apoios[k - 1] if k > 0 else None
        if anterior is not None and abs(anterior.t1 - a.t0) < 0.02:
            # apoio emendado em apoio: só uma fusão curta, nada de máscara sobre quem fala
            return Image.blend(self._ultimo_b or imb, imb, pecas.ease_io(el))
        if tr == "fade":
            return Image.blend(img, imb, pecas.ease_io(el))
        if tr == "deslize":
            out = img.copy()
            dx = int(self.W * (1 - pecas.ease_out(el)))
            out.paste(imb, (dx, 0))
            if dx > 0:
                out.paste(img.crop((dx - 3, 0, dx, self.H)).point(lambda v: int(v * 0.3)), (dx - 3, 0))
            return out
        out = img.copy()
        out.paste(imb, (0, 0), pecas.mascara_retangulo(int(min(el, 1) * 100), self.W, self.H))
        return out

    def graficos(self, t):
        c = self.ctx
        cam = Image.new("RGBA", (self.W, self.H), (0, 0, 0, 0))
        if self.e.com_acabamento:
            cam.alpha_composite(pecas.degrades(self.W, self.H))
        pecas.desenha_tag(cam, t, self.capitulos, c)
        for pc in self.pecas:
            pecas.DESENHA[pc["tipo"]](cam, t, pc, c)
        pecas.desenha_legenda(cam, t, self.blocos, c, self.p.destaques, self.p.correcoes, self.riscar)
        fim_fala = self.blocos[-1]["t1"] if self.blocos else self.p.total
        pecas.desenha_assinatura(cam, t, self.env_em, c, alpha=pecas.ease_out(t / 0.5) * (1 - pecas.ease_out((t - fim_fala) / 0.3)))
        return cam

    def quadro(self, t, fa, fb, i):
        acab = self.e.acabamento
        if t >= self.p.total:
            img = pecas.cartao_final(t, self.p.total, self.p.cartao_final, self.logo, self.ctx).convert("RGB")
            return pecas.acabamento(img, i, acab)
        img = self.base(t, fa, fb)
        k, a = self.apoio_em(t)
        if a is not None and t - a.t0 >= 0.3:
            self._ultimo_b = img
        img = pecas.acabamento(img, i, acab).convert("RGBA")
        img.alpha_composite(self.graficos(t))
        ff = (t - (self.p.total - 0.2)) / 0.2
        if ff > 0:
            img = Image.blend(img, pecas.cartao_final(self.p.total, self.p.total, self.p.cartao_final, self.logo, self.ctx), min(ff, 1))
        return img.convert("RGB")

    # ------------------------------------------------------------ quadro solto (mural, prévia sem camadas)
    def quadro_solto(self, t, i=None):
        """Um quadro desenhado direto da fonte, sem as camadas prontas: corta e trata na hora.
        Mais lento por quadro, mas serve pra qualquer estilo sem refazer o corte."""
        i = int(t * self.fps) if i is None else i
        W, H = self.W, self.H
        if t >= self.p.total:
            return self.quadro(t, None, None, i)
        grade = GRADES[self.e.acabamento]
        s = self.a_shot(t)
        fa = quadro_em(s["src"], s["ent"] + (t - s["t0"]), W, H, filtro_clipe(self.p, grade, s["centro"]))
        k, a = self.apoio_em(t)
        fb = Image.new("RGB", (W, H))
        if a is not None:
            fb = quadro_em(self.p.take(a.take), a.entrada + (t - a.t0), W, H, filtro_clipe(self.p, grade, a.centro))
            if t - a.t0 < 0.3 and k > 0 and abs(self.p.apoios[k - 1].t1 - a.t0) < 0.02:
                self._ultimo_b = fb
        return self.quadro(t, fa, fb, i)


# ================================================================ camadas
def render_camadas(cena: Cena, render: Path):
    """Camada A (quem fala, contínua) e camada B (só os apoios, preto no resto), cortadas por
    quadro com o mesmo arredondamento que o desenho usa. Se o apoio é mais curto que o trecho,
    a entrada recua pra não sobrar preto no fim."""
    W, H, fps = cena.W, cena.H, cena.fps
    n_total = round(cena.p.total * fps)
    grade = GRADES[cena.e.acabamento]
    p = cena.p

    def clipe(src, ent, n, o, centro=(0.5, 0.5)):
        util.ffmpeg(["-ss", f"{ent:.3f}", "-i", src, "-frames:v", str(n), "-an", *filtro_clipe(p, grade, centro),
                     "-c:v", "libx264", "-preset", "veryfast", "-crf", "14", "-pix_fmt", "yuv420p", o], erro=f"corte falhou em {Path(src).name}")

    def preto(n, o):
        util.ffmpeg(["-f", "lavfi", "-i", f"color=c=black:s={W}x{H}:r={fps}", "-frames:v", str(n), "-c:v", "libx264",
                     "-preset", "veryfast", "-crf", "14", "-pix_fmt", "yuv420p", o])

    def concat(lista, o):
        txt = render / (o.stem + ".txt")
        txt.write_text("".join(f"file '{Path(x).resolve().as_posix()}'\n" for x in lista), encoding="utf-8")
        util.ffmpeg(["-f", "concat", "-safe", "0", "-i", txt, "-c", "copy", o], erro="emenda das camadas falhou")

    lista = []
    for i, s in enumerate(cena.a_shots):
        n = round((s["t0"] + s["dur"]) * fps) - round(s["t0"] * fps)
        if n <= 0:
            continue
        o = render / f"a{i:02d}.mp4"
        clipe(s["src"], s["ent"], n, o, s["centro"])
        lista.append(o)
    concat(lista, render / "a_roll.mp4")

    lista, cur = [], 0
    for i, a in enumerate(cena.p.apoios):
        f0, f1 = round(a.t0 * fps), round(a.t1 * fps)
        f0 = max(f0, cur)
        if f1 <= f0:
            continue
        if f0 > cur:
            o = render / f"bp{i:02d}.mp4"
            preto(f0 - cur, o)
            lista.append(o)
        src = cena.p.take(a.take)
        dur_src = util.duracao(src)
        ent = max(0.0, min(a.entrada, dur_src - (f1 - f0) / fps - 0.1))
        o = render / f"b{i:02d}.mp4"
        clipe(src, ent, f1 - f0, o, a.centro)
        lista.append(o)
        cur = f1
    if cur < n_total:
        o = render / "bp_fim.mp4"
        preto(n_total - cur, o)
        lista.append(o)
    concat(lista, render / "b_roll.mp4")
    (render / "camadas.json").write_text(json.dumps({"acabamento": cena.e.acabamento, "total": cena.p.total}), encoding="utf-8")


def camadas_servem(cena: Cena, render: Path) -> bool:
    """As camadas prontas valem pra este estilo? (a cor do acabamento é cozida nelas)"""
    a, b, j = render / "a_roll.mp4", render / "b_roll.mp4", render / "camadas.json"
    if not (a.exists() and b.exists() and j.exists()):
        return False
    try:
        d = json.loads(j.read_text(encoding="utf-8"))
    except Exception:
        return False
    return d.get("acabamento") == cena.e.acabamento and abs(d.get("total", -1) - cena.p.total) < 1e-3


# ================================================================ principal
def preparar_cena(projeto: Path, plano_path: Path | None, crono, estilo=None) -> tuple[Cena, Path]:
    projeto = Path(projeto)
    trab = projeto / "trabalho"
    plano_path = plano_path or projeto / "plano.json"
    if not plano_path.exists():
        raise util.Falha(f"não achei {plano_path}; o agente escreve o plano depois de ler trabalho/catalogo.md e o roteiro")
    render = trab / "render"
    render.mkdir(parents=True, exist_ok=True)
    p = pl.carregar(plano_path, trab)
    if estilo is not None:
        import estilo as es

        p.estilo = es.carregar(estilo, projeto=projeto)
    with crono.etapa("medir o corte de cada fala"):
        p.resolver_falas()
        p.linha_do_tempo()
    with crono.etapa("montar e tratar a voz"):
        voz = render_voz(p, render)
    with crono.etapa("transcrever a voz montada"):
        tr = transcrever.em_subprocesso([(voz, render / "voz.json")], p.idioma)[0]
        p.palavras_saida = p.completar_com_takes(p.corrigir(tr["palavras"]))
        n = sum(1 for w in p.palavras_saida if w.get("completado"))
        if n:
            print(f"  {n} palavra(s) que o transcritor engoliu vieram da transcrição do take")
    p.resolver_apoios()
    cena = Cena(p, projeto)
    print(f"fala {p.total:.2f}s + cartão {cena.cartao}s · {len(cena.a_shots)} tomadas · {len(p.apoios)} apoios · "
          f"{len(cena.pecas)} peças · estilo {p.estilo.nome}")
    return cena, render


def folha(arquivos, destino: Path, cols=6):
    ims = [Image.open(x) for x in arquivos]
    cols = min(cols, len(ims))
    rows = -(-len(ims) // cols)
    w, h = ims[0].size
    out = Image.new("RGB", (cols * (w + 6), rows * (h + 6)), "white")
    for i, im in enumerate(ims):
        out.paste(im, ((i % cols) * (w + 6), (i // cols) * (h + 6)))
    out.save(destino, quality=85)


def previa(cena: Cena, render: Path, tempos: list[float], saida: Path):
    pasta = saida / "previa"
    pasta.mkdir(parents=True, exist_ok=True)
    W, H = cena.W, cena.H
    arquivos = []
    for t in tempos:
        im = cena.quadro_solto(t)
        o = pasta / f"pv_{t:06.2f}.jpg"
        im.resize((W // 2, H // 2), Image.LANCZOS).save(o, quality=90)
        arquivos.append(o)
    folha(arquivos, saida / "previa.jpg")
    print(f"prévias em {pasta} e {saida / 'previa.jpg'}")


def montar(projeto: Path, plano_path: Path | None = None, previa_s: str | None = None, nome: str | None = None,
           estilo: str | None = None) -> Path | None:
    projeto = Path(projeto)
    saida = projeto / "saida"
    saida.mkdir(exist_ok=True)
    crono = util.Cronometro(projeto / "trabalho" / "tempos.tsv")
    util.esperar_maquina()
    cena, render = preparar_cena(projeto, plano_path, crono, estilo)
    if previa_s:
        previa(cena, render, [float(x) for x in previa_s.split(",")], saida)
        return None
    with crono.etapa("cortar as duas camadas de imagem"):
        render_camadas(cena, render)
    with crono.etapa("trilha e efeitos"):
        audio = render_audio(cena, render)
    slug = re.sub(r"[^a-z0-9]+", "-", cena.p.titulo.lower()).strip("-") or "video"
    if estilo and not nome:
        slug += "-" + re.sub(r"[^a-z0-9]+", "-", cena.e.nome.lower()).strip("-")
    out = saida / (nome or f"{slug}.mp4")
    n = int(round((cena.p.total + cena.cartao) * cena.fps))
    W, H = cena.W, cena.H
    with crono.etapa("desenhar quadro a quadro e gravar"):
        la, lb = Leitor(render / "a_roll.mp4", W, H), Leitor(render / "b_roll.mp4", W, H)
        enc = subprocess.Popen(["ffmpeg", "-nostdin", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
                                "-r", str(cena.fps), "-i", "-", "-i", str(audio), "-map", "0:v", "-map", "1:a", "-c:v", "libx264",
                                "-threads", util.THREADS, "-preset", "medium", "-crf", "17", "-maxrate", "16M", "-bufsize", "32M", "-pix_fmt", "yuv420p",
                                "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", "-shortest", str(out)], stdin=subprocess.PIPE)
        preto = Image.new("RGB", (W, H))
        for i in range(n):
            t = i / cena.fps
            fa = la.proximo() if t < cena.p.total else None
            fb = lb.proximo() if t < cena.p.total else None
            enc.stdin.write(cena.quadro(t, fa or preto, fb or preto, i).tobytes())
            if i % 300 == 0:
                print(f"  quadro {i}/{n}", flush=True)
        enc.stdin.close()
        enc.wait()
        la.fecha()
        lb.fecha()
    if enc.returncode:
        raise util.Falha("o ffmpeg não fechou o mp4")
    print(f"pronto: {out}")
    return out


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("projeto", type=Path)
    ap.add_argument("--plano", type=Path)
    ap.add_argument("--previa")
    ap.add_argument("--nome")
    ap.add_argument("--estilo")
    a = ap.parse_args()
    montar(a.projeto, a.plano, a.previa, a.nome, a.estilo)
