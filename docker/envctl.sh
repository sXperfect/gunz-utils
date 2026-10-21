#!/usr/bin/env bash
#
# envctl.sh — mamba-like environment management over Docker for gunz-utils.
#
#   ./envctl.sh create              # docker build  (== mamba create)
#   ./envctl.sh shell               # interactive shell in the env (== mamba activate)
#   ./envctl.sh run <cmd...>        # run a command in the env
#   ./envctl.sh test                # run pytest (== mamba run pytest)
#   ./envctl.sh lint                # ruff check src tests benchmarks scripts
#   ./envctl.sh typecheck           # mypy src/gunz_utils
#   ./envctl.sh list                # docker images (== env list)
#   ./envctl.sh remove              # docker rmi (== mamba remove)
#
set -euo pipefail

IMAGE="gunz-utils:latest"
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "${DIR}/.." && pwd)"
RUN=(docker run --rm -e PYTHONDONTWRITEBYTECODE=1 -v "${ROOT}:/app:ro")

cmd="${1:-}"
shift || true

case "${cmd}" in
  create)
    docker build -t "${IMAGE}" -f "${DIR}/Dockerfile" "${ROOT}"
    ;;
  shell)
    docker run -it --rm -v "${ROOT}/src:/app/src" -v "${ROOT}/tests:/app/tests" "${IMAGE}" /bin/bash
    ;;
  run)
    "${RUN[@]}" "${IMAGE}" "$@"
    ;;
  test)
    "${RUN[@]}" "${IMAGE}" micromamba run -n base python -m pytest -m "not slow" -q -p no:cacheprovider
    ;;
  lint)
    "${RUN[@]}" "${IMAGE}" micromamba run -n base python -m ruff check --no-cache src tests benchmarks scripts
    ;;
  typecheck)
    "${RUN[@]}" "${IMAGE}" micromamba run -n base python -m mypy --cache-dir /tmp/mypy-cache src/gunz_utils
    ;;
  list)
    docker images "${IMAGE}"
    ;;
  remove)
    docker rmi "${IMAGE}"
    ;;
  *)
    echo "usage: $0 {create|shell|run <cmd>|test|lint|typecheck|list|remove}" >&2
    exit 1
    ;;
esac
