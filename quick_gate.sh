#!/usr/bin/env bash
set -euo pipefail

# ------------------------------------------------------------
# MRP sfizz persistent-worker QUICK GATE
#
# Gate 1:
#   Drums A -> B -> A with RAM mode + MIDI reset
#
# Gate 2:
#   Piano persistent RAM workers, concurrency=3, rounds=1
#
# This is intentionally NOT a stress / release qualification test.
# ------------------------------------------------------------

PROTO="${PROTO:-$HOME/src/mrp-sfizz-worker-prototype}"
MRP="${MRP:-$HOME/src/MidiRenderPipeline}"

A_DIR="${A_DIR:-/tmp/mrp-piano-debug/midi}"
B_DIR="${B_DIR:-/tmp/mrp-piano-debug-B/midi}"

OUT="${OUT:-/tmp/mrp-sfizz-quick-gate}"

: "${LIBSFIZZ:?Please export LIBSFIZZ first}"
: "${PIANO_SFZ:?Please export PIANO_SFZ first}"

DRUM_SFZ="$MRP/resources/instruments/SM_Drums/Programs/SM_Drums_kit.sfz"

PIANO_A="$A_DIR/周杰伦-蒲公英的约定.track-06.mid"

DRUM_A="$A_DIR/周杰伦-蒲公英的约定.track-05.mid"
DRUM_B="$B_DIR/周杰伦-一路向北.track-05.mid"


die() {
    echo "ERROR: $*" >&2
    exit 1
}


check_file() {
    [[ -f "$1" ]] || die "missing file: $1"
}


echo "============================================================"
echo " MRP sfizz persistent-worker QUICK GATE"
echo "============================================================"
echo
echo "Prototype : $PROTO"
echo "MRP       : $MRP"
echo "libsfizz  : $LIBSFIZZ"
echo "Piano SFZ : $PIANO_SFZ"
echo "Drum SFZ  : $DRUM_SFZ"
echo


# ------------------------------------------------------------
# Preflight
# ------------------------------------------------------------

check_file "$LIBSFIZZ"
check_file "$PIANO_SFZ"
check_file "$DRUM_SFZ"

check_file "$PIANO_A"
check_file "$DRUM_A"
check_file "$DRUM_B"

check_file "$PROTO/tools/run_sequence.py"
check_file "$PROTO/tools/parallel_pool_probe.py"

rm -rf "$OUT"
mkdir -p "$OUT"


# ------------------------------------------------------------
# GATE 1
# Drums: A -> B -> A
# ------------------------------------------------------------

echo
echo "============================================================"
echo " GATE 1/2: Drums A -> B -> A"
echo " RAM mode + MIDI reset"
echo "============================================================"
echo

python "$PROTO/tools/run_sequence.py" \
    --libsfizz "$LIBSFIZZ" \
    --sfz "$DRUM_SFZ" \
    --mode ram \
    --reset midi \
    --out-dir "$OUT/drums-aba" \
    "$DRUM_A" \
    "$DRUM_B" \
    "$DRUM_A" \
    | tee "$OUT/drums-aba.log"

echo

if grep -q 'A...A deterministic: YES' "$OUT/drums-aba.log"; then
    echo "PASS: drums A -> B -> A deterministic"
else
    echo "FAIL: drums A -> B -> A changed PCM state"
    echo
    echo "Quick gate FAILED at Gate 1."
    exit 2
fi


# ------------------------------------------------------------
# GATE 2
# Piano: persistent worker pool, C3
#
# Only one render per worker here.
# We already separately established:
#   - official sfizz_render PCM parity
#   - piano A/A/A persistence
#   - piano A/B/A MIDI-reset correctness
#
# This gate specifically tests concurrent RAM-safe workers.
# ------------------------------------------------------------

echo
echo "============================================================"
echo " GATE 2/2: Piano persistent worker pool C3"
echo " RAM mode + concurrency=3"
echo "============================================================"
echo

python "$PROTO/tools/parallel_pool_probe.py" \
    --libsfizz "$LIBSFIZZ" \
    --sfz "$PIANO_SFZ" \
    --midi "$PIANO_A" \
    --mode ram \
    --reset midi \
    --concurrency 3 \
    --rounds 1 \
    | tee "$OUT/piano-c3.log"

echo

if grep -Eq 'DETERMINISTIC[=: ]+YES' "$OUT/piano-c3.log"; then
    echo "PASS: piano C3 deterministic"
else
    echo "FAIL: piano C3 produced different PCM outputs"
    echo
    echo "Quick gate FAILED at Gate 2."
    exit 3
fi


# ------------------------------------------------------------
# Result
# ------------------------------------------------------------

echo
echo "============================================================"
echo " QUICK GATE: PASS"
echo "============================================================"
echo
echo "Verified:"
echo "  ✓ drums A -> B -> A survives MIDI reset"
echo "  ✓ piano RAM persistent workers survive C3 concurrency"
echo
echo "Logs:"
echo "  $OUT/drums-aba.log"
echo "  $OUT/piano-c3.log"
