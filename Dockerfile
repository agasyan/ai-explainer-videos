# syntax=docker/dockerfile:1
# One image with every tool the pipeline needs. The repo is mounted at /work, not copied.

# Stage 1: build whisper.cpp (speech to text). GGML_NATIVE=OFF: portable CPU code; native tuning fails to compile on ARM VMs
FROM python:3.12-slim-bookworm AS whisper
ARG WHISPER_CPP_VERSION=v1.9.5
RUN apt-get update && apt-get install -y --no-install-recommends build-essential cmake git ca-certificates \
 && rm -rf /var/lib/apt/lists/*
RUN git clone --depth 1 --branch "$WHISPER_CPP_VERSION" https://github.com/ggml-org/whisper.cpp /src \
 && cmake -S /src -B /src/build -DCMAKE_BUILD_TYPE=Release -DBUILD_SHARED_LIBS=OFF -DGGML_NATIVE=OFF \
 && cmake --build /src/build -j"$(nproc)" --target whisper-cli \
 && install -m 0755 /src/build/bin/whisper-cli /usr/local/bin/whisper-cli

# Stage 2: Node.js 22 (MIT), for the HyperFrames engine
FROM node:22.23.3-bookworm-slim AS node

# Stage 3: runtime
FROM python:3.12-slim-bookworm
RUN apt-get update && apt-get install -y --no-install-recommends \
      ffmpeg curl ca-certificates fontconfig libgomp1 \
      fonts-inter fonts-noto-core fonts-noto-color-emoji fonts-jetbrains-mono fonts-liberation \
 && rm -rf /var/lib/apt/lists/*

# Hand-drawn font for the whiteboard look (Caveat, SIL Open Font License)
RUN mkdir -p /usr/share/fonts/truetype/caveat \
 && curl -fsSL -o /usr/share/fonts/truetype/caveat/Caveat.ttf "https://github.com/google/fonts/raw/main/ofl/caveat/Caveat%5Bwght%5D.ttf" \
 && fc-cache -f

# Models: whisper.cpp base.en (148 MB), Kokoro v1.0 (326 MB) and its voices (28 MB)
ARG WHISPER_MODEL=base.en
RUN mkdir /models \
 && curl -fsSL -o /models/ggml-$WHISPER_MODEL.bin https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-$WHISPER_MODEL.bin \
 && curl -fsSL -o /models/kokoro-v1.0.onnx https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/kokoro-v1.0.onnx \
 && curl -fsSL -o /models/voices-v1.0.bin https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/voices-v1.0.bin

# Page libraries, pinned, both MIT: rough.js (hand-drawn shapes), KaTeX (math). Animation is ev/web/ev.js.
ARG ROUGH_VERSION=4.6.6
ARG KATEX_VERSION=0.19.0
RUN for lib in roughjs@$ROUGH_VERSION katex@$KATEX_VERSION; do \
      name=${lib%@*}; ver=${lib#*@}; mkdir -p /opt/vendor/$name; \
      curl -fsSL https://registry.npmjs.org/$name/-/$name-$ver.tgz | tar -xz -C /opt/vendor/$name --strip-components=1; \
    done

# three.js (MIT), for the few scenes where 3D explains better (script.yaml three: true). The tarball must match the
# npm registry's sha512. Only the module build and the add-ons (examples/jsm) are kept.
ARG THREE_VERSION=0.186.1
ARG THREE_SHA512=6e515ea9be3dc110921941a3ee0b697e74861f2da5c0393de11854992d5cfe14dbcbbd24bc285b5a9909e0f9b5dfdd0bab3cef4e6ce05ca1cf11a7c9c026fc8c
ENV THREE_VERSION=$THREE_VERSION
RUN mkdir -p /opt/vendor/three \
 && curl -fsSL -o /tmp/three.tgz https://registry.npmjs.org/three/-/three-$THREE_VERSION.tgz \
 && echo "$THREE_SHA512  /tmp/three.tgz" | sha512sum -c - \
 && tar -xzf /tmp/three.tgz -C /opt/vendor/three --strip-components=1 \
      package/LICENSE package/build/three.module.js package/build/three.core.js package/examples/jsm \
 && rm /tmp/three.tgz

# Python tools and headless Chromium (Playwright installs the system libraries it needs)
ENV PLAYWRIGHT_BROWSERS_PATH=/ms-playwright
RUN pip install --no-cache-dir playwright==1.63.0 kokoro-onnx==0.6.1 soundfile==0.14.0 pyyaml==6.0.3 pillow==12.3.0 \
 && python -m playwright install --with-deps --only-shell chromium \
 && rm -rf /var/lib/apt/lists/*

COPY --from=whisper /usr/local/bin/whisper-cli /usr/local/bin/whisper-cli

# HyperFrames engine (HeyGen, Apache-2.0), used when script.yaml says engine: hyperframes.
# Telemetry, update checks, and auto-installs are off: video content can be confidential.
# It uses Playwright's Chrome headless shell: Google builds none for Linux ARM64, so one browser serves both engines.
ARG HYPERFRAMES_VERSION=0.8.157
ENV HYPERFRAMES_VERSION=$HYPERFRAMES_VERSION \
    HYPERFRAMES_NO_TELEMETRY=1 \
    DO_NOT_TRACK=1 \
    HYPERFRAMES_NO_UPDATE_CHECK=1 \
    HYPERFRAMES_NO_AUTO_INSTALL=1 \
    PRODUCER_HEADLESS_SHELL_PATH=/usr/local/bin/chrome-headless-shell \
    HYPERFRAMES_BROWSER_PATH=/usr/local/bin/chrome-headless-shell
COPY --from=node /usr/local/bin/node /usr/local/bin/node
COPY --from=node /usr/local/lib/node_modules /usr/local/lib/node_modules
RUN ln -s ../lib/node_modules/npm/bin/npm-cli.js /usr/local/bin/npm \
 && ln -s ../lib/node_modules/npm/bin/npx-cli.js /usr/local/bin/npx \
 && npm install -g --no-fund --no-audit hyperframes@$HYPERFRAMES_VERSION \
 && ln -s "$(find /ms-playwright -type f \( -name chrome-headless-shell -o -name headless_shell \) | head -1)" \
          /usr/local/bin/chrome-headless-shell \
 && /usr/local/bin/chrome-headless-shell --version \
 && npm cache clean --force

ENV EV_MODELS=/models \
    EV_WHISPER_MODEL=/models/ggml-$WHISPER_MODEL.bin \
    EV_VENDOR=/opt/vendor \
    HOME=/tmp \
    PYTHONDONTWRITEBYTECODE=1
WORKDIR /work
# Isolated mode (-I): no PYTHONPATH, no current folder, no sitecustomize from the repo. The repo goes on the
# path last, so a file an agent writes at its root (json.py, sitecustomize.py) can never shadow a library.
ENTRYPOINT ["python", "-I", "-B", "-c", "import sys; sys.path.append('/work'); from ev.cli import main; main()"]
