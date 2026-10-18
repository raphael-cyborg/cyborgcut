# CyborgCut

**O agente edita o vídeo a partir do roteiro.** Você entrega os takes brutos e o texto do que o
vídeo tem que dizer; o agente lê os dois, escolhe o trecho certo de cada take por palavra, encaixa
imagem de apoio na palavra dita, desenha gráficos por capítulo, legenda palavra a palavra, põe
trilha e cartão final, e confere o resultado antes de te mostrar.

[English version](README.en.md)

É uma [Agent Skill](https://agentskills.io): funciona no Claude Code, Codex, Gemini CLI e em
qualquer agente que leia `SKILL.md`. Só Python e ffmpeg. Sem Remotion, sem Node, sem chave de API.

![Quadros da demo: vídeo 16:9 da Multiviascom virando reel com título, etiquetas, ondas, checklist, botão e cartão final](demo/quadros.jpg)

*Um vídeo de canal em 16:9 (CC BY) virando reel: a caixa no meio, as peças em cima, a legenda embaixo. O plano que gerou isso está em [`demo/plano.json`](demo/plano.json).*

## O que ela faz que as outras não fazem

As skills de vídeo que existem partem do take: cortam silêncio, tiram "é" e "tipo", põem legenda.
O CyborgCut parte do **roteiro**. A diferença aparece quando o falante gravou cinco tentativas,
quando o roteiro pede "imagem da loja aberta" em cima de uma frase, quando tem "texto na tela" e
uma enumeração que vira checklist. É o trabalho que uma agência faz, não o que um cortador de
silêncio faz.

| | Cortador de silêncio | CyborgCut |
|---|---|---|
| Entrada | um take | roteiro + vários takes + imagens de apoio |
| Corte | tira pausa | escolhe o trecho por palavra, aperta respiro no áudio |
| Imagem de apoio | manual | na palavra que ela ilustra |
| Gráficos | nenhum ou genéricos | título, checklist, contador, etapas, ondas, botão, por capítulo |
| Conferência | nenhuma | retranscreve, procura piscada e quadro preto, mede volume |

## Testar sem saber programar

Precisa de um Mac com chip Apple (de 2020 pra cá) ou um computador com Windows, e do app do
Claude com plano pago (Pro ou Max).

1. Baixe o app em [claude.ai/download](https://claude.ai/download), entre na sua conta e abra a
   aba **Code**.
2. Crie uma pasta pro vídeo com duas coisas dentro: uma pasta chamada `bruto` com os vídeos do
   jeito que saíram da câmera, e o roteiro do jeito que estiver (texto do ClickUp, Word, PDF).
3. No Claude, escolha essa pasta e cole:

   > Instala a skill do GitHub raphael-cyborg/cyborgcut pra eu usar em qualquer pasta, prepara meu
   > computador pra ela e edita o vídeo desta pasta seguindo o roteiro. Antes do vídeo final, me
   > mostra o mural de estilos pra eu escolher a cara do vídeo.

Na primeira vez ele instala algumas ferramentas e baixa o modelo que escuta a fala (2 a 3 GB), e
vai pedir pra você aprovar alguns passos. No Mac, se faltar uma ferramenta, ele pode pedir pra você
colar um comando no Terminal e digitar a senha do computador uma vez. Depois disso, cada vídeo novo
é só a pasta e a frase. O vídeo não sai do seu computador: a fala é transcrita aqui mesmo, e o
Claude lê só o texto e umas miniaturas pra decidir os cortes.

## Instalar

Qualquer agente (instala em `~/.claude/skills/`, `.codex/skills/`, etc.):

```bash
npx skills add raphael-cyborg/cyborgcut
```

Sem Node (sem `npx`): baixe o [zip](https://github.com/raphael-cyborg/cyborgcut/archive/refs/heads/main.zip)
e descompacte como `~/.claude/skills/cyborgcut/`.

Claude Code como plugin:

```bash
claude plugin marketplace add raphael-cyborg/cyborgcut
claude plugin install cyborgcut@cyborgcut
```

Depois, dentro da pasta da skill, o ambiente Python:

```bash
uv venv && uv pip install -e ".[mac]"      # Mac com Apple Silicon
uv venv && uv pip install -e ".[cpu]"      # Linux, Windows, Mac Intel
python scripts/cyborgcut.py doctor         # diz o que falta
```

Precisa de `ffmpeg` 5+ (`brew install ffmpeg` · `apt install ffmpeg` · no Windows, o build
**full** do [gyan.dev](https://www.gyan.dev/ffmpeg/builds/)). A transcrição roda na sua máquina
(mlx-whisper no Mac, faster-whisper nos outros); o modelo baixa na primeira vez.

## Usar

Uma pasta por vídeo:

```
meu-video/
  bruto/        os vídeos, do jeito que vieram do celular
  roteiro.md    o que o vídeo tem que dizer
  logo.png      opcional
```

E peça ao agente:

> edita o vídeo em `meu-video/` seguindo o roteiro, estilo agência

O agente roda `preparar` (cor, voz limpa, transcrição, catálogo do bruto), lê o roteiro e as
transcrições, escreve um `plano.json` ancorado em palavras, tira prévias, olha, renderiza e
confere. Você recebe `saida/<titulo>.mp4` e `saida/conferencia.md`.

Pra mexer na mão ou entender o que o agente faz: [`SKILL.md`](SKILL.md) é o manual do agente,
[`references/plano.md`](references/plano.md) é o formato do plano e
[`references/pecas.md`](references/pecas.md) o catálogo de gráficos.

## O estilo é do cliente, não da ferramenta

Nada de todo vídeo sair igual. O visual é montado a partir de um arsenal: 17 variáveis (fonte do
título, legenda, painel, tag, assinatura, transição, câmera, entrada, cor, cartão final, som…),
cada uma com opções. O agente desenha cada opção **no quadro do próprio vídeo** e a pessoa escolhe
olhando; a combinação é salva com o nome do cliente e replicada em todo vídeo seguinte.

![mural de opções](demo/mural.jpg)

```bash
python scripts/cyborgcut.py estilo mural demo                       # cada opção, no quadro do projeto
python scripts/cyborgcut.py estilo variacoes demo --n 8             # combinações inteiras pra apontar
python scripts/cyborgcut.py estilo salvar demo acme --set legenda=karaoke-caixa --set fonte_titulo=oswald
```

Depois é só `"estilo": "acme"` no plano. Cinco pontos de partida vêm prontos: `agencia`,
`editorial`, `impacto`, `clean`, `limpo`.

![o mesmo plano em quatro estilos](demo/estilos.jpg)

Variáveis e opções: [`references/estilo.md`](references/estilo.md).

## O que acontece por baixo

1. **Cor**: HDR do celular convertido (Apple `avconvert` no Mac, `zscale` no Linux e Windows).
2. **Voz**: RNNoise tira o ruído da loja; o nível é acertado antes do compressor; -14 LUFS no fim.
3. **Corte**: a janela de cada fala vai de uma palavra a outra, com a borda no vale de silêncio
   entre palavras e os respiros apertados, medido no áudio.
4. **Legenda e âncoras**: a voz montada é transcrita de novo; é daí que saem os tempos.
5. **Imagem**: duas camadas (quem fala, apoio) cortadas por quadro; câmera com avanço leve;
   peças desenhadas em Python quadro a quadro.
6. **Conferência**: retranscrição fala por fala, varredura de quadro escuro e piscada, volume.

Detalhes e o porquê de cada escolha: [`references/tecnicas.md`](references/tecnicas.md).

## Demo

`demo/` tem um projeto completo: um vídeo de 87 s em português (CC BY, créditos abaixo), o
roteiro reconstruído da fala e o plano que o agente escreveu. Pra rodar:

```bash
bash demo/baixar.sh                                  # baixa o bruto (yt-dlp)
python scripts/cyborgcut.py preparar demo
python scripts/cyborgcut.py montar demo
python scripts/cyborgcut.py montar demo --estilo impacto     # o mesmo plano, outra cara
python scripts/cyborgcut.py conferir demo
```

## Máquina

Testado num Mac M4 de 16 GB. Render com motion e acabamento: 4 a 5 s de máquina por segundo de vídeo.
Os scripts limitam o ffmpeg a 4 threads e esperam se outro render estiver rodando: dois vídeos ao
mesmo tempo em 16 GB travam a máquina. Linux e Windows passam no CI com fixture pequena; relato
de máquina real é bem-vindo.

## Licenças

- Código: MIT.
- Fontes Montserrat, IBM Plex Mono, Playfair Display, Oswald, Bebas Neue, Space Grotesk e Inter: SIL Open Font License (em `assets/fontes/`).
- Modelo de ruído RNNoise `sh`: domínio público ([GregorR/rnnoise-models](https://github.com/GregorR/rnnoise-models)).
- Trilhas `lofi-calma` ("Walking Away") e `groove-leve` ("Make Funk"): HoliznaCC0, CC0 1.0
  (`assets/trilhas/`).
- Vídeo da demo: "Pequenas Empresas podem se tornar Grandes Marcas", Multiviascom, YouTube,
  licença Creative Commons Attribution (não está no repositório; o script baixa).

## Quem fez

[Raphael Martins](https://instagram.com/raphael.cyborg), Synapse Sales. Nasceu de um teste real:
editar o mesmo anúncio que a equipe de uma agência editou, a partir do mesmo bruto e do mesmo
roteiro, e comparar lado a lado.
