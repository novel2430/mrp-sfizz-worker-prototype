#!/usr/bin/env python3
"""Apply the minimal persistent-offline reset experiment to sfizz 1.2.3.

This deliberately patches one exact upstream revision:
  4e70dc0bef53b41f2853ed46e26f5911114c92d0 (tag 1.2.3)

The experiment keeps the existing Synth/FilePool/sample residency intact and adds
an explicit canonical runtime baseline plus deterministic per-task reset API.
It is intentionally *not* the final multi-session Snapshot architecture.
"""
from __future__ import annotations

import argparse
import subprocess
from pathlib import Path

EXPECTED = "4e70dc0bef53b41f2853ed46e26f5911114c92d0"
MARKER = "MRP_OFFLINE_BASELINE_V1"


def git(repo: Path, *args: str) -> str:
    return subprocess.check_output(["git", "-C", str(repo), *args], text=True).strip()


def replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text()
    if new in text:
        return
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{path}: expected one patch anchor, found {count}: {old[:120]!r}")
    path.write_text(text.replace(old, new, 1))


def insert_after(path: Path, anchor: str, addition: str) -> None:
    replace_once(path, anchor, anchor + addition)


def apply(repo: Path) -> None:
    head = git(repo, "rev-parse", "HEAD")
    if head != EXPECTED:
        raise RuntimeError(f"sfizz revision mismatch: expected {EXPECTED}, got {head}")

    # One shared RNG is required so prepareOfflineTask(seed) can deterministically
    # rewind random SFZ opcodes across translation units. This is still process-wide
    # in V1; a future multi-session design must move it into RenderSession ownership.
    math_h = repo / "src/sfizz/MathHelpers.h"
    replace_once(math_h, "namespace Random {\nstatic fast_rand randomGenerator;\n}",
                 "namespace Random {\nextern fast_rand randomGenerator;\n}")
    math_cpp = repo / "src/sfizz/MathHelpers.cpp"
    if not math_cpp.exists():
        math_cpp.write_text(
            '// SPDX-License-Identifier: BSD-2-Clause\n'
            '#include "MathHelpers.h"\n\n'
            'namespace Random {\n'
            'fast_rand randomGenerator;\n'
            '} // namespace Random\n'
        )

    cmake = repo / "src/CMakeLists.txt"
    insert_after(cmake, "    sfizz/MidiState.cpp\n", "    sfizz/MathHelpers.cpp\n")

    # MidiState: snapshot the exact post-load state instead of trying to infer it
    # from CC121 or all-zero controller resets.
    midi_h = repo / "src/sfizz/MidiState.h"
    insert_after(midi_h, "    MidiState();\n", r'''

    struct RuntimeState {
        int activeNotes { 0 };
        MidiNoteArray<unsigned> noteOnTimes { {} };
        MidiNoteArray<unsigned> noteOffTimes { {} };
        std::bitset<128> noteStates;
        MidiNoteArray<float> lastNoteVelocities;
        float velocityOverride { 0.0f };
        int lastNotePlayed { -1 };
        std::array<EventVector, config::numCCs> ccEvents;
        EventVector pitchEvents;
        EventVector channelAftertouchEvents;
        std::array<EventVector, 128> polyAftertouchEvents;
        int currentProgram { 0 };
        float alternate { 0.0f };
        unsigned internalClock { 0 };
    };

    RuntimeState captureRuntimeState() const;
    void restoreRuntimeState(const RuntimeState& state);
''')
    midi_cpp = repo / "src/sfizz/MidiState.cpp"
    insert_after(midi_cpp, "sfz::MidiState::MidiState()\n{\n    resetEventStates();\n    resetNoteStates();\n}\n", r'''

sfz::MidiState::RuntimeState sfz::MidiState::captureRuntimeState() const
{
    RuntimeState state;
    state.activeNotes = activeNotes;
    state.noteOnTimes = noteOnTimes;
    state.noteOffTimes = noteOffTimes;
    state.noteStates = noteStates;
    state.lastNoteVelocities = lastNoteVelocities;
    state.velocityOverride = velocityOverride;
    state.lastNotePlayed = lastNotePlayed;
    state.ccEvents = ccEvents;
    state.pitchEvents = pitchEvents;
    state.channelAftertouchEvents = channelAftertouchEvents;
    state.polyAftertouchEvents = polyAftertouchEvents;
    state.currentProgram = currentProgram;
    state.alternate = alternate;
    state.internalClock = internalClock;
    return state;
}

void sfz::MidiState::restoreRuntimeState(const RuntimeState& state)
{
    activeNotes = state.activeNotes;
    noteOnTimes = state.noteOnTimes;
    noteOffTimes = state.noteOffTimes;
    noteStates = state.noteStates;
    lastNoteVelocities = state.lastNoteVelocities;
    velocityOverride = state.velocityOverride;
    lastNotePlayed = state.lastNotePlayed;
    ccEvents = state.ccEvents;
    pitchEvents = state.pitchEvents;
    channelAftertouchEvents = state.channelAftertouchEvents;
    polyAftertouchEvents = state.polyAftertouchEvents;
    currentProgram = state.currentProgram;
    alternate = state.alternate;
    internalClock = state.internalClock;
}
''')

    # Layer: capture all mutable performance switches/counters. Delayed release
    # vectors are guaranteed empty at our canonical post-load baseline and are
    # explicitly cleared on restore to avoid carrying note release state.
    layer_h = repo / "src/sfizz/Layer.h"
    insert_after(layer_h, "    ~Layer();\n", r'''

    struct RuntimeState {
        bool sustainPressed { false };
        bool sostenutoPressed { false };
        bool keySwitched {};
        bool previousKeySwitched {};
        bool sequenceSwitched {};
        bool pitchSwitched {};
        bool programSwitched {};
        bool bpmSwitched {};
        bool aftertouchSwitched {};
        std::bitset<config::numCCs> ccSwitched;
        int sequenceCounter { 0 };
    };

    RuntimeState captureRuntimeState() const noexcept;
    void restoreRuntimeState(const RuntimeState& state) noexcept;
''')
    layer_cpp = repo / "src/sfizz/Layer.cpp"
    insert_after(layer_cpp, "Layer::~Layer()\n{\n}\n", r'''

Layer::RuntimeState Layer::captureRuntimeState() const noexcept
{
    RuntimeState state;
    state.sustainPressed = sustainPressed_;
    state.sostenutoPressed = sostenutoPressed_;
    state.keySwitched = keySwitched_;
    state.previousKeySwitched = previousKeySwitched_;
    state.sequenceSwitched = sequenceSwitched_;
    state.pitchSwitched = pitchSwitched_;
    state.programSwitched = programSwitched_;
    state.bpmSwitched = bpmSwitched_;
    state.aftertouchSwitched = aftertouchSwitched_;
    state.ccSwitched = ccSwitched_;
    state.sequenceCounter = sequenceCounter_;
    return state;
}

void Layer::restoreRuntimeState(const RuntimeState& state) noexcept
{
    sustainPressed_ = state.sustainPressed;
    sostenutoPressed_ = state.sostenutoPressed;
    delayedSustainReleases_.clear();
    delayedSostenutoReleases_.clear();
    keySwitched_ = state.keySwitched;
    previousKeySwitched_ = state.previousKeySwitched;
    sequenceSwitched_ = state.sequenceSwitched;
    pitchSwitched_ = state.pitchSwitched;
    programSwitched_ = state.programSwitched;
    bpmSwitched_ = state.bpmSwitched;
    aftertouchSwitched_ = state.aftertouchSwitched;
    ccSwitched_ = state.ccSwitched;
    sequenceCounter_ = state.sequenceCounter;
}
''')

    # Preserve group configuration while resetting session-only timer history.
    poly_h = repo / "src/sfizz/PolyphonyGroup.h"
    insert_after(poly_h, "    void removeAllVoices() noexcept;\n",
                 "    void resetRuntimeState() noexcept;\n")
    poly_cpp = repo / "src/sfizz/PolyphonyGroup.cpp"
    insert_after(poly_cpp, "void sfz::PolyphonyGroup::removeAllVoices() noexcept\n{\n    voices.clear();\n}\n", r'''

void sfz::PolyphonyGroup::resetRuntimeState() noexcept
{
    voices.clear();
    mostRecentStartStamp_ = 0;
}
''')

    vm_h = repo / "src/sfizz/VoiceManager.h"
    insert_after(vm_h, "    void reset();\n",
                 "    void resetRuntimeState() noexcept;\n")
    vm_cpp = repo / "src/sfizz/VoiceManager.cpp"
    insert_after(vm_cpp, "void VoiceManager::reset()\n{\n    for (auto& voice : list_)\n        voice.reset();\n\n    polyphonyGroups_.clear();\n    polyphonyGroups_.emplace(0, PolyphonyGroup{});\n    setStealingAlgorithm(StealingAlgorithm::Oldest);\n}\n", r'''

void VoiceManager::resetRuntimeState() noexcept
{
    for (auto& voice : list_)
        voice.reset();
    activeVoices_.clear();
    temp_.clear();
    for (auto& item : polyphonyGroups_)
        item.second.resetRuntimeState();
}
''')

    # Synth owns the minimal baseline. It deliberately holds no samples and no
    # copied Region graph; FilePool remains exactly where it is in the resident Synth.
    synth_h = repo / "src/sfizz/Synth.h"
    insert_after(synth_h, "    void allSoundOff() noexcept;\n", r'''

    /** Experimental MRP hook: seal the current post-load performance baseline. */
    void captureOfflineBaseline();
    /** Experimental MRP hook: restore the sealed performance baseline and seed RNG. */
    void prepareOfflineTask(unsigned int seed);
''')

    private_h = repo / "src/sfizz/SynthPrivate.h"
    insert_after(private_h, "    void clear();\n", r'''
    // MRP_OFFLINE_BASELINE_V1: intentionally task state only; no sample copies.
''')
    insert_after(private_h, "    absl::optional<uint8_t> currentSwitch_;\n", r'''
    bool offlineBaselineReady_ { false };
    MidiState::RuntimeState offlineMidiState_;
    absl::optional<uint8_t> offlineCurrentSwitch_;
    std::vector<Layer::RuntimeState> offlineLayerStates_;
''')

    synth_cpp = repo / "src/sfizz/Synth.cpp"
    # Invalidate stale baseline whenever the instrument graph is cleared/reloaded.
    insert_after(synth_cpp, "void Synth::Impl::clear()\n{\n",
                 "    offlineBaselineReady_ = false;\n    offlineLayerStates_.clear();\n")

    # Add methods adjacent to allSoundOff. captureOfflineBaseline waits once for
    # RAM/background preload, so LOAD timing in the prototype is true cold-ready time.
    insert_after(synth_cpp, r'''void Synth::allSoundOff() noexcept
{
    Impl& impl = *impl_;
    for (auto& voice : impl.voiceManager_)
        voice.reset();
    for (int i = 0; i < impl.numOutputs_; ++i) {
        for (auto& effectBus : impl.getEffectBusesForOutput(i))
            if (effectBus)
                effectBus->clear();
    }
}
''', r'''
void Synth::captureOfflineBaseline()
{
    Impl& impl = *impl_;
    impl.resources_.getFilePool().waitForBackgroundLoading();
    impl.offlineMidiState_ = impl.resources_.getMidiState().captureRuntimeState();
    impl.offlineCurrentSwitch_ = impl.currentSwitch_;
    impl.offlineLayerStates_.clear();
    impl.offlineLayerStates_.reserve(impl.layers_.size());
    for (const Impl::LayerPtr& layer : impl.layers_)
        impl.offlineLayerStates_.push_back(layer->captureRuntimeState());
    impl.offlineBaselineReady_ = true;
}

void Synth::prepareOfflineTask(unsigned int seed)
{
    Impl& impl = *impl_;
    SFIZZ_CHECK(impl.offlineBaselineReady_);
    if (!impl.offlineBaselineReady_ || impl.offlineLayerStates_.size() != impl.layers_.size())
        return;

    // Runtime teardown only: keep FilePool, regions, effect graph and voice capacity.
    impl.voiceManager_.resetRuntimeState();
    for (int i = 0; i < impl.numOutputs_; ++i) {
        for (auto& effectBus : impl.getEffectBusesForOutput(i))
            if (effectBus)
                effectBus->clear();
    }

    impl.resources_.getMidiState().restoreRuntimeState(impl.offlineMidiState_);
    impl.currentSwitch_ = impl.offlineCurrentSwitch_;
    for (size_t i = 0; i < impl.layers_.size(); ++i)
        impl.layers_[i]->restoreRuntimeState(impl.offlineLayerStates_[i]);

    impl.resources_.getBeatClock().clear();
    impl.changedCCsThisCycle_.clear();
    impl.changedCCsLastCycle_.clear();
    impl.playheadMoved_ = false;
    impl.dispatchDuration_ = 0.0;
    impl.genController_->resetSmoothers();
    impl.randNoteDistribution_.reset();

    Random::randomGenerator.seed(seed);
}
''')

    # Export the two narrow C ABI hooks used by the dlopen prototype.
    c_header = repo / "src/sfizz.h"
    insert_after(c_header, "SFIZZ_EXPORTED_API void sfizz_all_sound_off(sfizz_synth_t* synth);\n", r'''
/** Experimental MRP offline-render API: capture canonical post-load runtime state. */
SFIZZ_EXPORTED_API void sfizz_capture_offline_baseline(sfizz_synth_t* synth);
/** Experimental MRP offline-render API: restore runtime baseline and deterministic RNG seed. */
SFIZZ_EXPORTED_API void sfizz_prepare_offline_task(sfizz_synth_t* synth, unsigned int seed);
''')
    wrapper = repo / "src/sfizz/sfizz_wrapper.cpp"
    insert_after(wrapper, "void sfizz_all_sound_off(sfizz_synth_t* synth)\n{\n    return synth->synth.allSoundOff();\n}\n", r'''
void sfizz_capture_offline_baseline(sfizz_synth_t* synth)
{
    synth->synth.captureOfflineBaseline();
}
void sfizz_prepare_offline_task(sfizz_synth_t* synth, unsigned int seed)
{
    synth->synth.prepareOfflineTask(seed);
}
''')

    # A basic sanity check catches whitespace/compiler warnings in the patch itself.
    subprocess.run(["git", "-C", str(repo), "diff", "--check"], check=True)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("repo", type=Path)
    ns = ap.parse_args()
    repo = ns.repo.resolve()
    apply(repo)
    print(f"patched sfizz {EXPECTED[:12]} for minimal offline baseline experiment")
    print(git(repo, "status", "--short"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
