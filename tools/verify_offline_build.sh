#!/bin/sh
set -eu
if [ "$#" -ne 1 ]; then
  echo "usage: $0 /absolute/path/to/libsfizz.so" >&2
  exit 2
fi
LIB=$1
if [ ! -f "$LIB" ]; then
  echo "not a file: $LIB" >&2
  exit 2
fi
if command -v nm >/dev/null 2>&1; then
  SYMS=$(nm -D "$LIB" 2>/dev/null || nm -g "$LIB" 2>/dev/null || true)
elif command -v objdump >/dev/null 2>&1; then
  SYMS=$(objdump -T "$LIB" 2>/dev/null || true)
else
  echo "need nm or objdump to inspect exported symbols" >&2
  exit 2
fi
for sym in \
  sfizz_get_offline_render_api_version \
  sfizz_set_offline_ram_loading \
  sfizz_seal_offline_instrument \
  sfizz_begin_offline_task \
  sfizz_get_num_bytes64
do
  printf '%s\n' "$SYMS" | grep -q "$sym" || {
    echo "MISSING $sym" >&2; exit 1;
  }
done
echo "PASS: patched offline ABI is exported by $LIB"
