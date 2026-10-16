"""O estilo: o arsenal de variáveis visuais e as combinações salvas.

Um estilo é um conjunto de escolhas, uma por variável (fonte do título, legenda, painel, tag,
assinatura, transição, câmera, entrada, acabamento, cartão final…). Quatro combinações vêm
prontas (`agencia`, `editorial`, `impacto`, `clean`, mais `limpo`), mas o uso certo é a pessoa
montar a dela olhando as opções no próprio vídeo e salvar em `estilos/<nome>.json`. Daí em
diante todo plano diz só `"estilo": "<nome>"`.

    python scripts/cyborgcut.py estilo opcoes                       # a lista de variáveis e opções
    python scripts/cyborgcut.py estilo mural <projeto>              # cada opção, no quadro do projeto
    python scripts/cyborgcut.py estilo variacoes <projeto> --n 8    # combinações aleatórias, inteiras
    python scripts/cyborgcut.py estilo salvar <projeto> <nome> --base agencia --set legenda=karaoke-caixa

O arquivo salvo é pequeno: a base e só o que muda.

    {"base": "agencia", "legenda": "karaoke-caixa", "fonte_titulo": "oswald"}
"""
from __future__ import annotations

import json
import random
import sys
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import util  # noqa: E402

PASTA_ESTILOS = util.RAIZ / "estilos"                       # os que vêm com a skill
PASTA_USUARIO = Path.home() / ".cyborgcut" / "estilos"     # os da pessoa, valem em todo projeto

# ---------------------------------------------------------------- fontes
# nome → (arquivo, peso padrão pra título, peso pra texto, caixa alta por natureza)
FONTES = {
    "montserrat": ("Montserrat[wght].ttf", 820, 640, False),
    "playfair": ("PlayfairDisplay[wght].ttf", 600, 500, False),
    "bebas": ("BebasNeue-Regular.ttf", None, None, True),
    "oswald": ("Oswald[wght].ttf", 600, 500, True),
    "space-grotesk": ("SpaceGrotesk[wght].ttf", 600, 500, False),
    "inter": ("Inter[opsz,wght].ttf", 700, 500, False),
    "plex-mono": ("IBMPlexMono-Regular.ttf", None, None, False),
}

# ---------------------------------------------------------------- variáveis
# ordem = ordem do mural. Cada opção com uma frase do que ela é.
VARIAVEIS: dict[str, dict] = {
    "fonte_titulo": {"o": {
        "montserrat": "geométrica, pesada, a cara de agência digital",
        "playfair": "serifa de revista, elegante",
        "bebas": "condensada em caixa alta, impacto",
        "oswald": "condensada média, esportiva",
        "space-grotesk": "grotesca com personalidade, cara de tecnologia",
        "inter": "neutra, sistema, lê em qualquer tamanho"}, "p": "montserrat"},
    "fonte_texto": {"o": {
        "montserrat": "mesma família do título agência",
        "inter": "neutra e muito legível em legenda",
        "oswald": "condensada, combina com impacto",
        "space-grotesk": "tecnológica",
        "playfair": "serifa, só pra editorial calmo"}, "p": "montserrat"},
    "titulo_caixa": {"o": {"normal": "Como se escreve", "alta": "TUDO EM MAIÚSCULA"}, "p": "normal"},
    "legenda": {"o": {
        "palavra-sublinhado": "palavra a palavra, destaque na cor com sublinhado que cresce",
        "bloco-contorno": "frase inteira em caixa alta com contorno preto, estilo reel",
        "karaoke-caixa": "palavra atual com caixa na cor atrás e texto escuro",
        "barra-preta": "frase sobre uma barra preta sólida, cara de revista",
        "pilula": "frase numa pílula escura translúcida, palavra atual na cor"}, "p": "palavra-sublinhado"},
    "legenda_caixa": {"o": {"normal": "como se fala", "alta": "MAIÚSCULA"}, "p": "normal"},
    "legenda_tamanho": {"o": {"pequena": "discreta", "media": "padrão", "grande": "domina a tela"}, "p": "media"},
    "legenda_posicao": {"o": {"baixo": "abaixo do rosto, perto do fim", "centro": "no meio da tela (quem lê sem som)"}, "p": "baixo"},
    "painel": {"o": {
        "escuro-arredondado": "fundo escuro translúcido, canto redondo",
        "claro-arredondado": "fundo claro translúcido, texto escuro",
        "blocos-cor": "cada item é um bloco sólido na cor da marca",
        "linhas": "sem fundo, só texto, número e linha fina"}, "p": "escuro-arredondado"},
    "marcador": {"o": {"check": "círculo que vira check", "numero": "01, 02, 03", "traco": "traço na cor", "bloco": "quadrado que preenche"}, "p": "check"},
    "tag": {"o": {
        "ponto-mono": "quadradinho na cor, MARCA | 01 CAPÍTULO em fonte mono",
        "barra": "barra vertical na cor + texto",
        "pilula": "pílula branca com texto escuro",
        "linha-versalete": "linha fina + versalete, editorial",
        "bloco-cor": "bloco sólido na cor, texto escuro",
        "nenhuma": "sem tag"}, "p": "ponto-mono"},
    "assinatura": {"o": {
        "onda": "linha de onda sob a legenda que reage à voz",
        "barra": "barra de progresso grossa",
        "linha": "linha fina de progresso com ponto",
        "nenhuma": "nada"}, "p": "onda"},
    "transicao_apoio": {"o": {
        "mascara": "a imagem de apoio cresce do centro",
        "corte": "corte seco",
        "deslize": "entra pela direita empurrando",
        "fade": "fusão rápida"}, "p": "mascara"},
    "camera": {"o": {
        "avanco": "avanço lento contínuo em cada tomada",
        "zoom-corte": "pequeno zoom a cada corte, que assenta",
        "fixa": "parada"}, "p": "avanco"},
    "entrada": {"o": {"mola": "entra passando do ponto e volta", "suave": "entra desacelerando", "seca": "aparece"}, "p": "suave"},
    "acabamento": {"o": {
        "grao-vinheta": "grão fino, vinheta leve, curva em S",
        "neutro": "a cor do bruto",
        "frio": "dessaturado e azulado, sóbrio",
        "quente": "contraste e calor, vinheta forte"}, "p": "grao-vinheta"},
    "cartao_final": {"o": {
        "logo-sobe": "onda atravessa, logo sobe, duas linhas e rodapé",
        "nome": "nome da marca em tipografia grande",
        "cor-solida": "fundo na cor da marca, texto escuro",
        "minimo": "preto, logo ou nome pequeno, nada mais"}, "p": "logo-sobe"},
    "som": {"o": {"efeitos": "tiques, toques e sopros discretos", "so-trilha": "só voz e trilha"}, "p": "efeitos"},
}

PRESETS: dict[str, dict] = {
    "agencia": {},
    "limpo": {"legenda": "bloco-contorno", "legenda_caixa": "alta", "tag": "nenhuma", "assinatura": "nenhuma",
              "transicao_apoio": "corte", "camera": "fixa", "entrada": "suave", "acabamento": "neutro",
              "cartao_final": "nome", "som": "so-trilha"},
    "editorial": {"fonte_titulo": "playfair", "fonte_texto": "inter", "legenda": "barra-preta", "painel": "linhas",
                  "marcador": "numero", "tag": "linha-versalete", "assinatura": "nenhuma", "transicao_apoio": "corte",
                  "camera": "fixa", "entrada": "suave", "acabamento": "frio", "cartao_final": "nome", "som": "so-trilha"},
    "impacto": {"fonte_titulo": "bebas", "fonte_texto": "oswald", "titulo_caixa": "alta", "legenda": "karaoke-caixa",
                "legenda_caixa": "alta", "legenda_tamanho": "grande", "painel": "blocos-cor", "marcador": "traco",
                "tag": "bloco-cor", "assinatura": "barra", "transicao_apoio": "deslize", "camera": "zoom-corte",
                "entrada": "mola", "acabamento": "quente", "cartao_final": "cor-solida"},
    "clean": {"fonte_titulo": "space-grotesk", "fonte_texto": "inter", "legenda": "pilula", "painel": "claro-arredondado",
              "marcador": "check", "tag": "pilula", "assinatura": "linha", "transicao_apoio": "fade", "camera": "fixa",
              "entrada": "suave", "acabamento": "neutro", "cartao_final": "minimo", "som": "so-trilha"},
}


@dataclass
class Estilo:
    nome: str
    escolhas: dict = field(default_factory=dict)

    def __getattr__(self, k):
        if k in VARIAVEIS:
            return self.escolhas.get(k, VARIAVEIS[k]["p"])
        raise AttributeError(k)

    # fontes resolvidas
    def fonte_arquivo(self, qual: str) -> Path:
        return util.ASSETS / "fontes" / FONTES[getattr(self, qual)][0]

    def peso_titulo(self):
        return FONTES[self.fonte_titulo][1]

    def peso_texto(self):
        return FONTES[self.fonte_texto][2]

    @property
    def titulo_em_caixa_alta(self) -> bool:
        return self.titulo_caixa == "alta" or FONTES[self.fonte_titulo][3]

    @property
    def legenda_em_caixa_alta(self) -> bool:
        return self.legenda_caixa == "alta" or self.legenda == "bloco-contorno"

    @property
    def painel_claro(self) -> bool:
        return self.painel == "claro-arredondado"

    @property
    def com_acabamento(self) -> bool:
        return self.acabamento != "neutro"

    def resumo(self) -> str:
        return ", ".join(f"{k}={self.escolhas.get(k, VARIAVEIS[k]['p'])}" for k in VARIAVEIS)

    def como_json(self, base: str | None = None) -> dict:
        d = {"base": base} if base else {}
        d.update(self.escolhas)
        return d


def validar(escolhas: dict, origem: str):
    for k, v in escolhas.items():
        if k == "base":
            continue
        if k not in VARIAVEIS:
            raise util.Falha(f"{origem}: variável `{k}` não existe. As que existem: {', '.join(VARIAVEIS)}")
        if v not in VARIAVEIS[k]["o"]:
            raise util.Falha(f"{origem}: `{k}` não aceita `{v}`; opções: {', '.join(VARIAVEIS[k]['o'])}")


def carregar(nome_ou_dict, projeto: Path | None = None) -> Estilo:
    """`agencia` (preset) · `multivias` (estilos/multivias.json no projeto ou na skill) · caminho
    de um JSON · um dict já aberto. O JSON pode ter `base`."""
    if isinstance(nome_ou_dict, dict):
        d, nome = dict(nome_ou_dict), nome_ou_dict.get("nome", "inline")
    else:
        nome = str(nome_ou_dict)
        if nome in PRESETS:
            return Estilo(nome, dict(PRESETS[nome]))
        cands = []
        if projeto:
            cands += [Path(projeto) / "estilos" / f"{nome}.json", Path(projeto) / f"{nome}.json"]
        cands += [PASTA_USUARIO / f"{nome}.json", PASTA_ESTILOS / f"{nome}.json", Path(nome)]
        arq = next((c for c in cands if c.exists()), None)
        if arq is None:
            salvos = [q.stem for pasta in (PASTA_USUARIO, PASTA_ESTILOS) if pasta.exists() for q in pasta.glob("*.json")]
            raise util.Falha(f"estilo `{nome}` não existe. Presets: {', '.join(PRESETS)}. Salvos: {', '.join(salvos) or 'nenhum'}")
        d = json.loads(arq.read_text(encoding="utf-8"))
        nome = arq.stem
    validar(d, f"estilo {nome}")
    base = d.pop("base", "agencia")
    if base not in PRESETS:
        raise util.Falha(f"estilo {nome}: base `{base}` não é um preset ({', '.join(PRESETS)})")
    escolhas = dict(PRESETS[base])
    escolhas.update({k: v for k, v in d.items() if k != "nome"})
    return Estilo(nome, escolhas)


def salvar(nome: str, base: str, overrides: dict, destino: Path) -> Path:
    validar(overrides, "salvar")
    destino.mkdir(parents=True, exist_ok=True)
    arq = destino / f"{nome}.json"
    arq.write_text(json.dumps({"base": base, **overrides}, ensure_ascii=False, indent=2), encoding="utf-8")
    return arq


def aleatorio(semente: int) -> Estilo:
    rng = random.Random(semente)
    esc = {k: rng.choice(list(v["o"])) for k, v in VARIAVEIS.items()}
    # combinações que não fazem sentido
    if esc["fonte_titulo"] == "bebas":
        esc["titulo_caixa"] = "alta"
    if esc["legenda"] == "bloco-contorno":
        esc["legenda_caixa"] = "alta"
    return Estilo(f"variacao-{semente}", esc)


def listar() -> str:
    linhas = ["# Variáveis do estilo", ""]
    for k, v in VARIAVEIS.items():
        linhas.append(f"## {k}  (padrão: {v['p']})")
        for o, desc in v["o"].items():
            linhas.append(f"- `{o}`: {desc}")
        linhas.append("")
    linhas.append("# Presets")
    for n, d in PRESETS.items():
        linhas.append(f"- `{n}`: " + (", ".join(f"{a}={b}" for a, b in d.items()) or "o padrão de tudo"))
    return "\n".join(linhas)
