#!/bin/sh
set -eu
PREFIX=${1:-"$PWD/.deps/sfizz-install"}
SRC=${SFIZZ_SRC:-"$PWD/.deps/sfizz-src"}
BUILD=${SFIZZ_BUILD:-"$PWD/.deps/sfizz-build"}
mkdir -p "$(dirname "$SRC")"
if [ ! -d "$SRC/.git" ]; then
  git clone --recursive --branch 1.2.3 --depth 1 https://github.com/sfztools/sfizz.git "$SRC"
fi
python3 "$PWD/tools/apply_sfizz_offline_patch.py" "$SRC"
cmake -S "$SRC" -B "$BUILD" \
  -DCMAKE_BUILD_TYPE=Release \
  -DCMAKE_INSTALL_PREFIX="$PREFIX" \
  -DSFIZZ_SHARED=ON \
  -DSFIZZ_RENDER=OFF \
  -DSFIZZ_JACK=OFF \
  -DSFIZZ_TESTS=OFF -DSFIZZ_DEMOS=OFF -DSFIZZ_BENCHMARKS=OFF -DSFIZZ_DEVTOOLS=OFF
cmake --build "$BUILD" -j"${JOBS:-2}"
cmake --install "$BUILD"
printf 'Look for libsfizz under: %s\n' "$PREFIX"
find "$PREFIX" -type f -name 'libsfizz.so*' -print
