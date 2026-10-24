#!/usr/bin/env python3
"""
Fatiador único da base do CNES para os observatórios irmãos.

Os observatórios de Fonoaudiologia, Psicologia e Odontologia leem as MESMAS
tabelas-fato do CNES — `tbEstabelecimento`, `tbCargaHorariaSus` (834 MB
descomprimidos), `rlEstabServClass` e, só para Odontologia, `tbEquipe`. Cada um
tem o seu próprio extrator, autônomo e sem dependência dos irmãos, o que é
deliberado: um observatório não deve quebrar porque o vizinho mudou. O preço é
que rodar os três em sequência lê as mesmas tabelas três vezes, algo como três
horas.

Este script lê UMA vez e grava, na mesma passada, a fatia filtrada de cada
observatório no cache que o extrator daquele projeto espera encontrar. Cerca de
uma hora em vez de três. Depois disso, cada observatório é reconsolidado
separadamente, pelo seu próprio código, sem saber que isto existiu.

Por que isto funciona, e qual é a condição: a guarda de cache de cada
`extrair_cnes.py` é arquivo por arquivo (`if not alvos["X"].exists()`), não
tudo-ou-nada. Fatias presentes são aproveitadas; o que falta é baixado.

O que este script deliberadamente NÃO faz
-----------------------------------------

**Não gera `dominio.json`.** As tabelas de rótulo somam menos de 200 KB, e cada
projeto tem a sua própria forma para esse arquivo — Psicologia e Odontologia
inclusive diferem entre si. Replicar as formas aqui seria duplicar uma estrutura
que, divergindo em silêncio, degradaria os rótulos do site sem acusar erro
nenhum. Encontrando as fatias grandes prontas e o domínio ausente, cada extrator
lê sozinho as suas tabelinhas. Custa segundos.

**Não agrega, não consolida, não escreve em `data/`.** Só grava arquivos de
cache. A medida continua sendo feita por quem a publica.

**Não traz a sua própria cópia de `rede.py`.** Uma quarta cópia de um módulo que
já existe em triplicado é uma quarta oportunidade de divergir. Este script
confere que o `rede.py` dos destinos é byte a byte idêntico e usa o deles. Se
divergirem, ele para e diz qual — divergência entre irmãos é notícia, não
detalhe de implementação.

Uso
---
    python cnes/fatiar.py 202609
    python cnes/fatiar.py 202609 --base /caminho/onde/estao/os/repos
    python cnes/fatiar.py 202609 --so fonoaudiologia --so psicologia
"""
import argparse
import csv
import hashlib
import importlib.util
import json
import sys
from pathlib import Path

AQUI = Path(__file__).resolve().parent
SPEC = AQUI / "observatorios.json"

HOST = "ftp.datasus.gov.br"
DIRETORIO = "/cnes"
PADRAO = "BASE_DE_DADOS_CNES_{competencia}.ZIP"
BLOCO = 16 << 20

COL_ESTAB = ["CO_UNIDADE", "CO_MUNICIPIO_GESTOR", "CO_ESTADO_GESTOR", "ATIVO"]
COL_VINC = ["CO_UNIDADE", "CO_PROFISSIONAL_SUS", "CO_CBO", "TP_SUS_NAO_SUS"]
COL_SERV = ["CO_UNIDADE", "CO_SERVICO", "CO_CLASSIFICACAO", "ST_ATIVO_SN",
            "CO_AMBULATORIAL_SUS", "CO_HOSPITALAR_SUS"]
COL_EQUIPE = ["CO_UNIDADE", "TIPO", "SUBTIPO", "CO_EQUIPE", "DESATIVACAO"]

csv.field_size_limit(1 << 24)


# --------------------------------------------------------------------------- #
# Conferências que acontecem ANTES de baixar 710 MB
# --------------------------------------------------------------------------- #

def carregar_spec(so=None):
    spec = json.loads(SPEC.read_text(encoding="utf-8"))
    spec.pop("_leia", None)
    if so:
        faltando = [n for n in so if n not in spec]
        if faltando:
            raise SystemExit(f"[ERRO] observatório desconhecido: {faltando}. "
                             f"Conhecidos: {sorted(spec)}")
        spec = {n: c for n, c in spec.items() if n in so}
    return spec


def conferir_destinos(spec, base):
    """Todo destino tem de existir e ter extrator. Caminho errado é silencioso."""
    faltando = []
    for nome, cfg in spec.items():
        repo = base / cfg["repo"]
        if not (repo / "etl" / "extrair_cnes.py").exists():
            faltando.append(f"{nome}: {repo} sem etl/extrair_cnes.py")
    if faltando:
        raise SystemExit("[ERRO] destinos inválidos:\n  " + "\n  ".join(faltando)
                         + "\n(use --base para dizer onde os repositórios estão)")


def conferir_spec(spec, base):
    """
    O que está declarado aqui tem de ser o que o extrator de lá espera.

    Uma fatia gravada com o nome que o extrator não procura não causa erro: ele
    a ignora, conclui que falta, e rebaixa a tabela de 834 MB — justamente o
    custo que este script existe para evitar, perdido sem nenhuma mensagem. O
    mesmo vale para o prefixo de CBO: gravar a família errada produz um cache
    plausível, do tamanho esperado, com o conteúdo de outra profissão.

    A conferência é textual porque é a única que não exige importar o extrator
    de cada projeto (o que acoplaria esta ferramenta ao código deles).
    """
    problemas = []
    for nome, cfg in spec.items():
        fonte = (base / cfg["repo"] / "etl" / "extrair_cnes.py").read_text(
            encoding="utf-8")
        esperados = [cfg["vinculos"]["arquivo"], cfg["servicos"]["arquivo"]]
        if cfg.get("equipes"):
            esperados.append(cfg["equipes"])
        for arquivo in esperados:
            if arquivo not in fonte:
                problemas.append(
                    f"{nome}: `{arquivo}` não aparece em extrair_cnes.py — "
                    "o extrator procura outro nome e a fatia seria ignorada")
        prefixo = cfg["vinculos"]["cbo_prefixo"]
        if f'"{prefixo}"' not in fonte:
            problemas.append(
                f"{nome}: prefixo de CBO {prefixo} não aparece em "
                "extrair_cnes.py — a família declarada aqui não é a de lá")
    if problemas:
        raise SystemExit("[ERRO] a declaração divergiu dos extratores:\n  "
                         + "\n  ".join(problemas)
                         + "\n\nCorrija cnes/observatorios.json. Divergir aqui "
                           "não dá erro na hora de rodar: dá cache errado.")


def _sem_ua(fonte):
    """O módulo sem a linha de User-Agent, que é a única que deve diferir."""
    return "\n".join(l for l in fonte.splitlines() if not l.startswith("UA = "))


def _ua(fonte):
    for linha in fonte.splitlines():
        if linha.startswith("UA = "):
            return linha.split("=", 1)[1].strip().strip('"')
    return None


def carregar_rede(spec, base):
    """
    Usa o `rede.py` dos destinos, depois de conferir que o comportamento é um só.

    Trazer uma cópia própria faria quatro versões do mesmo módulo, e a desta
    ferramenta seria a que ninguém revisa. Conferir e reusar mantém uma verdade
    só; se os irmãos divergirem, isso aparece aqui em vez de virar um
    comportamento diferente a cada repositório.

    Uma linha PRECISA diferir: o `UA`, com que cada projeto se identifica aos
    servidores públicos. Então ela sai da comparação — e entra numa conferência
    própria, porque o modo de ela estar errada é justamente o modo de ela passar
    desapercebida. Foi assim que a Odontologia, derivada da Psicologia, passou a
    se apresentar a INEP e DATASUS com o nome da irmã: parecer idêntica ao
    original é exatamente o que uma cópia faz quando ninguém olha.
    """
    fontes = {}
    for nome, cfg in spec.items():
        caminho = base / cfg["repo"] / "etl" / "rede.py"
        if not caminho.exists():
            raise SystemExit(f"[ERRO] {caminho} ausente")
        texto = caminho.read_bytes().replace(b"\r\n", b"\n").decode("utf-8")
        fontes[nome] = (texto, caminho)

    hashes = {n: hashlib.sha256(_sem_ua(f).encode("utf-8")).hexdigest()
              for n, (f, _) in fontes.items()}
    if len(set(hashes.values())) > 1:
        linhas = [f"  {n}: {h[:12]}" for n, h in sorted(hashes.items())]
        raise SystemExit(
            "[ERRO] o `rede.py` dos observatórios divergiu (fora da linha UA):\n"
            + "\n".join(linhas)
            + "\n\nEste fatiador lê as tabelas uma vez para todos, então não "
              "pode escolher um comportamento de rede em nome dos outros. "
              "Reconcilie os módulos antes de rodar.")

    erradas = {n: _ua(f) for n, (f, _) in fontes.items()
               if not (_ua(f) or "").startswith(spec[n]["repo"] + "/")}
    if erradas:
        linhas = [f"  {n}: UA={v!r}, esperado começar por "
                  f"{spec[n]['repo'] + '/'!r}"
                  for n, v in sorted(erradas.items())]
        raise SystemExit(
            "[ERRO] observatório se identificando com o nome de outro:\n"
            + "\n".join(linhas)
            + "\n\nO User-Agent é como o projeto se apresenta a INEP e DATASUS. "
              "Errado, ele manda o operador do servidor reclamar com o projeto "
              "errado, e faz a proveniência afirmar uma origem que não é a "
              "verdadeira. Corrija no repositório apontado.")

    caminho = next(iter(fontes.values()))[1]
    plural = "destinos" if len(fontes) > 1 else "destino"
    print(f"[REDE] rede.py com comportamento idêntico nos {len(fontes)} "
          f"{plural} ({next(iter(hashes.values()))[:12]}), cada um com o seu UA")
    espec = importlib.util.spec_from_file_location("rede_compartilhado", caminho)
    modulo = importlib.util.module_from_spec(espec)
    espec.loader.exec_module(modulo)
    return modulo


# --------------------------------------------------------------------------- #
# Escrita
# --------------------------------------------------------------------------- #

def _limpo(valor):
    return (valor or "").strip().strip('"')


def _coluna(campos, *alvos):
    """Nome real da coluna, tolerando variação de caixa e de espaço."""
    normal = {(c or "").strip().upper(): c for c in (campos or [])}
    for alvo in alvos:
        if alvo.upper() in normal:
            return normal[alvo.upper()]
    return None


class Saida:
    """
    Um CSV escrito em fluxo, em arquivo parcial, renomeado só no fim.

    Escrever direto no destino final deixaria, numa interrupção, um CSV
    truncado — e truncado é o pior estado possível: os extratores o aceitam
    como cache pronto, porque o arquivo existe, e o dado que falta não aparece
    em lugar nenhum. Nenhum teste de âncora pega isso, porque o número que sai
    é plausível, só menor.
    """

    def __init__(self, caminho, cabecalho):
        self.caminho = caminho
        caminho.parent.mkdir(parents=True, exist_ok=True)
        self.parcial = caminho.with_suffix(caminho.suffix + ".parcial")
        self._f = open(self.parcial, "w", encoding="utf-8", newline="")
        self._w = csv.writer(self._f, delimiter=";")
        self._w.writerow(cabecalho)
        self.n = 0

    def escrever(self, linha):
        self._w.writerow(linha)
        self.n += 1

    def concluir(self):
        self._f.close()
        self.parcial.replace(self.caminho)

    def abortar(self):
        self._f.close()
        self.parcial.unlink(missing_ok=True)


def _casa(criterios, servico, classificacao):
    """Serviço e classificação contra os critérios declarados do observatório."""
    for c in criterios:
        if c["servico"] != servico:
            continue
        classes = c.get("classificacoes")
        if classes is None or classificacao in classes:
            return True
    return False


# --------------------------------------------------------------------------- #
# Passada
# --------------------------------------------------------------------------- #

def _cache(base, cfg, competencia):
    return base / cfg["repo"] / "etl" / "dados" / f"cnes_{competencia}"


def pendencias(spec, base, competencia):
    """Quais fatias faltam, por tabela-fato. Pronta não é relida."""
    falta = {"estabelecimentos": [], "vinculos": [], "servicos": [], "equipes": []}
    for nome, cfg in spec.items():
        destino = _cache(base, cfg, competencia)
        if not (destino / "estabelecimentos.csv").exists():
            falta["estabelecimentos"].append(nome)
        if not (destino / cfg["vinculos"]["arquivo"]).exists():
            falta["vinculos"].append(nome)
        if not (destino / cfg["servicos"]["arquivo"]).exists():
            falta["servicos"].append(nome)
        if cfg.get("equipes") and not (destino / cfg["equipes"]).exists():
            falta["equipes"].append(nome)
    return falta


def _ler(z, sufixo, competencia, consumir, saidas, rotulo):
    """Lê um membro em fluxo. Falha apaga os parciais em vez de truncar."""
    alvo = z.localizar(sufixo.lower(), competencia)
    if not alvo:
        for s in saidas:
            s.abortar()
        raise SystemExit(f"[ERRO] membro {sufixo}{competencia} não está no ZIP")
    print(f"[CNES] lendo {alvo} -> {rotulo}", flush=True)
    try:
        with z.membro_arquivo(alvo, bloco=BLOCO) as f:
            consumir(csv.DictReader(f, delimiter=";"))
    except BaseException:
        for s in saidas:
            s.abortar()
        raise
    for s in saidas:
        s.concluir()
        print(f"[CNES]   {s.n} linhas -> {s.caminho}", flush=True)


def fatiar(competencia, base, so=None):
    spec = carregar_spec(so)
    conferir_destinos(spec, base)
    conferir_spec(spec, base)
    rede = carregar_rede(spec, base)

    falta = pendencias(spec, base, competencia)
    if not any(falta.values()):
        print(f"[CNES] todas as fatias de {sorted(spec)} já existem para "
              f"{competencia}; nada a baixar.")
        return
    for tabela, repos in falta.items():
        print(f"[CNES] pendente em {tabela}: {repos or '—'}")

    nome = PADRAO.format(competencia=competencia)
    z = rede.ZipRemotoFTP(HOST, DIRETORIO, nome)
    print(f"[CNES] {nome} — {z.tamanho() / 1048576:.0f} MB no servidor; "
          f"uma leitura só, {len(spec)} observatórios", flush=True)

    # ---- tbEstabelecimento: fatia idêntica para todos -------------------- #
    if falta["estabelecimentos"]:
        saidas = {r: Saida(_cache(base, spec[r], competencia) / "estabelecimentos.csv",
                           COL_ESTAB)
                  for r in falta["estabelecimentos"]}

        def consumir(leitor, saidas=saidas):
            ativos = desab = 0
            for linha in leitor:
                unidade = _limpo(linha.get("CO_UNIDADE"))
                if not unidade:
                    continue
                # Guardamos TODOS, com uma coluna dizendo se está ativo. O
                # desabilitado precisa continuar conhecido: é ele que permite
                # distinguir "excluído de propósito" de "não encontrado", e é
                # essa distinção que dá sentido à guarda de junção dos projetos.
                ativo = "0" if _limpo(linha.get("CO_MOTIVO_DESAB")) else "1"
                if ativo == "1":
                    ativos += 1
                else:
                    desab += 1
                registro = [unidade,
                            _limpo(linha.get("CO_MUNICIPIO_GESTOR")),
                            _limpo(linha.get("CO_ESTADO_GESTOR")),
                            ativo]
                for s in saidas.values():
                    s.escrever(registro)
            print(f"[CNES]   {ativos} ativos, {desab} desabilitados")

        _ler(z, "tbEstabelecimento", competencia, consumir,
             list(saidas.values()), ", ".join(saidas))

    # ---- tbCargaHorariaSus: 834 MB, uma leitura, N filtros de CBO -------- #
    if falta["vinculos"]:
        saidas = {r: (Saida(_cache(base, spec[r], competencia)
                            / spec[r]["vinculos"]["arquivo"], COL_VINC),
                      spec[r]["vinculos"]["cbo_prefixo"])
                  for r in falta["vinculos"]}

        def consumir(leitor, saidas=saidas):
            total = 0
            for linha in leitor:
                total += 1
                cbo = _limpo(linha.get("CO_CBO"))
                if not cbo:
                    continue
                destinos = [s for s, p in saidas.values() if cbo.startswith(p)]
                if not destinos:
                    continue
                registro = [_limpo(linha.get("CO_UNIDADE")),
                            _limpo(linha.get("CO_PROFISSIONAL_SUS")),
                            cbo,
                            _limpo(linha.get("TP_SUS_NAO_SUS"))]
                for s in destinos:
                    s.escrever(registro)
            print(f"[CNES]   {total} vínculos lidos")

        _ler(z, "tbCargaHorariaSus", competencia, consumir,
             [s for s, _ in saidas.values()], ", ".join(saidas))

    # ---- rlEstabServClass: uma leitura, N filtros de serviço ------------- #
    if falta["servicos"]:
        saidas = {r: (Saida(_cache(base, spec[r], competencia)
                            / spec[r]["servicos"]["arquivo"], COL_SERV),
                      spec[r]["servicos"]["criterios"])
                  for r in falta["servicos"]}

        def consumir(leitor, saidas=saidas):
            total = 0
            for linha in leitor:
                total += 1
                servico = _limpo(linha.get("CO_SERVICO"))
                classificacao = _limpo(linha.get("CO_CLASSIFICACAO"))
                destinos = [s for s, crit in saidas.values()
                            if _casa(crit, servico, classificacao)]
                if not destinos:
                    continue
                registro = [_limpo(linha.get("CO_UNIDADE")),
                            servico,
                            classificacao,
                            _limpo(linha.get("ST_ATIVO_SN")),
                            _limpo(linha.get("CO_AMBULATORIAL_SUS")),
                            _limpo(linha.get("CO_HOSPITALAR_SUS"))]
                for s in destinos:
                    s.escrever(registro)
            print(f"[CNES]   {total} registros de serviço lidos")

        _ler(z, "rlEstabServClass", competencia, consumir,
             [s for s, _ in saidas.values()], ", ".join(saidas))

    # ---- tbEquipe: só quem declarou querer ------------------------------- #
    if falta["equipes"]:
        saidas = {r: Saida(_cache(base, spec[r], competencia) / spec[r]["equipes"],
                           COL_EQUIPE)
                  for r in falta["equipes"]}

        def consumir(leitor, saidas=saidas):
            campos = leitor.fieldnames or []
            colunas = {
                "unidade": _coluna(campos, "CO_UNIDADE"),
                "tipo": _coluna(campos, "TP_EQUIPE", "CO_TIPO_EQUIPE"),
                "subtipo": _coluna(campos, "SUBTIPO", "SUB_TIPO"),
                "codigo": _coluna(campos, "CO_EQUIPE"),
                "desativacao": _coluna(campos, "DESATIVACAO", "DT_DESAT"),
            }
            if not colunas["unidade"] or not colunas["tipo"]:
                raise SystemExit("[ERRO] tbEquipe sem coluna de unidade ou de "
                                 f"tipo. Colunas: {campos}")
            print(f"[CNES]   colunas: {colunas}")
            total = 0
            # Todas as equipes, não só as de saúde bucal: esse filtro depende do
            # domínio, e domínio que falhou não pode obrigar a reler isto.
            for linha in leitor:
                total += 1
                registro = [
                    _limpo(linha.get(colunas["unidade"])),
                    _limpo(linha.get(colunas["tipo"])),
                    _limpo(linha.get(colunas["subtipo"])) if colunas["subtipo"] else "",
                    _limpo(linha.get(colunas["codigo"])) if colunas["codigo"] else "",
                    _limpo(linha.get(colunas["desativacao"])) if colunas["desativacao"] else "",
                ]
                for s in saidas.values():
                    s.escrever(registro)
            print(f"[CNES]   {total} equipes lidas")

        _ler(z, "tbEquipe", competencia, consumir, list(saidas.values()),
             ", ".join(saidas))

    print("\n[CNES] fatias gravadas. Falta, em cada repositório, apenas o "
          "`dominio.json` (tabelas de rótulo, <200 KB), que o extrator de lá "
          "lê sozinho ao rodar.")
    for nome, cfg in spec.items():
        print(f"  {nome:16} {_cache(base, cfg, competencia)}")


def main():
    p = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("competencia", help="AAAAMM, p. ex. 202609")
    p.add_argument("--base", default=str(AQUI.parent.parent),
                   help="pasta onde estão os repositórios dos observatórios "
                        "(padrão: a pasta que contém este repositório)")
    p.add_argument("--so", action="append", metavar="OBSERVATORIO",
                   help="limita a estes observatórios; repetível")
    a = p.parse_args()
    if not (len(a.competencia) == 6 and a.competencia.isdigit()):
        raise SystemExit("[ERRO] competência deve ser AAAAMM")
    fatiar(a.competencia, Path(a.base).resolve(), a.so)


if __name__ == "__main__":
    sys.exit(main())
