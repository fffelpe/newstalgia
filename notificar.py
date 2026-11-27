
import os
import json
import re
import argparse

from pathlib import Path
from urllib.parse import urlencode, urlsplit, parse_qs
from urllib.request import Request, urlopen
from urllib.error import HTTPError

ROOT = Path(__file__).resolve().parent

DESCOBERTAS = ROOT / "descobertas.json"
HISTORICO = ROOT / "notificados.json"
CATALOGO = ROOT / "catalogo-player.json"

EMAIL_REMETENTE = os.getenv("EMAIL_REMETENTE", "").strip()
EMAIL_DESTINATARIO = os.getenv("EMAIL_DESTINATARIO", "").strip()

CLIENT_ID = os.getenv("MICROSOFT_CLIENT_ID", "").strip()
REFRESH_TOKEN = os.getenv("MICROSOFT_REFRESH_TOKEN", "").strip()


# CARREGAMENTO DOS ARQUIVOS

def carregar(arquivo):

    if not arquivo.exists():
        return []

    return json.loads(
        arquivo.read_text(encoding="utf-8")
    )


# IDENTIFICAÇÃO DE DUPLICATAS

def identificar_video(url):

    partes = urlsplit(url)
    host = partes.hostname or ""

    if host == "youtu.be":

        codigo = partes.path.strip("/").split("/")[0]

        if re.fullmatch(r"[A-Za-z0-9_-]{11}", codigo):
            return "youtube:" + codigo

    if host in (
        "youtube.com",
        "www.youtube.com",
        "m.youtube.com"
    ):

        codigo = parse_qs(
            partes.query
        ).get("v", [""])[0]

        if not codigo:
            match = re.search(
                r"/(?:embed|shorts|live)/([A-Za-z0-9_-]{11})",
                partes.path
            )

            if match:
                codigo = match.group(1)

        if re.fullmatch(r"[A-Za-z0-9_-]{11}", codigo):
            return "youtube:" + codigo

    if host in ("archive.org", "www.archive.org"):

        match = re.search(
            r"/(?:details|embed)/youtube-([A-Za-z0-9_-]{11})(?:/|$)",
            partes.path
        )

        if match:
            return "youtube:" + match.group(1)

        match = re.search(
            r"/(?:details|embed)/([^/]+)",
            partes.path
        )

        if match:
            return "archive:" + match.group(1)

    return host + partes.path.rstrip("/") + (
        "?" + partes.query if partes.query else ""
    )


def carregar_catalogo():

    dados = carregar(CATALOGO)

    if isinstance(dados, dict):

        return [
            dict(zip(dados["campos"], registro))
            for registro in dados["registros"]
        ]

    return dados


# IDENTIFICAÇÃO DO ANO HISTÓRICO

def identificar_ano(item):

    data = str(item.get("data_exibicao") or "")

    if data:

        match = re.match(r"^(199\d|200\d)(?!\d)", data)

        return match.group(1) if match else ""

    titulo = item.get("titulo") or ""
    descricao = item.get("descricao_fonte") or ""

    anos_titulo = re.findall(
        r"(?<!\d)(?:19\d{2}|20\d{2})(?!\d)",
        titulo
    )

    if anos_titulo:

        if any(
            not 1990 <= int(ano) <= 2009
            for ano in anos_titulo
        ):
            return ""

        return ", ".join(sorted(set(anos_titulo)))

    anos_descricao = re.findall(
        r"(?<!\d)(199\d|200\d)(?!\d)",
        descricao
    )

    return ", ".join(sorted(set(anos_descricao)))


# VALIDAÇÃO DAS CREDENCIAIS

def validar_configuracao():

    configuracoes = {
        "EMAIL_REMETENTE": EMAIL_REMETENTE,
        "EMAIL_DESTINATARIO": EMAIL_DESTINATARIO,
        "MICROSOFT_CLIENT_ID": CLIENT_ID,
        "MICROSOFT_REFRESH_TOKEN": REFRESH_TOKEN
    }

    faltando = [
        nome for nome, valor in configuracoes.items()
        if not valor
    ]

    if faltando:

        raise RuntimeError(
            "Secrets ausentes: " + ", ".join(faltando)
        )


# AUTENTICAÇÃO MICROSOFT

def obter_access_token():

    validar_configuracao()

    endereco = (
        "https://login.microsoftonline.com/"
        "consumers/oauth2/v2.0/token"
    )

    dados = urlencode({

        "client_id": CLIENT_ID,

        "grant_type": "refresh_token",

        "refresh_token": REFRESH_TOKEN,

        "scope": (
            "https://graph.microsoft.com/Mail.Send "
            "offline_access"
        )

    }).encode("utf-8")

    requisicao = Request(

        endereco,

        data=dados,

        headers={
            "Content-Type":
                "application/x-www-form-urlencoded"
        },

        method="POST"

    )

    try:

        with urlopen(requisicao, timeout=60) as resposta:

            resultado = json.load(resposta)

    except HTTPError as erro:

        try:

            codigo = json.loads(
                erro.read()
            ).get("error", "desconhecido")

        except Exception:

            codigo = "desconhecido"

        raise RuntimeError(
            f"Falha na autenticação Microsoft: "
            f"HTTP {erro.code} - {codigo}. "
            "Confira o CLIENT_ID e o REFRESH_TOKEN."
        ) from None

    if "access_token" not in resultado:

        raise RuntimeError(
            "A Microsoft não retornou o token de acesso."
        )

    print("Autenticação Microsoft realizada com sucesso.")

    return resultado["access_token"]


# ENVIO PELA MICROSOFT GRAPH

def enviar_email(assunto, corpo):

    token = obter_access_token()

    mensagem = {

        "message": {

            "subject": assunto,

            "body": {
                "contentType": "Text",
                "content": corpo
            },

            "from": {
                "emailAddress": {
                    "address": EMAIL_REMETENTE
                }
            },

            "toRecipients": [

                {
                    "emailAddress": {
                        "address": EMAIL_DESTINATARIO
                    }
                }

            ]

        },

        "saveToSentItems": True

    }

    requisicao = Request(

        "https://graph.microsoft.com/v1.0/me/sendMail",

        data=json.dumps(
            mensagem,
            ensure_ascii=False
        ).encode("utf-8"),

        headers={

            "Authorization": "Bearer " + token,

            "Content-Type": "application/json"

        },

        method="POST"

    )

    try:

        with urlopen(requisicao, timeout=60) as resposta:

            if resposta.status != 202:

                raise RuntimeError(
                    f"Resposta inesperada: {resposta.status}"
                )

    except HTTPError as erro:

        raise RuntimeError(
            f"Falha no envio Microsoft Graph: HTTP {erro.code}"
        ) from None

    print("Email aceito pela Microsoft Graph.")


# EMAIL DE TESTE

def testar_email():

    enviar_email(

        "Newstalgia | Teste de notificações",

        (
            "NEWSTALGIA - TESTE DE CONEXÃO\n\n"
            "A solicitação de envio pelo Outlook foi realizada.\n\n"
            "Rastreador de materiais históricos\n"
            "Cidade Alerta, Brasil Urgente e Repórter Cidadão\n\n"
            "As notícias passam. A história permanece."
        )

    )


# RASTREAMENTO E NOTIFICAÇÕES

def executar():

    descobertas = carregar(DESCOBERTAS)

    notificados = set(carregar(HISTORICO))

    catalogo = carregar_catalogo()

    conhecidos = set()

    for video in catalogo:

        for campo in (
            "youtube_url",
            "archive_url",
            "video_url",
            "url"
        ):

            if video.get(campo):

                conhecidos.add(
                    identificar_video(video[campo])
                )

    novos = []
    selecionados = set()
    chaves_selecionadas = set()

    for item in descobertas:

        identificador = item.get("id")

        url = item.get("url") or ""

        if not identificador:
            continue

        if urlsplit(url).scheme not in ("http", "https"):
            continue

        chave = identificar_video(url)

        if identificador in notificados:
            continue

        if chave in notificados:
            continue

        if chave in conhecidos:
            continue

        if chave in chaves_selecionadas:
            continue

        ano = identificar_ano(item)

        if not ano:
            continue

        novos.append((item, ano))

        selecionados.add(identificador)
        selecionados.add(chave)

        chaves_selecionadas.add(chave)

    if not novos:

        print("Nenhum novo material histórico encontrado.")
        return

    novos.sort(
        key=lambda registro: (
            registro[0].get("programa", ""),
            registro[1]
        )
    )

    linhas = [

        "NEWSTALGIA",
        "MONITORAMENTO DO ACERVO",
        "",
        f"Novos materiais encontrados: {len(novos)}",
        "",
        "Período: 1990 a 2009",
        ""

    ]

    for numero, (item, ano) in enumerate(novos, 1):

        linhas.extend([

            f"{numero}. {item.get('titulo')}",
            "",
            f"Programa: {item.get('programa')}",
            f"Ano: {ano} (a confirmar)",
            f"Fonte: {item.get('fonte')}",
            "",
            f"Link: {item.get('url')}",
            "",
            "----------------------------------------",
            ""

        ])

    linhas.extend([

        "Materiais pendentes de revisão histórica.",
        "",
        "Newstalgia",
        "As notícias passam. A história permanece."

    ])

    assunto = (
        f"Newstalgia | {len(novos)} novos materiais históricos"
    )

    enviar_email(
        assunto,
        "\n".join(linhas)
    )

    notificados.update(selecionados)

    temporario = HISTORICO.with_suffix(".tmp")

    temporario.write_text(

        json.dumps(
            sorted(notificados),
            ensure_ascii=False,
            indent=2
        ),

        encoding="utf-8"

    )

    temporario.replace(HISTORICO)

    print(f"Notificação enviada com {len(novos)} materiais.")


if __name__ == "__main__":

    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--teste",
        action="store_true"
    )

    args = parser.parse_args()

    if args.teste:

        testar_email()

    else:

        executar()