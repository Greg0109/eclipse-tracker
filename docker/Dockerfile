# Build/installation stage
# hadolint ignore=DL3006

# We may want to use our image instead bullseye to avoid copy uv like this.
FROM ghcr.io/astral-sh/uv:0.5.11 AS uv
FROM python:3.12-bullseye AS builder

# Install UV
WORKDIR /usr/local/bin
COPY --from=uv /uv /bin/uv

# Set environment variables for UV
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

WORKDIR /opt/eclipse_tracker

COPY ./pyproject.toml ./uv.lock* ./
RUN touch README.md
COPY ./LICENSE ./
COPY ./src ./src/

# Install dependencies using UV
RUN uv sync --frozen --no-group dev --no-group docs

# Install project is now done by uv sync above


# Final stage
FROM astral/uv:python3.12-trixie AS runtime

RUN groupadd -r eclipse_tracker -g 1000 && \
    useradd -u 1000 -r -m -g eclipse_tracker eclipse_tracker && \
    mkdir /opt/eclipse_tracker && chown eclipse_tracker:eclipse_tracker /opt/eclipse_tracker
WORKDIR /opt/eclipse_tracker

ENV VIRTUAL_ENV=/opt/eclipse_tracker/.venv \
   PATH="/opt/eclipse_tracker/.venv/bin:$PATH"

COPY --from=builder --chown=eclipse_tracker:eclipse_tracker ${VIRTUAL_ENV} ${VIRTUAL_ENV}
COPY --from=builder --chown=eclipse_tracker:eclipse_tracker /opt/eclipse_tracker/src ./src

EXPOSE 8080/tcp
USER eclipse_tracker
ENTRYPOINT ["/bin/bash", "-c"]


CMD ["uvicorn --host=0.0.0.0 --port=8080 eclipse_tracker.app:app"]

ARG VERSION
ARG REVISION
ARG BUILD_DATE

LABEL org.opencontainers.image.created="${BUILD_DATE}" \
  org.opencontainers.image.authors='greg0109 <greg.rabago@gmail.com>' \
  org.opencontainers.image.version="${VERSION}" \
  org.opencontainers.image.revision="${REVISION}" \
  org.opencontainers.image.created="${BUILD_DATE}" \
  org.opencontainers.image.title='eclipse_tracker' \
  org.opencontainers.image.description='Gives you the best location (or array of locations) for vieweing the eclipse'
