# Como ler um roteiro e virar plano

O roteiro é a intenção; o take é o que aconteceu. O plano junta os dois: a **ordem** vem do
roteiro, as **palavras** vêm do take.

## O que um roteiro de agência traz

Roteiro de anúncio ou reel costuma vir assim (ClickUp, Notion, doc da agência):

```
GANCHO: Se você atende gestantes… [imagens de barrigas pintadas]
DESENVOLVIMENTO: Muitas profissionais deixam de… [Paula pra câmera]
Foi por isso que eu criei o Arte Gestacional… [tela dividida: decalque, plataforma]
CTA: Clica em "Saiba Mais" [Paula pra câmera]
Texto na tela: …
```

Ou como "takes" numerados:

```
TAKE #03 - PASSO 02: Diagnóstico
Cena: o consultor caminhando pela loja
Fala: "Aí a gente vai até a sua loja e faz o estudo…"
Texto na tela: Passo 02 - Diagnóstico
```

Leia procurando quatro coisas:

| No roteiro | Vira no plano |
|---|---|
| A ordem dos blocos (gancho, passos, chamada) | a ordem das `falas` |
| O que está entre colchetes ou em "Cena/Visual" | os `apoios` (que imagem, em cima de que frase) |
| "Texto na tela" | `titulo`, `texto` ou `passo` |
| Enumerações na fala ("circulação, segurança, abastecimento") | `checklist` ou `etiquetas` |
| Números afirmados ("99,9%", "0 dias", "12 meses") | `contador` ou `marcos` |
| A chamada ("clica em", "link na bio") | `botao` |

## Casar roteiro com take

1. Pra cada bloco do roteiro, ache o take que diz aquilo (`catalogo.md` → `transcricoes/*.txt`).
   O falante raramente diz igual ao roteiro. Vale o que ele disse.
2. Take longo com várias tentativas? Escolha a melhor tentativa e ancore nela com `n_de`/`n_ate`
   (a terceira vez que ele diz "vem" é `"n_de": 3`). Ouvir não dá; leia os segundos no `.txt` e
   prefira a tentativa mais fluente (menos "é", menos repetição).
3. Frase do roteiro que ninguém falou: **não entra.** Não existe texto na tela sem fala por baixo,
   a não ser o título de abertura e o cartão final.
4. Falante que troca termo ("estacional" por "gestacional", "mecanológico" por "mercadológico")
   ou que o transcritor errou: `correcoes`. A legenda sai certa e a âncora funciona.

## Escolher apoios

- Olhe a folha de cada apoio (`folhas/<take>.jpg`) e anote em 5 palavras o que ele mostra e em
  que segundo começa a parte boa: "corredor com cliente, 0 a 6 s", "obra isolada com lona, 1 s".
- Apoio entra **na palavra que ele ilustra** e sai no fim da frase. "Loja aberta" na palavra
  "loja", não no começo da frase.
- Continuidade: se o falante está de roupa diferente em outro take, esse take só serve de apoio
  se ele não aparecer.
- Apoio curto demais pro trecho? O motor recua a entrada pra não sobrar preto. Mas escolha
  outro se a diferença passar de 2 s.
- Nunca apoio em cima da primeira frase do gancho (o rosto vende) nem da chamada final.

## Capítulos

Em vídeo de processo, um capítulo por passo do roteiro, com a numeração dele. Em anúncio curto,
3 a 6 capítulos de uma palavra: PROBLEMA, MÉTODO, PROVA, CHAMADA. É a tag do canto; ninguém
lê, mas todo mundo sente a estrutura.

## Destaques

As palavras que a legenda pinta: números, verbos de resultado ("fechou", "cresce"), o nome do
método, a palavra da chamada. Umas 10 a 15 por minuto. Sem adjetivo bobo.

## Quando o roteiro é só um copy de tráfego

Sem "takes" nem "cena", só o texto do anúncio: trate cada frase como um bloco, case com o take
que a diz, e use as regras acima. Se o copy tem lista, vira checklist; se tem número, contador;
se termina em botão, `botao`.

## Quando não tem roteiro

Peça um ao usuário em três linhas: o que o vídeo promete, os 3 a 5 pontos no meio, o que a
pessoa deve fazer no fim. Sem isso você está adivinhando, e adivinhar é o que esta skill não faz.
