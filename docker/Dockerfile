# syntax=docker/dockerfile:1
# mamba-in-Docker env for gunz-utils.
#
# Layering strategy:
#   Layer A - conda base (python)          -> built once, cached
#   Layer B - project + pip/optional deps  -> thin, cached
#   Layer C - tests/code changes           -> rebuilds most often
FROM ghcr.io/mamba-org/micromamba:latest

# Layer A: conda packages via the mamba solver (declared in env.yml).
COPY --chown=$MAMBA_USER:$MAMBA_USER docker/env.yml /tmp/env.yml
RUN micromamba install -y -n base -f /tmp/env.yml && \
    micromamba clean -a -y

# Layer B: project source + pip deps (extras: pydantic, cryptography,
# gitpython, loguru) and tooling (pytest, ruff, mypy).
WORKDIR /app
COPY --chown=$MAMBA_USER:$MAMBA_USER pyproject.toml README.md LICENSE.md ./
COPY --chown=$MAMBA_USER:$MAMBA_USER src ./src
COPY --chown=$MAMBA_USER:$MAMBA_USER native ./native
COPY --chown=$MAMBA_USER:$MAMBA_USER scripts ./scripts
COPY --chown=$MAMBA_USER:$MAMBA_USER configs ./configs
COPY --chown=$MAMBA_USER:$MAMBA_USER docker/requirements.txt /tmp/requirements.txt
RUN micromamba run -n base pip install --no-cache-dir -r /tmp/requirements.txt

# Layer C: tests (copy last so code/test edits only rebuild this layer).
COPY --chown=$MAMBA_USER:$MAMBA_USER tests ./tests

# Default: run the pytest suite (deselecting slow/resource-heavy tests).
ENV PYTHONDONTWRITEBYTECODE=1
USER $MAMBA_USER
CMD ["micromamba", "run", "-n", "base", "python", "-m", "pytest", "-m", "not slow", "-q", "-p", "no:cacheprovider"]
