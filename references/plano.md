# O plano (`plano.json`)

É o que você escreve depois de ler o roteiro e o catálogo. Tudo ancorado em **palavra**; o motor
converte em tempo medindo o áudio. Palavras são comparadas sem acento de caixa, sem pontuação
(`"Clica,"` casa com `clica`). Quando a mesma palavra aparece mais de uma vez na fala, use
`n_de`/`n_ate` (ou o terceiro item em listas) pra dizer qual ocorrência.

## Esqueleto

```json
{
  "titulo": "p1-comercial",
  "idioma": "pt",
  "estilo": "agencia",
  "formato": "9:16",
  "trilha": "lofi-calma",
  "marca": {"nome": "Loja em Dia", "destaque": "#F5B942", "logo": "logo.png",
            "rodape": "ENTRE EM CONTATO  ·  LINK NA BIO"},
  "falas": [...],
  "apoios": [...],
  "capitulos": [...],
  "pecas": [...],
  "destaques": ["fechou", "sequer"],
  "riscar": ["improviso"],
  "correcoes": {"mecanológico": "mercadológico"},
  "cartao_final": {"linhas": [["Reforma de supermercado", "branco"], ["sem fechar a loja.", "destaque"]],
                   "duracao": 3.2}
}
```

## Campo a campo

### Cabeçalho

| Campo | Valores | Padrão |
|---|---|---|
| `titulo` | nome do mp4 de saída | nome da pasta |
| `idioma` | código do idioma da fala (`pt`, `en`, `es`) | `pt` |
| `estilo` | um preset (`agencia`, `editorial`, `impacto`, `clean`, `limpo`), o nome de um estilo salvo (`acme` → `estilos/acme.json`), um caminho de JSON, ou o estilo escrito ali mesmo (`{"base": "agencia", "legenda": "pilula"}`). Ver `references/estilo.md` | `agencia` |
| `formato` | `9:16` (1080x1920), `16:9`, `1:1`, `4:5` | `9:16` |
| `fps` | quadros por segundo | 30 |
| `trilha` | `lofi-calma`, `groove-leve` (CC0, vêm na skill), caminho de um arquivo, ou `null` | `lofi-calma` |
| `recorte` | `preencher` (o bruto enche a tela e o que sobra é cortado) ou `caixa` (vídeo deitado dentro de uma caixa no meio do reel, com o próprio vídeo desfocado de fundo; sobra espaço pras peças em cima e pra legenda embaixo). **Bruto 16:9 virando 9:16 quase sempre pede `caixa`** | `preencher` |
| `caixa_largura`, `caixa_y` | largura da caixa e onde fica o topo dela (px numa tela de 1080x1920) | 1000, 700 |
| `centro` | `[x, y]` em fração, onde o falante está no bruto; vale pro `preencher` (que lado fica) | `[0.5, 0.5]` |
| `pecas_y` | altura (px numa tela de 1920) onde as peças começam. Suba ou desça quando a prévia mostrar peça em cima do rosto: rosto no topo pede peça mais baixa; na `caixa`, 280 | 300 |

### `marca`

| Campo | O que é |
|---|---|
| `nome` | aparece na tag de canto e no cartão final se não houver logo |
| `destaque` | cor em hex: palavras destacadas, filetes, botão de check. Peça a cor da marca; se não tiver, dourado `#F5B942` |
| `logo` | PNG com transparência, caminho relativo à pasta do projeto. Opcional |
| `rodape` | linha pequena do cartão final |

### `falas` (obrigatório)

Cada fala é um trecho contínuo de um take, na ordem em que entram no vídeo.

```json
{"id": "c1", "take": "fala-01", "de": "essa", "ate": "gente", "enquadramento": "aberto"}
```

| Campo | O que é |
|---|---|
| `id` | nome curto e único; as outras seções apontam pra ele |
| `take` | nome do arquivo em `bruto/` sem extensão (como está no `catalogo.md`) |
| `de`, `ate` | primeira e última palavra do trecho, como estão em `transcricoes/<take>.txt` |
| `n_de`, `n_ate` | qual ocorrência da palavra, quando ela se repete no take (padrão 1) |
| `enquadramento` | `aberto`, `medio` ou `fechado`. Alterne entre falas seguidas do mesmo take: corte sem troca de enquadramento vira pulo |
| `centro` | `[x, y]` em fração do quadro de origem, onde o falante está. Só importa quando o formato de saída é mais estreito que o bruto (16:9 virando 9:16): diz que lado fica. Padrão `[0.5, 0.5]`; pode ir no topo do plano pra valer pra todas |

O motor mede, no áudio limpo, onde a voz começa e termina de verdade e aperta as pausas internas
(respiro vira 0,08 s; fim de frase, 0,14 s). Você não precisa (nem deve) marcar isso.

### `apoios`

Imagem por cima de parte de uma fala. A voz continua a da fala.

```json
{"fala": "c3", "de": "circulação", "ate": "circulação", "take": "IMG_8581", "entrada": 1.2, "rotulo": "LOJA ABERTA"}
```

| Campo | O que é |
|---|---|
| `fala` | id da fala por cima da qual entra |
| `de`, `ate` | palavra em que entra e palavra em que sai (sai no fim dela) |
| `take` | arquivo de apoio em `bruto/`. Pode ser de outro projeto: caminho absoluto pro mp4 já preparado |
| `entrada` | segundo do apoio em que ele começa a ser mostrado (olhe a folha pra escolher) |
| `rotulo` | opcional: pílula "● TEXTO" no canto, pra loja funcionando, ao vivo, bastidores |

Apoio que acaba a menos de 0,5 s do fim da fala vai até o fim dela (senão quem fala pisca por
alguns quadros). Dois apoios não se sobrepõem: o segundo corta o primeiro.

### `capitulos`

A tag de canto "■ MARCA | 01 CONTATO". Troca quando a fala indicada começa.

```json
{"fala": "c2a", "numero": "02", "nome": "MÉTODO"}
```

### `pecas`

Gráficos. Todos têm `tipo`, `fala` e, em geral, `de` (palavra em que aparece) e `ate` (palavra em
que some, `"fim"` = fim da fala, `"video"` = até o fim do vídeo) ou `duracao` em segundos.
`antecipa` (padrão 0,1 s) faz a peça entrar um pouco antes da palavra. Catálogo com exemplos e
quando usar cada uma: `references/pecas.md`.

### `destaques`, `riscar`, `correcoes`

- `destaques`: palavras que a legenda pinta com a cor da marca e sublinha. As que carregam a
  promessa: números, verbos fortes, o nome do método. Umas 10 a 15 num vídeo de 1 min.
- `riscar`: palavras que a legenda risca em vez de sublinhar ("improviso", "achismo").
- `correcoes`: `{"como o transcritor escreveu": "como é"}`. Vale pra legenda e pras âncoras.
  Números quebrados ("99" ",9" "%") o motor já junta sozinho.

### `cartao_final`

```json
{"linhas": [["Reforma de supermercado", "branco"], ["sem fechar a loja.", "destaque"]],
 "rodape": "ENTRE EM CONTATO  ·  LINK NA BIO", "duracao": 3.2}
```

Com logo, o logo entra; sem logo, o `marca.nome`. Duas linhas no máximo.

## Exemplo completo

Anúncio de 50 s de uma consultoria de reforma de supermercado (6 falas, 11 apoios, 7 peças).
O roteiro pedia "Texto na tela: Reforma sem fechar o supermercado" e "Circulação, Segurança,
Abastecimento"; o resto das peças saiu do que a fala dizia.

```json
{
  "titulo": "p1-comercial",
  "estilo": "agencia",
  "formato": "9:16",
  "trilha": "lofi-calma",
  "marca": {"nome": "Loja em Dia", "destaque": "#F5B942", "logo": "logo.png", "rodape": "ENTRE EM CONTATO  ·  LINK NA BIO"},
  "falas": [
    {"id": "c1",  "take": "fala-01", "de": "essa",    "ate": "gente",        "enquadramento": "aberto"},
    {"id": "c2a", "take": "fala-02", "de": "pessoal", "ate": "improviso",    "enquadramento": "medio"},
    {"id": "c2b", "take": "fala-03", "de": "depende", "ate": "mercado",      "enquadramento": "aberto"},
    {"id": "c3",  "take": "fala-04", "de": "cada",    "ate": "movimento",    "enquadramento": "aberto"},
    {"id": "c4",  "take": "fala-05", "de": "sem",     "ate": "funcionários", "enquadramento": "medio"},
    {"id": "c5a", "take": "fala-06", "de": "quando",  "ate": "sintonia",     "enquadramento": "aberto"},
    {"id": "c5b", "take": "fala-07", "de": "a",       "ate": "acontece",     "enquadramento": "medio"},
    {"id": "c6",  "take": "fala-08", "de": "clica",   "ate": "fina",         "enquadramento": "fechado"}
  ],
  "apoios": [
    {"fala": "c1",  "de": "eu",            "ate": "gente",         "take": "IMG_8581", "entrada": 0.0, "rotulo": "LOJA ABERTA"},
    {"fala": "c2b", "de": "respeitando",   "ate": "mercado",       "take": "IMG_8582", "entrada": 0.3, "rotulo": "LOJA ABERTA"},
    {"fala": "c3",  "de": "circulação",    "ate": "circulação",    "take": "IMG_8581", "entrada": 1.2},
    {"fala": "c3",  "de": "segurança",     "ate": "segurança",     "take": "IMG_8583", "entrada": 1.0},
    {"fala": "c3",  "de": "abastecimento", "ate": "abastecimento", "take": "IMG_8580", "entrada": 1.4},
    {"fala": "c3",  "de": "horários",      "ate": "movimento",     "take": "apoio-01", "entrada": 8.6},
    {"fala": "c4",  "de": "começa",        "ate": "espaço",        "take": "IMG_8585", "entrada": 0.5},
    {"fala": "c4",  "de": "clientes",      "ate": "funcionários",  "take": "IMG_8584", "entrada": 3.0},
    {"fala": "c5a", "de": "planejamento",  "ate": "execução",      "take": "apoio-02", "entrada": 2.0},
    {"fala": "c5a", "de": "trabalham",     "ate": "sintonia",      "take": "apoio-03", "entrada": 6.0},
    {"fala": "c5b", "de": "enquanto",      "ate": "acontece",      "take": "IMG_8582", "entrada": 2.0, "rotulo": "LOJA EM OPERAÇÃO"}
  ],
  "capitulos": [
    {"fala": "c1",  "numero": "01", "nome": "REFORMA SEM FECHAR"},
    {"fala": "c2a", "numero": "02", "nome": "MÉTODO"},
    {"fala": "c3",  "numero": "03", "nome": "OPERAÇÃO"},
    {"fala": "c4",  "numero": "04", "nome": "PLANEJAMENTO"},
    {"fala": "c5a", "numero": "05", "nome": "SINTONIA"},
    {"fala": "c6",  "numero": "06", "nome": "PRÓXIMO PASSO"}
  ],
  "pecas": [
    {"tipo": "titulo",    "fala": "c1", "ate": "não", "linhas": [["Reforma sem fechar", "branco"], ["o supermercado.", "destaque"]]},
    {"tipo": "contador",  "fala": "c1", "de": "fechou", "ate": "dia", "valor": "0", "rotulo": "dias com a loja\nfechada"},
    {"tipo": "barra",     "fala": "c2b", "de": "dividindo", "acende": "etapas", "ate": "etapas", "n": 4, "rotulo": "Etapa"},
    {"tipo": "checklist", "fala": "c3", "ate": "fim",
     "itens": [["Circulação", "circulação"], ["Segurança", "segurança"], ["Abastecimento", "abastecimento"], ["Horários de maior movimento", "horários"]]},
    {"tipo": "etiquetas", "fala": "c4", "de": "disputar", "ate": "fim", "titulo": "Sem planejamento, a obra disputa espaço com",
     "itens": [["Clientes", "clientes"], ["Fornecedores", "fornecedores"], ["Funcionários", "funcionários"]]},
    {"tipo": "ondas",     "fala": "c5a", "ate": "fim", "rotulos": ["Planejamento", "Execução"],
     "palavra_a": "planejamento", "palavra_b": "execução", "une": "sintonia", "texto_uniao": "Em sintonia"},
    {"tipo": "botao",     "fala": "c6", "de": "clica", "toque": "saiba", "texto": "Saiba mais"}
  ],
  "destaques": ["fechou", "sequer", "improviso", "etapas", "circulação", "segurança", "abastecimento",
                "planejamento", "sintonia", "transformação", "saiba", "mais", "possível", "operação", "fina"],
  "riscar": ["improviso"],
  "correcoes": {},
  "cartao_final": {"linhas": [["Reforma de supermercado", "branco"], ["sem fechar a loja.", "destaque"]], "duracao": 3.2}
}
```

## Erros que o motor pega e o que fazer

| Mensagem | Causa | Conserto |
|---|---|---|
| `palavra X (ocorrência 1) não está na transcrição` | a palavra não é a da transcrição, ou está grafada diferente | abra `transcricoes/<take>.txt` e copie de lá; se o transcritor errou, ponha em `correcoes` |
| `não achei voz entre a e b` | janela sem fala (de/ate invertidos, ocorrência errada) | confira `n_de`/`n_ate` |
| `take X não existe` | nome diferente do `catalogo.md` | use o nome do catálogo, sem extensão |
| `peça de tipo X não existe` | tipo fora do catálogo | ver `references/pecas.md` |
