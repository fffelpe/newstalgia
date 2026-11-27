
(() => {

    const root = document.querySelector("[data-player]");

    if (!root) return;

    const video = root.querySelector("video");
    const stage = root.querySelector(".stage");
    const seek = root.querySelector(".seek");
    const volume = root.querySelector(".volume");
    const clock = root.querySelector(".clock");
    const status = root.querySelector(".status");
    const buttons = root.querySelectorAll("button");

    let youtubePlayer = null;
    let pronto = false;

    const isYouTube = Boolean(root.dataset.youtube);

    function habilitar(estado) {
        buttons.forEach(button => {
            button.disabled = !estado;
        });

        seek.disabled = !estado;
        volume.disabled = !estado;
    }

    habilitar(false);

    function formatarTempo(segundos) {
        segundos = Math.max(0, Math.floor(segundos || 0));

        const horas = Math.floor(segundos / 3600);
        const minutos = Math.floor(segundos % 3600 / 60);
        const restante = segundos % 60;

        return [horas, minutos, restante]
            .map(n => String(n).padStart(2, "0"))
            .join(":");
    }

    function duracao() {
        if (isYouTube) {
            return pronto ? youtubePlayer.getDuration() : 0;
        }

        return video.duration || 0;
    }

    function tempoAtual() {
        if (isYouTube) {
            return pronto ? youtubePlayer.getCurrentTime() : 0;
        }

        return video.currentTime;
    }

    function atualizarBarra() {
        const total = duracao();
        const atual = tempoAtual();

        if (Number.isFinite(total) && total > 0) {
            seek.value = atual / total * 1000;

            clock.textContent =
                formatarTempo(atual) + " / " +
                formatarTempo(total);
        }
    }

    function comando(acao) {

        if (isYouTube && pronto) {

            if (acao === "play") {
                youtubePlayer.playVideo();
            }

            if (acao === "pause") {
                youtubePlayer.pauseVideo();
            }

            if (acao === "stop") {
                youtubePlayer.pauseVideo();
                youtubePlayer.seekTo(0, true);
            }

        } else if (video.getAttribute("src")) {

            if (acao === "play") {
                video.play().catch(() => {
                    status.textContent =
                        "Não foi possível reproduzir o vídeo.";
                });
            }

            if (acao === "pause") {
                video.pause();
            }

            if (acao === "stop") {
                video.pause();
                video.currentTime = 0;
            }
        }
    }

    buttons.forEach(button => {
        button.addEventListener("click", () => {
            comando(button.dataset.action);
        });
    });

    seek.addEventListener("input", () => {

        const total = duracao();

        if (!Number.isFinite(total) || total <= 0) return;

        const novoTempo = Number(seek.value) / 1000 * total;

        if (isYouTube && pronto) {
            youtubePlayer.seekTo(novoTempo, true);
        } else if (video.getAttribute("src")) {
            video.currentTime = novoTempo;
        }
    });

    volume.addEventListener("input", () => {

        if (isYouTube && pronto) {
            youtubePlayer.setVolume(Number(volume.value));
        } else {
            video.volume = Number(volume.value) / 100;
        }
    });

    if (isYouTube) {

        video.hidden = true;

        const elemento = document.createElement("div");
        elemento.id = "yt";

        stage.appendChild(elemento);

        window.onYouTubeIframeAPIReady = () => {

            youtubePlayer = new YT.Player("yt", {

                videoId: root.dataset.youtube,

                playerVars: {
                    playsinline: 1,
                    origin: location.origin
                },

                events: {

                    onReady: () => {
                        pronto = true;
                        habilitar(true);

                        youtubePlayer.setVolume(
                            Number(volume.value)
                        );

                        status.textContent =
                            "Pronto para reprodução";
                    },

                    onError: () => {
                        habilitar(false);

                        status.textContent =
                            "Incorporação indisponível. Consulte a fonte original.";
                    }
                }
            });
        };

        const script = document.createElement("script");

        script.src = "https://www.youtube.com/iframe_api";

        script.onerror = () => {
            status.textContent =
                "Não foi possível carregar o YouTube.";
        };

        document.head.appendChild(script);

    } else if (root.dataset.video) {

        video.src = root.dataset.video;
        video.hidden = false;
        video.volume = Number(volume.value) / 100;

        video.addEventListener("loadedmetadata", () => {
            habilitar(true);
            status.textContent = "Pronto para reprodução";
        });

        video.addEventListener("error", () => {
            habilitar(false);
            status.textContent = "Arquivo indisponível.";
        });

    } else {

        video.hidden = true;

        status.textContent =
            "Consulte o arquivo original no acervo.";
    }

    setInterval(atualizarBarra, 400);

})();