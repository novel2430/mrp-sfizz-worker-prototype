#!/bin/sh
set -eu
rm -rf .test-out
mkdir -p .test-out
cat > .test-out/test.sfz <<'SFZ'
<control> hint_ram_based=0
<region> sample=dummy.wav key=60
SFZ
cat > .test-out/a.mrpev <<'EV'
MRPEV1 48000
0 note_on 60 64
4800 note_off 60 0
END 4800
EV
LIB=$(find build -maxdepth 2 -type f \( -name 'libfake_sfizz.so' -o -name 'libfake_sfizz.dylib' \) | head -1)
[ -n "$LIB" ]
printf 'LOAD\t%s\nRENDER\t%s\t%s\t123\nRENDER\t%s\t%s\t123\nQUIT\n' \
  "$PWD/.test-out/test.sfz" \
  "$PWD/.test-out/a.mrpev" "$PWD/.test-out/a1.wav" \
  "$PWD/.test-out/a.mrpev" "$PWD/.test-out/a2.wav" \
  | build/mrp-sfizz-worker --libsfizz "$LIB" > .test-out/worker.log
grep -q '^READY.*protocol=3.*offline_api=1' .test-out/worker.log
grep -q '^OK.*LOAD.*sfizz_bytes=2649309424' .test-out/worker.log
[ "$(grep -c '^OK.*RENDER' .test-out/worker.log)" -eq 2 ]
[ "$(grep -c 'instrument_loads=1' .test-out/worker.log)" -eq 2 ]
test -s .test-out/a1.wav
test -s .test-out/a2.wav
H1=$(python tools/pcm_hash.py .test-out/a1.wav | awk '{print $1}')
H2=$(python tools/pcm_hash.py .test-out/a2.wav | awk '{print $1}')
[ "$H1" = "$H2" ]
printf 'fake resident-worker PCM hash: %s\n' "$H1"
