#pragma once

// Minimal subset of the libsfizz C ABI required by this prototype.
// The two offline-baseline functions are provided by the pinned MRP sfizz
// patch/fork; they are part of this prototype's required renderer contract.

#include <cstddef>

extern "C" {

struct sfizz_synth_t;

enum sfizz_process_mode_t {
    SFIZZ_PROCESS_LIVE = 0,
    SFIZZ_PROCESS_FREEWHEELING = 1,
};

using sfizz_create_synth_fn = sfizz_synth_t* (*)();
using sfizz_free_fn = void (*)(sfizz_synth_t*);
using sfizz_load_string_fn = bool (*)(sfizz_synth_t*, const char*, const char*);
using sfizz_set_samples_per_block_fn = void (*)(sfizz_synth_t*, int);
using sfizz_set_sample_rate_fn = void (*)(sfizz_synth_t*, float);
using sfizz_set_num_voices_fn = void (*)(sfizz_synth_t*, int);
using sfizz_set_sample_quality_fn = void (*)(sfizz_synth_t*, sfizz_process_mode_t, int);
using sfizz_enable_freewheeling_fn = void (*)(sfizz_synth_t*);
using sfizz_send_note_on_fn = void (*)(sfizz_synth_t*, int, int, int);
using sfizz_send_note_off_fn = void (*)(sfizz_synth_t*, int, int, int);
using sfizz_send_cc_fn = void (*)(sfizz_synth_t*, int, int, int);
using sfizz_send_pitch_wheel_fn = void (*)(sfizz_synth_t*, int, int);
using sfizz_render_block_fn = void (*)(sfizz_synth_t*, float**, int, int);
using sfizz_capture_offline_baseline_fn = void (*)(sfizz_synth_t*);
using sfizz_prepare_offline_task_fn = void (*)(sfizz_synth_t*, unsigned int);
using sfizz_get_num_active_voices_fn = int (*)(sfizz_synth_t*);
using sfizz_get_num_regions_fn = int (*)(sfizz_synth_t*);
using sfizz_get_num_preloaded_samples_fn = std::size_t (*)(sfizz_synth_t*);
using sfizz_get_num_bytes_fn = int (*)(sfizz_synth_t*);

} // extern "C"
