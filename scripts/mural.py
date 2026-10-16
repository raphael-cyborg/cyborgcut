"""O mural: cada opção de cada variável, desenhada no quadro do próprio projeto.

    python scripts/cyborgcut.py estilo mural <projeto> [--variavel legenda,painel] [--base agencia]
    python scripts/cyborgcut.py estilo variacoes <projeto> [--n 8] [--semente 1]

Sai em `<projeto>/saida/estilo/`: `mural.jpg` (tudo), `mural-<variavel>.jpg` (uma por vez) e,
nas variações, `variacoes.jpg` + `variacoes.json` (a combinação inteira de cada uma, pra salvar
depois com `estilo salvar <projeto> <nome> --variacao 3`).

Câmera, entrada e som não aparecem em quadro parado; ficam listados em `estilo opcoes`.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parent))
import estilo as es  # noqa: E402
import montar  # noqa: E402
import pecas  # noqa: E402
import util  # noqa: E402

NAO_VISUAIS = {"camera", "entrada", "som"}
TILE_W = 300  # largura de cada quadrinho no mural


# ---------------------------------------------------------------- escolher o segundo certo
def _peca(cena, *tipos):
    """A primeira peça do primeiro tipo que existir, na ordem de preferência dada."""
    for tipo in tipos:
        for pc in cena.pecas:
            if pc["tipo"] == tipo:
                return pc
    return None


def momentos(cena) -> dict:
    """Pra cada variável, o segundo em que ela aparece melhor neste projeto."""
    p = cena.p
    tit = _peca(cena, "titulo", "texto", "passo", "contador")
    t_tit = (tit["t0"] + 1.2) if tit else min(1.2, p.total * 0.3)
    lst = _peca(cena, "checklist", "lista", "marcos", "barra", "passo", "etiquetas")
    if lst:
        itens = lst.get("itens") or []
        t_lst = (itens[-1]["t"] + 0.5) if itens and isinstance(itens[0], dict) else lst["t0"] + 1.6
        t_lst = min(t_lst, lst["t1"] - 0.1)
    else:
        t_lst = t_tit
    # legenda: um bloco com palavra de destaque, no fim da última palavra
    t_leg = None
    for b in cena.blocos:
        if any(pecas._limpa(w) in p.destaques for w in b["ws"]) and len(b["ws"]) >= 2:
            t_leg = b["ws"][-1]["inicio"] + 0.12
            break
    if t_leg is None and cena.blocos:
        b = cena.blocos[min(2, len(cena.blocos) - 1)]
        t_leg = b["ws"][-1]["inicio"] + 0.12
    t_leg = t_leg if t_leg is not None else t_tit
    t_apoio = (p.apoios[0].t0 + 0.14) if p.apoios else None
    t_fim = p.total + 1.7
    return {
        "fonte_titulo": t_tit, "titulo_caixa": t_tit, "fonte_texto": t_lst,
        "legenda": t_leg, "legenda_caixa": t_leg, "legenda_tamanho": t_leg, "legenda_posicao": t_leg,
        "painel": t_lst, "marcador": t_lst, "tag": t_tit, "assinatura": t_leg,
        "transicao_apoio": t_apoio, "acabamento": t_tit, "cartao_final": t_fim,
        "_titulo": t_tit, "_lista": t_lst, "_legenda": t_leg, "_fim": t_fim,
    }


# ---------------------------------------------------------------- desenhar
def _rotulo(im: Image.Image, txt: str, sub: str = ""):
    d = ImageDraw.Draw(im)
    f = pecas._fonte(str(util.FONTE_MONO), 15, None)
    w = max(f.getlength(txt), f.getlength(sub)) + 16
    d.rectangle((0, 0, w, 24 + (18 if sub else 0)), fill=(0, 0, 0))
    d.text((8, 4), txt, font=f, fill=(255, 255, 255))
    if sub:
        d.text((8, 22), sub, font=f, fill=(180, 180, 180))
    return im


def tile(cena, t, e, rotulo="", sub="") -> Image.Image:
    c = cena.com_estilo(e)
    im = c.quadro_solto(t)
    h = int(TILE_W * c.H / c.W)
    return _rotulo(im.resize((TILE_W, h), Image.LANCZOS), rotulo, sub)


def linha(tiles: list[Image.Image], titulo: str, largura_rotulo=190) -> Image.Image:
    h = tiles[0].height
    out = Image.new("RGB", (largura_rotulo + len(tiles) * (TILE_W + 6), h + 8), (24, 24, 26))
    d = ImageDraw.Draw(out)
    f = pecas._fonte(str(util.FONTE_TITULO), 20, 700)
    y = 12
    for parte in titulo.split("\n"):
        d.text((12, y), parte, font=f, fill=(255, 255, 255))
        y += 26
    for i, tl in enumerate(tiles):
        out.paste(tl, (largura_rotulo + i * (TILE_W + 6), 4))
    return out


def empilha(linhas: list[Image.Image]) -> Image.Image:
    w = max(l.width for l in linhas)
    out = Image.new("RGB", (w, sum(l.height for l in linhas)), (24, 24, 26))
    y = 0
    for l in linhas:
        out.paste(l, (0, y))
        y += l.height
    return out


def mural(projeto: Path, variaveis: list[str] | None = None, base: str | None = None, tempos: dict | None = None) -> Path:
    projeto = Path(projeto)
    saida = projeto / "saida" / "estilo"
    saida.mkdir(parents=True, exist_ok=True)
    crono = util.Cronometro(projeto / "trabalho" / "tempos.tsv")
    util.esperar_maquina()
    cena, _ = montar.preparar_cena(projeto, None, crono, base)
    base_e = cena.e
    mom = {**momentos(cena), **(tempos or {})}
    quais = variaveis or [v for v in es.VARIAVEIS if v not in NAO_VISUAIS]
    linhas = []
    with crono.etapa("mural de estilos"):
        for var in quais:
            if var not in es.VARIAVEIS:
                raise util.Falha(f"variável `{var}` não existe; veja `estilo opcoes`")
            if var in NAO_VISUAIS:
                print(f"  {var}: não dá pra ver em quadro parado, pulei (opções em `estilo opcoes`)")
                continue
            t = mom.get(var)
            if t is None:
                print(f"  {var}: este projeto não tem apoio, pulei")
                continue
            tiles = []
            partida = dict(base_e.escolhas)
            if var == "marcador" and base_e.painel == "blocos-cor":
                partida["painel"] = "escuro-arredondado"  # blocos-cor tem a própria marca; mostra o marcador num painel
                print("  marcador: o painel blocos-cor não usa marcador, mostrei num painel escuro")
            for opc, desc in es.VARIAVEIS[var]["o"].items():
                e = es.Estilo(f"{var}={opc}", {**partida, var: opc})
                marca = " (atual)" if base_e.escolhas.get(var, es.VARIAVEIS[var]["p"]) == opc else ""
                tiles.append(tile(cena, t, e, opc + marca, desc[:40]))
            ln = linha(tiles, var.replace("_", "\n"))
            ln.save(saida / f"mural-{var}.jpg", quality=86)
            linhas.append(ln)
            print(f"  {var}: {len(tiles)} opções em t={t:.2f}s")
    out = saida / "mural.jpg"
    empilha(linhas).save(out, quality=84)
    print(f"mural em {out} (e um mural-<variavel>.jpg por variável)")
    return out


def variacoes(projeto: Path, n: int = 8, semente: int = 1, base: str | None = None) -> Path:
    projeto = Path(projeto)
    saida = projeto / "saida" / "estilo"
    saida.mkdir(parents=True, exist_ok=True)
    crono = util.Cronometro(projeto / "trabalho" / "tempos.tsv")
    util.esperar_maquina()
    cena, _ = montar.preparar_cena(projeto, None, crono, base)
    mom = momentos(cena)
    linhas, registro = [], []
    with crono.etapa(f"{n} variações de estilo"):
        for i in range(n):
            e = es.aleatorio(semente * 1000 + i)
            tiles = [tile(cena, mom["_titulo"], e, f"#{i + 1} título"), tile(cena, mom["_lista"], e, f"#{i + 1} lista"),
                     tile(cena, mom["_legenda"], e, f"#{i + 1} legenda"), tile(cena, mom["_fim"], e, f"#{i + 1} cartão")]
            resumo = "\n".join(f"{k}: {v}" for k, v in e.escolhas.items() if v != es.VARIAVEIS[k]["p"])
            ln = linha(tiles, f"#{i + 1}", largura_rotulo=60)
            # descrição embaixo da linha
            f = pecas._fonte(str(util.FONTE_MONO), 13, None)
            desc = Image.new("RGB", (ln.width, 14 * (resumo.count("\n") + 1) + 12), (24, 24, 26))
            ImageDraw.Draw(desc).multiline_text((66, 6), resumo or "(tudo no padrão)", font=f, fill=(200, 200, 200), spacing=2)
            linhas += [ln, desc]
            registro.append({"n": i + 1, **e.escolhas})
            print(f"  #{i + 1}: {', '.join(f'{k}={v}' for k, v in e.escolhas.items())}")
    out = saida / "variacoes.jpg"
    empilha(linhas).save(out, quality=84)
    (saida / "variacoes.json").write_text(json.dumps(registro, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"variações em {out} e {saida / 'variacoes.json'}")
    return out
