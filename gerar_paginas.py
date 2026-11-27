
import json
import re
import os
import html

from pathlib import Path
from urllib.parse import urlsplit, parse_qs

ROOT = Path(__file__).resolve().parent

dados = json.loads(
    (ROOT / "catalogo-player.json").read_text(encoding="utf-8")
)

if isinstance(dados, list):
    catalogo = dados
else:
    catalogo = [
        dict(zip(dados["campos"], registro))
        for registro in dados["registros"]
    ]

PASTA_VIDEOS = ROOT / "assistir"
PASTA_METADADOS = ROOT / "metadados"

PASTA_VIDEOS.mkdir(exist_ok=True)
PASTA_METADADOS.mkdir(exist_ok=True)


def texto(valor):
    if isinstance(valor, list):
        return "; ".join(map(str, valor)) or "A identificar"

    return str(valor) if valor is not None and valor != "" else "A identificar"


def escapar(valor):
    return html.escape(texto(valor), quote=True)


def url_segura(url):
    if isinstance(url, str):
        if urlsplit(url).scheme in ("https", "http"):
            return url

    return ""


def youtube_id(url):
    if not url:
        return ""

    codigo = parse_qs(urlsplit(url).query).get("v", [""])[0]

    if re.fullmatch(r"[A-Za-z0-9_-]{11}", codigo):
        return codigo

    return ""


paginas = []
itens = []

for video in catalogo:

    identificador = video["drive_id"]
    titulo = video["titulo"]
    programa = video["programa"]
    emissora = video["emissora"]

    youtube = url_segura(video.get("youtube_url"))
    codigo_youtube = youtube_id(youtube)
    video_direto = url_segura(video.get("video_url"))

    drive = (
        "https://drive.google.com/file/d/"
        + identificador
        + "/view"
    )

    campos = {
        "Título": titulo,
        "Programa": programa,
        "Emissora": emissora,
        "Apresentador (a confirmar)": video.get("apresentadores"),
        "Repórter": video.get("reporter"),
        "Data de exibição (preliminar)": video.get("data_exibicao"),
        "Local da reportagem": video.get("local_reportagem"),
        "Duração em segundos": video.get("duracao_segundos"),
        "Matérias": video.get("materias_identificadas"),
        "Canal de origem": video.get("canal_origem")
    }

    descricao = (
        f"{titulo}. Acervo histórico de {programa}, "
        f"{emissora}. Data: {texto(video.get('data_exibicao'))}."
    )

    ficha = "\n".join(
        f"{campo}: {texto(valor)}"
        for campo, valor in campos.items()
    )

    ficha += (
        f"\nFonte original: {youtube or 'A identificar'}"
        f"\nArquivo no Drive: {drive}"
        "\nStatus: Metadados preliminares"
    )

    (PASTA_METADADOS / f"{identificador}.txt").write_text(
        ficha,
        encoding="utf-8"
    )

    detalhes = "".join(
        f"<dt>{escapar(campo)}</dt>"
        f"<dd>{escapar(valor)}</dd>"
        for campo, valor in campos.items()
    )

    fontes = f'<a href="{escapar(drive)}">Arquivo no Drive</a>'

    if youtube:
        fontes += (
            f' | <a href="{escapar(youtube)}">'
            "Fonte original no YouTube</a>"
        )

    schema = ""

    if (
        video.get("upload_date")
        and video.get("thumbnail_url")
        and (codigo_youtube or video_direto)
    ):

        objeto = {
            "@context": "https://schema.org",
            "@type": "VideoObject",
            "name": titulo,
            "description": descricao,
            "thumbnailUrl": video["thumbnail_url"],
            "uploadDate": video["upload_date"]
        }

        if codigo_youtube:
            objeto["embedUrl"] = (
                "https://www.youtube.com/embed/"
                + codigo_youtube
            )

        if video_direto:
            objeto["contentUrl"] = video_direto

        if video.get("duracao_segundos"):
            objeto["duration"] = (
                "PT" + str(round(video["duracao_segundos"])) + "S"
            )

        schema = (
            '<script type="application/ld+json">'
            + json.dumps(objeto, ensure_ascii=False)
                .replace("<", "\\u003c")
            + "</script>"
        )

    pagina = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="description" content="{escapar(descricao)}">
<title>{escapar(titulo)} | Newstalgia</title>
<link rel="stylesheet" href="../player.css">
{schema}
</head>

<body>
<main>

<div class="brand">Newstalgia</div>

<p class="tag">
As notícias passam. A história permanece.
</p>

<p>
<a href="../index.html">Início</a> |
<a href="../acervo.html">Voltar ao acervo</a>
</p>

<section class="window"
    data-player
    data-youtube="{html.escape(codigo_youtube, quote=True)}"
    data-video="{html.escape(video_direto, quote=True)}">

    <div class="titlebar">
        Newstalgia Media Player
    </div>

    <div class="menu">
        Reprodução | Biblioteca de mídia
    </div>

    <div class="stage">
        <video playsinline preload="metadata" hidden></video>
        <span>Arquivo histórico</span>
    </div>

    <div class="controls">

        <input type="range" class="seek"
            min="0" max="1000" value="0"
            aria-label="Posição do vídeo" disabled>

        <button data-action="play"
            aria-label="Reproduzir" disabled>▶</button>

        <button data-action="pause"
            aria-label="Pausar" disabled>Ⅱ</button>

        <button data-action="stop"
            aria-label="Parar" disabled>■</button>

        <label>
            Volume
            <input class="volume" type="range"
                min="0" max="100" value="70" disabled>
        </label>

        <span class="clock">00:00:00 / --:--:--</span>

    </div>

    <div class="status" role="status">
        Carregando fonte...
    </div>

</section>

<article class="details">

    <h1>{escapar(titulo)}</h1>

    <p>{escapar(descricao)}</p>

    <dl>{detalhes}</dl>

    <p>{fontes}</p>

    <p class="muted">
        Ficha histórica preliminar, sujeita a revisão.
    </p>

</article>

</main>

<script src="../player.js"></script>

</body>
</html>
"""

    arquivo = PASTA_VIDEOS / f"{identificador}.html"

    arquivo.write_text(pagina, encoding="utf-8")

    if not video.get("duplicata_provavel_de"):
        paginas.append(f"assistir/{identificador}.html")

        pesquisa = escapar(" ".join(
            texto(valor) for valor in campos.values()
        ))

        itens.append(
            f'<li data-programa="{escapar(programa)}" '
            f'data-search="{pesquisa}">'
            f'<a href="assistir/{identificador}.html">'
            f'{escapar(titulo)}</a>'
            f'<p class="muted">{escapar(programa)} | '
            f'{escapar(video.get("data_exibicao"))}</p></li>'
        )

indice = """<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Acervo | Newstalgia</title>
<meta name="description" content="Acervo histórico do jornalismo televisivo brasileiro.">
<link rel="stylesheet" href="player.css">
</head>
<body>
<main>
<div class="brand">Newstalgia</div>
<p class="tag">As notícias passam. A história permanece.</p>
<nav class="menu"><a href="index.html">Início</a></nav>
<h1>Acervo de vídeos</h1>

<input type="search" id="busca" placeholder="Pesquisar no acervo">

<select id="programa">
<option value="">Todos os programas</option>
<option>Cidade Alerta</option>
<option>Brasil Urgente</option>
<option>Repórter Cidadão</option>
</select>

<p id="contador" aria-live="polite"></p>
<ul class="results">
""" + "\n".join(itens) + """
</ul>
</main>

<script>
const busca = document.querySelector("#busca");
const programa = document.querySelector("#programa");
const itens = [...document.querySelectorAll(".results li")];

const normalizar = texto => texto.normalize("NFD")
    .replace(/[\\u0300-\\u036f]/g, "").toLowerCase();

function pesquisar() {
    let total = 0;

    for (const item of itens) {
        const texto = normalizar(
            item.textContent + " " + item.dataset.search
        );

        item.hidden = !(
            texto.includes(normalizar(busca.value)) &&
            (!programa.value ||
                programa.value === item.dataset.programa)
        );

        if (!item.hidden) total++;
    }

    document.querySelector("#contador").textContent =
        total + " vídeos encontrados";
}

busca.oninput = pesquisar;
programa.onchange = pesquisar;
pesquisar();
</script>
</body>
</html>
"""

(ROOT / "acervo.html").write_text(indice, encoding="utf-8")

site_url = os.getenv("SITE_URL", "").rstrip("/")

if site_url.startswith("https://"):

    sitemap = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
    ]

    for pagina in ["index.html", "acervo.html"] + paginas:

        endereco = html.escape(
            site_url + "/" + pagina
        )

        sitemap.append(
            f"<url><loc>{endereco}</loc></url>"
        )

    sitemap.append("</urlset>")

    (ROOT / "sitemap.xml").write_text(
        "\n".join(sitemap),
        encoding="utf-8"
    )

print(f"{len(catalogo)} páginas geradas.")
print(f"{len(paginas)} registros no índice.")