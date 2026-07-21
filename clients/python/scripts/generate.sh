#!/usr/bin/env bash
# Regenerate the vendored protobuf / gRPC stubs from proto_volt/.
#
# Run from clients/python/:  ./scripts/generate.sh
#
# Reads proto_volt/voltnir_api_v1.proto directly out of the repo root.
# Output (src/voltnir_sdk/_generated/*.py) is committed to git so end users
# can `pip install` without protoc on their machine.

set -euo pipefail

SDK_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPO_ROOT="$(cd "${SDK_ROOT}/../.." && pwd)"

# Locate proto_volt/. This script runs from two differently-shaped checkouts, so
# the location is probed rather than hardcoded:
#   - alongside the SDK at the repository root (<root>/proto_volt)
#   - or inside a sibling component directory (<root>/*/proto_volt)
# Set VOLTNIR_PROTO_DIR to skip the probe entirely.
PROTO_DIR="${VOLTNIR_PROTO_DIR:-}"
if [[ -z "${PROTO_DIR}" ]]; then
    for _cand in "${REPO_ROOT}/proto_volt" "${REPO_ROOT}"/*/proto_volt; do
        if [[ -f "${_cand}/voltnir_api_v1.proto" ]]; then
            PROTO_DIR="${_cand}"
            break
        fi
    done
fi
PROTO_FILE="${PROTO_DIR:-${REPO_ROOT}/proto_volt}/voltnir_api_v1.proto"
PROTO_DIR="$(dirname "${PROTO_FILE}")"
OUT_DIR="${SDK_ROOT}/src/voltnir_sdk/_generated"

if [[ ! -f "${PROTO_FILE}" ]]; then
    echo "error: proto not found at ${PROTO_FILE}" >&2
    exit 1
fi

# Keep in sync with the pinned grpcio-tools in pyproject.toml [dev].
REQUIRED_GRPCIO_TOOLS="1.80.0"

if ! python3 -c "import grpc_tools.protoc" >/dev/null 2>&1; then
    echo "error: grpcio-tools not installed. Run:" >&2
    echo "  pip install 'grpcio-tools==${REQUIRED_GRPCIO_TOOLS}'" >&2
    echo "or:" >&2
    echo "  pip install -e '.[dev]'" >&2
    exit 1
fi

# The stubs embed their generator's version, so a different grpcio-tools rewrites
# them wholesale, cosmetic churn that hides real contract changes. Refuse to run
# on a mismatch rather than silently producing a misleading diff.
INSTALLED_GRPCIO_TOOLS="$(python3 -c \
    'import importlib.metadata as m; print(m.version("grpcio-tools"))' 2>/dev/null || echo unknown)"

if [[ "${INSTALLED_GRPCIO_TOOLS}" != "${REQUIRED_GRPCIO_TOOLS}" ]]; then
    if [[ "${ALLOW_GRPCIO_TOOLS_MISMATCH:-0}" == "1" ]]; then
        echo "warning: grpcio-tools ${INSTALLED_GRPCIO_TOOLS} != pinned ${REQUIRED_GRPCIO_TOOLS};" >&2
        echo "         continuing because ALLOW_GRPCIO_TOOLS_MISMATCH=1. Expect a large diff." >&2
    else
        cat >&2 <<MSG
error: grpcio-tools version mismatch
  installed: ${INSTALLED_GRPCIO_TOOLS}
  pinned:    ${REQUIRED_GRPCIO_TOOLS}  (pyproject.toml [dev])

Regenerating with a different version rewrites the committed stubs wholesale,
so a real contract change would be invisible in the diff. Either install the
pinned version:

  pip install 'grpcio-tools==${REQUIRED_GRPCIO_TOOLS}'

or, if you intend to move to ${INSTALLED_GRPCIO_TOOLS}, bump BOTH pyproject.toml
and REQUIRED_GRPCIO_TOOLS in this script, then re-run and commit the regenerated
stubs as a deliberate generator bump. To override once:

  ALLOW_GRPCIO_TOOLS_MISMATCH=1 ./scripts/generate.sh
MSG
        exit 1
    fi
fi

mkdir -p "${OUT_DIR}"

# --pyi_out is what makes the package actually type-check for a consumer.
# Without it every response message is `Any`: py.typed says "trust our
# annotations" and there are none for the generated types, so a typo'd response
# field or a wrong-typed argument passes mypy silently.
python3 -m grpc_tools.protoc \
    --proto_path="${PROTO_DIR}" \
    --python_out="${OUT_DIR}" \
    --pyi_out="${OUT_DIR}" \
    --grpc_python_out="${OUT_DIR}" \
    "${PROTO_FILE}"

# grpcio-tools emits `import voltnir_api_v1_pb2` (absolute) into the *_pb2_grpc.py
# file, which fails when the module lives in a sub-package. Rewrite to a relative
# import so the generated package works regardless of how it is imported.
sed -i \
    's/^import voltnir_api_v1_pb2 as voltnir__api__v1__pb2$/from . import voltnir_api_v1_pb2 as voltnir__api__v1__pb2/' \
    "${OUT_DIR}/voltnir_api_v1_pb2_grpc.py"

# Make sure the package marker exists.
touch "${OUT_DIR}/__init__.py"

echo "generated:"
echo "  ${OUT_DIR}/voltnir_api_v1_pb2.py"
echo "  ${OUT_DIR}/voltnir_api_v1_pb2.pyi"
echo "  ${OUT_DIR}/voltnir_api_v1_pb2_grpc.py"
echo "(source: ${PROTO_FILE})"
