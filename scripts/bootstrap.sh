#!/usr/bin/env bash
set -euo pipefail

root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
python=${UMI_PYTHON:-python3}
source_dir="$root/upstream/universal_manipulation_interface"
tool_dir="$root/.tools/exiftool"
venv="$root/.venv"

for tool in git perl ffmpeg ffprobe "$python"; do
  if ! command -v "$tool" >/dev/null; then
    printf 'Missing command: %s. See README.md for setup.\n' "$tool" >&2
    exit 1
  fi
done
if ! "$python" -c 'import sys; sys.exit(sys.version_info[:2] != (3, 12))'; then
  printf 'Python 3.12 is required. Set UMI_PYTHON to a Python 3.12 executable.\n' >&2
  exit 1
fi

checkout_revision() (
  set -e
  url=$1
  commit=$2
  dest=$3
  if [[ -e "$dest" ]]; then
    if [[ -d "$dest/.git" && "$(git -C "$dest" rev-parse HEAD)" == "$commit" ]]; then
      printf 'Using %s at %.12s\n' "$dest" "$commit"
      return
    fi
    printf 'Expected revision %s at %s. Move that checkout aside to recreate it.\n' "$commit" "$dest" >&2
    exit 1
  fi

  parent=$(dirname -- "$dest")
  mkdir -p -- "$parent"
  staging=$(mktemp -d "$parent/.checkout.XXXXXX")
  trap 'rm -rf -- "$staging"' EXIT

  export GIT_TERMINAL_PROMPT=0
  git -C "$staging" init --quiet
  git -C "$staging" remote add origin "$url"
  git -C "$staging" fetch --quiet --depth=1 origin "$commit"
  git -C "$staging" -c advice.detachedHead=false checkout --detach --quiet FETCH_HEAD
  test "$(git -C "$staging" rev-parse HEAD)" = "$commit"
  mv -T -- "$staging" "$dest"
  printf 'Fetched %s at %.12s\n' "$dest" "$commit"
)

checkout_revision https://github.com/real-stanford/universal_manipulation_interface.git \
  d095ba9590df789df5189eea5ee7e431689038a6 "$source_dir"
checkout_revision https://github.com/exiftool/exiftool.git \
  aa4baf5c71d92e5dc9a077ee24fcc4fd478936c1 "$tool_dir"

if [[ ! -x "$venv/bin/python" ]]; then
  "$python" -m venv "$venv"
fi
if ! "$venv/bin/python" -c 'import sys; sys.exit(sys.version_info[:2] != (3, 12))'; then
  printf 'Existing .venv uses a different Python. Move it aside and rerun.\n' >&2
  exit 1
fi

# PyExifTool and upstream subprocess calls resolve tools through PATH.
cat > "$venv/bin/exiftool" <<'WRAPPER'
#!/usr/bin/env bash
set -euo pipefail
bin_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
exec perl "$bin_dir/../../.tools/exiftool/exiftool" "$@"
WRAPPER
chmod +x "$venv/bin/exiftool"

"$venv/bin/python" -m pip --disable-pip-version-check install --only-binary=:all: \
  -r "$root/requirements-cpu.txt"
"$venv/bin/python" -m pip check
printf 'ExifTool %s\n' "$("$venv/bin/exiftool" -ver)"
printf 'Ready. In the project root, run: .venv/bin/python scripts/smoke_test.py\n'
