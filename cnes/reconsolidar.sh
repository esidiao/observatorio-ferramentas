#!/bin/sh
# Reconsolida UM observatório sobre uma competência nova do CNES.
#
# Deliberadamente não chama `etl/pipeline.py` inteiro: ele reextrai Censo e CPC,
# que normalmente continuam na mesma edição, e isso custaria centenas de MB por
# repositório para reescrever arquivos idênticos. Quando o Censo ou o CPC também
# mudarem, use o pipeline do projeto, que é quem sabe fazer isso.
#
# Uso:
#   cnes/reconsolidar.sh ../observatorio-fonoaudiologia 202609
set -e

repo="$1"
competencia="$2"
if [ -z "$repo" ] || [ -z "$competencia" ]; then
  echo "uso: reconsolidar.sh <caminho-do-repo> <AAAAMM>" >&2
  exit 2
fi
cd "$repo"

echo "############################## $(basename "$repo") — CNES $competencia"
python etl/extrair_cnes.py --competencia "$competencia"
python etl/consolidar.py

echo "----- portões GO"
python etl/indices.py --autoteste
python site/estatistica.py
python site/catalogo.py

echo "----- conferência de riqueza (contra HEAD)"
python etl/pipeline.py --so-riqueza

echo "----- testes"
python tests/test_catalogo.py
python tests/test_validacao.py
python tests/test_check_fontes.py

# O registro autoral vem DEPOIS dos testes, ao contrário do pipeline do projeto.
# Motivo medido: a troca de competência faz os testes de âncora falharem (é o
# que eles existem para fazer), a correção mexe em prosa e constantes, e um
# registro gerado antes disso descreve criptograficamente uma árvore que deixou
# de existir. Se os testes acima falharem, nada é registrado — que é o certo.
echo "----- registro autoral"
python etl/registro_autoral.py

echo "----- site"
python site/build.py

# Nem todo repositório tem os mesmos testes pós-build: a auditoria de
# acessibilidade só existe onde a paleta foi trocada. Rodamos o que existe, em
# vez de listar nomes que falham por ausência em metade dos projetos.
for teste in tests/test_acessibilidade.py tests/test_links.py; do
  [ -f "$teste" ] && python "$teste"
done

echo "############################## $(basename "$repo") OK"
