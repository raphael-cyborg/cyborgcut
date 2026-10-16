"""CyborgCut: o agente edita o vídeo a partir do roteiro. Este é o comando único.

    python scripts/cyborgcut.py doctor                  o que a máquina tem e o que falta
    python scripts/cyborgcut.py preparar <projeto>      cor, voz limpa, transcrição, folhas, catálogo
    python scripts/cyborgcut.py montar <projeto>        renderiza <projeto>/plano.json em saida/
    python scripts/cyborgcut.py conferir <projeto>      retranscreve, procura piscada e quadro preto, mede o volume
    python scripts/cyborgcut.py comparar <projeto> <referencia.mp4>   lado a lado com um vídeo de referência
    python scripts/cyborgcut.py estilo opcoes                 as variáveis do estilo e as opções de cada uma
    python scripts/cyborgcut.py estilo mural <projeto>        cada opção desenhada no quadro do projeto
    python scripts/cyborgcut.py estilo variacoes <projeto>    combinações aleatórias inteiras
    python scripts/cyborgcut.py estilo salvar <projeto> <nome> --base agencia --set legenda=karaoke-caixa

Um projeto é uma pasta com `bruto/` (os vídeos), `roteiro.md` (o que o vídeo tem que dizer) e,
depois que o agente planeja, `plano.json`. Tudo que a skill gera vai pra `trabalho/` e `saida/`.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import util  # noqa: E402


def doctor() -> int:
    """Diz, em uma tabela, o que esta máquina consegue fazer."""
    import importlib

    linhas = []
    falta = 0

    def ok(nome, bom, detalhe, obrigatorio=True):
        nonlocal falta
        marca = "ok " if bom else ("FALTA" if obrigatorio else "opcional")
        if not bom and obrigatorio:
            falta += 1
        linhas.append(f"  {marca:8s} {nome:28s} {detalhe}")

    ff = util.tem("ffmpeg")
    ver = ""
    if ff:
        ver = util.run(["ffmpeg", "-version"]).stdout.splitlines()[0].split()[2]
    ok("ffmpeg", bool(ff), f"versão {ver}" if ff else "instale: brew install ffmpeg | apt install ffmpeg | gyan.dev (Windows, build full)")
    ok("ffprobe", bool(util.tem("ffprobe")), "")
    if ff:
        ok("arnndn (limpeza de voz)", util.tem_filtro("arnndn"), "vem no ffmpeg 4.3+")
        modo = "avconvert (Apple)" if util.so() == "mac" and util.tem("avconvert") else \
               "zscale + tonemap (ffmpeg)" if util.tem_filtro("zscale") and util.tem_filtro("tonemap") else \
               "aproximação (sem zscale; cor do HDR fica lavada)"
        ok("conversão de HDR", "aproximação" not in modo, modo, obrigatorio=False)
    for mod, nome in (("numpy", "numpy"), ("PIL", "pillow"), ("soundfile", "soundfile")):
        try:
            importlib.import_module(mod)
            ok(nome, True, "")
        except Exception:
            ok(nome, False, "uv pip install -e .")
    import transcrever

    disp = transcrever.disponiveis()
    dica = "Mac: uv pip install -e '.[mac]'   outros: uv pip install -e '.[cpu]'   ou brew install whisper-cpp"
    ok("transcritor", bool(disp), ", ".join(disp) if disp else dica)
    import estilo as es

    faltam = [n for n, (arq, *_) in es.FONTES.items() if not (util.ASSETS / "fontes" / arq).exists()]
    ok("fontes", not faltam, "7 famílias OFL" if not faltam else "faltam: " + ", ".join(faltam))
    ok("modelo de ruído", util.RNNOISE.exists(), "RNNoise sh (domínio público)")
    ok("trilhas", any(util.TRILHAS.glob("*.m4a")), ", ".join(p.stem for p in util.TRILHAS.glob("*.m4a")) + " (CC0)")
    print(f"cyborgcut doctor  ({util.so()}, {'Apple Silicon' if util.apple_silicon() else 'x86/outros'})")
    print("\n".join(linhas))
    print("tudo pronto." if not falta else f"{falta} coisa(s) faltando.")
    return 0 if not falta else 1


def estilo_cmd(a) -> int:
    import estilo as es

    if a.acao == "opcoes":
        print(es.listar())
        return 0
    import mural

    if a.acao == "mural":
        tempos = {}
        for par in (a.t or "").split(","):
            if "=" in par:
                k, v = par.split("=", 1)
                tempos[k.strip()] = float(v)
        mural.mural(a.projeto, a.variavel.split(",") if a.variavel else None, a.base, tempos)
        return 0
    if a.acao == "variacoes":
        mural.variacoes(a.projeto, a.n, a.semente)
        return 0
    if a.acao == "salvar":
        over = {}
        if a.variacao:
            reg = a.projeto / "saida" / "estilo" / "variacoes.json"
            if not reg.exists():
                raise util.Falha("rode `estilo variacoes` antes de salvar por número")
            import json

            lista = json.loads(reg.read_text(encoding="utf-8"))
            item = next((x for x in lista if x["n"] == a.variacao), None)
            if not item:
                raise util.Falha(f"variação #{a.variacao} não existe (tem {len(lista)})")
            over = {k: v for k, v in item.items() if k != "n"}
        for par in a.set:
            if "=" not in par:
                raise util.Falha(f"--set espera variavel=opcao, veio `{par}`")
            k, v = par.split("=", 1)
            over[k.strip()] = v.strip()
        destino = es.PASTA_USUARIO if a.global_ else a.projeto / "estilos"
        arq = es.salvar(a.nome, a.base, over, destino)
        print(f"estilo `{a.nome}` salvo em {arq}\nno plano: \"estilo\": \"{a.nome}\"")
        return 0
    return 1


def main(argv=None):
    ap = argparse.ArgumentParser(prog="cyborgcut", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("doctor")
    p = sub.add_parser("preparar")
    p.add_argument("projeto", type=Path)
    p.add_argument("--idioma", default="pt")
    p.add_argument("--backend", default="auto")
    p.add_argument("--refazer", action="store_true")
    m = sub.add_parser("montar")
    m.add_argument("projeto", type=Path)
    m.add_argument("--plano", type=Path, help="padrão: <projeto>/plano.json")
    m.add_argument("--previa", help="segundos separados por vírgula: só desenha esses quadros em saida/previa/")
    m.add_argument("--nome", help="nome do mp4 de saída (padrão: <titulo>.mp4)")
    m.add_argument("--estilo", help="ignora o `estilo` do plano e usa este (preset, salvo ou caminho de JSON)")
    c = sub.add_parser("conferir")
    c.add_argument("projeto", type=Path)
    c.add_argument("--video", type=Path, help="padrão: o último mp4 em saida/")
    k = sub.add_parser("comparar")
    k.add_argument("projeto", type=Path)
    k.add_argument("referencia", type=Path)
    k.add_argument("--video", type=Path)
    e = sub.add_parser("estilo")
    es_sub = e.add_subparsers(dest="acao", required=True)
    es_sub.add_parser("opcoes")
    mu = es_sub.add_parser("mural")
    mu.add_argument("projeto", type=Path)
    mu.add_argument("--variavel", help="só estas, separadas por vírgula (padrão: todas as visuais)")
    mu.add_argument("--base", help="estilo de partida (padrão: o do plano)")
    mu.add_argument("--t", help="segundo fixo pra uma variável: legenda=12.4,painel=30")
    va = es_sub.add_parser("variacoes")
    va.add_argument("projeto", type=Path)
    va.add_argument("--n", type=int, default=8)
    va.add_argument("--semente", type=int, default=1)
    sa = es_sub.add_parser("salvar")
    sa.add_argument("projeto", type=Path)
    sa.add_argument("nome")
    sa.add_argument("--base", default="agencia")
    sa.add_argument("--set", action="append", default=[], help="variavel=opcao (repita)")
    sa.add_argument("--variacao", type=int, help="número de uma variação gerada antes")
    sa.add_argument("--global", dest="global_", action="store_true", help="salva em ~/.cyborgcut/estilos/ (vale pra todo projeto)")
    a = ap.parse_args(argv)

    if a.cmd == "doctor":
        return doctor()
    if a.cmd == "preparar":
        import preparar

        preparar.preparar(a.projeto, a.idioma, a.backend, so_faltantes=not a.refazer)
        return 0
    if a.cmd == "montar":
        import montar

        montar.montar(a.projeto, a.plano, a.previa, a.nome, a.estilo)
        return 0
    if a.cmd == "estilo":
        return estilo_cmd(a)
    if a.cmd == "conferir":
        import conferir

        return conferir.conferir(a.projeto, a.video)
    if a.cmd == "comparar":
        import conferir

        conferir.comparar(a.projeto, a.referencia, a.video)
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
