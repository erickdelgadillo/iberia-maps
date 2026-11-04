#!/usr/bin/env bash
set -euo pipefail
project_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
if [[ ! -x "$project_dir/.venv/bin/python" ]]; then
  echo "Primero instala el programa siguiendo README.md." >&2
  exit 1
fi
if [[ $# -eq 0 ]]; then
  set -- "$project_dir/ejemplos/vigo.toml"
fi
exec "$project_dir/.venv/bin/python" -m iberia_maps "$@"
