FROM debian:bookworm-slim

ARG OPENCODE_VERSION
ARG UID=1000
ARG GID=1000
ARG PYTHON_VERSION=3.10
ARG TOFU_VERSION=1.10.0
ARG JUST_VERSION=1.58.0
# Matched to ~/git/platform/touchsurgery (Dockerfile and poetry.lock).
ARG POETRY_VERSION=2.5.1
ARG BLACK_VERSION=22.3.0
ARG RUFF_VERSION=0.11.7
ARG MYPY_VERSION=1.7.1

RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      ca-certificates curl git openssh-client socat ripgrep less procps jq tini \
      build-essential libssl-dev zlib1g-dev libbz2-dev libreadline-dev \
      libsqlite3-dev libncursesw5-dev xz-utils tk-dev libxml2-dev \
      libxmlsec1-dev libffi-dev liblzma-dev \
 && rm -rf /var/lib/apt/lists/*

RUN test -n "$OPENCODE_VERSION" \
 && arch=$(dpkg --print-architecture | sed 's/amd64/x64/') \
 && curl -fsSL "https://opencode.ai/files/bin/${OPENCODE_VERSION}/opencode-linux-${arch}.tar.gz" \
    | tar -xz -C /usr/local/bin opencode \
 && opencode --version

RUN arch=$(dpkg --print-architecture) \
 && curl -fsSL "https://github.com/opentofu/opentofu/releases/download/v${TOFU_VERSION}/tofu_${TOFU_VERSION}_linux_${arch}.tar.gz" \
    | tar -xz -C /usr/local/bin tofu \
 && tofu version

RUN arch=$(uname -m) \
 && curl -fsSL "https://github.com/casey/just/releases/download/${JUST_VERSION}/just-${JUST_VERSION}-${arch}-unknown-linux-musl.tar.gz" \
    | tar -xz -C /usr/local/bin just \
 && just --version

RUN groupadd -g "$GID" dev && useradd -m -u "$UID" -g "$GID" -s /bin/bash dev

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/
COPY entrypoint.sh /usr/local/bin/entrypoint.sh

USER dev
ENV PYENV_ROOT=/home/dev/.pyenv
ENV PATH=/home/dev/.local/bin:$PYENV_ROOT/shims:$PYENV_ROOT/bin:$PATH

RUN git clone --depth 1 https://github.com/pyenv/pyenv.git "$PYENV_ROOT" \
 && pyenv install "$PYTHON_VERSION" \
 && pyenv global "$PYTHON_VERSION" \
 && uv tool install "poetry==${POETRY_VERSION}" \
 && uv tool install "black==${BLACK_VERSION}" \
 && uv tool install "ruff==${RUFF_VERSION}" \
 && uv tool install "mypy==${MYPY_VERSION}" \
 && uv tool install isort \
 && uv tool install pre-commit \
 && mkdir -p /home/dev/.local/share/opencode /home/dev/.config/opencode /home/dev/.cache

WORKDIR /work
EXPOSE 4096
ENTRYPOINT ["/usr/bin/tini", "--", "/usr/local/bin/entrypoint.sh"]
