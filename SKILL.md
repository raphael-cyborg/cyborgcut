---
name: cyborgcut
description: Edita vídeo a partir do roteiro. Lê o roteiro e o bruto (takes de alguém falando pra câmera + imagens de apoio), escolhe o trecho certo de cada take por palavra, encaixa imagem de apoio na palavra dita, desenha gráficos por capítulo (título, checklist, contador, barra de etapas, ondas, botão), legenda, trilha e cartão final, e confere o resultado sozinho. O visual é um estilo montado com o usuário (fonte, legenda, painel, tag, transição, cor, cartão) a partir de um arsenal de opções, salvo com o nome do cliente e repetido em todo vídeo seguinte. Use quando o usuário pedir pra editar/montar um vídeo, reel, short ou anúncio a partir de um roteiro, briefing ou copy, ou quando mandar vídeos brutos e disser o que o vídeo tem que dizer. Só Python e ffmpeg, sem Remotion. Também em inglês — edit video from script, talking head, reel, b-roll, captions, motion graphics.
license: MIT
compatibility: Python 3.10+, uv, ffmpeg 5+. Mac (Apple Silicon ou Intel), Linux e Windows. Transcrição local (mlx-whisper no Mac, faster-whisper nos outros).
metadata:
  author: raphael-cyborg
  version: "0.1.0"
---

# CyborgCut

Você é o editor. A skill te dá as mãos (scripts); a cabeça é sua: ler o roteiro, escolher o que
entra, decidir que gráfico cabe em cada parte. **Tudo que você decide vai num arquivo, o
`plano.json`, ancorado em palavras, nunca em segundos.** O motor mede o resto.

Responda ao usuário na língua dele. Os arquivos da skill estão em português.

## Quando usar

- "edita esse vídeo a partir desse roteiro", "monta o reel", "faz o anúncio com esses takes".
- O usuário manda vídeos brutos e um texto do que o vídeo tem que dizer (roteiro, copy, briefing).
- Não serve pra: cortar silêncio de aula longa sem roteiro, gerar vídeo do zero, legenda avulsa.

## Primeira vez nesta máquina

A pasta da skill é a pasta deste `SKILL.md` (em geral `~/.claude/skills/cyborgcut/`). Os scripts
rodam com um Python próprio, num ambiente dentro dela; o vídeo do usuário fica em outra pasta.
Se `<skill>/.venv` ainda não existe, prepare tudo antes de qualquer outra coisa:

1. `uv` (instala Python sem pedir senha), se `uv --version` falhar:
   Mac/Linux `curl -LsSf https://astral.sh/uv/install.sh | sh` ·
   Windows `powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"`.
2. O ambiente, dentro da pasta da skill:
   `uv venv && uv pip install -e ".[mac]"` (Mac com chip Apple) ou `".[cpu]"` (Windows, Linux, Mac Intel).
3. `ffmpeg` 5+, se faltar: Mac `brew install ffmpeg`; Windows `winget install Gyan.FFmpeg`
   (depois, abra um terminal novo pra ele aparecer); Linux `sudo apt install ffmpeg`.
   **Mac sem Homebrew:** a instalação do Homebrew pede a senha do computador e você não consegue
   digitar senha. Peça ao usuário, em uma frase, pra abrir o app Terminal, colar o comando do
   [brew.sh](https://brew.sh) e digitar a senha; depois continue você.
4. `doctor` até sair "tudo pronto". Avise o usuário que o primeiro vídeo baixa o modelo de fala
   (2 a 3 GB) e por isso demora mais.

Daqui pra baixo, `python scripts/cyborgcut.py` é atalho de
`<skill>/.venv/bin/python <skill>/scripts/cyborgcut.py` (Windows: `<skill>\.venv\Scripts\python.exe`),
chamado de qualquer pasta, com o caminho do projeto do usuário como argumento.

## O fluxo

```
doctor → preparar → LER (roteiro + catálogo + folhas) → ESCREVER plano.json
       → montar --previa → OLHAR → ESTILO (primeiro vídeo do cliente) → montar → conferir → entregar
```

Cada seta é um portão. Não pule o OLHAR nem o conferir.

### 1. `doctor`: a máquina está pronta?

```bash
python scripts/cyborgcut.py doctor
```

Se faltar algo, ele diz o comando. Não contorne: sem transcritor não existe corte por palavra.

### 2. `preparar`: o bruto vira matéria-prima

O projeto é uma pasta assim:

```
meu-video/
  bruto/        os vídeos (takes de quem fala, imagens de apoio), do jeito que vieram
  roteiro.md    o que o vídeo tem que dizer (copy, briefing, roteiro da agência)
  logo.png      opcional, com transparência
```

Chegou diferente? Arrume antes de preparar, sem perguntar: vídeos soltos na pasta vão pra
`bruto/`; roteiro em `.docx`, `.pdf`, `.txt` ou colado na conversa vira `roteiro.md` (o texto
inteiro, sem resumir).

```bash
python scripts/cyborgcut.py preparar meu-video
```

Sai em `meu-video/trabalho/`: cor normalizada (HDR do celular convertido), voz sem ruído,
transcrição com tempo por palavra, uma folha de quadros por take e o **`catalogo.md`**.
Demora: uns 20 s por minuto de bruto no Mac, mais na primeira vez (baixa o modelo de fala).

### 3. LER, antes de escrever qualquer coisa

Nesta ordem, sem pular:

1. `roteiro.md`: entenda a estrutura (gancho, passos, chamada). Anote os "textos na tela" que o
   roteiro pede e as imagens que ele sugere. Ver `references/roteiro.md` pra ler roteiro de agência.
2. `trabalho/catalogo.md`: que takes têm fala e quais são imagem de apoio.
3. `trabalho/transcricoes/<take>.txt`: o que cada take de fala diz, com os segundos. É daqui
   que saem as palavras-âncora. **Só use palavra que está na transcrição.**
4. `trabalho/folhas/<take>.jpg`: olhe (Read) as folhas dos apoios pra saber o que cada um mostra
   e em que segundo. Imagem de apoio errada no lugar errado é o erro mais visível que existe.

### 4. ESCREVER o `plano.json`

Formato completo e um exemplo inteiro em `references/plano.md`. O essencial:

| Chave | O que é | Como ancorar |
|---|---|---|
| `falas` | trechos que entram, na ordem | take + primeira palavra + última palavra |
| `apoios` | imagem por cima da fala | fala + palavra em que entra + palavra em que sai + take de apoio |
| `capitulos` | a tag de canto "01 CONTATO" | fala em que começa |
| `pecas` | gráficos (título, checklist, contador, barra, ondas, botão…) | fala + palavra; itens de lista cada um com a palavra que o acende |
| `destaques` | palavras que ficam na cor da marca na legenda | lista de palavras |
| `cartao_final` | fecho com logo ou nome | duas linhas + rodapé |

Regras que não se negociam:

- **Palavra, não segundo.** O motor mede o corte no áudio (vale de silêncio entre palavras,
  respiro apertado). Se você escrever segundo, está fazendo o trabalho dele pior.
- **Uma fala = um trecho contínuo de um take.** Precisa pular um pedaço? São duas falas.
- **O roteiro manda na ordem; o take manda nas palavras.** Se o roteiro diz "Clique em Saiba Mais"
  e o apresentador falou "Clica em Saiba Mais", a âncora é `clica`.
- **Apoio só onde a fala pede imagem.** "A loja não fecha um dia" com a loja aberta, sim.
  Apoio em cima da frase de abertura ou da chamada final, quase nunca.
- **Uma peça por momento.** Checklist e etiquetas ao mesmo tempo é poluição. Catálogo e
  quando usar cada uma em `references/pecas.md`.
- **Nada inventado.** Número, nome e afirmação que entram em tela vêm do roteiro ou da fala.
  Se o roteiro pede "99,9%" e ninguém falou, não entra.
- O transcritor erra nome próprio e termo técnico: corrija em `correcoes` (`"mecanológico":
  "mercadológico"`). Vale pra legenda e pra âncora.

### 5. `montar --previa`: olhar antes de gastar máquina

```bash
python scripts/cyborgcut.py montar meu-video --previa 1,4,9,15,22,30
```

Escolha os segundos onde cada peça aparece (o comando imprime o total da fala). Sai
`saida/previa.jpg`. **Abra e olhe** (Read). O que procurar: texto cortado na borda, peça em cima
do rosto, apoio que não combina com a frase, legenda com palavra errada, dois gráficos juntos.
Corrija o plano e rode de novo. Três rodadas de prévia custam menos que um render errado.

Dois ajustes resolvem a maior parte do que a prévia mostra:

- **Bruto deitado (16:9) virando reel:** `"recorte": "caixa"`. O vídeo fica numa caixa no meio,
  com ele mesmo desfocado de fundo; as peças ficam em cima e a legenda embaixo. Preencher a tela
  com um 16:9 deixa o rosto no meio e não sobra lugar pra nada.
- **Peça em cima do rosto:** `"pecas_y"` (altura onde as peças começam). Rosto que ocupa o topo
  do quadro pede peça mais baixa.

### 5b. ESTILO: a cara do cliente, montada uma vez

O visual não é um só: são 17 variáveis (fonte do título, legenda, painel, tag, assinatura,
transição do apoio, câmera, entrada, acabamento, cartão final, som…) com opções cada. **No
primeiro vídeo de um cliente ou canal, monte o estilo com o usuário; nos seguintes, só replique.**

```bash
python scripts/cyborgcut.py estilo mural meu-video            # cada opção, no quadro deste vídeo
python scripts/cyborgcut.py estilo variacoes meu-video --n 8  # oito combinações inteiras pra apontar
python scripts/cyborgcut.py estilo salvar meu-video acme --base agencia --set legenda=karaoke-caixa
```

Mostre `saida/estilo/mural-legenda.jpg`, `mural-fonte_titulo.jpg`, `mural-painel.jpg` (uma
variável por pergunta, com a imagem), salve com o nome do cliente e ponha `"estilo": "acme"` no
plano. Pontos de partida prontos: `agencia`, `editorial`, `impacto`, `clean`, `limpo`. Nunca
entregue um preset sem ter mostrado alternativa. Tudo em `references/estilo.md`.

### 6. `montar`: o render

```bash
python scripts/cyborgcut.py montar meu-video
python scripts/cyborgcut.py montar meu-video --estilo impacto   # o mesmo plano em outro estilo
```

Uns 4 a 5 s de máquina por segundo de vídeo com acabamento e motion, metade sem. Sai em
`saida/<titulo>.mp4`. Avise o usuário em marcos curtos; não fique em silêncio por 5 minutos.

### 7. `conferir`: o que o olho não pega

```bash
python scripts/cyborgcut.py conferir meu-video
```

Retranscreve o vídeo pronto e confere se cada fala está inteira (palavra comida no corte aparece
aqui), procura quadro escuro e piscada de um quadro, mede o volume. Sai `saida/conferencia.md`
com APROVADO ou REPROVADO. **Reprovou, corrige e renderiza de novo. Nunca entregue reprovado.**

Tem um vídeo de referência (a versão que a equipe fez)? `comparar meu-video referencia.mp4` monta
o lado a lado, uma cópia com cada som.

### 8. Entregar

Mande o mp4 e diga em uma frase o que o vídeo ficou e o que depende do usuário. Você não escuta:
diga que a trilha e os efeitos precisam de um ouvido humano. Não liste arquivos nem etapas.

## O que a máquina aguenta

- **Nunca rode dois renders ao mesmo tempo** (nem em background). 16 GB travam com dois vídeos
  mais um modelo de fala. Os scripts esperam se outro ffmpeg estiver rodando; respeite isso.
- Prévia antes de render. Render de 1 minuto é o teto por rodada enquanto o plano não está certo.

## Pontos de partida do estilo

| Preset | Cara | Quando partir dele |
|---|---|---|
| `agencia` | Montserrat pesada, legenda palavra a palavra sublinhada, painel escuro, onda que reage à voz, grão, efeitos | anúncio, reel de marca |
| `editorial` | Playfair, legenda em barra preta, listas numeradas sem painel, câmera parada, cor fria | conteúdo de opinião, consultoria, "sério" |
| `impacto` | Bebas em caixa alta, legenda karaokê com caixa na cor, blocos sólidos, zoom no corte, cor quente | corte de podcast, chamada, energia |
| `clean` | Space Grotesk, legenda em pílula, painel claro, fusão, sem acabamento | produto, tecnologia, SaaS |
| `limpo` | corte seco, legenda em bloco com contorno, nada de acabamento nem efeito | institucional, aula, "simples" |

O usuário monta o dele a partir de qualquer um: `references/estilo.md`.

## Referências

- `references/plano.md`: formato do plano, campo a campo, com exemplo completo.
- `references/estilo.md`: as variáveis do estilo, os presets, como montar com o usuário e salvar.
- `references/pecas.md`: as peças, o que cada uma faz e quando usar.
- `references/roteiro.md`: como transformar roteiro de agência (ClickUp, copy de tráfego) em plano.
- `references/tecnicas.md`: por que as coisas são como são (cor, ruído, legenda, conferência).
