#!/usr/bin/env sh
set -eu

usage() {
    cat <<'EOF'
Usage: ./scripts/install.sh

  Install the complete crawler and its managed Chromium browser.
EOF
}

case "${1:-}" in
    "")
        ;;
    -h|--help)
        usage
        exit 0
        ;;
    *)
        usage >&2
        exit 2
        ;;
esac

script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
project_root=$(CDPATH= cd -- "$script_dir/.." && pwd)
venv_dir="$project_root/.venv"
python_command="${PYTHON:-python3}"

cd "$project_root"
"$python_command" -m venv "$venv_dir"

venv_python="$venv_dir/bin/python"
"$venv_python" -m pip install --upgrade pip
"$venv_python" -m pip install -e .
case "$(uname -s)" in
    Linux)
        "$venv_python" -m playwright install --with-deps chromium
        ;;
    *)
        "$venv_python" -m playwright install chromium
        ;;
esac

printf '%s\n' \
    "Installation complete, including managed browser fallback." \
    "Activate the environment with:" \
    "  . \"$venv_dir/bin/activate\"" \
    "Then verify the installed command with:" \
    "  zhihu --version" \
    "  zhihu --help"
