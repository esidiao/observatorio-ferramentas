# observatorio-ferramentas

Ferramentas de manutenção dos observatórios nacionais de formação. Nenhum
observatório depende deste repositório para rodar: eles continuam autônomos,
cada um com o seu ETL completo. O que está aqui serve para operar vários ao
mesmo tempo sem pagar o mesmo custo várias vezes.

| Observatório | Repositório |
|---|---|
| Fonoaudiologia | [observatorio-fonoaudiologia](https://github.com/esidiao/observatorio-fonoaudiologia) |
| Psicologia | [observatorio-psicologia](https://github.com/esidiao/observatorio-psicologia) |
| Odontologia | [observatorio-odontologia](https://github.com/esidiao/observatorio-odontologia) |

## `cnes/fatiar.py` — uma leitura do CNES para todos

Os três observatórios de saúde leem as mesmas tabelas-fato do CNES:
`tbEstabelecimento`, `tbCargaHorariaSus` (834 MB descomprimidos),
`rlEstabServClass` e, só para Odontologia, `tbEquipe`. Rodar os três extratores
em sequência lê tudo três vezes — cerca de três horas.

```bash
python cnes/fatiar.py 202609
```

Uma passada, as três fatias, cerca de uma hora. Medido na competência 202609,
de 710 MB no servidor:

| Tabela lida uma vez | Fonoaudiologia | Psicologia | Odontologia |
|---|---|---|---|
| `tbEstabelecimento` | 640.122 | 640.122 | 640.122 |
| `tbCargaHorariaSus` (6.821.813 vínculos) | 57.002 (CBO 2238) | 172.230 (2515) | 263.997 (2232) |
| `rlEstabServClass` (1.479.538 registros) | 14.204 (107, 135/005, 135/010) | 28.906 (115) | 89.976 (114, 157) |
| `tbEquipe` | — | — | 125.841 |

### Por que isto funciona

A guarda de cache de cada `extrair_cnes.py` é **arquivo por arquivo**
(`if not alvos["X"].exists()`), não tudo-ou-nada. Fatias presentes são
aproveitadas; o que falta é baixado. Então basta gravar as fatias grandes no
cache de cada projeto e deixar que o extrator de lá faça o resto.

### O que ele deliberadamente não faz

**Não gera `dominio.json`.** As tabelas de rótulo somam menos de 200 KB e cada
projeto tem a sua própria forma para esse arquivo — Psicologia e Odontologia
inclusive diferem entre si. Replicar as formas aqui seria duplicar uma estrutura
que, divergindo em silêncio, degradaria os rótulos do site sem acusar erro
nenhum. Encontrando as fatias grandes prontas e o domínio ausente, cada extrator
lê sozinho as suas tabelinhas, em segundos.

**Não traz a sua própria cópia de `rede.py`.** Uma quarta cópia de um módulo que
já existe em triplicado seria uma quarta oportunidade de divergir, e a desta
ferramenta seria a que ninguém revisa. O script confere que o `rede.py` dos
destinos é idêntico (normalizando fim de linha) e usa o deles. Se divergirem,
ele para e diz quais — divergência entre irmãos é notícia.

**Não agrega, não consolida, não escreve em `data/`.** Grava arquivos de cache e
nada mais. A medida continua sendo feita por quem a publica.

### Duas guardas que valem a leitura

`conferir_spec` compara o declarado em `cnes/observatorios.json` com o
`extrair_cnes.py` de cada destino, **antes** de baixar qualquer coisa. O motivo é
que o modo de falhar aqui é silencioso: uma fatia gravada com um nome que o
extrator não procura não dá erro — ele a ignora, conclui que falta e rebaixa 834
MB, que é exatamente o custo que esta ferramenta existe para evitar. Um prefixo
de CBO errado é pior: produz um cache plausível, do tamanho esperado, com o
conteúdo de outra profissão.

Cada CSV é escrito em `.parcial` e renomeado só no fim. Escrever direto no
destino deixaria, numa interrupção, um arquivo truncado — e truncado é o pior
estado possível, porque os extratores o aceitam como cache pronto (o arquivo
existe) e o dado que falta não aparece em lugar nenhum. Nenhum teste de âncora
pega isso: o número que sai é plausível, só menor.

## `cnes/reconsolidar.sh` — a volta de cada projeto

```bash
cnes/reconsolidar.sh ../observatorio-fonoaudiologia 202609
```

Roda extração (do cache), consolidação, portões GO, conferência de riqueza,
testes, registro autoral e build de um observatório. Não chama o
`etl/pipeline.py` inteiro de propósito: ele reextrai Censo e CPC, que
normalmente não mudaram.

A ordem difere do pipeline dos projetos num ponto: o **registro autoral vem
depois dos testes**. A troca de competência faz os testes de âncora falharem —
é o que eles existem para fazer —, a correção mexe em prosa e constantes, e um
registro gerado antes disso descreveria criptograficamente uma árvore que deixou
de existir.

## Como trocar a competência do CNES, do começo ao fim

```bash
python cnes/fatiar.py AAAAMM                              # ~1 h, uma vez
cnes/reconsolidar.sh ../observatorio-fonoaudiologia AAAAMM
cnes/reconsolidar.sh ../observatorio-psicologia      AAAAMM
cnes/reconsolidar.sh ../observatorio-odontologia     AAAAMM
```

**Os testes de âncora vão falhar, e isso é o comportamento correto.** Eles fixam
os totais medidos na competência anterior justamente para que a mudança não passe
calada. Reconfira cada valor contra o `data/nacional.json` recém-gerado e
atualize as constantes — **nunca ajuste até o teste passar**. Depois procure os
números antigos também em `README.md`, em `site/catalogo.py` e nos templates: há
figuras nacionais escritas à mão em texto que vai ao ar.

Publicação é manual em cada repositório, por decisão de projeto: aba **Actions →
Run workflow → `acao: publicar`**.

## Acrescentar um observatório

Uma entrada em `cnes/observatorios.json`. Não há código específico de projeto no
fatiador; os critérios de serviço são declarativos, inclusive os compostos
(serviço inteiro, ou serviço mais lista de classificações).

## Licença e autoria

Edson Sidião de Souza Júnior — I9 Educar. Ver [DIREITOS.md](DIREITOS.md), que
separa o que é obra do autor (o desenho das guardas) do que não é (os códigos
de classificação do CNES, que são do Ministério da Saúde).

`registro_autoral.json` guarda o resumo SHA-256 de cada arquivo autoral,
calculado sobre o conteúdo com fim de linha normalizado, e o commit que ancora a
data. Para conferir, em qualquer sistema:

```bash
python registro_autoral.py --verificar
```
