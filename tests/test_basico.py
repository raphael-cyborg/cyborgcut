"""Testes das partes puras: comparação de palavra, correções, quebra de legenda, medição de corte."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import estilo as es  # noqa: E402
import pecas  # noqa: E402
import plano  # noqa: E402


def test_limpa_ignora_pontuacao_e_caixa():
    assert plano.limpa("Pessoal,") == "pessoal"
    assert plano.limpa("Fina!") == "fina"
    assert plano.limpa("sequer.") == "sequer"
    assert plano.limpa("Não") == "não"


def test_limpa_mantem_virgula_de_numero():
    assert plano.limpa("99,9%") == "99,9%"
    assert plano.limpa("3,") == "3"


def _plano_vazio(correcoes=None):
    return plano.Plano(caminho=Path("x"), trabalho=Path("x"), bruto={}, falas=[], apoios=[], capitulos=[], pecas=[],
                       destaques=set(), correcoes=correcoes or {}, cartao_final={}, marca={}, estilo=es.carregar("agencia"),
                       largura=1080, altura=1920, fps=30, trilha=None, titulo="t", idioma="pt")


def test_corrigir_junta_numero_quebrado_e_troca_termo():
    p = _plano_vazio({"mecanológico": "mercadológico"})
    ws = [dict(texto="estudo", inicio=0, fim=0.3), dict(texto="mecanológico,", inicio=0.3, fim=0.9),
          dict(texto="99", inicio=1.0, fim=1.2), dict(texto=",9", inicio=1.2, fim=1.4), dict(texto="%", inicio=1.4, fim=1.6)]
    out = p.corrigir(ws)
    assert [w["texto"] for w in out] == ["estudo", "mercadológico,", "99,9%"]
    assert out[-1]["fim"] == 1.6


def test_quebra_legenda_nao_termina_em_palavra_de_ligacao():
    f = pecas.fonte(66, 720)
    ws = [dict(texto=t, inicio=i * 0.3, fim=i * 0.3 + 0.25) for i, t in
          enumerate("a loja continua operando enquanto a transformação acontece.".split())]
    grupos = pecas.quebra_legenda(ws, f, 900)
    assert all(len(g) <= 4 for g in grupos)
    for g in grupos[:-1]:
        assert pecas._limpa(g[-1]) not in pecas.FUNCAO, [w["texto"] for w in g]
    assert " ".join(w["texto"] for g in grupos for w in g) == " ".join(w["texto"] for w in ws)


def test_quebra_legenda_nao_separa_saiba_mais():
    f = pecas.fonte(66, 720)
    ws = [dict(texto=t, inicio=i * 0.3, fim=i * 0.3 + 0.25) for i, t in enumerate("Clica em Saiba Mais e conheça".split())]
    grupos = pecas.quebra_legenda(ws, f, 900)
    juntos = [" ".join(pecas._limpa(w) for w in g) for g in grupos]
    assert any("saiba mais" in j for j in juntos)


def test_medir_acha_fala_e_aperta_pausa(tmp_path):
    """Áudio sintético: 1 s de silêncio, 1 s de tom, 0,5 s de pausa, 1 s de tom, silêncio."""
    import soundfile as sf

    sr = 48000
    t = np.arange(sr) / sr
    tom = 0.3 * np.sin(2 * np.pi * 220 * t)
    sil = np.zeros(sr)
    a = np.concatenate([sil, tom, sil[: sr // 2], tom, sil]) + np.random.default_rng(0).normal(0, 1e-4, 4 * sr + sr // 2)
    (tmp_path / "limpo").mkdir()
    sf.write(tmp_path / "limpo" / "x.wav", a, sr)
    p = _plano_vazio()
    p.trabalho = tmp_path
    f = plano.Fala(id="f", take="x", de="a", ate="b")
    f.janela = (0.5, 4.0)
    f.t_de, f.t_ate = 1.05, 3.5  # onde o transcritor teria posto a primeira e a última palavra
    p.medir(f)
    assert 0.85 <= f.ini <= 1.0
    assert 3.45 <= f.fim <= 3.65
    assert len(f.apertar) == 1
    a0, b0, fica = f.apertar[0]
    assert 1.95 <= a0 <= 2.05 and 2.45 <= b0 <= 2.55 and fica == 0.14


def test_formato_invalido_da_erro(tmp_path):
    (tmp_path / "plano.json").write_text('{"formato": "2:3", "falas": []}', encoding="utf-8")
    with pytest.raises(SystemExit):
        plano.carregar(tmp_path / "plano.json", tmp_path)


def test_estilo_preset_e_salvo(tmp_path):
    ag = es.carregar("agencia")
    assert ag.legenda == "palavra-sublinhado" and ag.fonte_titulo == "montserrat"
    imp = es.carregar("impacto")
    assert imp.fonte_titulo == "bebas" and imp.titulo_em_caixa_alta
    arq = es.salvar("meu", "editorial", {"legenda": "karaoke-caixa"}, tmp_path / "estilos")
    meu = es.carregar("meu", projeto=tmp_path)
    assert meu.fonte_titulo == "playfair" and meu.legenda == "karaoke-caixa"
    assert arq.name == "meu.json"


def test_estilo_invalido_da_erro():
    with pytest.raises(SystemExit):
        es.carregar({"legenda": "nao-existe"})
    with pytest.raises(SystemExit):
        es.carregar({"variavel_que_nao_existe": "x"})
    with pytest.raises(SystemExit):
        es.carregar("estilo-que-nao-existe")


def test_toda_opcao_de_estilo_desenha_sem_quebrar():
    """Cada opção de cada variável, num quadro falso, passa por todas as peças e pela legenda."""
    from PIL import Image

    ws = [dict(texto=t, inicio=i * 0.3, fim=i * 0.3 + 0.25) for i, t in enumerate("Pequenas empresas, grandes marcas.".split())]
    pcs = [
        dict(tipo="titulo", t0=0, t1=5, linhas=[["Pequenas empresas,", "branco"], ["grandes marcas.", "destaque"]]),
        dict(tipo="checklist", t0=0, t1=5, itens=[dict(texto="Técnicas", t=0.2), dict(texto="Cases", t=0.6)]),
        dict(tipo="etiquetas", t0=0, t1=5, titulo="Tudo em dia", itens=[dict(texto="Trabalhar", t=0.1)]),
        dict(tipo="lista", t0=0, t1=5, itens=["Um", "Dois"]),
        dict(tipo="passo", t0=0, t1=5, numero=2, total=4, nome="Diagnóstico"),
        dict(tipo="barra", t0=0, t1=5, n=3, acende=0.2),
        dict(tipo="marcos", t0=0, t1=5, itens=[dict(texto="30d", t=0.1), dict(texto="60d", t=0.5)], titulo="Prazo"),
        dict(tipo="ondas", t0=0, t1=5, t_a=0.1, t_b=0.3, une=0.6, rotulos=["A", "B"]),
        dict(tipo="botao", t0=0, t1=5, texto="Clica", toque=0.8),
        dict(tipo="texto", t0=0, t1=5, linhas=[["Falta algo.", "destaque"]]),
        dict(tipo="contador", t0=0, t1=5, valor="35%", rotulo="de margem"),
        dict(tipo="pilula", t0=0, t1=5, texto="AO VIVO"),
    ]
    caps = [dict(numero="01", nome="PROPÓSITO", t0=0.0)]
    for var, spec in es.VARIAVEIS.items():
        for opc in spec["o"]:
            e = es.carregar({var: opc})
            c = pecas.Ctx(540, 960, (63, 169, 245), {"nome": "Marca"}, e, y_pecas=300, total=5.0)
            blocos = pecas.blocos_legenda(ws, c)
            for t in (0.05, 0.4, 1.2):
                cam = Image.new("RGBA", (540, 960), (0, 0, 0, 0))
                pecas.desenha_tag(cam, t, caps, c)
                for pc in pcs:
                    pecas.DESENHA[pc["tipo"]](cam, t, pc, c)
                pecas.desenha_legenda(cam, t, blocos, c, {"grandes"}, {}, set())
                pecas.desenha_assinatura(cam, t, lambda _t: 0.5, c)
            img = pecas.cartao_final(1.7, 0.0, {"linhas": [["Oi", "destaque"]], "rodape": "x"}, None, c)
            pecas.acabamento(img.convert("RGB"), 3, e.acabamento)


def test_referencia_de_estilo_cobre_todas_as_variaveis():
    doc = (Path(__file__).resolve().parents[1] / "references" / "estilo.md").read_text(encoding="utf-8")
    for var, spec in es.VARIAVEIS.items():
        assert f"`{var}`" in doc, var
        for opc in spec["o"]:
            assert f"`{opc}`" in doc, (var, opc)
    for preset in es.PRESETS:
        assert f"`{preset}`" in doc, preset
