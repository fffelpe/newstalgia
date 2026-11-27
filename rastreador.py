import json
import os
import re
import time
import html
import argparse
import unicodedata

from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode, urlsplit, parse_qs, quote
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parent

PROGRAMAS = [
    "Cidade Alerta",
    "Brasil Urgente",
    "Repórter Cidadão"
]

YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")
BRAVE_API_KEY = os.getenv("BRAVE_API_KEY")


def normalizar(texto):
    return "".join(
        c for c in unicodedata.normalize(
            "NFKD", str(texto).lower()
        )
        if not unicodedata.combining(c)
    )


def limpar(texto):
    return re.sub(
        r"\s+", " ",
        html.unescape(
            re.sub(r"<[^>]*>", " ", str(texto or ""))
        )
    ).strip()


def consultar(url, parametros, headers=None):

    requisicao = Request(
        url + "?" + urlencode(parametros, doseq=True),
        headers={
            "User-Agent": "Newstalgia-Research/1.0",
            "Accept": "application/json",
            **(headers or {})
        }
    )

    with urlopen(requisicao, timeout=15) as resposta:
        return json.load(resposta)


def chave(url):

    partes = urlsplit(url)
    host = partes.hostname or ""
    caminho = partes.path

    if host == "youtu.be":
        codigo = caminho.strip("/").split("/")[0]

        if re.fullmatch(r"[A-Za-z0-9_-]{11}", codigo):
            return "youtube:" + codigo

    if host in ("youtube.com", "www.youtube.com", "m.youtube.com"):

        codigo = parse_qs(partes.query).get("v", [""])[0]

        if not codigo and caminho.startswith(
            ("/embed/", "/shorts/", "/live/")
        ):
            codigo = caminho.split("/")[2]

        if re.fullmatch(r"[A-Za-z0-9_-]{11}", codigo):
            return "youtube:" + codigo

    if host in ("archive.org", "www.archive.org"):

        if caminho.startswith(("/details/", "/embed/")):
            return "archive:" + caminho.split("/")[2]

    return (
        host + caminho.rstrip("/")
        + ("?" + partes.query if partes.query else "")
    )


def criar_registro(programa, titulo, descricao, url, fonte, **extras):

    titulo = limpar(titulo)
    descricao = limpar(descricao)

    anos = sorted(set(re.findall(
        r"(?<!\d)(?:199\d|200\d)(?!\d)",
        titulo + " " + descricao
    )))

    return {
        "id": chave(url),
        "programa": programa,
        "titulo": titulo,
        "descricao_fonte": descricao[:2500],
        "url": url,
        "fonte": fonte,
        "anos_mencionados": anos,
        "data_exibicao": None,
        "apresentador": None,
        "reporter": None,
        "local_reportagem": None,
        "duracao_segundos": None,
        "status": "Pendente de revisão",
        "descoberto_em": datetime.now(timezone.utc).isoformat(),
        **extras
    }


def buscar_archive(programa, pagina):

    dados = consultar(
        "https://archive.org/advancedsearch.php",
        {
            "q": (
                'mediatype:movies AND '
                f'(title:"{programa}" OR description:"{programa}")'
            ),
            "fl[]": [
                "identifier",
                "title",
                "description",
                "creator",
                "date",
                "licenseurl"
            ],
            "rows": 50,
            "page": pagina,
            "output": "json"
        }
    )

    resultados = []

    for item in dados.get("response", {}).get("docs", []):

        if not item.get("identifier"):
            continue

        resultados.append(criar_registro(
            programa,
            item.get("title"),
            item.get("description"),
            "https://archive.org/details/" +
                quote(item["identifier"], safe=""),
            "Internet Archive",
            criador=item.get("creator"),
            licenca_informada=item.get("licenseurl"),
            data_informada_pela_fonte=item.get("date")
        ))

    return resultados


def buscar_youtube(programa, ano):

    dados = consultar(
        "https://www.googleapis.com/youtube/v3/search",
        {
            "part": "snippet",
            "q": f'"{programa}" {ano}',
            "type": "video",
            "maxResults": 50,
            "relevanceLanguage": "pt",
            "key": YOUTUBE_API_KEY
        }
    )

    ids = [
        item["id"]["videoId"]
        for item in dados.get("items", [])
        if item.get("id", {}).get("videoId")
    ]

    if not ids:
        return []

    detalhes = consultar(
        "https://www.googleapis.com/youtube/v3/videos",
        {
            "part": "snippet,contentDetails,status",
            "id": ",".join(ids),
            "key": YOUTUBE_API_KEY
        }
    )

    resultados = []

    for item in detalhes.get("items", []):

        snippet = item["snippet"]

        duracao = item.get(
            "contentDetails", {}
        ).get("duration", "")

        segundos = None

        formato = re.fullmatch(
            r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?",
            duracao
        )

        if formato:
            segundos = sum(
                int(valor or 0) * fator
                for valor, fator in zip(
                    formato.groups(), [3600, 60, 1]
                )
            )

        resultados.append(criar_registro(
            programa,
            snippet["title"],
            snippet.get("description"),
            "https://www.youtube.com/watch?v=" + item["id"],
            "YouTube",
            canal=snippet.get("channelTitle"),
            data_upload=snippet.get("publishedAt"),
            duracao_segundos=segundos,
            miniatura=snippet.get(
                "thumbnails", {}
            ).get("high", {}).get("url"),
            incorporacao_permitida=item.get(
                "status", {}
            ).get("embeddable")
        ))

    return resultados


def buscar_web(programa, ano):

    dados = consultar(
        "https://api.search.brave.com/res/v1/web/search",
        {
            "q": (
                f'"{programa}" "{ano}" '
                "(vídeo OR reportagem OR arquivo OR edição)"
            ),
            "count": 20,
            "country": "BR",
            "search_lang": "pt"
        },
        {
            "X-Subscription-Token": BRAVE_API_KEY
        }
    )

    return [
        criar_registro(
            programa,
            item.get("title"),
            item.get("description"),
            item["url"],
            "Busca web",
            tipo="Página candidata"
        )
        for item in dados.get("web", {}).get("results", [])
        if urlsplit(item.get("url", "")).scheme
        in ("http", "https")
    ]


def ler(arquivo, padrao):

    if arquivo.exists():
        return json.loads(
            arquivo.read_text(encoding="utf-8")
        )

    return padrao


def salvar(arquivo, dados):

    temporario = arquivo.with_suffix(".tmp")

    temporario.write_text(
        json.dumps(dados, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )

    temporario.replace(arquivo)


def executar():

    parser = argparse.ArgumentParser()

    parser.add_argument("--inicio", type=int, default=1990)
    parser.add_argument("--fim", type=int, default=2009)
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--dry-run", action="store_true")

    args = parser.parse_args()

    if args.self_test:

        assert chave(
            "https://youtu.be/abcdefghijk?t=5"
        ) == chave(
            "https://www.youtube.com/watch?v=abcdefghijk"
        )

        assert chave(
            "https://archive.org/details/test"
        ) == "archive:test"

        print("Testes locais aprovados.")
        return

    if not 1990 <= args.inicio <= args.fim <= 2009:
        parser.error("Intervalo permitido: 1990 a 2009.")

    catalogo = ler(ROOT / "catalogo-player.json", [])

    if isinstance(catalogo, dict):
        catalogo = [
            dict(zip(catalogo["campos"], registro))
            for registro in catalogo["registros"]
        ]

    conhecidos = {
        chave(video["youtube_url"])
        for video in catalogo
        if video.get("youtube_url")
    }

    arquivo = ROOT / "descobertas.json"

    descobertas = {
        item["id"]: item
        for item in ler(arquivo, [])
    }

    erros = []
    novos = 0
    fontes_desativadas = set()
    tarefas = []

    for programa in PROGRAMAS:

        for pagina in range(1, 3):

            tarefas.append((
                "Internet Archive",
                programa,
                pagina,
                lambda p=programa, n=pagina: buscar_archive(p, n)
            ))

        for ano in range(args.inicio, args.fim + 1):

            if YOUTUBE_API_KEY:

                tarefas.append((
                    "YouTube",
                    programa,
                    ano,
                    lambda p=programa, a=ano: buscar_youtube(p, a)
                ))

            if BRAVE_API_KEY:

                tarefas.append((
                    "Web",
                    programa,
                    ano,
                    lambda p=programa, a=ano: buscar_web(p, a)
                ))

    print(f"Consultas planejadas: {len(tarefas)}")

    if args.dry_run:
        return

    for fonte, programa, referencia, pesquisa in tarefas:

        if fonte in fontes_desativadas:
            continue

        try:

            for item in pesquisa():

                identificador = item["id"]

                texto = normalizar(
                    item["titulo"] + " "
                    + item["descricao_fonte"]
                )

                if normalizar(programa) not in texto:
                    continue

                if identificador in conhecidos:
                    continue

                if identificador in descobertas:
                    continue

                descobertas[identificador] = item

                novos += 1

                print("Encontrado:", item["titulo"])

            salvar(arquivo, list(descobertas.values()))

        except Exception as erro:

            codigo = getattr(erro, "code", None)

            erros.append({
                "fonte": fonte,
                "programa": programa,
                "referencia": referencia,
                "erro": type(erro).__name__,
                "codigo": codigo
            })

            if codigo in (401, 403, 429):
                fontes_desativadas.add(fonte)

        time.sleep(0.5)

    salvar(arquivo, list(descobertas.values()))

    salvar(
        ROOT / "rastreamento-log.json",
        {
            "novos": novos,
            "total": len(descobertas),
            "erros": erros,
            "fontes_desativadas": sorted(fontes_desativadas)
        }
    )

    print(f"Novos materiais: {novos}")
    print(f"Total de descobertas: {len(descobertas)}")
    print(f"Falhas: {len(erros)}")


if __name__ == "__main__":
    executar()