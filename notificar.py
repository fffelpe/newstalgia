
import os
import json
import re
import ssl
import smtplib

from pathlib import Path
from email.message import EmailMessage
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parent

DESCOBERTAS = ROOT / "descobertas.json"
HISTORICO = ROOT / "notificados.json"

EMAIL_REMETENTE = os.getenv("EMAIL_REMETENTE")
EMAIL_DESTINATARIO = os.getenv("EMAIL_DESTINATARIO")
EMAIL_SENHA = os.getenv("EMAIL_SENHA")


def carregar(arquivo):

    if not arquivo.exists():
        return []

    return json.loads(
        arquivo.read_text(encoding="utf-8")
    )


def identificar_ano(item):

    data = str(item.get("data_exibicao") or "")

    ano = re.match(r"^(199\d|200\d)", data)

    if ano:
        return ano.group(1)

    titulo = item.get("titulo") or ""
    descricao = item.get("descricao_fonte") or ""

    anos = re.findall(
        r"(?<!\d)(199\d|200\d)(?!\d)",
        titulo
    )

    if not anos:

        anos = re.findall(
            r"(?<!\d)(199\d|200\d)(?!\d)",
            descricao
        )

    anos = sorted(set(anos))

    return ", ".join(anos)


def executar():

    descobertas = carregar(DESCOBERTAS)

    notificados = set(carregar(HISTORICO))

    novos = []
    selecionados = set()

    for item in descobertas:

        identificador = item.get("id")
        url = item.get("url") or ""

        if not identificador:
            continue

        if identificador in notificados:
            continue

        if identificador in selecionados:
            continue

        if urlsplit(url).scheme not in ("http", "https"):
            continue

        ano = identificar_ano(item)

        if not ano:
            continue

        novos.append((item, ano))
        selecionados.add(identificador)

    if not novos:

        print("Nenhum novo material histórico para notificar.")
        return

    if not all([
        EMAIL_REMETENTE,
        EMAIL_DESTINATARIO,
        EMAIL_SENHA
    ]):

        raise RuntimeError(
            "Configure os Secrets de e-mail no GitHub."
        )

    linhas = [

        "NEWSTALGIA",
        "MONITORAMENTO DO ACERVO",
        "",
        f"Novos materiais encontrados: {len(novos)}",
        "",
        "Período histórico: 1990 a 2009",
        ""
    ]

    novos.sort(
        key=lambda registro: (
            registro[0].get("programa", ""),
            registro[1]
        )
    )

    for numero, (item, ano) in enumerate(novos, 1):

        linhas.extend([

            f"{numero}. {item.get('titulo')}",
            "",
            f"Programa: {item.get('programa')}",
            f"Ano: {ano} (a confirmar)",
            f"Fonte: {item.get('fonte')}",
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

    mensagem = EmailMessage()

    mensagem["Subject"] = (
        f"Newstalgia | {len(novos)} novos materiais históricos"
    )

    mensagem["From"] = EMAIL_REMETENTE
    mensagem["To"] = EMAIL_DESTINATARIO

    mensagem.set_content(
        "\n".join(linhas)
    )

    contexto = ssl.create_default_context()

    with smtplib.SMTP_SSL(
        "smtp.gmail.com",
        465,
        context=contexto,
        timeout=30
    ) as servidor:

        servidor.login(
            EMAIL_REMETENTE,
            EMAIL_SENHA
        )

        recusados = servidor.send_message(mensagem)

        if recusados:
            raise RuntimeError(
                "O servidor recusou destinatários."
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

    print(f"E-mail enviado com {len(novos)} materiais.")


if __name__ == "__main__":

    executar()
