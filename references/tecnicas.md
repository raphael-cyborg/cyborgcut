# Por que as coisas são como são

Decisões técnicas que custaram um erro cada. Se for mexer no motor, leia antes.

## Cor: o HDR do celular

Todo celular moderno grava em HDR (HLG, 10 bits). Jogar isso direto num mp4 comum deixa a
imagem lavada. Três caminhos, do melhor pro pior, e o `preparar` escolhe sozinho:

1. `avconvert -p PresetHighestQuality` (Mac): a conversão da Apple, feita pro HDR do iPhone.
   3 s por take e já entrega o vídeo em pé (aplica a rotação).
2. `zscale` + `tonemap=hable` (ffmpeg do Linux e do Windows): comparado lado a lado com o da
   Apple, igual a olho. O ffmpeg do Homebrew no Mac **não tem** zscale; por isso o avconvert.
3. `colorspace` (qualquer ffmpeg): só troca as primárias, não faz tone mapping. Fica mais lavado;
   uma curva em S compensa um pouco. O doctor avisa.

Depois da conversão, o acabamento do estilo aplica a cor: `grao-vinheta` é uma curva em S leve e um
pouco mais de saturação (o que mais se aproximou de um final de agência), `frio` dessatura e esfria,
`quente` contrasta e esquenta, `neutro` não toca (`GRADES` em `montar.py`; grão e vinheta são por
quadro, em `pecas.acabamento`).

## Voz: o ruído

A primeira cadeia de áudio comprimia a voz ANTES de acertar o nível e usava um redutor de ruído
genérico (`afftdn`). Resultado medido: voz 7,5 dB acima do fundo, pior que o cru (16 dB).

O que funciona: `arnndn` com o modelo RNNoise `sh` (treinado em fala de gravação, domínio
público), antes de qualquer coisa. Voz 30 dB acima do fundo. Depois: nível pra -20 LUFS,
compressor leve, EQ de presença (menos 180 Hz, mais 3,5 kHz), nível final -14 LUFS (o padrão
das redes). A trilha fica 10 a 14 dB abaixo e cede mais 5 dB quando ele fala (sidechain).

## Corte: por palavra, medido no áudio

O transcritor erra o tempo de cada palavra em até 0,4 s. Cortar no tempo dele come sílaba ou
deixa respiro. Então:

- a janela da fala vai da palavra `de` à palavra `ate`, mas a borda cai no **vale de energia**
  entre a palavra e a vizinha (o instante mais silencioso), medido no áudio limpo;
- dentro da janela, fala = 10 ms acima de (pico − 24 dB); pausa de 0,15 s ou mais é apertada pra
  0,08 s (ou 0,14 s se passar de 0,3 s, respiro de fim de frase);
- estalo ou respiro curto solto antes da primeira palavra não conta.

Foi isso que tirou "vários respiros que passaram batido" da primeira versão.

## Legenda: transcrever a voz montada, não os takes

A legenda e as âncoras das peças saem de uma segunda transcrição, feita **do áudio já montado e
limpo**. Transcrever os takes crus e converter o tempo deixava a legenda até 0,4 s adiantada,
porque o ruído da loja confunde o começo das palavras. Se o transcritor escrever uma palavra
diferente na segunda passada ("clique" em vez de "clica"), a âncora cai na transcrição do take,
que é a mesma em que o plano foi escrito, e converte o tempo.

Blocos de legenda: no máximo 4 palavras, escolhidos pela divisão de menor custo dentro de cada
frase (sem terminar em "de", "a", "que"; sem palavra curta sozinha; sem passar da largura;
"Saiba Mais" nunca se separa).

## Desenho: cada coisa na sua camada

O Pillow **substitui** o pixel quando desenha texto translúcido em cima de camada já preenchida
(texto virava buraco no painel). Todo texto vai numa camada própria e entra por
`alpha_composite`. É o `escreve()` de `pecas.py`.

## Imagem: duas camadas e contagem por quadro

Quem fala (camada A) e os apoios (camada B, preto onde não tem apoio) são cortados por quadro,
com `round(t * fps)`, e o desenho escolhe a camada com o **mesmo** arredondamento. Escolher por
segundo deixava um quadro preto na fronteira. Apoio que acaba a menos de 0,5 s do fim da fala
vai até o fim dela: senão quem fala pisca por 4 a 13 quadros antes do próximo corte. Apoio mais
curto que o trecho tem a entrada recuada, pra não sobrar preto no fim.

## Conferência: o que o olho não pega

Depois do render, sempre:

- retranscrever o mp4 e conferir se a primeira e a última palavra de cada fala estão lá, na ordem
  (palavra comida no corte aparece aqui);
- brilho médio de cada quadro em 32x56: quadro abaixo de 25 é escuro; quadro muito diferente dos
  dois vizinhos iguais é piscada;
- volume integrado (alvo -14 LUFS, tolerância 2).

Os três pegaram bugs reais antes de o usuário ver.

## Máquina

- ffmpeg com teto de threads (`THREADS`, 4 num Mac de 10 núcleos). Sem teto ele toma tudo e, com
  outro render na mesma máquina, 16 GB travam.
- O transcritor roda em subprocesso: o modelo sai da memória quando acaba. No Mac, o modelo
  `large-v3-turbo` (1,6 GB) no lugar do `large-v3` (3 GB), mesma qualidade na prática.
- `esperar_maquina()`: se outro ffmpeg/whisper estiver rodando, os comandos pesados esperam.
- Render do estilo agência: 4 a 5 s de máquina por segundo de vídeo (desenho quadro a quadro em
  Python). Prévia antes de render.

## O que fica de fora de propósito

- **Remotion/Node**: licença paga a partir de 4 funcionários; o público desta skill é agência
  pequena. Tudo aqui é Python e ffmpeg.
- **Geração de imagem ou voz por IA**: a skill edita o que existe. Nada inventado em tela.
- **Timeline/editor**: o agente é o editor; o plano é a timeline.
