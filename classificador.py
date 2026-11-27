
import re
import unicodedata

APRESENTADORES = {
    "Cidade Alerta": [
        "José Luiz Datena",
        "Marcelo Rezende",
        "Márcio Campos",
        "Milton Neves"
    ],
    "Brasil Urgente": [
        "Roberto Cabrini",
        "José Luiz Datena"
    ],
    "Repórter Cidadão": [
        "Marcelo Rezende",
        "José Luiz Datena"
    ]
}

CANAIS = [
    "Pedro Janov",
    "Arquivo Marckezini",
    "Fabio Marckezini",
    "Rodrigo Marckezini",
    "Memorial da Televisão Brasileira"
]

TIPOS = {
    "Edição completa": [
        "edicao completa",
        "programa completo",
        "integra"
    ],
    "Reportagem": [
        "reportagem",
        "materia",
        "cobertura"
    ],
    "Identidade visual": [
        "abertura",
        "vinheta",
        "encerramento",
        "chamada"
    ],
    "Registro histórico": [
        "estreia",
        "despedida",
        "vhs",
        "raridade",
        "arquivo"
    ]
}


def normalizar(valor):

    return "".join(
        c for c in unicodedata.normalize(
            "NFKD", str(valor or "").lower()
        )
        if not unicodedata.combining(c)
    )


def classificar(item):

    titulo = normalizar(item.get("titulo"))

    descricao = normalizar(
        item.get("descricao_fonte")
    )

    programa = item.get("programa", "")

    texto = titulo + " " + descricao

    canal = normalizar(
        item.get("canal") or item.get("criador")
    )

    pontos = 0
    apresentadores = []
    categorias = []

    anos = re.findall(
        r"(?<!\d)(?:19\d{2}|20\d{2})(?!\d)",
        titulo
    )

    anos_historicos = [
        ano for ano in anos
        if 1990 <= int(ano) <= 2009
    ]

    if normalizar(programa) in titulo:
        pontos += 25

    if anos_historicos:
        pontos += 25

    elif re.search(
        r"(?<!\d)(199\d|200\d)(?!\d)",
        descricao
    ):
        pontos += 10

    if any(
        not 1990 <= int(ano) <= 2009
        for ano in anos
    ):
        pontos -= 50

    for nome in APRESENTADORES.get(programa, []):

        if normalizar(nome) in texto:
            apresentadores.append(nome)

    if apresentadores:
        pontos += 10

    if any(
        normalizar(nome) in canal
        for nome in CANAIS
    ):
        pontos += 15

    for categoria, termos in TIPOS.items():

        if any(termo in texto for termo in termos):
            categorias.append(categoria)

    if "Edição completa" in categorias:
        pontos += 15

    if "Reportagem" in categorias:
        pontos += 10

    pontos = max(0, min(100, pontos))

    if pontos >= 80:
        prioridade = "Alta"

    elif pontos >= 50:
        prioridade = "Media"

    elif pontos >= 30:
        prioridade = "Baixa"

    else:
        prioridade = "Insuficiente"

    item["relevancia"] = pontos

    item["prioridade"] = prioridade

    item["apresentadores_mencionados"] = apresentadores

    item["categorias"] = categorias

    return item
