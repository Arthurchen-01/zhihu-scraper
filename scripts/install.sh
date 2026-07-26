#!/usr/bin/env sh
set -eu

usage() {
    cat <<'EOF'
Usage: ./scripts/install.sh [full]

  no argument  Install the normal local-first crawler.
  full         Also install the optional browser-fallback dependency.
EOF
}

install_profile="${1:-default}"
case "$install_profile" in
    default)
        ;;
    full|--full)
        install_profile="full"
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

if [ "$install_profile" = "full" ]; then
    "$venv_python" -m pip install -e ".[full]"
    printf '%s\n' \
        "Browser fallback support is installed." \
        "Browser binaries are not downloaded automatically." \
        "If you need browser fallback, run:" \
        "  $venv_python -m playwright install chromium"
else
    "$venv_python" -m pip install -e .
fi

printf '%s\n' \
    "Installation complete." \
    "Activate the environment with:" \
    "  . \"$venv_dir/bin/activate\"" \
    "Then check the command with:" \
    "  zhihu --help"
