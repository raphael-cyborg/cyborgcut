"""As peças desenhadas por cima do vídeo, vestidas pelo estilo.

Cada peça é `desenha_<tipo>(cam, t, p, ctx)`: recebe a camada transparente do quadro, o segundo
atual, a peça já resolvida (com `t0`, `t1` e os campos do plano) e o contexto (tamanho, cores,
fontes e o `estilo`). Toda peça entra e sai com movimento curto; nada aparece de uma vez.

Regra de desenho que custou caro descobrir: o Pillow SUBSTITUI o pixel quando desenha texto
translúcido em cima de uma camada já preenchida (vira buraco no painel). Por isso texto vai
sempre numa camada própria e entra por `alpha_composite`. É o `escreve()` daqui.
"""
from __future__ import annotations

from functools import lru_cache

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

import estilo as es
import util

BRANCO = (248, 246, 241)
GRAFITE = (18, 19, 22)
VERMELHO = (255, 72, 66)


# ================================================================ base
def ease_out(x):
    x = min(max(x, 0.0), 1.0)
    return 1 - (1 - x) ** 3


def ease_io(x):
    x = min(max(x, 0.0), 1.0)
    return 4 * x ** 3 if x < 0.5 else 1 - (-2 * x + 2) ** 3 / 2


def mola(x):
    x = min(max(x, 0.0), 1.0)
    return 1 - np.exp(-6 * x) * np.cos(9 * x)


@lru_cache(maxsize=None)
def _fonte(arquivo: str, tam: int, peso) -> ImageFont.FreeTypeFont:
    f = ImageFont.truetype(arquivo, tam)
    if peso is not None:
        try:
            vals = []
            for ax in f.get_variation_axes():
                tag = ax.get("name", b"")
                tag = tag.decode() if isinstance(tag, bytes) else str(tag)
                if "eight" in tag or tag == "wght":
                    vals.append(min(max(peso, ax.get("minimum", peso)), ax.get("maximum", peso)))
                else:
                    vals.append(ax["default"])
            f.set_variation_by_axes(vals)
        except Exception:
            pass
    return f


def fonte(tam: int, peso=720) -> ImageFont.FreeTypeFont:
    """Atalho: a fonte padrão do título (Montserrat) num tamanho e peso."""
    return _fonte(str(util.FONTE_TITULO), tam, peso)


def com_alpha(img: Image.Image, a: float) -> Image.Image:
    if a >= 0.999:
        return img
    arr = np.array(img)
    arr[..., 3] = (arr[..., 3].astype(np.float32) * max(a, 0.0)).astype(np.uint8)
    return Image.fromarray(arr)


def escreve(cam: Image.Image, xy, txt: str, f, cor, alpha: float = 1.0):
    """Texto misturado de verdade com o que já está na camada."""
    if alpha <= 0.003 or not txt:
        return
    bb = f.getbbox(txt)
    w, h = int(bb[2]) + 8, int(bb[3]) + 8
    lay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    ImageDraw.Draw(lay).text((0, 0), txt, font=f, fill=tuple(cor) + (int(255 * min(alpha, 1)),))
    x, y = int(round(xy[0])), int(round(xy[1]))
    sx, sy, dx, dy = max(-x, 0), max(-y, 0), max(x, 0), max(y, 0)
    w2, h2 = min(lay.width - sx, cam.width - dx), min(lay.height - sy, cam.height - dy)
    if w2 <= 0 or h2 <= 0:
        return
    cam.alpha_composite(lay.crop((sx, sy, sx + w2, sy + h2)), (dx, dy))


def texto_sombra(cam, xy, txt, f, cor, alpha=1.0, sombra=110):
    if alpha <= 0.003 or not txt:
        return
    sh = Image.new("RGBA", cam.size, (0, 0, 0, 0))
    ImageDraw.Draw(sh).text((xy[0], xy[1] + 4), txt, font=f, fill=(0, 0, 0, int(sombra * alpha)))
    cam.alpha_composite(sh.filter(ImageFilter.GaussianBlur(7)))
    escreve(cam, xy, txt, f, cor, alpha)


def texto_contorno(cam, xy, txt, f, cor, alpha=1.0, contorno=8):
    if alpha <= 0.003:
        return
    bb = f.getbbox(txt)
    w, h = int(bb[2]) + 40, int(bb[3]) + 40
    lay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    ImageDraw.Draw(lay).text((20, 20), txt, font=f, fill=tuple(cor) + (255,), stroke_width=contorno, stroke_fill=(0, 0, 0, 255))
    cam.alpha_composite(com_alpha(lay, alpha), (int(xy[0]) - 20, int(xy[1]) - 20))


class Ctx:
    """O que toda peça precisa: tamanho, cores, fontes e o estilo escolhido."""

    def __init__(self, largura, altura, destaque, marca, estilo: es.Estilo, y_pecas=300, total=1.0):
        self.W, self.H = largura, altura
        self.destaque = tuple(destaque)
        self.marca = marca
        self.e = estilo
        self.y_pecas = y_pecas
        self.total = total              # duração da fala, pras assinaturas de progresso
        self.margem = 64 if largura <= 1200 else 96
        self.escala = largura / 1080
        self._ft = str(estilo.fonte_arquivo("fonte_titulo"))
        self._fx = str(estilo.fonte_arquivo("fonte_texto"))
        self._fm = str(util.FONTE_MONO)

    def px(self, v):
        return int(v * self.escala)

    def cor(self, nome):
        return self.destaque if nome in ("destaque", "ouro", "amarelo", "cor") else BRANCO

    # fontes
    def ft(self, tam, peso=None):
        return _fonte(self._ft, self.px(tam), self.e.peso_titulo() if peso is None else peso)

    def fx(self, tam, peso=None):
        return _fonte(self._fx, self.px(tam), self.e.peso_texto() if peso is None else peso)

    def fm(self, tam):
        return _fonte(self._fm, self.px(tam), None)

    def fx_forte(self, tam):
        p = self.e.peso_texto()
        return self.fx(tam, None if p is None else min(900, p + 200))

    # painel
    @property
    def texto_painel(self):
        return GRAFITE if self.e.painel_claro else BRANCO

    def painel(self, w, h, a=None):
        p = Image.new("RGBA", (int(w), int(h)), (0, 0, 0, 0))
        d = ImageDraw.Draw(p)
        est = self.e.painel
        if est == "escuro-arredondado":
            d.rounded_rectangle((0, 0, w - 1, h - 1), radius=self.px(30), fill=(12, 12, 14, a or 200))
            d.rounded_rectangle((0, 0, w - 1, h - 1), radius=self.px(30), outline=(255, 255, 255, 40), width=2)
        elif est == "claro-arredondado":
            d.rounded_rectangle((0, 0, w - 1, h - 1), radius=self.px(24), fill=(255, 255, 255, a or 225))
        elif est == "blocos-cor":
            pass  # cada item desenha seu bloco
        else:  # linhas
            pass
        return p

    def entra(self, x):
        """Curva de entrada do estilo: mola, suave ou seca."""
        if self.e.entrada == "mola":
            return mola(x)
        if self.e.entrada == "seca":
            return 1.0 if x > 0 else 0.0
        return ease_out(x)


def entra_sai(c: Ctx, t, t0, t1, dentro=0.3, fora=0.3):
    return min(c.entra((t - t0) / dentro), 1.0) * (1 - ease_out((t - t1) / fora))


def _caixa(c: Ctx, txt: str, titulo=False):
    alta = c.e.titulo_em_caixa_alta if titulo else c.e.legenda_em_caixa_alta
    return txt.upper() if alta else txt


# ================================================================ peças de texto
def desenha_titulo(cam, t, p, c: Ctx):
    """Duas linhas grandes no topo, entram linha a linha subindo por uma máscara."""
    if t >= p["t1"] + 0.3:
        return
    sai = ease_out((t - p["t1"]) / 0.3)
    caps = c.e.titulo_em_caixa_alta
    tam = {"bebas": 150, "oswald": 96, "playfair": 92, "space-grotesk": 80, "inter": 80}.get(c.e.fonte_titulo, 84)
    f = c.ft(tam)
    passo = c.px(int(tam * 1.12))
    y = c.px(p.get("y", c.y_pecas + 18))
    for i, (txt, cor) in enumerate(p["linhas"]):
        k = c.entra((t - p["t0"] - 0.12 - i * 0.14) / 0.42)
        if k <= 0:
            continue
        txt = txt.upper() if caps else txt
        h = passo
        lay = Image.new("RGBA", (c.W, h + 40), (0, 0, 0, 0))
        if c.e.painel == "blocos-cor" and cor != "branco":
            lw = f.getlength(txt)
            ImageDraw.Draw(lay).rectangle((c.margem - c.px(12), (1 - k) * h + c.px(8), c.margem + lw + c.px(14), (1 - k) * h + h - c.px(6)), fill=c.destaque + (int(255 * (1 - sai)),))
            escreve(lay, (c.margem, (1 - k) * h - 8), txt, f, GRAFITE, alpha=1 - sai)
        else:
            texto_sombra(lay, (c.margem, (1 - k) * h - 8), txt, f, c.cor(cor), alpha=1 - sai, sombra=130)
        cam.alpha_composite(lay.crop((0, 0, c.W, h + 16)), (0, int(y + i * passo - sai * 40)))
    if c.e.fonte_titulo == "playfair" and t > p["t0"] + 0.6:
        k = ease_out((t - p["t0"] - 0.6) / 0.4) * (1 - sai)
        lin = Image.new("RGBA", (c.px(140), c.px(6)), (0, 0, 0, 0))
        ImageDraw.Draw(lin).rectangle((0, 0, c.px(120) * k, c.px(3)), fill=c.destaque + (255,))
        cam.alpha_composite(lin, (c.margem, int(y + len(p["linhas"]) * passo + c.px(10))))


def desenha_texto(cam, t, p, c: Ctx):
    """Rótulo grande no meio da tela com faixa."""
    if not (p["t0"] <= t < p["t1"] + 0.2):
        return
    a = entra_sai(c, t, p["t0"], p["t1"], 0.22, 0.18)
    f = c.ft(96)
    linhas = p["linhas"] if isinstance(p.get("linhas"), list) else [[p["texto"], "branco"]]
    linhas = [[_caixa(c, l, True), cor] for l, cor in linhas]
    pad_x, pad_y, gap = c.px(34), c.px(18), c.px(12)
    alt = [f.getbbox(l)[3] - f.getbbox(l)[1] for l, _ in linhas]
    larg = max(f.getlength(l) for l, _ in linhas)
    hbox = sum(alt) + gap * (len(linhas) - 1) + pad_y * 2
    lay = Image.new("RGBA", (int(larg + pad_x * 2), int(hbox + 30)), (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    if c.e.painel == "blocos-cor":
        d.rectangle((0, 0, lay.width - 1, hbox), fill=c.destaque + (255,))
        cor_txt = lambda cor: GRAFITE  # noqa: E731
    elif c.e.painel_claro:
        d.rounded_rectangle((0, 0, lay.width - 1, hbox), radius=14, fill=(255, 255, 255, 230))
        cor_txt = lambda cor: c.destaque if cor != "branco" else GRAFITE  # noqa: E731
    else:
        d.rounded_rectangle((0, 0, lay.width - 1, hbox), radius=14, fill=(16, 16, 16, 215))
        d.rectangle((0, hbox - 8, lay.width - 1, hbox), fill=c.destaque + (255,))
        cor_txt = c.cor
    y = pad_y
    for (l, cor), h in zip(linhas, alt):
        bb = f.getbbox(l)
        escreve(lay, ((lay.width - f.getlength(l)) / 2, y - bb[1]), l, f, cor_txt(cor))
        y += h + gap
    k_in = c.entra((t - p["t0"]) / 0.22)
    y0 = c.px(p.get("y", c.y_pecas + 320))
    cam.alpha_composite(com_alpha(lay, a), ((c.W - lay.width) // 2, int(y0 + 40 * (1 - min(k_in, 1)))))


def desenha_contador(cam, t, p, c: Ctx):
    """Número que conta até o valor, com rótulo."""
    if not (p["t0"] <= t < p["t1"] + 0.3):
        return
    a = entra_sai(c, t, p["t0"], p["t1"], 0.25, 0.3)
    alvo = str(p["valor"])
    num = "".join(ch for ch in alvo if ch.isdigit() or ch in ",.")
    sufixo = alvo[len(num):] if alvo.startswith(num) else ""
    try:
        val = float(num.replace(",", "."))
    except ValueError:
        val = 0.0
    k = ease_io((t - p["t0"]) / 1.1)
    dec = len(num.split(",")[1]) if "," in num else (len(num.split(".")[1]) if "." in num else 0)
    atual = val * k if val > 0 else 0.0
    txt = (f"{atual:.{dec}f}".replace(".", ",") if "," in num or dec == 0 else f"{atual:.{dec}f}") + sufixo
    f = c.ft(170 if len(txt) > 2 else 250)
    base = c.px(p.get("y", c.y_pecas))
    lay = Image.new("RGBA", (c.W, c.px(300)), (0, 0, 0, 0))
    texto_sombra(lay, (c.margem, 0), txt, f, c.destaque if k > 0.99 else BRANCO, alpha=a, sombra=140)
    cam.alpha_composite(lay, (0, base))
    rot = p.get("rotulo")
    if rot:
        q = ease_out((t - p["t0"] - 0.5) / 0.4)
        f2 = c.fx(44)
        y = base + (c.px(212) if len(txt) > 2 else c.px(72))
        x = c.margem + (0 if len(txt) > 2 else f.getlength(txt) + c.px(30))
        for i, linha in enumerate(str(rot).split("\n")):
            texto_sombra(cam, (x, y + i * c.px(58) + (1 - q) * 16), linha, f2, BRANCO, alpha=a * q)


# ================================================================ listas
def _marcador(c: Ctx, d: ImageDraw.ImageDraw, x, cy, ok: float, i: int, lay: Image.Image, claro: bool):
    """Marca do item: check, número, traço ou bloco, conforme o estilo."""
    cor_on = c.destaque
    cor_txt_check = GRAFITE if not claro else (255, 255, 255)
    cor_off = (30, 30, 34, 90) if claro else (255, 255, 255, 120)
    m = c.e.marcador
    if m == "numero":
        f = c.ft(40) if c.e.fonte_titulo == "playfair" else c.fm(28)
        escreve(lay, (x, cy - c.px(22)), f"{i + 1:02d}", f, cor_on if ok > 0.5 else (GRAFITE if claro else BRANCO), 0.45 + 0.55 * ok)
        return c.px(70)
    if m == "traco":
        w = c.px(28)
        d.rounded_rectangle((x, cy - 3, x + w * (0.4 + 0.6 * ok), cy + 3), radius=3, fill=(cor_on if ok > 0.5 else (cor_off[:3])) + (255,))
        return c.px(48)
    if m == "bloco":
        s = c.px(18)
        d.rectangle((x, cy - s, x + 2 * s, cy + s), outline=cor_off, width=2)
        if ok > 0:
            q = ease_out(ok * 1.3)
            d.rectangle((x, cy + s - 2 * s * q, x + 2 * s, cy + s), fill=cor_on + (255,))
        return c.px(60)
    # check
    r = c.px(20)
    cx = x + r
    d.ellipse((cx - r, cy - r, cx + r, cy + r), outline=cor_off, width=3)
    if ok > 0:
        rr = r * ease_out(ok * 1.4)
        d.ellipse((cx - rr, cy - rr, cx + rr, cy + rr), fill=cor_on + (255,))
        k = ease_out((ok - 0.3) / 0.7)
        p1, p2, p3 = (cx - 9, cy + 1), (cx - 3, cy + 8), (cx + 10, cy - 7)
        if 0 < k < 0.4:
            q = k / 0.4
            d.line([p1, (p1[0] + (p2[0] - p1[0]) * q, p1[1] + (p2[1] - p1[1]) * q)], fill=cor_txt_check + (255,), width=4)
        elif k >= 0.4:
            q = (k - 0.4) / 0.6
            d.line([p1, p2, (p2[0] + (p3[0] - p2[0]) * q, p2[1] + (p3[1] - p2[1]) * q)], fill=cor_txt_check + (255,), width=4)
    return c.px(64)


def desenha_checklist(cam, t, p, c: Ctx):
    """Itens que vão sendo marcados quando a palavra é dita, no painel do estilo."""
    itens = p["itens"]
    if not (p["t0"] <= t < p["t1"] + 0.3):
        return
    a = entra_sai(c, t, p["t0"], p["t1"], 0.35, 0.3)
    y0 = int(c.px(p.get("y", c.y_pecas + 12)) + (1 - a) * 20)
    est = c.e.painel
    if est == "blocos-cor":
        f = c.fx_forte(46)
        row, gap = c.px(86), c.px(18)
        for i, it in enumerate(itens):
            e = c.entra((t - p["t0"] - 0.08 * i) / 0.35)
            ok = ease_out((t - it["t"]) / 0.3)
            y = y0 + i * (row + gap)
            bar = Image.new("RGBA", (c.W - 2 * c.margem, row), (0, 0, 0, 0))
            d = ImageDraw.Draw(bar)
            d.rectangle((0, 0, bar.width - 1, row - 1), fill=(c.destaque + (255,)) if ok > 0.5 else (0, 0, 0, 170))
            escreve(bar, (c.px(32), c.px(16)), _caixa(c, it["texto"]), f, GRAFITE if ok > 0.5 else BRANCO, 1 if ok > 0.5 else 0.7)
            if ok > 0.5:
                d.line([(bar.width - c.px(86), c.px(44)), (bar.width - c.px(70), c.px(60)), (bar.width - c.px(42), c.px(28))], fill=GRAFITE + (255,), width=7)
            cam.alpha_composite(com_alpha(bar, a * min(e, 1)), (c.margem + int((1 - min(e, 1)) * 40), y))
        return
    if est == "linhas":
        f = c.fx(40)
        row = c.px(92)
        lay = Image.new("RGBA", (c.W, row * len(itens) + c.px(20)), (0, 0, 0, 0))
        d = ImageDraw.Draw(lay)
        for i, it in enumerate(itens):
            e = c.entra((t - p["t0"] - 0.08 * i) / 0.35)
            ok = ease_out((t - it["t"]) / 0.3)
            y = i * row
            dx = _marcador(c, d, c.margem, y + c.px(30), ok, i, lay, claro=False)
            escreve(lay, (c.margem + dx + c.px(16), y + c.px(4)), it["texto"], f, BRANCO, (0.4 + 0.6 * ok) * min(e, 1))
            d.line((c.margem + dx + c.px(16), y + c.px(64), c.W - c.margem, y + c.px(64)), fill=(255, 255, 255, int((60 if ok > 0.5 else 25) * e)), width=1)
        cam.alpha_composite(com_alpha(lay, a), (0, y0))
        return
    # painel (escuro ou claro)
    claro = c.e.painel_claro
    w, row = c.W - 2 * c.margem, c.px(96)
    h = row * len(itens) + c.px(36)
    pn = c.painel(w, h)
    cont = Image.new("RGBA", pn.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(cont)
    f = c.fx(42)
    for i, it in enumerate(itens):
        yy = c.px(18) + i * row
        e = min(c.entra((t - p["t0"] - 0.08 * i) / 0.35), 1)
        ok = ease_out((t - it["t"]) / 0.3)
        dx = _marcador(c, d, c.px(32), yy + row / 2, ok, i, cont, claro)
        escreve(cont, (c.px(32) + dx + c.px(20) + 10 * ok, yy + row / 2 - c.px(27)), it["texto"], f, c.texto_painel, (0.45 + 0.55 * ok) * e)
        if i < len(itens) - 1:
            d.line((c.px(96), yy + row, w - c.px(36), yy + row), fill=((30, 30, 34, int(25 * e)) if claro else (255, 255, 255, int(28 * e))), width=1)
    pn.alpha_composite(cont)
    cam.alpha_composite(com_alpha(pn, a), (c.margem, y0))


def desenha_etiquetas(cam, t, p, c: Ctx):
    """Etiquetas que entram uma por palavra dita, com título opcional."""
    itens = p["itens"]
    if not itens or t < itens[0]["t"] - 0.4 or t >= p["t1"] + 0.3:
        return
    a = 1 - ease_out((t - p["t1"]) / 0.3)
    y = c.px(p.get("y", c.y_pecas))
    claro = c.e.painel_claro
    blocos = c.e.painel == "blocos-cor"
    if p.get("titulo"):
        f0 = c.fx_forte(32)
        tit = _caixa(c, p["titulo"]) if blocos else p["titulo"]
        tw = int(f0.getlength(tit)) + c.px(52)
        et = Image.new("RGBA", (tw, c.px(64)), (0, 0, 0, 0))
        d0 = ImageDraw.Draw(et)
        if blocos:
            d0.rectangle((0, 0, tw - 1, c.px(63)), fill=c.destaque + (255,))
            escreve(et, (c.px(26), c.px(13)), tit, f0, GRAFITE)
        else:
            d0.rounded_rectangle((0, 0, tw - 1, c.px(63)), radius=c.px(32), fill=(255, 255, 255, 230) if claro else (12, 12, 14, 205))
            escreve(et, (c.px(26), c.px(13)), p["titulo"], f0, c.destaque)
        e0 = ease_out((t - itens[0]["t"] + 0.4) / 0.3)
        cam.alpha_composite(com_alpha(et, a * e0), (c.margem, int(y)))
        y += c.px(84)
    f = c.fx_forte(44)
    for i, it in enumerate(itens):
        if t < it["t"]:
            continue
        k = c.entra((t - it["t"]) / 0.55)
        txt = _caixa(c, it["texto"]) if blocos else it["texto"]
        lw = f.getlength(txt)
        pw, ph = int(lw + c.px(56)), c.px(72)
        pil = Image.new("RGBA", (pw, ph), (0, 0, 0, 0))
        dd = ImageDraw.Draw(pil)
        if blocos:
            dd.rectangle((0, 0, pw - 1, ph - 1), fill=c.destaque + (255,))
            dd.text((c.px(28), c.px(10)), txt, font=f, fill=GRAFITE + (255,))
        elif c.e.painel == "linhas":
            dd.rectangle((0, ph - 4, pw - 1, ph - 1), fill=c.destaque + (255,))
            texto_sombra(pil, (c.px(6), c.px(8)), txt, f, BRANCO)
        else:
            dd.rounded_rectangle((0, 0, pw - 1, ph - 1), radius=ph // 2, fill=BRANCO + (245,))
            dd.text((c.px(28), c.px(10)), txt, font=f, fill=GRAFITE + (255,))
        x = c.margem - (1 - min(k, 1)) * 200 + (k - 1) * 30
        cam.alpha_composite(com_alpha(pil, a * min(1, k * 1.6)), (int(x), int(y + i * c.px(88))))


def desenha_lista(cam, t, p, c: Ctx):
    """Lista numerada que aparece em sequência: o mapa do vídeo."""
    itens = p["itens"]
    if not (p["t0"] <= t < p["t1"] + 0.3):
        return
    a = entra_sai(c, t, p["t0"], p["t1"])
    row = c.px(74)
    sem_painel = c.e.painel in ("linhas", "blocos-cor")
    pn = c.painel(c.W - 2 * c.margem, row * len(itens) + c.px(40)) if not sem_painel else Image.new("RGBA", (c.W - 2 * c.margem, row * len(itens) + c.px(40)), (0, 0, 0, 0))
    cont = Image.new("RGBA", pn.size, (0, 0, 0, 0))
    f, fm = c.fx(40), c.fm(28)
    cor = c.texto_painel if not sem_painel else BRANCO
    for i, nome in enumerate(itens):
        e = min(c.entra((t - p["t0"] - 0.12 * i) / 0.3), 1)
        y = c.px(20) + i * row
        escreve(cont, (c.px(36), y + c.px(20)), f"{i + 1:02d}", fm, c.destaque, e)
        escreve(cont, (c.px(106) + (1 - e) * 24, y + c.px(13)), nome, f, cor, e)
        if i < len(itens) - 1:
            ImageDraw.Draw(cont).line((c.px(106), y + row, pn.width - c.px(36), y + row), fill=(cor + (int(26 * e),)), width=1)
    pn.alpha_composite(cont)
    cam.alpha_composite(com_alpha(pn, a), (c.margem, int(c.px(p.get("y", c.y_pecas)) + (1 - a) * 20)))


def desenha_passo(cam, t, p, c: Ctx):
    """Cartão "PASSO 03 · Nome" com a trilha dos passos acendendo até o atual."""
    if not (p["t0"] <= t < p["t1"] + 0.3):
        return
    a = entra_sai(c, t, p["t0"], p["t1"])
    n, total = int(p["numero"]), int(p.get("total", 6))
    blocos = c.e.painel == "blocos-cor"
    pn = c.painel(c.W - 2 * c.margem, c.px(196)) if not blocos else Image.new("RGBA", (c.W - 2 * c.margem, c.px(196)), (0, 0, 0, 0))
    cont = Image.new("RGBA", pn.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(cont)
    cor = c.texto_painel if c.e.painel in ("escuro-arredondado", "claro-arredondado") else BRANCO
    escreve(cont, (c.px(36), c.px(26)), f"{p.get('prefixo', 'PASSO')} {n:02d}", c.fm(28), c.destaque)
    k = c.entra((t - p["t0"] - 0.1) / 0.4)
    escreve(cont, (c.px(36) + (1 - min(k, 1)) * 30, c.px(62)), _caixa(c, p["nome"], True), c.ft(60), cor, min(k, 1))
    gap, x0 = c.px(12), c.px(36)
    w = (pn.width - 2 * x0 - gap * (total - 1)) / total
    for i in range(total):
        x = x0 + i * (w + gap)
        d.rounded_rectangle((x, c.px(154), x + w, c.px(164)), radius=5, fill=(cor + (50,)))
        if i < n - 1:
            d.rounded_rectangle((x, c.px(154), x + w, c.px(164)), radius=5, fill=c.destaque + (255,))
        elif i == n - 1:
            q = ease_out((t - p["t0"] - 0.25) / 0.5)
            d.rounded_rectangle((x, c.px(154), x + w * q, c.px(164)), radius=5, fill=c.destaque + (255,))
    pn.alpha_composite(cont)
    cam.alpha_composite(com_alpha(pn, a), (c.margem, int(c.px(p.get("y", c.y_pecas)) + (1 - a) * 20)))


def desenha_barra(cam, t, p, c: Ctx):
    """N etapas que se acendem em sequência a partir de uma palavra."""
    if not (p["t0"] <= t < p["t1"] + 0.3):
        return
    a = entra_sai(c, t, p["t0"], p["t1"])
    n = int(p.get("n", 4))
    pn = c.painel(c.W - 2 * c.margem, c.px(150)) if c.e.painel in ("escuro-arredondado", "claro-arredondado") else Image.new("RGBA", (c.W - 2 * c.margem, c.px(150)), (0, 0, 0, 0))
    cont = Image.new("RGBA", pn.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(cont)
    cor = c.texto_painel if c.e.painel in ("escuro-arredondado", "claro-arredondado") else BRANCO
    gap, x0 = c.px(16), c.px(36)
    w = (pn.width - 2 * x0 - gap * (n - 1)) / n
    f = c.fx(30)
    rot = p.get("rotulo", "Etapa")
    for i in range(n):
        x = x0 + i * (w + gap)
        e = min(c.entra((t - p["t0"] - i * 0.06) / 0.3), 1)
        fill = ease_out((t - p["acende"] - i * 0.22) / 0.3)
        escreve(cont, (x, c.px(30)), f"{rot} {i + 1}", f, c.destaque if fill > 0.5 else cor, e * (0.55 + 0.45 * min(fill * 2, 1)))
        d.rounded_rectangle((x, c.px(92), x + w, c.px(104)), radius=6, fill=cor + (int(55 * e),))
        if fill > 0:
            d.rounded_rectangle((x, c.px(92), x + w * fill, c.px(104)), radius=6, fill=c.destaque + (255,))
    pn.alpha_composite(cont)
    cam.alpha_composite(com_alpha(pn, a), (c.margem, int(c.px(p.get("y", c.y_pecas)) + (1 - a) * 20)))


def desenha_marcos(cam, t, p, c: Ctx):
    """Linha do tempo com marcos que acendem quando ditos."""
    marcos = p["itens"]
    if t < marcos[0]["t"] - 0.5 or t >= p["t1"] + 0.3:
        return
    a = entra_sai(c, t, marcos[0]["t"] - 0.5, p["t1"])
    com_painel = c.e.painel in ("escuro-arredondado", "claro-arredondado")
    pn = c.painel(c.W - 2 * c.margem, c.px(230)) if com_painel else Image.new("RGBA", (c.W - 2 * c.margem, c.px(230)), (0, 0, 0, 0))
    cont = Image.new("RGBA", pn.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(cont)
    cor = c.texto_painel if com_painel else BRANCO
    if p.get("titulo"):
        escreve(cont, (c.px(36), c.px(24)), p["titulo"], c.fm(26), c.destaque)
    if p.get("unidade"):
        fu = c.fm(24)
        escreve(cont, (pn.width - c.px(36) - fu.getlength(p["unidade"]), c.px(24)), p["unidade"], fu, cor, 0.7)
    x0, x1, y = c.px(70), pn.width - c.px(70), c.px(140)
    d.line((x0, y, x1, y), fill=cor + (60,), width=4)
    n = len(marcos)
    ult = max([i for i, mm in enumerate(marcos) if t >= mm["t"]] or [-1])
    if ult >= 0:
        k = ease_out((t - marcos[ult]["t"]) / 0.35)
        xa = x0 + (x1 - x0) * (ult - 1 + k) / (n - 1) if ult > 0 else x0
        d.line((x0, y, xa, y), fill=c.destaque + (255,), width=4)
    f = c.ft(44)
    for i, mm in enumerate(marcos):
        x = x0 + (x1 - x0) * i / (n - 1)
        on = ease_out((t - mm["t"]) / 0.3)
        r = c.px(12) + c.px(6) * on
        d.ellipse((x - r, y - r, x + r, y + r), fill=(c.destaque if on > 0.5 else (90, 90, 95)) + (255,))
        lw = f.getlength(mm["texto"])
        escreve(cont, (x - lw / 2, y + c.px(24)), mm["texto"], f, c.destaque if on > 0.5 else cor, 0.45 + 0.55 * on)
    pn.alpha_composite(cont)
    cam.alpha_composite(com_alpha(pn, a), (c.margem, int(c.px(p.get("y", c.y_pecas)) + (1 - a) * 20)))


def desenha_ondas(cam, t, p, c: Ctx):
    """Duas ondas fora de fase que entram em sintonia na palavra."""
    if not (p["t0"] <= t < p["t1"] + 0.3):
        return
    a = entra_sai(c, t, p["t0"], p["t1"])
    s = ease_io((t - p["une"]) / 0.7)
    base = c.px(p.get("y", c.y_pecas))
    claro = c.e.painel_claro
    if c.e.painel in ("escuro-arredondado", "claro-arredondado"):
        fundo = c.painel(c.W - 2 * c.margem + c.px(40), c.px(386), a=170 if not claro else 215)
        cam.alpha_composite(com_alpha(fundo, a), (c.margem - c.px(20), base + c.px(14)))
    cor_base = GRAFITE if claro else BRANCO
    camw = Image.new("RGBA", (c.W, c.px(420)), (0, 0, 0, 0))
    d = ImageDraw.Draw(camw)
    f = c.fx_forte(36)
    x0, x1 = c.px(88), c.W - c.px(88)
    xs = np.linspace(0, 1, 220)
    rotulos = p.get("rotulos", ["A", "B"])
    specs = [(rotulos[0], p["t_a"], c.px(130), 2.0, 0.0, 1.0), (rotulos[1], p["t_b"], c.px(290), 3.3, 2.4, -1.3)]
    for nome, tq, yb, freq, fase, vel in specs:
        e = ease_out((t - tq + 0.2) / 0.4)
        if e <= 0:
            continue
        yb2 = yb + (c.px(180) - yb) * s
        fr = freq + (2.6 - freq) * s
        fa = fase * (1 - s)
        ve = vel + (1.0 - vel) * s
        amp = c.px(46) * (1 - 0.3 * s)
        xx = x0 + (x1 - x0) * xs * e
        yy = yb2 + amp * np.sin(2 * np.pi * fr * xs + fa - ve * 6 * t) * np.sin(np.pi * xs)
        cor_m = tuple(int(cor_base[k] + (c.destaque[k] - cor_base[k]) * s) for k in range(3))
        d.line(list(zip(xx, yy)), fill=cor_m + (int((200 + 30 * s) * a),), width=5 if s < 0.5 else 7, joint="curve")
        (escreve if claro else texto_sombra)(camw, (x0 + c.px(24), yb - c.px(84)), nome, f, cor_base, a * e * max(0, 1 - s * 2.5))
    k = ease_out((s - 0.45) / 0.55)
    if k > 0:
        (escreve if claro else texto_sombra)(camw, (x0 + c.px(24), c.px(84) + (1 - k) * 16), p.get("texto_uniao", "Em sintonia"), c.ft(40), c.destaque, a * k)
    cam.alpha_composite(camw, (0, base))


# ================================================================ chamada e marca
def desenha_botao(cam, t, p, c: Ctx):
    """Botão que entra e recebe um toque (com onda) na palavra combinada."""
    if not (p["t0"] <= t < p["t1"]):
        return
    k = c.entra((t - p["t0"]) / 0.6)
    f = c.fx_forte(50)
    txt = _caixa(c, p["texto"]) if c.e.painel == "blocos-cor" else p["texto"]
    lw = f.getlength(txt)
    bw, bh = int(lw + c.px(140)), c.px(108)
    tap = t - p["toque"] if p.get("toque") else 1e9
    esc = 1 - 0.07 * np.sin(np.pi * tap / 0.25) if 0 <= tap < 0.25 else 1.0
    bt = Image.new("RGBA", (bw, bh), (0, 0, 0, 0))
    d = ImageDraw.Draw(bt)
    if c.e.painel == "blocos-cor":
        d.rectangle((0, 0, bw - 1, bh - 1), fill=c.destaque + (255,))
    else:
        d.rounded_rectangle((0, 0, bw - 1, bh - 1), radius=bh // 2, fill=BRANCO + (250,))
    d.text((c.px(48), c.px(22)), txt, font=f, fill=GRAFITE + (255,))
    ax, ay = c.px(48) + lw + c.px(28), bh / 2
    d.line([(ax, ay), (ax + c.px(32), ay)], fill=GRAFITE + (255,), width=5)
    d.line([(ax + c.px(19), ay - c.px(14)), (ax + c.px(33), ay), (ax + c.px(19), ay + c.px(14))], fill=GRAFITE + (255,), width=5, joint="curve")
    s = (0.6 + 0.4 * min(k, 1.05)) * esc
    bt = bt.resize((max(1, int(bw * s)), max(1, int(bh * s))), Image.LANCZOS)
    cx, cy = c.W / 2, c.px(p.get("y", 1530))
    cam.alpha_composite(com_alpha(bt, min(1, k * 2)), (int(cx - bt.width / 2), int(cy - bt.height / 2)))
    if 0 <= tap < 0.7:
        q = ease_out(tap / 0.7)
        r = c.px(40) + c.px(260) * q
        ring = Image.new("RGBA", (c.W, c.px(700)), (0, 0, 0, 0))
        ImageDraw.Draw(ring).ellipse((cx - r, c.px(350) - r * 0.42, cx + r, c.px(350) + r * 0.42), outline=c.destaque + (int(220 * (1 - q)),), width=4)
        cam.alpha_composite(ring, (0, int(cy - c.px(350))))


def desenha_pilula(cam, t, p, c: Ctx):
    """Pílula "● AO VIVO" com ponto vermelho pulsando."""
    if not (p["t0"] <= t < p["t1"] + 0.2):
        return
    k = ease_out((t - p["t0"]) / 0.3) * (1 - ease_out((t - p["t1"]) / 0.2))
    f = c.fm(24)
    w = int(f.getlength(p["texto"])) + c.px(74)
    pil = Image.new("RGBA", (w, c.px(50)), (0, 0, 0, 0))
    d = ImageDraw.Draw(pil)
    d.rounded_rectangle((0, 0, w - 1, c.px(49)), radius=c.px(25), fill=(14, 14, 16, 190))
    pul = 0.5 + 0.5 * np.sin((t - p["t0"]) * 2 * np.pi * 1.2)
    d.ellipse((c.px(20), c.px(17), c.px(36), c.px(33)), fill=VERMELHO + (int(255 * (0.55 + 0.45 * pul)),))
    d.text((c.px(48), c.px(11)), p["texto"], font=f, fill=BRANCO + (255,))
    cam.alpha_composite(com_alpha(pil, k), (c.margem, int(c.px(292) + (1 - k) * 14)))


def desenha_tag(cam, t, capitulos: list[dict], c: Ctx):
    """Assinatura no canto: marca + capítulo, no estilo escolhido."""
    est = c.e.tag
    if est == "nenhuma":
        return
    atual, t_ini = None, 0.0
    for cap in capitulos:
        if t >= cap["t0"] - 0.05:
            atual, t_ini = cap, cap["t0"]
    nome = (c.marca.get("nome") or "").strip()
    if atual is None and not nome:
        return
    a = ease_out(t / 0.4)
    k = ease_out((t - t_ini) / 0.35) if atual is not None else 1.0
    cap_txt = f"{atual.get('numero', '')} {atual.get('nome', '')}".strip() if atual is not None else ""
    x, y = c.margem, c.px(228)
    lay = Image.new("RGBA", (c.W, c.px(90)), (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    if est == "ponto-mono":
        f = c.fm(28)
        d.rectangle((x, c.px(27), x + c.px(12), c.px(39)), fill=c.destaque + (int(255 * a * (0.55 + 0.45 * (0.5 + 0.5 * np.sin(t * 2 * np.pi * 0.9)))),))
        xx = x + c.px(26)
        texto_sombra(lay, (xx, c.px(20)), nome.upper(), f, BRANCO, 0.92 * a, 90)
        xx += f.getlength(nome.upper()) + c.px(18)
        if cap_txt and nome:
            d.line((xx, c.px(24), xx, c.px(46)), fill=BRANCO + (int(110 * a),), width=2)
            xx += c.px(18)
        texto_sombra(lay, (xx, c.px(20) + 4 + (1 - k) * 26), cap_txt.upper(), f, BRANCO, 0.62 * k * a, 70)
    elif est == "barra":
        f = c.fx(26)
        d.rectangle((x, c.px(18), x + c.px(6), c.px(50)), fill=c.destaque + (int(255 * a),))
        texto_sombra(lay, (x + c.px(22), c.px(22)), f"{nome.upper()}  |  {cap_txt.upper()}".strip(" |"), f, BRANCO, 0.9 * a * (0.5 + 0.5 * k), 80)
    elif est == "pilula":
        f = c.fx(26)
        txt = f"{nome} · {cap_txt}".strip(" ·")
        tw = f.getlength(txt) + c.px(48)
        d.rounded_rectangle((x, c.px(12), x + tw, c.px(56)), radius=c.px(22), fill=(255, 255, 255, int(235 * a)))
        escreve(lay, (x + c.px(24), c.px(20)), txt, f, GRAFITE, a * (0.5 + 0.5 * k))
    elif est == "linha-versalete":
        f = c.fx(24)
        d.line((x, c.px(34), x + c.px(96), c.px(34)), fill=BRANCO + (int(200 * a),), width=1)
        txt = f"{nome.upper()}   ·   Nº {cap_txt.upper()}" if cap_txt else nome.upper()
        escreve(lay, (x + c.px(112), c.px(20)), txt, f, BRANCO, 0.85 * a * (0.5 + 0.5 * k))
    elif est == "bloco-cor":
        f = c.fx_forte(28)
        txt = f"{nome.upper()} / {cap_txt.upper()}".strip(" /")
        tw = f.getlength(txt) + c.px(32)
        d.rectangle((x, c.px(14), x + tw, c.px(54)), fill=c.destaque + (int(255 * a),))
        escreve(lay, (x + c.px(16), c.px(18)), txt, f, GRAFITE, a * (0.5 + 0.5 * k))
    cam.alpha_composite(lay, (0, y - c.px(20)))


# ================================================================ legenda
FUNCAO = {"a", "o", "e", "um", "uma", "de", "da", "do", "em", "com", "por", "que", "eu", "te", "se", "no", "na",
          "não", "esse", "essa", "pode", "the", "an", "of", "to", "and", "in", "on", "is"}
PARES = {("saiba", "mais")}


def _limpa(w):
    return w["texto"].strip().strip(",.?!").lower()


def largura_legenda(ws, f) -> float:
    return f.getlength(" ".join(x["texto"].strip().strip(",.?!") for x in ws))


def _custo(g, fim_de_frase, f, larg_max):
    larg = largura_legenda(g, f)
    if larg > larg_max or len(g) > 4:
        return float("inf")
    c = 1.0
    ultima = _limpa(g[-1])
    if not fim_de_frase and ultima in FUNCAO:
        c += 4
    if len(g) == 1 and len(ultima) < 9 and not fim_de_frase:
        c += 1.5
    if len(g) >= 2 and (_limpa(g[0]), _limpa(g[1])) in PARES:
        c -= 0.5
    c += abs(larg - larg_max * 0.6) / (larg_max * 1.6)
    return c


def quebra_legenda(ws: list[dict], f, larg_max: float) -> list[list[dict]]:
    frases, cur = [], []
    for w in ws:
        cur.append(w)
        if w["texto"].strip()[-1:] in ",.?!":
            frases.append(cur)
            cur = []
    if cur:
        frases.append(cur)
    grupos = []
    for fr in frases:
        n = len(fr)
        melhor = [0.0] + [float("inf")] * n
        corte = [0] * (n + 1)
        for j in range(1, n + 1):
            for i in range(max(0, j - 4), j):
                if i > 0 and (_limpa(fr[i - 1]), _limpa(fr[i])) in PARES:
                    continue
                cc = melhor[i] + _custo(fr[i:j], j == n, f, larg_max)
                if cc < melhor[j]:
                    melhor[j], corte[j] = cc, i
        j, partes = n, []
        while j > 0:
            partes.append(fr[corte[j]:j])
            j = corte[j]
        grupos += partes[::-1]
    return grupos


def fonte_legenda(c: Ctx):
    esc = {"pequena": 0.85, "media": 1.0, "grande": 1.15}[c.e.legenda_tamanho]
    tam = {"palavra-sublinhado": 66, "bloco-contorno": 70, "karaoke-caixa": 72, "barra-preta": 56, "pilula": 58}[c.e.legenda]
    peso_extra = {"palavra-sublinhado": 80, "bloco-contorno": 200, "karaoke-caixa": 200, "barra-preta": 100, "pilula": 0}[c.e.legenda]
    p = c.e.peso_texto()
    return c.fx(int(tam * esc), None if p is None else min(900, p + peso_extra))


def y_legenda(c: Ctx):
    if c.e.legenda_posicao == "centro":
        return int(c.H * 0.56)
    return c.px(1318) if c.H > c.W else int(c.H * 0.82)


def blocos_legenda(palavras: list[dict], c: Ctx) -> list[dict]:
    f = fonte_legenda(c)
    larg_max = c.W - 2 * c.margem - c.px(90)
    if c.e.legenda_em_caixa_alta:
        larg_max *= 0.86
    out = []
    for g in quebra_legenda(palavras, f, larg_max):
        out.append(dict(t0=g[0]["inicio"] - 0.04, fim_fala=g[-1]["fim"], ws=g))
    for x, y in zip(out, out[1:]):
        x["t1"] = y["t0"] if y["t0"] - x["fim_fala"] < 0.7 else x["fim_fala"] + 0.35
    if out:
        out[-1]["t1"] = out[-1]["fim_fala"] + 0.4
    return out


def _grafia(w, correcoes, caps):
    t = w["texto"].strip().rstrip(".").strip(",?!")
    t = correcoes.get(t.lower(), t)
    return t.upper() if caps else t


def _metrica(f):
    """Topo e base do texto em relação ao y de desenho (varia muito de fonte pra fonte)."""
    bb = f.getbbox("ÁgQ")
    return bb[1], bb[3]


def desenha_legenda(cam, t, blocos, c: Ctx, destaques: set, correcoes: dict, riscar: set):
    """A legenda no estilo escolhido. As caixas são medidas pela fonte, não por número fixo."""
    est = c.e.legenda
    f = fonte_legenda(c)
    caps = c.e.legenda_em_caixa_alta
    yb = y_legenda(c)
    topo, base = _metrica(f)
    alt_txt = base - topo
    pad_y, pad_x = c.px(12), c.px(14)
    alt = alt_txt + 2 * pad_y
    y_top = yb - c.px(46)
    y_txt = y_top + pad_y - topo
    for b in blocos:
        if not (b["t0"] <= t < b["t1"] + 0.12):
            continue
        txts = [_grafia(w, correcoes, caps) for w in b["ws"]]
        chaves = [x.lower().strip(".") for x in txts]
        esp = f.getlength(" ")
        larg = [f.getlength(x) for x in txts]
        total = sum(larg) + esp * (len(txts) - 1)
        x0 = (c.W - total) / 2
        if est in ("palavra-sublinhado", "karaoke-caixa"):
            saida = ease_out((t - b["t1"]) / 0.12) if t >= b["t1"] else 0.0
            x = x0
            for w, txt, lw, ch in zip(b["ws"], txts, larg, chaves):
                k = ease_out((t - (w["inicio"] - 0.05)) / 0.16)
                if k <= 0:
                    x += lw + esp
                    continue
                atual = w["inicio"] - 0.05 <= t < (w["fim"] + 0.1)
                dy = (1 - k) * 30 - saida * 18
                alpha = k * (1 - saida)
                if est == "karaoke-caixa":
                    if atual or ch in destaques:
                        box = Image.new("RGBA", (int(lw + 2 * pad_x), int(alt)), (0, 0, 0, 0))
                        ImageDraw.Draw(box).rectangle((0, 0, box.width - 1, box.height - 1), fill=c.destaque + (int(255 * alpha),))
                        cam.alpha_composite(box, (int(x - pad_x), int(y_top + dy)))
                        escreve(cam, (x, y_txt + dy), txt, f, GRAFITE, alpha)
                    else:
                        texto_sombra(cam, (x, y_txt + dy), txt, f, BRANCO, alpha=alpha, sombra=160)
                else:
                    cor = c.destaque if ch in destaques else BRANCO
                    texto_sombra(cam, (x, y_txt + dy), txt, f, cor, alpha=alpha)
                    if ch in destaques and ch not in riscar:
                        u = ease_out((t - w["inicio"] - 0.05) / 0.28)
                        if u > 0:
                            risco = Image.new("RGBA", (int(lw) + 4, c.px(6)), (0, 0, 0, 0))
                            ImageDraw.Draw(risco).rounded_rectangle((0, 0, lw * u, c.px(5)), radius=2, fill=c.destaque + (int(230 * alpha),))
                            cam.alpha_composite(risco, (int(x), int(y_top + pad_y + alt_txt + c.px(6) + dy)))
                    if ch in riscar:
                        u = ease_out((t - w["inicio"] - 0.35) / 0.3)
                        if u > 0:
                            risco = Image.new("RGBA", (int(lw) + 16, c.px(8)), (0, 0, 0, 0))
                            ImageDraw.Draw(risco).rounded_rectangle((0, 0, (lw + 12) * u, c.px(6)), radius=3, fill=c.destaque + (int(255 * alpha),))
                            cam.alpha_composite(risco, (int(x - 6), int(y_top + pad_y + alt_txt * 0.5 + dy)))
                x += lw + esp
        elif est == "bloco-contorno":
            if t >= b["t1"]:
                continue
            lay = Image.new("RGBA", (c.W, int(alt) + 80), (0, 0, 0, 0))
            x = x0
            for txt, lw, ch in zip(txts, larg, chaves):
                texto_contorno(lay, (x, 40 + pad_y - topo), txt, f, c.destaque if ch in destaques else BRANCO)
                x += lw + esp
            k = ease_out((t - b["t0"]) / 0.13)
            esc = 0.88 + 0.12 * k
            if esc < 0.999:
                lay = lay.resize((int(c.W * esc), int(lay.height * esc)), Image.LANCZOS)
            cam.alpha_composite(lay, ((c.W - lay.width) // 2, int(y_top + alt / 2 - lay.height / 2)))
        else:  # barra-preta / pilula
            if t >= b["t1"]:
                continue
            k = ease_out((t - b["t0"]) / 0.15)
            pad = c.px(28)
            lay = Image.new("RGBA", (int(total + 2 * pad + 8), int(alt)), (0, 0, 0, 0))
            d = ImageDraw.Draw(lay)
            if est == "barra-preta":
                d.rectangle((0, 0, lay.width - 1, lay.height - 1), fill=(0, 0, 0, 255))
            else:
                d.rounded_rectangle((0, 0, lay.width - 1, lay.height - 1), radius=lay.height // 2, fill=(14, 14, 18, 190))
            x = pad
            for w, txt, lw, ch in zip(b["ws"], txts, larg, chaves):
                atual = w["inicio"] - 0.05 <= t
                cor = c.destaque if (ch in destaques or (est == "pilula" and atual and t < w["fim"] + 0.1)) else BRANCO
                escreve(lay, (x, pad_y - topo), txt, f, cor)
                x += lw + esp
            cam.alpha_composite(com_alpha(lay, k), ((c.W - lay.width) // 2, int(y_top)))
        break


def desenha_assinatura(cam, t, env_em, c: Ctx, alpha=1.0):
    est = c.e.assinatura
    if est == "nenhuma" or alpha <= 0:
        return
    y = c.px(1418) if c.H > c.W else int(c.H * 0.9)
    if c.e.legenda_posicao == "centro":
        y = int(c.H * 0.56) + c.px(100)
    d = ImageDraw.Draw(cam)
    prog = min(max(t / max(c.total, 1e-3), 0), 1)
    if est == "onda":
        largura = c.px(520)
        n = 140
        xs = np.linspace(0, 1, n)
        janela = np.sin(np.pi * xs) ** 1.5
        amps = np.array([env_em(t + (x - 0.5) * 0.6) for x in xs])
        ys = y + c.px(22) * amps * janela * np.sin(2 * np.pi * 3.2 * xs - 7.5 * t)
        x0 = (c.W - largura) / 2
        lin = Image.new("RGBA", (c.W, c.px(120)), (0, 0, 0, 0))
        ImageDraw.Draw(lin).line([(x0 + largura * x, yy - y + c.px(60)) for x, yy in zip(xs, ys)], fill=BRANCO + (int(170 * alpha),), width=3, joint="curve")
        cam.alpha_composite(lin, (0, int(y - c.px(60))))
        r = c.px(5) + c.px(3) * env_em(t)
        ponto = Image.new("RGBA", (c.px(40), c.px(40)), (0, 0, 0, 0))
        ImageDraw.Draw(ponto).ellipse((c.px(20) - r, c.px(20) - r, c.px(20) + r, c.px(20) + r), fill=c.destaque + (int(255 * alpha),))
        cam.alpha_composite(ponto, (int(c.W / 2 - c.px(20)), int(ys[n // 2] - c.px(20))))
    elif est == "barra":
        lin = Image.new("RGBA", (c.W, c.px(20)), (0, 0, 0, 0))
        dd = ImageDraw.Draw(lin)
        dd.rectangle((c.margem, 0, c.W - c.margem, c.px(10)), fill=(255, 255, 255, int(60 * alpha)))
        dd.rectangle((c.margem, 0, c.margem + (c.W - 2 * c.margem) * prog, c.px(10)), fill=c.destaque + (int(255 * alpha),))
        cam.alpha_composite(lin, (0, y - c.px(5)))
    elif est == "linha":
        lin = Image.new("RGBA", (c.W, c.px(20)), (0, 0, 0, 0))
        dd = ImageDraw.Draw(lin)
        xp = c.margem + (c.W - 2 * c.margem) * prog
        dd.line((c.margem, c.px(10), c.W - c.margem, c.px(10)), fill=(255, 255, 255, int(70 * alpha)), width=2)
        dd.line((c.margem, c.px(10), xp, c.px(10)), fill=c.destaque + (int(255 * alpha),), width=2)
        dd.ellipse((xp - c.px(7), c.px(3), xp + c.px(7), c.px(17)), fill=c.destaque + (int(255 * alpha),))
        cam.alpha_composite(lin, (0, y - c.px(10)))


# ================================================================ cartão final
@lru_cache(maxsize=8)
def fundo_final(W, H, estilo, destaque):
    if estilo == "cor-solida":
        return Image.new("RGB", (W, H), destaque)
    if estilo == "minimo":
        return Image.new("RGB", (W, H), (8, 8, 10))
    y = np.linspace(0, 1, H, dtype=np.float32)[:, None, None]
    x = np.linspace(-1, 1, W, dtype=np.float32)[None, :, None]
    base = np.array(GRAFITE, np.float32)[None, None, :]
    luz = 26 * np.exp(-((x * 0.9) ** 2 + ((y - 0.42) * 2.2) ** 2))
    arr = np.clip(base + luz + 8 * y, 0, 255).astype(np.uint8)
    return Image.fromarray(np.broadcast_to(arr, (H, W, 3)).copy(), "RGB")


def cartao_final(t, t0, cf: dict, logo: Image.Image | None, c: Ctx) -> Image.Image:
    est = c.e.cartao_final
    u = t - t0
    img = fundo_final(c.W, c.H, est, c.destaque).convert("RGBA")
    escuro = est != "cor-solida"
    cor_txt = BRANCO if escuro else GRAFITE
    cor_dest = c.destaque if escuro else GRAFITE
    if est == "logo-sobe":
        lin = ease_io(u / 0.55)
        sai = ease_out((u - 0.55) / 0.35)
        if sai < 1:
            larg = c.px(900) * lin * (1 - sai)
            d = ImageDraw.Draw(img)
            xs = np.linspace(0, 1, 160)
            yy = c.H / 2 + c.px(26) * np.sin(2 * np.pi * 3 * xs - 8 * u) * np.sin(np.pi * xs) * (1 - sai)
            d.line(list(zip(c.W / 2 - larg / 2 + larg * xs, yy)), fill=c.destaque + (int(255 * (1 - sai)),), width=4, joint="curve")
    k = ease_out((u - (0.6 if est == "logo-sobe" else 0.15)) / 0.6)
    y_logo = c.px(470) if est != "minimo" else c.px(760)
    y_txt = c.px(1150)
    if k > 0:
        nome = c.marca.get("nome") or ""
        if logo is not None:
            esc = 0.86 + 0.14 * k
            alvo_w = min(logo.width, int(c.W * (0.62 if est != "minimo" else 0.36)))
            l2 = logo.resize((int(alvo_w * esc), int(logo.height * alvo_w / logo.width * esc)), Image.LANCZOS)
            if not escuro:  # logo branco em fundo de cor: escurece
                arr = np.array(l2)
                arr[..., :3] = 18
                l2 = Image.fromarray(arr)
            corte = int(l2.height * k)
            l2c = l2.crop((0, l2.height - corte, l2.width, l2.height))
            img.alpha_composite(l2c, (int((c.W - l2.width) / 2), int(y_logo + (l2.height - corte) + (1 - k) * 30)))
            y_txt = y_logo + l2.height + c.px(90)
        elif nome:
            f = c.ft(96 if est != "minimo" else 56)
            txt = nome.upper() if c.e.titulo_em_caixa_alta else nome
            lay = Image.new("RGBA", (c.W, c.px(160)), (0, 0, 0, 0))
            (texto_sombra if escuro else escreve)(lay, ((c.W - f.getlength(txt)) / 2, 0), txt, f, cor_txt, k)
            img.alpha_composite(lay, (0, int(y_logo + c.px(200) + (1 - k) * 30)))
            y_txt = y_logo + c.px(420)
    if est != "minimo":
        f = c.fx_forte(52)
        for i, (txt, cor) in enumerate(cf.get("linhas", [])):
            q = ease_out((u - 1.05 - i * 0.12) / 0.45)
            if q > 0:
                txt = _caixa(c, txt, True)
                (texto_sombra if escuro else escreve)(img, ((c.W - f.getlength(txt)) / 2, y_txt + i * c.px(66) + (1 - q) * 24), txt, f, cor_dest if cor != "branco" else cor_txt, q)
        rod = cf.get("rodape") or c.marca.get("rodape")
        if rod:
            q = ease_out((u - 1.5) / 0.45)
            if q > 0:
                f2 = c.fm(26)
                (texto_sombra if escuro else escreve)(img, ((c.W - f2.getlength(rod)) / 2, y_txt + c.px(190) + (1 - q) * 14), rod, f2, cor_txt, 0.75 * q)
    return img


# ================================================================ acabamento
@lru_cache(maxsize=4)
def vinheta(W, H, forca):
    y, x = np.mgrid[0:H, 0:W].astype(np.float32)
    r2 = ((x - W / 2) / (W * 0.62)) ** 2 + ((y - H * 0.45) / (H * 0.62)) ** 2
    return np.clip(1 - forca * r2, 0.70, 1)[..., None]


@lru_cache(maxsize=4)
def graos(W, H):
    rng = np.random.default_rng(7)
    out = []
    for _ in range(6):
        g = rng.normal(0, 3.2, (H // 2 + 1, W // 2 + 1)).astype(np.float32)
        g = np.kron(g, np.ones((2, 2), np.float32))[:H, :W]
        out.append(g[..., None])
    return out


def acabamento(img: Image.Image, i: int, estilo: str) -> Image.Image:
    """Grão e vinheta são feitos aqui, por quadro; cor e contraste vão no ffmpeg (ver montar.GRADES)."""
    if estilo == "neutro" or estilo == "frio":
        return img
    W, H = img.size
    arr = np.asarray(img, dtype=np.float32)
    if estilo == "grao-vinheta":
        arr = arr * vinheta(W, H, 0.13) + graos(W, H)[i % 6]
    elif estilo == "quente":
        arr = arr * vinheta(W, H, 0.22)
    return Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))


@lru_cache(maxsize=4)
def degrades(W, H):
    a = np.zeros((H, W), np.float32)
    y = np.arange(H, dtype=np.float32)
    a += np.clip(1 - y / (H * 0.35), 0, 1)[:, None] ** 1.2 * 150
    a += np.clip((y - H * 0.55) / (H * 0.45), 0, 1)[:, None] ** 1.3 * 175
    rgba = np.zeros((H, W, 4), np.uint8)
    rgba[..., 3] = np.clip(a, 0, 255).astype(np.uint8)
    return Image.fromarray(rgba, "RGBA")


@lru_cache(maxsize=None)
def mascara_retangulo(k100: int, W: int, H: int) -> Image.Image:
    e = ease_out(k100 / 100)
    w, h = W * (0.62 + 0.38 * e), H * (0.46 + 0.54 * e)
    r = int(64 * (1 - e))
    msk = Image.new("L", (W, H), 0)
    ImageDraw.Draw(msk).rounded_rectangle(((W - w) / 2, (H - h) / 2, (W + w) / 2, (H + h) / 2), radius=r, fill=255)
    return msk


DESENHA = {
    "titulo": desenha_titulo, "texto": desenha_texto, "contador": desenha_contador, "etiquetas": desenha_etiquetas,
    "checklist": desenha_checklist, "lista": desenha_lista, "passo": desenha_passo, "barra": desenha_barra,
    "marcos": desenha_marcos, "ondas": desenha_ondas, "botao": desenha_botao, "pilula": desenha_pilula,
}
