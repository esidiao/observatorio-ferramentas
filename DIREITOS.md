# Direitos autorais

© 2026 **Edson Sidião de Souza Júnior** — sidiao@i9educar.com
[Currículo Lattes](http://lattes.cnpq.br/9464330669014306)

Todos os direitos reservados sobre a obra autoral, nos termos da
**Lei 9.610/1998** (direitos autorais) e da **Lei 9.609/1998** (programa de
computador).

## O que é obra do autor

Tudo neste repositório: o código de `cnes/fatiar.py`, a declaração de
`cnes/observatorios.json`, a rotina de `cnes/reconsolidar.sh`, este documento e
o `README.md`.

O que há de autoral aqui não é a leitura de um ZIP por faixa de bytes — é o
**desenho das guardas**. Cada uma existe porque um modo específico de falhar em
silêncio foi encontrado na prática e passou a ser visível:

- comparar o declarado com o extrator de cada destino **antes** de baixar,
  porque uma fatia com o nome errado não dá erro, é ignorada, e custa a releitura
  de 834 MB sem nenhuma mensagem;
- escrever em arquivo parcial e renomear no fim, porque arquivo truncado é
  aceito como cache pronto e produz número plausível, só menor;
- comparar o `rede.py` dos projetos irmãos ignorando a única linha que deve
  diferir, e conferir separadamente que ela difere certo.

Esse conjunto não pode ser copiado, adaptado ou redistribuído sem autorização,
ressalvadas as exceções legais — entre elas a citação com identificação da
fonte.

## O que não é

**Os códigos de classificação não são obra do autor.** As famílias de CBO
(`2238`, `2515`, `2232`) e os códigos de serviço especializado (`107`, `114`,
`115`, `135`, `157`) declarados em `cnes/observatorios.json` são classificações
do **Ministério da Saúde**, publicadas no CNES. O que é autoral é o critério de
seleção — quais códigos respondem à pergunta de cada observatório, e por quê.

**Nenhum dado público é publicado aqui.** Este repositório não contém nem
distribui dado do CNES: ele lê a base no servidor do DATASUS e grava recortes
nos caches locais dos observatórios, que não são versionados. Os dados primários
pertencem às instituições que os produzem, e reivindicá-los seria o oposto do
que estes projetos defendem.

**Não há biblioteca de terceiros.** O fatiador usa apenas a biblioteca padrão do
Python, e o módulo de rede que ele carrega é o dos próprios observatórios, por
decisão de projeto explicada no `README.md`. Não há, portanto, licença de
terceiro a observar neste repositório — ao contrário dos observatórios irmãos,
que embarcam Leaflet, Chart.js e fontes sob a SIL OFL.

## Como citar

> SOUZA JÚNIOR, Edson Sidião de. *Ferramentas dos Observatórios Nacionais da
> Formação*: leitura única da base do CNES para projetos irmãos. 2026.
> Disponível em: https://github.com/esidiao/observatorio-ferramentas.
> Acesso em: [data].

## Observatórios atendidos

Cada um tem o seu próprio `DIREITOS.md`, e nenhum depende deste repositório para
funcionar:

- [observatorio-fonoaudiologia](https://github.com/esidiao/observatorio-fonoaudiologia)
- [observatorio-psicologia](https://github.com/esidiao/observatorio-psicologia)
- [observatorio-odontologia](https://github.com/esidiao/observatorio-odontologia)

## Registro de anterioridade

`registro_autoral.json` guarda o resumo SHA-256 de cada arquivo autoral, a data
do registro e o commit que ancora essa data no histórico do repositório.

O resumo é calculado sobre o **conteúdo**, com fim de linha normalizado — não
sobre os bytes como cada sistema operacional os grava. É isso que permite a
outra pessoa, em outra máquina, chegar ao mesmo número. Para conferir:

```bash
python registro_autoral.py --verificar
```

**O que ele é:** declaração datada de conteúdo, verificável por terceiros.
**O que não é:** registro em cartório ou depósito no INPI — e não substitui
nenhum dos dois.
