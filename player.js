
(() => {

    "use strict";

    const root = document.querySelector("[data-player]");

    if (!root) return;

    const video = root.querySelector("video");
    const stage = root.querySelector(".stage");
    const seek = root.querySelector(".seek");
    const volume = root.querySelector(".volume");
    const clock = root.querySelector(".clock");
    const status = root.querySelector(".status");
    const controls = root.querySelector(".controls");

    const buttons = root.querySelectorAll(
        ".controls button[data-action]"
    );

    const isYouTube = Boolean(root.dataset.youtube);

    let youtubePlayer = null;
    let pronto = false;
    let arrastando = false;
    let estado = "conectando";
    let ultimoKBs = null;
    let ultimaTransferencia = 0;

    /* =====================================
       TÍTULO DA JANELA
       ===================================== */

    const titlebar = root.querySelector(".titlebar");

    const ficha = document.querySelector(".details");

    function lerCampo(nome) {

        if (!ficha) return "";

        const campos = ficha.querySelectorAll("dt");

        for (const campo of campos) {

            if (campo.textContent.trim().startsWith(nome)) {

                return campo.nextElementSibling
                    ?.textContent.trim() || "";

            }
        }

        return "";

    }

    function formatarData(data) {

        if (/^\d{4}-\d{2}-\d{2}$/.test(data)) {

            return data.split("-").reverse().join("/");

        }

        if (/^\d{4}-\d{2}$/.test(data)) {

            return data.split("-").reverse().join("/");

        }

        return data || "Data não identificada";

    }

    if (titlebar) {

        const programa =
            lerCampo("Programa") || "Newstalgia";

        const data = formatarData(
            lerCampo("Data de exibição")
        );

        const icone = document.createElement("img");

        icone.src = "../favicon.svg";
        icone.alt = "Newstalgia";
        icone.className = "nt-window-icon";

        const titulo = document.createElement("span");

        titulo.className = "nt-window-title";

        titulo.textContent = programa + " - " + data;

        titlebar.replaceChildren(icone, titulo);

    }

    /* =====================================
       TELA DE ABERTURA
       ===================================== */

    const splash = document.createElement("div");

    splash.className = "nt-splash";

    splash.innerHTML = `

        <img
            src="../favicon.svg"
            class="nt-splash-logo"
            alt="Newstalgia">

        <div class="nt-splash-brand">
            NEWSTALGIA
        </div>

        <div class="nt-splash-version">
            PLAYER 1.0
        </div>

        <div class="nt-splash-line"></div>

        <div class="nt-connection nt-connecting">

            <span class="nt-led"></span>
            <span class="nt-led"></span>
            <span class="nt-led"></span>

            <span class="nt-connection-text">
                Conectando...
            </span>

        </div>

        <div class="nt-splash-slogan">
            As notícias passam. A história permanece.
        </div>

    `;

    /*
       Em vídeos do YouTube, a abertura fica
       antes do carregamento do iframe.
       Não encobre os controles do YouTube.
    */

    stage.appendChild(splash);

    const splashInicio = performance.now();

    function ocultarSplash() {

        const restante = Math.max(
            0,
            800 - (performance.now() - splashInicio)
        );

        setTimeout(() => {
            splash.hidden = true;
        }, restante);

    }

    /* =====================================
       BUFFER
       ===================================== */

    const bufferPanel = document.createElement("div");

    bufferPanel.className = "buffer-panel";

    bufferPanel.innerHTML = `

        <span>BUFFER</span>

        <div class="buffer-track"
            role="progressbar"
            aria-label="Vídeo armazenado em buffer"
            aria-valuemin="0"
            aria-valuemax="100"
            aria-valuenow="0">

            <div class="buffer-fill"></div>

        </div>

        <span class="buffer-percent">0%</span>

    `;

    controls.prepend(bufferPanel);

    const bufferTrack =
        bufferPanel.querySelector(".buffer-track");

    const bufferFill =
        bufferPanel.querySelector(".buffer-fill");

    const bufferPercent =
        bufferPanel.querySelector(".buffer-percent");

    /* =====================================
       PAINEL TÉCNICO
       ===================================== */

    const telemetry = document.createElement("div");

    telemetry.className = "nt-telemetry";

    telemetry.innerHTML = `

        <div class="nt-connection nt-connecting"
            id="nt-network">

            <span class="nt-led"></span>
            <span class="nt-led"></span>
            <span class="nt-led"></span>

        </div>

        <div class="nt-quality-display">

            <span>QUALIDADE:</span>

            <span class="nt-quality"
                data-quality="240">240p</span>

            <span class="nt-quality"
                data-quality="360">360p</span>

            <span class="nt-quality"
                data-quality="480">480p</span>

            <span class="nt-resolution">AUTO</span>

        </div>

        <div>

            TRANSFERÊNCIA:

            <span class="nt-transfer-value">
                -- KB/s
            </span>

        </div>

    `;

    bufferPanel.after(telemetry);

    const network =
        telemetry.querySelector("#nt-network");

    const resolution =
        telemetry.querySelector(".nt-resolution");

    const transfer =
        telemetry.querySelector(".nt-transfer-value");

    /* =====================================
       ASSINATURA
       ===================================== */

    const assinatura = document.createElement("div");

    assinatura.className = "player-signature";

    assinatura.innerHTML = `

        <span>NEWSTALGIA PLAYER 1.0</span>

        <span>DIGITAL MEDIA ARCHIVE</span>

    `;

    root.appendChild(assinatura);

    /* =====================================
       CONTROLE DE ESTADO
       ===================================== */

    function mudarEstado(novo, mensagem) {

        estado = novo;

        status.textContent = mensagem;

        network.classList.toggle(
            "nt-connecting",
            novo === "conectando" ||
            novo === "buffering"
        );

        network.classList.toggle(
            "nt-connected",
            novo === "pronto" ||
            novo === "reproduzindo"
        );

    }

    function habilitar(ativo) {

        buttons.forEach(button => {
            button.disabled = !ativo;
        });

        seek.disabled = !ativo;
        volume.disabled = !ativo;

    }

    habilitar(false);

    mudarEstado(
        "conectando",
        "Estabelecendo conexão com a fonte..."
    );

    /* =====================================
       RELÓGIO DIGITAL
       ===================================== */

    function formatarTempo(segundos) {

        segundos = Number.isFinite(segundos)
            ? Math.max(0, Math.floor(segundos))
            : 0;

        const horas = Math.floor(segundos / 3600);

        const minutos =
            Math.floor(segundos % 3600 / 60);

        const restante = segundos % 60;

        return [horas, minutos, restante]

            .map(n => String(n).padStart(2, "0"))

            .join(":");

    }

    function duracao() {

        if (isYouTube) {

            return pronto
                ? youtubePlayer.getDuration()
                : 0;

        }

        return video.duration || 0;

    }

    function tempoAtual() {

        if (isYouTube) {

            return pronto
                ? youtubePlayer.getCurrentTime()
                : 0;

        }

        return video.currentTime || 0;

    }

    function atualizarBarra() {

        const total = duracao();
        const atual = tempoAtual();

        if (Number.isFinite(total) && total > 0) {

            if (!arrastando) {

                seek.value = atual / total * 1000;

            }

            clock.textContent =

                formatarTempo(atual) + " / " +

                formatarTempo(total);

        }

    }

    /* =====================================
       ATUALIZAÇÃO DO BUFFER
       ===================================== */

    function atualizarBuffer() {

        if (!pronto) return;

        let fracao = 0;

        if (isYouTube && youtubePlayer) {

            fracao =
                youtubePlayer.getVideoLoadedFraction();

        } else if (

            Number.isFinite(video.duration) &&
            video.duration > 0

        ) {

            let carregado = 0;

            for (
                let i = 0;
                i < video.buffered.length;
                i++
            ) {

                carregado +=

                    video.buffered.end(i) -
                    video.buffered.start(i);

            }

            fracao = carregado / video.duration;

        }

        const percentual = Math.max(

            0,

            Math.min(
                100,
                Math.floor((fracao || 0) * 100)
            )

        );

        bufferFill.style.width = percentual + "%";

        bufferPercent.textContent = percentual + "%";

        bufferTrack.setAttribute(
            "aria-valuenow",
            percentual
        );

    }

    /* =====================================
       INDICADOR DE QUALIDADE
       ===================================== */

    function atualizarQualidade() {

        if (!pronto) return;

        let altura = 0;

        if (isYouTube) {

            try {

                const qualidade =
                    youtubePlayer.getPlaybackQuality?.();

                const resolucoes = {

                    tiny: 144,
                    small: 240,
                    medium: 360,
                    large: 480,
                    hd720: 720,
                    hd1080: 1080,
                    hd1440: 1440,
                    hd2160: 2160

                };

                altura = resolucoes[qualidade] || 0;

            } catch {

                altura = 0;

            }

        } else {

            altura = video.videoHeight || 0;

        }

        telemetry.querySelectorAll(
            "[data-quality]"
        ).forEach(item => {

            item.classList.toggle(

                "active",

                Number(item.dataset.quality) === altura

            );

        });

        resolution.textContent =
            altura ? altura + "p" : "AUTO";

    }

    /* =====================================
       TRANSFERÊNCIA EM KB/s

       Mede respostas de mídia diretas
       quando o navegador fornece bytes.
       Não utiliza valores aleatórios.
       ===================================== */

    if (
        !isYouTube &&
        root.dataset.video &&
        "PerformanceObserver" in window
    ) {

        const fonte = new URL(
            root.dataset.video,
            location.href
        );

        try {

            const observador =
                new PerformanceObserver(lista => {

                    for (const recurso of lista.getEntries()) {

                        if (recurso.name !== fonte.href) {
                            continue;
                        }

                        const bytes =
                            recurso.encodedBodySize;

                        const segundos = (

                            recurso.responseEnd -
                            recurso.responseStart

                        ) / 1000;

                        if (bytes > 0 && segundos > 0) {

                            ultimoKBs =
                                bytes / 1024 / segundos;

                            ultimaTransferencia =
                                performance.now();

                        }

                    }

                });

            observador.observe({

                type: "resource",

                buffered: true

            });

        } catch (erro) {

            console.warn(
                "Medição de transferência indisponível.",
                erro
            );

        }

    }

    function atualizarTransferencia() {

        if (
            ultimoKBs !== null &&
            performance.now() - ultimaTransferencia < 5000
        ) {

            transfer.textContent =
                ultimoKBs.toFixed(1) + " KB/s";

        } else {

            transfer.textContent = "-- KB/s";

        }

    }

    /* =====================================
       REPRODUÇÃO
       ===================================== */

    function comando(acao) {

        if (!pronto) return;

        if (isYouTube) {

            if (acao === "play") {

                youtubePlayer.playVideo();

            }

            if (acao === "pause") {

                youtubePlayer.pauseVideo();

            }

            if (acao === "stop") {

                youtubePlayer.pauseVideo();

                youtubePlayer.seekTo(0, true);

                mudarEstado("parado", "Parado");

            }

        } else {

            if (acao === "play") {

                video.play().catch(() => {

                    mudarEstado(
                        "erro",
                        "Não foi possível reproduzir."
                    );

                });

            }

            if (acao === "pause") {

                video.pause();

            }

            if (acao === "stop") {

                video.pause();

                video.currentTime = 0;

                mudarEstado("parado", "Parado");

            }

        }

    }

    buttons.forEach(button => {

        button.addEventListener("click", () => {

            comando(button.dataset.action);

        });

    });

    /* =====================================
       POSIÇÃO DO VÍDEO
       ===================================== */

    seek.addEventListener("pointerdown", () => {

        arrastando = true;

    });

    window.addEventListener("pointerup", () => {

        arrastando = false;

    });

    window.addEventListener("pointercancel", () => {

        arrastando = false;

    });

    seek.addEventListener("input", () => {

        const total = duracao();

        if (
            !pronto ||
            !Number.isFinite(total) ||
            total <= 0
        ) return;

        const novoTempo =
            Number(seek.value) / 1000 * total;

        if (isYouTube) {

            youtubePlayer.seekTo(novoTempo, true);

        } else {

            video.currentTime = novoTempo;

        }

    });

    /* =====================================
       VOLUME
       ===================================== */

    volume.addEventListener("input", () => {

        if (isYouTube && pronto) {

            youtubePlayer.setVolume(
                Number(volume.value)
            );

        } else {

            video.volume =
                Number(volume.value) / 100;

        }

    });

    /* =====================================
       YOUTUBE
       ===================================== */

    if (isYouTube) {

        video.hidden = true;

        window.onYouTubeIframeAPIReady = () => {

            const restante = Math.max(
                0,
                800 - (performance.now() - splashInicio)
            );

            setTimeout(() => {

                splash.hidden = true;

                const elemento =
                    document.createElement("div");

                elemento.id = "yt";

                stage.appendChild(elemento);

                youtubePlayer = new YT.Player("yt", {

                    videoId: root.dataset.youtube,

                    playerVars: {

                        playsinline: 1,

                        controls: 1,

                        rel: 0,

                        origin: location.origin

                    },

                    events: {

                        onReady: evento => {

                            youtubePlayer = evento.target;

                            pronto = true;

                            habilitar(true);

                            youtubePlayer.setVolume(
                                Number(volume.value)
                            );

                            mudarEstado(
                                "pronto",
                                "Conexão estabelecida. Pronto."
                            );

                        },

                        onStateChange: evento => {

                            switch (evento.data) {

                                case 1:

                                    mudarEstado(
                                        "reproduzindo",
                                        "Reproduzindo..."
                                    );

                                    break;

                                case 2:

                                    mudarEstado(
                                        "pausado",
                                        "Pausado"
                                    );

                                    break;

                                case 3:

                                    mudarEstado(
                                        "buffering",
                                        "Armazenando em buffer..."
                                    );

                                    break;

                                case 0:

                                    mudarEstado(
                                        "parado",
                                        "Reprodução concluída."
                                    );

                                    break;

                                default:

                                    mudarEstado(
                                        "pronto",
                                        "Pronto"
                                    );

                            }

                        },

                        onError: () => {

                            pronto = false;

                            habilitar(false);

                            mudarEstado(
                                "erro",
                                "Vídeo indisponível. Consulte a fonte."
                            );

                        }

                    }

                });

            }, restante);

        };

        const script = document.createElement("script");

        script.src =
            "https://www.youtube.com/iframe_api";

        script.onerror = () => {

            ocultarSplash();

            mudarEstado(
                "erro",
                "Falha na conexão com o YouTube."
            );

        };

        document.head.appendChild(script);

    }

    /* =====================================
       ARQUIVOS MP4
       ===================================== */

    else if (root.dataset.video) {

        video.hidden = false;

        video.volume =
            Number(volume.value) / 100;

        video.addEventListener("loadedmetadata", () => {

            pronto = true;

            habilitar(true);

            atualizarQualidade();

            ocultarSplash();

            mudarEstado(
                "pronto",
                "Arquivo localizado. Pronto."
            );

        });

        video.addEventListener("waiting", () => {

            mudarEstado(
                "buffering",
                "Armazenando em buffer..."
            );

        });

        video.addEventListener("playing", () => {

            mudarEstado(
                "reproduzindo",
                "Reproduzindo..."
            );

        });

        video.addEventListener("pause", () => {

            mudarEstado(
                video.currentTime === 0
                    ? "parado"
                    : "pausado",

                video.currentTime === 0
                    ? "Parado"
                    : "Pausado"
            );

        });

        video.addEventListener("ended", () => {

            mudarEstado(
                "parado",
                "Reprodução concluída."
            );

        });

        video.addEventListener("error", () => {

            pronto = false;

            habilitar(false);

            ocultarSplash();

            mudarEstado(
                "erro",
                "Arquivo de vídeo indisponível."
            );

        });

        video.src = root.dataset.video;

    }

    /* =====================================
       FONTE NÃO DISPONÍVEL
       ===================================== */

    else {

        ocultarSplash();

        mudarEstado(
            "erro",
            "Consulte o arquivo original no acervo."
        );

    }

    /* =====================================
       LIMITE DE CONEXÃO
       ===================================== */

    setTimeout(() => {

        if (!pronto && estado === "conectando") {

            ocultarSplash();

            mudarEstado(
                "erro",
                "Tempo de conexão excedido."
            );

        }

    }, 20000);

    /* =====================================
       ATUALIZAÇÃO DOS INDICADORES
       ===================================== */

    setInterval(() => {

        atualizarBarra();

        atualizarBuffer();

        atualizarQualidade();

        atualizarTransferencia();

    }, 500);

})();
