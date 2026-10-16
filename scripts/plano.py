"""O plano: o que o agente escreve depois de ler o roteiro e o catálogo do bruto.

Tudo no plano é ancorado em PALAVRA, nunca em segundo. O agente diz "a fala c1 vai de 'essa'
até 'gente' no take 094320"; este módulo mede no áudio onde essas palavras caem, aperta os
respiros e converte pra tempo de saída. Ver `references/plano.md` pro formato completo.

    import plano
    p = plano.carregar(projeto / "plano.json", projeto / "trabalho")
    p.resolver_falas()        # janela de cada fala no take (vale de energia entre palavras)
    p.linha_do_tempo()        # tempo de saída de cada pedaço
    ...                       # depois que a voz montada é transcrita:
    p.palavras_saida = [...]
    p.quando("c3", "circulação")   # segundo, na saída, em que a palavra é dita
"""
from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import estilo as es  # noqa: E402
import util  # noqa: E402

FORMATOS = {"9:16": (1080, 1920), "16:9": (1920, 1080), "1:1": (1080, 1080), "4:5": (1080, 1350)}
ENQUADRAMENTOS = {"aberto": (1.0, .5, .45), "medio": (1.12, .5, .40), "fechado": (1.25, .5, .36)}


def limpa(txt: str) -> str:
    """Chave de comparação de palavra: minúscula, sem pontuação; a vírgula só sobrevive
    dentro de número ("99,9%")."""
    s = txt.strip().lower().replace("’", "'")
    s = re.sub(r"(?<!\d),|,(?!\d)", "", s)
    return re.sub(r"[^\w%,]", "", s)


@dataclass
class Fala:
    id: str
    take: str
    de: str
    ate: str
    n_de: int = 1
    n_ate: int = 1
    enquadramento: str = "aberto"
    centro: tuple[float, float] = (0.5, 0.5)   # onde está o falante no quadro de origem (fração), pro recorte 16:9 → 9:16
    # medidos
    janela: tuple[float, float] | None = None
    ini: float = 0.0
    fim: float = 0.0
    apertar: list[tuple[float, float, float]] = field(default_factory=list)
    segmentos: list[tuple[float, float, float]] = field(default_factory=list)  # (ini_fonte, fim_fonte, t0_saida)
    t_de: float = 0.0     # onde o transcritor pôs a primeira palavra (guarda-corpo da medição)
    t_ate: float = 0.0    # e o fim da última

    @property
    def t0(self) -> float:
        return self.segmentos[0][2]

    @property
    def t1(self) -> float:
        a, b, t0 = self.segmentos[-1]
        return t0 + (b - a)

    def para_saida(self, ts: float) -> float:
        for a, b, t0 in self.segmentos:
            if ts <= b:
                return t0 + max(0.0, ts - a)
        a, b, t0 = self.segmentos[-1]
        return t0 + (b - a)


@dataclass
class Apoio:
    fala: str
    de: str
    ate: str
    take: str
    entrada: float = 0.0
    rotulo: str | None = None
    n_de: int = 1
    n_ate: int = 1
    centro: tuple[float, float] = (0.5, 0.5)
    t0: float = 0.0
    t1: float = 0.0


@dataclass
class Plano:
    caminho: Path
    trabalho: Path
    bruto: dict
    falas: list[Fala]
    apoios: list[Apoio]
    capitulos: list[dict]
    pecas: list[dict]
    destaques: set[str]
    correcoes: dict
    cartao_final: dict
    marca: dict
    estilo: es.Estilo
    largura: int
    altura: int
    fps: int
    trilha: Path | None
    titulo: str
    idioma: str
    recorte: str = "preencher"          # ou "caixa": vídeo deitado numa caixa no meio, fundo desfocado
    caixa_largura: int = 1000
    caixa_y: int = 700
    palavras_saida: list[dict] = field(default_factory=list)
    total: float = 0.0

    # ------------------------------------------------------------ fontes
    def take(self, nome: str) -> Path:
        p = self.trabalho / "sdr" / f"{nome}.mp4"
        if not p.exists():
            # apoio de outro projeto: caminho direto
            q = Path(nome)
            if q.exists():
                return q
            raise util.Falha(f"take `{nome}` não existe em {self.trabalho / 'sdr'} (rode preparar)")
        return p

    def limpo(self, nome: str) -> Path:
        p = self.trabalho / "limpo" / f"{nome}.wav"
        if not p.exists():
            raise util.Falha(f"áudio limpo de `{nome}` não existe (rode preparar)")
        return p

    def corrigir(self, palavras: list[dict]) -> list[dict]:
        """Aplica as `correcoes` do plano (o transcritor erra nome próprio e termo técnico) e
        junta número quebrado ("99" ",9" "%" vira "99,9%"). Âncoras e legenda usam o corrigido."""
        out = []
        for w in palavras:
            w = dict(w)
            txt = w["texto"].strip()
            if out and (txt.startswith(",") and txt[1:2].isdigit() or txt == "%" or txt.startswith("-")):
                out[-1]["texto"] = out[-1]["texto"].strip() + txt
                out[-1]["fim"] = w["fim"]
                continue
            nucleo = txt.strip(",.?!;:")
            pont = txt[len(nucleo):] if txt.endswith(tuple(",.?!;:")) else ""
            if nucleo.lower() in self.correcoes:
                txt = self.correcoes[nucleo.lower()] + pont
            w["texto"] = txt
            out.append(w)
        return out

    def transcricao(self, nome: str) -> list[dict]:
        p = self.trabalho / "transcricoes" / f"{nome}.json"
        if not p.exists():
            raise util.Falha(f"transcrição de `{nome}` não existe (rode preparar)")
        return self.corrigir(json.loads(p.read_text(encoding="utf-8"))["palavras"])

    def fala(self, fid: str) -> Fala:
        for f in self.falas:
            if f.id == fid:
                return f
        raise util.Falha(f"fala `{fid}` não existe no plano")

    # ------------------------------------------------------------ energia
    _env: dict = field(default_factory=dict)

    def energia(self, take: str) -> np.ndarray:
        """Volume do áudio limpo em blocos de 10 ms, em dB."""
        if take not in self._env:
            import soundfile as sf

            a, sr = sf.read(self.limpo(take))
            if a.ndim > 1:
                a = a.mean(1)
            h = sr // 100
            n = len(a) // h
            self._env[take] = 20 * np.log10(np.sqrt((a[:n * h].reshape(n, h) ** 2).mean(1)) + 1e-9)
        return self._env[take]

    def vale(self, take: str, a: float, b: float) -> float:
        """O instante mais silencioso entre a e b: é onde o corte não leva pedaço de palavra."""
        e = self.energia(take)
        i0, i1 = max(int(a * 100), 0), min(int(b * 100) + 1, len(e))
        if i1 <= i0:
            return (a + b) / 2
        return (i0 + int(np.argmin(e[i0:i1]))) / 100 + 0.005

    # ------------------------------------------------------------ falas
    def _acha(self, palavras: list[dict], txt: str, n: int, desde: int = 0) -> int:
        alvo = limpa(txt)
        k = 0
        for i in range(desde, len(palavras)):
            if limpa(palavras[i]["texto"]) == alvo:
                k += 1
                if k == n:
                    return i
        raise util.Falha(f"palavra `{txt}` (ocorrência {n}) não está na transcrição a partir da posição {desde}: "
                         f"{' '.join(w['texto'] for w in palavras[desde:desde + 40])} …")

    def janela_da_fala(self, f: Fala) -> tuple[float, float]:
        """Trecho do take entre a palavra `de` e a palavra `ate`, com as bordas no vale de
        energia entre a palavra e a vizinha (o transcritor erra o tempo em até 0,4 s)."""
        ws = self.transcricao(f.take)
        i0 = self._acha(ws, f.de, f.n_de)
        i1 = self._acha(ws, f.ate, f.n_ate, desde=i0)
        f.t_de, f.t_ate = ws[i0]["inicio"], ws[i1]["fim"]
        # A busca do vale fica perto da palavra: se a vizinha está longe (pausa longa, vinheta
        # do vídeo original no meio), o vale não pode ir parar lá dentro.
        if i0 > 0:
            a = self.vale(f.take, max(ws[i0 - 1]["fim"] - 0.15, ws[i0]["inicio"] - 0.9), ws[i0]["inicio"] + 0.45)
        else:
            a = max(0.0, ws[i0]["inicio"] - 0.5)
        if i1 + 1 < len(ws):
            b = self.vale(f.take, ws[i1]["fim"] - 0.1, min(ws[i1 + 1]["inicio"] + 0.35, ws[i1]["fim"] + 0.9))
        else:
            b = ws[i1]["fim"] + 0.6
        return (a, b)

    def medir(self, f: Fala):
        """Onde a fala começa e termina de verdade e quais pausas apertar, no áudio limpo.

        Fala = 10 ms acima de (pico - 24 dB); trechos a menos de 80 ms viram um só; um pedaço
        curto (< 0,2 s) solto no começo ou no fim não conta (respiro, estalo). Pausa interna de
        0,15 s ou mais é apertada: fica 0,08 s, ou 0,14 s se passar de 0,3 s (fim de frase)."""
        e = self.energia(f.take)
        a0, b0 = f.janela
        t = np.arange(len(e)) * 0.01
        pk = np.percentile(e[(t >= a0) & (t < b0)], 97)
        fala = e > pk - 24
        seg, i, n = [], 0, len(e)
        while i < n:
            if fala[i]:
                j = i
                while j < n and fala[j]:
                    j += 1
                seg.append([t[i], t[j - 1] + 0.01])
                i = j
            else:
                i += 1
        seg = [[max(x[0], a0), min(x[1], b0)] for x in seg if x[1] > a0 and x[0] < b0 and x[1] - x[0] >= 0.04]
        m: list[list[float]] = []
        for x in seg:
            if m and x[0] - m[-1][1] < 0.08:
                m[-1][1] = x[1]
            else:
                m.append(x)
        while len(m) > 1 and m[0][1] - m[0][0] < 0.2 and m[1][0] - m[0][1] > 0.12:
            m.pop(0)
        while len(m) > 1 and m[-1][1] - m[-1][0] < 0.2 and m[-1][0] - m[-2][1] > 0.12:
            m.pop()
        if not m:
            raise util.Falha(f"fala `{f.id}`: não achei voz entre {a0:.2f}s e {b0:.2f}s do take {f.take}")
        f.ini, f.fim = max(0.0, m[0][0] - 0.05), m[-1][1] + 0.08
        # Guarda-corpo: começo de frase dito baixinho fica abaixo do limiar de energia e a
        # medição "come" a primeira palavra. O corte nunca começa depois de onde o transcritor
        # pôs a primeira palavra (com folga de 0,15 s), nem termina antes do fim da última.
        f.ini = max(a0, min(f.ini, f.t_de - 0.15))
        f.fim = min(b0, max(f.fim, f.t_ate + 0.05))
        f.apertar = []
        for x, y in zip(m, m[1:]):
            g = y[0] - x[1]
            if g >= 0.15:
                f.apertar.append((x[1], y[0], 0.14 if g > 0.3 else 0.08))

    def resolver_falas(self):
        for f in self.falas:
            f.janela = self.janela_da_fala(f)
            self.medir(f)

    def pedacos(self, f: Fala) -> list[tuple[float, float]]:
        out, cur = [], f.ini
        for a, b, fica in f.apertar:
            out.append((cur, a + fica / 2))
            cur = b - fica / 2
        out.append((cur, f.fim))
        return out

    def linha_do_tempo(self) -> float:
        t = 0.0
        for f in self.falas:
            f.segmentos = []
            for a, b in self.pedacos(f):
                f.segmentos.append((a, b, t))
                t += b - a
        self.total = t
        return t

    # ------------------------------------------------------------ âncoras na saída
    def palavras_da_fala(self, fid: str) -> list[dict]:
        f = self.fala(fid)
        return [w for w in self.palavras_saida if f.t0 - 0.05 <= w["inicio"] < f.t1 + 0.05]

    def quando(self, fid: str, txt: str, n: int = 1, fim=False) -> float:
        """Segundo (na saída) em que a n-ésima `txt` da fala é dita. `fim=True` dá o fim dela.

        Procura primeiro na transcrição da voz montada (tempo exato). Se o transcritor escreveu
        a palavra diferente ali ("clique" em vez de "clica"), cai na transcrição do take, que é
        a mesma em que o plano foi escrito, e converte o tempo pro da saída."""
        f = self.fala(fid)
        try:
            ws = self.palavras_da_fala(fid)
            i = self._acha(ws, txt, n)
            return ws[i]["fim"] if fim else ws[i]["inicio"]
        except util.Falha:
            pass
        a0, b0 = f.janela
        ws = [w for w in self.transcricao(f.take) if w["fim"] > a0 and w["inicio"] < b0]
        try:
            i = self._acha(ws, txt, n)
        except util.Falha:
            raise util.Falha(f"fala `{fid}`: a palavra `{txt}` (ocorrência {n}) não está nem na voz montada nem no take. "
                             f"O que a fala diz: {' '.join(w['texto'] for w in ws)}")
        return f.para_saida(ws[i]["fim"] if fim else ws[i]["inicio"])

    def completar_com_takes(self, voz: list[dict]) -> list[dict]:
        """O transcritor às vezes engole duas ou três palavras depois de uma pausa ("E como fazer
        isso" sumiu numa demo, embora o áudio estivesse lá). Onde a voz montada tem um buraco
        de 0,5 s ou mais e a transcrição do take tem palavra naquele lugar, a palavra do take
        entra, com o tempo convertido pra saída."""
        out = list(voz)
        for f in self.falas:
            tw = [w for w in self.transcricao(f.take) if w["inicio"] >= f.ini - 0.05 and w["fim"] <= f.fim + 0.05]
            for w in tw:
                s, e = f.para_saida(w["inicio"]), f.para_saida(w["fim"])
                if any(not (v["fim"] < s - 0.12 or v["inicio"] > e + 0.12) for v in out):
                    continue
                antes = [v["fim"] for v in out if v["fim"] <= s + 0.12]
                depois = [v["inicio"] for v in out if v["inicio"] >= e - 0.12]
                buraco = (min(depois) if depois else self.total) - (max(antes) if antes else 0.0)
                if buraco < 0.5:
                    continue
                out.append(dict(texto=w["texto"], inicio=round(s, 3), fim=round(e, 3), completado=True))
        out.sort(key=lambda w: w["inicio"])
        return out

    def resolver_apoios(self):
        for a in self.apoios:
            a.t0 = self.quando(a.fala, a.de, a.n_de) - 0.05
            a.t1 = self.quando(a.fala, a.ate, a.n_ate, fim=True) + 0.25
            f = self.fala(a.fala)
            if 0 < f.t1 - a.t1 < 0.5:      # perto do fim da fala: vai até o fim, sem piscar o falante
                a.t1 = f.t1
            a.t1 = min(a.t1, f.t1)
        self.apoios.sort(key=lambda x: x.t0)
        for x, y in zip(self.apoios, self.apoios[1:]):
            if x.t1 > y.t0:
                x.t1 = y.t0

    def inicio_capitulo(self, fid: str) -> float:
        return self.fala(fid).t0


# ---------------------------------------------------------------- carregar
def carregar(caminho: Path, trabalho: Path) -> Plano:
    d = json.loads(Path(caminho).read_text(encoding="utf-8"))
    estilo = es.carregar(d.get("estilo", "agencia"), projeto=Path(caminho).parent)
    fmt = d.get("formato", "9:16")
    if fmt not in FORMATOS:
        raise util.Falha(f"formato `{fmt}` não existe; use um de {sorted(FORMATOS)}")
    if d.get("recorte", "preencher") not in ("preencher", "caixa"):
        raise util.Falha("recorte deve ser `preencher` (corta o que sobra) ou `caixa` (vídeo deitado numa caixa, fundo desfocado)")
    w, h = FORMATOS[fmt]
    falas = [Fala(id=f["id"], take=str(f["take"]), de=f["de"], ate=f["ate"], n_de=f.get("n_de", 1),
                  n_ate=f.get("n_ate", 1), enquadramento=f.get("enquadramento", "aberto"),
                  centro=tuple(f.get("centro", d.get("centro", [0.5, 0.5])))) for f in d["falas"]]
    ids = [f.id for f in falas]
    if len(ids) != len(set(ids)):
        raise util.Falha("duas falas com o mesmo id")
    for f in falas:
        if f.enquadramento not in ENQUADRAMENTOS:
            raise util.Falha(f"enquadramento `{f.enquadramento}` na fala {f.id}; use {sorted(ENQUADRAMENTOS)}")
    apoios = [Apoio(fala=a["fala"], de=a["de"], ate=a["ate"], take=str(a["take"]), entrada=float(a.get("entrada", 0)),
                    rotulo=a.get("rotulo"), n_de=a.get("n_de", 1), n_ate=a.get("n_ate", 1),
                    centro=tuple(a.get("centro", [0.5, 0.5]))) for a in d.get("apoios", [])]
    for a in apoios:
        if a.fala not in ids:
            raise util.Falha(f"apoio aponta pra fala `{a.fala}` que não existe")
    trilha = d.get("trilha", "lofi-calma")
    if trilha:
        cand = util.TRILHAS / f"{trilha}.m4a"
        trilha = cand if cand.exists() else Path(trilha)
        if not Path(trilha).exists():
            raise util.Falha(f"trilha `{trilha}` não existe; as que vêm na skill: "
                             f"{', '.join(p.stem for p in util.TRILHAS.glob('*.m4a'))}")
    marca = {"nome": "", "destaque": "#F5B942", "logo": None, "rodape": "", **d.get("marca", {})}
    return Plano(
        caminho=Path(caminho), trabalho=Path(trabalho), bruto=d, falas=falas, apoios=apoios,
        capitulos=d.get("capitulos", []), pecas=d.get("pecas", []),
        destaques={limpa(x) for x in d.get("destaques", [])}, correcoes={k.lower(): v for k, v in d.get("correcoes", {}).items()},
        cartao_final=d.get("cartao_final", {}), marca=marca, estilo=estilo, largura=w, altura=h,
        fps=int(d.get("fps", 30)), trilha=Path(trilha) if trilha else None,
        titulo=d.get("titulo", Path(caminho).parent.name), idioma=d.get("idioma", "pt"),
        recorte=d.get("recorte", "preencher"), caixa_largura=int(d.get("caixa_largura", 1000)), caixa_y=int(d.get("caixa_y", 700)),
    )


def cor_hex(s: str) -> tuple[int, int, int]:
    s = s.lstrip("#")
    return tuple(int(s[i:i + 2], 16) for i in (0, 2, 4))
