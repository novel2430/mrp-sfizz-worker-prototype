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
printf '%s\n' "$SYMS" | grep -q 'sfizz_capture_offline_baseline' || {
  echo "MISSING sfizz_capture_offline_baseline" >&2; exit 1;
}
printf '%s\n' "$SYMS" | grep -q 'sfizz_prepare_offline_task' || {
  echo "MISSING sfizz_prepare_offline_task" >&2; exit 1;
}
echo "PASS: patched offline ABI is exported by $LIB"
