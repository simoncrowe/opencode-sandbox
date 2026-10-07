FROM debian:bookworm-slim

ARG OPENCODE_VERSION
ARG UID=1000
ARG GID=1000
ARG PYTHON_VERSION=3.11

RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      ca-certificates curl git openssh-client ripgrep less procps jq tini \
      build-essential libssl-dev zlib1g-dev libbz2-dev libreadline-dev \
      libsqlite3-dev libncursesw5-dev xz-utils tk-dev libxml2-dev \
      libxmlsec1-dev libffi-dev liblzma-dev \
 && rm -rf /var/lib/apt/lists/*

RUN test -n "$OPENCODE_VERSION" \
 && arch=$(dpkg --print-architecture | sed 's/amd64/x64/') \
 && curl -fsSL "https://opencode.ai/files/bin/${OPENCODE_VERSION}/opencode-linux-${arch}.tar.gz" \
    | tar -xz -C /usr/local/bin opencode \
 && opencode --version

RUN groupadd -g "$GID" dev && useradd -m -u "$UID" -g "$GID" -s /bin/bash dev

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/
COPY entrypoint.sh /usr/local/bin/entrypoint.sh

USER dev
ENV PYENV_ROOT=/home/dev/.pyenv
ENV PATH=/home/dev/.local/bin:$PYENV_ROOT/shims:$PYENV_ROOT/bin:$PATH

RUN git clone --depth 1 https://github.com/pyenv/pyenv.git "$PYENV_ROOT" \
 && pyenv install "$PYTHON_VERSION" \
 && pyenv global "$PYTHON_VERSION" \
 && uv tool install poetry \
 && mkdir -p /home/dev/.local/share/opencode /home/dev/.config/opencode /home/dev/.cache

WORKDIR /work
EXPOSE 4096
ENTRYPOINT ["/usr/bin/tini", "--", "/usr/local/bin/entrypoint.sh"]
