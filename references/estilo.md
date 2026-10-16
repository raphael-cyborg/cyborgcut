# O estilo: criar uma vez, replicar em todo vídeo

Um estilo é um conjunto de escolhas, uma por variável: a fonte do título, como a legenda aparece,
que cara tem o painel das listas, a tag de canto, a assinatura, como o apoio entra, a câmera, a
entrada das peças, a cor, o cartão final e o som. São 17 variáveis com
63 opções; combinadas dão mais de um milhão de
estilos diferentes. O trabalho da skill é **ajudar a pessoa a montar o dela, salvar, e repetir
igual em todos os vídeos seguintes**, sem ela precisar descrever de novo.

## O fluxo com o usuário

1. **Primeiro vídeo de um cliente ou canal:** depois do plano e da primeira prévia, rode o mural:
   ```bash
   python scripts/cyborgcut.py estilo mural meu-video
   ```
   Sai `saida/estilo/mural.jpg` (tudo) e um `mural-<variavel>.jpg` por variável, cada opção
   desenhada **no quadro do próprio vídeo** (não num exemplo genérico). Mostre ao usuário uma
   variável por vez, começando pelas que mais mudam a cara: `legenda`, `fonte_titulo`, `painel`,
   `acabamento`, `cartao_final`. Pergunte "qual dessas?" com a imagem, não com a lista.
2. Sem ideia de onde começar? `estilo variacoes meu-video --n 8` gera oito combinações inteiras
   aleatórias (título, lista, legenda e cartão de cada uma, lado a lado) e `variacoes.json`.
   O usuário aponta uma ("a 3, mas com legenda em pílula") e você parte dela.
3. **Salve** com o nome do cliente ou do canal:
   ```bash
   python scripts/cyborgcut.py estilo salvar meu-video acme --base agencia --set legenda=karaoke-caixa --set fonte_titulo=oswald
   python scripts/cyborgcut.py estilo salvar meu-video acme --variacao 3 --set legenda=pilula
   ```
   Vai pra `meu-video/estilos/acme.json`. Com `--global` vai pra `~/.cyborgcut/estilos/`, que
   vale pra qualquer projeto na máquina (o normal pra um cliente com vários vídeos).
4. **Nos próximos vídeos** o plano diz só `"estilo": "acme"` e tudo sai igual. Mudou uma coisa
   só ("deixa a legenda maior nesse"), escreva o estilo direto no plano:
   ```json
   "estilo": {"base": "acme", "legenda_tamanho": "grande"}
   ```
5. `montar --estilo <nome>` renderiza o mesmo plano em outro estilo sem editar o arquivo (o mp4
   ganha o nome do estilo no fim). Serve pra mostrar duas versões.

Regras:
- **Não escolha pelo usuário sem mostrar.** Preset é ponto de partida, não entrega. Dois ou três
  murais e uma pergunta resolvem; descrever as opções em texto, não.
- **Uma variável por pergunta.** "Legenda: a 2 ou a 3?" com a imagem. Nunca a lista inteira.
- Combinações que não fazem sentido o motor já evita (Bebas é sempre caixa alta; legenda em
  bloco com contorno também).
- O estilo não muda o corte, a voz nem as âncoras: só o visual e o som de apoio. Trocar de
  estilo não exige nova prévia do corte, mas peça uma prévia do visual antes do render.

## Os pontos de partida

| Preset | O que muda em relação ao padrão |
|---|---|
| `agencia` | o padrão de todas as variáveis |
| `limpo` | legenda=bloco-contorno, legenda_caixa=alta, tag=nenhuma, assinatura=nenhuma, transicao_apoio=corte, camera=fixa, entrada=suave, acabamento=neutro, cartao_final=nome, som=so-trilha |
| `editorial` | fonte_titulo=playfair, fonte_texto=inter, legenda=barra-preta, painel=linhas, marcador=numero, tag=linha-versalete, assinatura=nenhuma, transicao_apoio=corte, camera=fixa, entrada=suave, acabamento=frio, cartao_final=nome, som=so-trilha |
| `impacto` | fonte_titulo=bebas, fonte_texto=oswald, titulo_caixa=alta, legenda=karaoke-caixa, legenda_caixa=alta, legenda_tamanho=grande, painel=blocos-cor, marcador=traco, tag=bloco-cor, assinatura=barra, transicao_apoio=deslize, camera=zoom-corte, entrada=mola, acabamento=quente, cartao_final=cor-solida |
| `clean` | fonte_titulo=space-grotesk, fonte_texto=inter, legenda=pilula, painel=claro-arredondado, marcador=check, tag=pilula, assinatura=linha, transicao_apoio=fade, camera=fixa, entrada=suave, acabamento=neutro, cartao_final=minimo, som=so-trilha |

`agencia` é o padrão de tudo (motion, legenda palavra a palavra, grão, onda, efeitos).
`limpo` é o antigo estilo simples (corte seco, legenda em bloco com contorno, sem acabamento).

## As variáveis

| Variável | Opções |
|---|---|
| `fonte_titulo` | `montserrat` (padrão): geométrica, pesada, a cara de agência digital<br>`playfair`: serifa de revista, elegante<br>`bebas`: condensada em caixa alta, impacto<br>`oswald`: condensada média, esportiva<br>`space-grotesk`: grotesca com personalidade, cara de tecnologia<br>`inter`: neutra, sistema, lê em qualquer tamanho |
| `fonte_texto` | `montserrat` (padrão): mesma família do título agência<br>`inter`: neutra e muito legível em legenda<br>`oswald`: condensada, combina com impacto<br>`space-grotesk`: tecnológica<br>`playfair`: serifa, só pra editorial calmo |
| `titulo_caixa` | `normal` (padrão): Como se escreve<br>`alta`: TUDO EM MAIÚSCULA |
| `legenda` | `palavra-sublinhado` (padrão): palavra a palavra, destaque na cor com sublinhado que cresce<br>`bloco-contorno`: frase inteira em caixa alta com contorno preto, estilo reel<br>`karaoke-caixa`: palavra atual com caixa na cor atrás e texto escuro<br>`barra-preta`: frase sobre uma barra preta sólida, cara de revista<br>`pilula`: frase numa pílula escura translúcida, palavra atual na cor |
| `legenda_caixa` | `normal` (padrão): como se fala<br>`alta`: MAIÚSCULA |
| `legenda_tamanho` | `pequena`: discreta<br>`media` (padrão): padrão<br>`grande`: domina a tela |
| `legenda_posicao` | `baixo` (padrão): abaixo do rosto, perto do fim<br>`centro`: no meio da tela (quem lê sem som) |
| `painel` | `escuro-arredondado` (padrão): fundo escuro translúcido, canto redondo<br>`claro-arredondado`: fundo claro translúcido, texto escuro<br>`blocos-cor`: cada item é um bloco sólido na cor da marca<br>`linhas`: sem fundo, só texto, número e linha fina |
| `marcador` | `check` (padrão): círculo que vira check<br>`numero`: 01, 02, 03<br>`traco`: traço na cor<br>`bloco`: quadrado que preenche |
| `tag` | `ponto-mono` (padrão): quadradinho na cor, MARCA | 01 CAPÍTULO em fonte mono<br>`barra`: barra vertical na cor + texto<br>`pilula`: pílula branca com texto escuro<br>`linha-versalete`: linha fina + versalete, editorial<br>`bloco-cor`: bloco sólido na cor, texto escuro<br>`nenhuma`: sem tag |
| `assinatura` | `onda` (padrão): linha de onda sob a legenda que reage à voz<br>`barra`: barra de progresso grossa<br>`linha`: linha fina de progresso com ponto<br>`nenhuma`: nada |
| `transicao_apoio` | `mascara` (padrão): a imagem de apoio cresce do centro<br>`corte`: corte seco<br>`deslize`: entra pela direita empurrando<br>`fade`: fusão rápida |
| `camera` | `avanco` (padrão): avanço lento contínuo em cada tomada<br>`zoom-corte`: pequeno zoom a cada corte, que assenta<br>`fixa`: parada |
| `entrada` | `mola`: entra passando do ponto e volta<br>`suave` (padrão): entra desacelerando<br>`seca`: aparece |
| `acabamento` | `grao-vinheta` (padrão): grão fino, vinheta leve, curva em S<br>`neutro`: a cor do bruto<br>`frio`: dessaturado e azulado, sóbrio<br>`quente`: contraste e calor, vinheta forte |
| `cartao_final` | `logo-sobe` (padrão): onda atravessa, logo sobe, duas linhas e rodapé<br>`nome`: nome da marca em tipografia grande<br>`cor-solida`: fundo na cor da marca, texto escuro<br>`minimo`: preto, logo ou nome pequeno, nada mais |
| `som` | `efeitos` (padrão): tiques, toques e sopros discretos<br>`so-trilha`: só voz e trilha |

`camera`, `entrada` e `som` não aparecem em quadro parado; o mural pula essas três. Descreva em
uma frase ou renderize uma prévia curta.

## O arquivo salvo

Pequeno de propósito: a base e só o que muda.

```json
{"base": "agencia", "legenda": "karaoke-caixa", "fonte_titulo": "oswald", "painel": "blocos-cor"}
```

Onde o motor procura um nome: `<projeto>/estilos/<nome>.json` → `~/.cyborgcut/estilos/<nome>.json`
→ `estilos/<nome>.json` na pasta da skill → caminho literal. Preset ganha de tudo.

## Comandos

| Comando | Faz |
|---|---|
| `estilo opcoes` | imprime variáveis, opções e presets |
| `estilo mural <projeto> [--variavel a,b] [--base x] [--t legenda=12.4]` | cada opção no quadro do projeto |
| `estilo variacoes <projeto> [--n 8] [--semente 1]` | combinações inteiras aleatórias |
| `estilo salvar <projeto> <nome> [--base x] [--set k=v]… [--variacao n] [--global]` | grava o JSON |
| `montar <projeto> --estilo <nome>` | renderiza com outro estilo sem mexer no plano |
