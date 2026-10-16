# As peças

Cada peça é um gráfico que entra por cima do vídeo, ancorado em palavra. Todas entram e saem com
movimento curto; nada aparece de uma vez. Uma peça por momento: duas juntas é poluição.

Campos comuns: `tipo`, `fala`, `de` (palavra em que aparece; sem `de`, no começo da fala), `ate`
(palavra em que some; `"fim"` = fim da fala; `"video"` = até o fim), `duracao` (segundos, no lugar
de `ate`), `antecipa` (entra X s antes da palavra, padrão 0,1), `n_de`/`n_ate` (qual ocorrência).

Em listas (`itens`), cada item é `[texto, palavra]` ou `[texto, palavra, ocorrência]`: a palavra é
a que acende aquele item.

## Texto

### `titulo`
Duas linhas grandes no topo, entram linha a linha. Pro "texto na tela" de abertura do roteiro.
Some em `ate` (use a palavra onde o próximo gráfico começa).
```json
{"tipo": "titulo", "fala": "c1", "ate": "não", "linhas": [["Reforma sem fechar", "branco"], ["o supermercado.", "destaque"]]}
```
Quando usar: só na abertura, uma vez. Cor `destaque` na linha que carrega a promessa.

### `texto`
Um rótulo grande no meio da tela com faixa escura. Pra uma palavra-chave que a fala diz
("CIRCULAÇÃO"), quando não cabe um checklist. `y` opcional (padrão 620, numa tela de 1920).
```json
{"tipo": "texto", "fala": "c3", "de": "circulação", "ate": "circulação", "texto": "CIRCULAÇÃO"}
```

### `contador`
Número que conta até o valor, com rótulo. Pra um número que a fala afirma. Aceita `"0"`,
`"12"`, `"99,9%"`, `"R$ 1.200"` não (só número e `%`).
```json
{"tipo": "contador", "fala": "c1", "de": "fechou", "ate": "dia", "valor": "0", "rotulo": "dias com a loja\nfechada"}
```
Quando usar: um por vídeo, no número mais forte. Nunca invente o número.

## Listas

### `checklist`
Painel com itens que vão sendo marcados quando a palavra é dita. Pra enumeração de 3 a 5 itens
("circulação, segurança, abastecimento e horários").
```json
{"tipo": "checklist", "fala": "c3", "ate": "fim",
 "itens": [["Circulação", "circulação"], ["Segurança", "segurança"], ["Abastecimento", "abastecimento"]]}
```
Sem `de`, aparece 0,6 s antes do primeiro item.

### `etiquetas`
Etiquetas brancas que entram com mola, uma por palavra, com título opcional. Pra lista mais
solta ou pra coisas que "chegam" (clientes, fornecedores, funcionários).
```json
{"tipo": "etiquetas", "fala": "c4", "de": "disputar", "ate": "fim", "titulo": "A obra disputa espaço com",
 "itens": [["Clientes", "clientes"], ["Fornecedores", "fornecedores"], ["Funcionários", "funcionários"]]}
```
Checklist ou etiquetas? Checklist quando são requisitos ou passos cumpridos; etiquetas quando são
atores, exemplos, coisas que se acumulam.

### `lista`
Lista numerada que aparece em sequência, sem âncora por item. Pro "mapa" do vídeo na abertura
("vou te mostrar os 6 passos").
```json
{"tipo": "lista", "fala": "h", "de": "deixa", "ate": "fim", "itens": ["Contato", "Diagnóstico", "Estudo", "Projeto", "Obra", "Inauguração"]}
```

### `passo`
Cartão "PASSO 03 · Nome" com a trilha de todos os passos acendendo até o atual. Pra vídeo de
processo, um por capítulo, no começo dele. `total` é quantos passos existem.
```json
{"tipo": "passo", "fala": "p3", "duracao": 2.4, "numero": 3, "total": 6, "nome": "Estudo mercadológico"}
```
`prefixo` troca "PASSO" por "ETAPA", "DICA", "STEP".

### `barra`
N etapas que acendem em sequência a partir de uma palavra. Pra "dividindo por etapas".
```json
{"tipo": "barra", "fala": "c2b", "de": "dividindo", "acende": "etapas", "ate": "etapas", "n": 4, "rotulo": "Etapa"}
```

### `marcos`
Linha do tempo com marcos que acendem quando ditos. Pra "em 3, 6, 9 e 12 meses".
```json
{"tipo": "marcos", "fala": "p3b", "ate": "fim", "titulo": "PROJEÇÃO DE FATURAMENTO", "unidade": "MESES",
 "itens": [["3", "3"], ["6", "6"], ["9", "9"], ["12", "12"]]}
```

## Metáfora

### `ondas`
Duas ondas fora de fase que entram em sintonia na palavra. Pra "planejamento e execução
trabalham juntos", "alinhamento", "sintonia".
```json
{"tipo": "ondas", "fala": "c5a", "ate": "fim", "rotulos": ["Planejamento", "Execução"],
 "palavra_a": "planejamento", "palavra_b": "execução", "une": "sintonia", "texto_uniao": "Em sintonia"}
```

## Chamada

### `botao`
Botão branco que entra com mola e recebe um toque na palavra. Pra "clica em Saiba Mais",
"link na bio". Sem `ate`, fica até o fim do vídeo.
```json
{"tipo": "botao", "fala": "c6", "de": "clica", "toque": "saiba", "texto": "Saiba mais"}
```

### `pilula`
Pílula "● AO VIVO" com ponto vermelho pulsando, no canto. Em geral vem pelo `rotulo` do apoio;
avulsa só se precisar fora de apoio.
```json
{"tipo": "pilula", "fala": "c2b", "de": "respeitando", "ate": "mercado", "texto": "LOJA ABERTA"}
```

## O que vem sem pedir (e o estilo decide a cara)

Cada item abaixo tem opções em `references/estilo.md`; o que está aqui é o padrão (`agencia`).

- **Legenda**: palavra a palavra, blocos de até 4 palavras escolhidos pela melhor quebra (nunca
  termina em "de", "a", "que"), destaques na cor da marca sublinhados, `riscar` riscadas. Outras
  caras: bloco com contorno, karaokê com caixa, barra preta, pílula.
- **Tag de capítulo**: "■ MARCA | 02 MÉTODO" no canto, troca com deslize.
- **Assinatura**: onda sob a legenda que reage à voz (ou barra de progresso, linha, nada).
- **Câmera**: avanço lento contínuo em cada tomada (ou zoom no corte, ou parada); troca de
  enquadramento vira corte.
- **Apoio**: entra por máscara crescendo do centro, com leve zoom (ou corte, deslize, fusão).
- **Acabamento**: vinheta e grão leves, escurecimento no topo e na base pra texto ler (ou
  neutro, frio, quente).
- **Cartão final**: a onda atravessa e se recolhe, o logo sobe, duas linhas e o rodapé (ou nome
  grande, fundo na cor, mínimo).
- **Som**: sopro nas entradas de apoio, tique em item marcado, toque em etiqueta e no botão (ou só
  trilha). Trilha uns 14 dB abaixo da voz, cedendo quando ele fala.

## Quanto cabe num vídeo de 1 minuto

Um título, um contador, dois ou três gráficos de lista ou metáfora, um botão. Mais que isso vira
apresentação de slides. Quando em dúvida, tire.
