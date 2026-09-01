#include "sfizz_abi_min.h"
#include <algorithm>
#include <cmath>
#include <cstddef>
#include <string>
#include <vector>

struct sfizz_synth_t {
    int sr = 48000, block = 1024, voices = 64;
    float phase = 0.0f;
    int note = -1, velocity = 0;
    bool sustain = false;
    bool loaded = false;
    float baseline_phase = 0.0f;
    bool baseline_sustain = false;
};
extern "C" {
sfizz_synth_t* sfizz_create_synth(){ return new sfizz_synth_t; }
void sfizz_free(sfizz_synth_t* s){ delete s; }
bool sfizz_load_file(sfizz_synth_t* s,const char*){ s->loaded=true; s->note=-1; s->phase=0; return true; }
void sfizz_set_samples_per_block(sfizz_synth_t* s,int n){s->block=n;}
void sfizz_set_sample_rate(sfizz_synth_t* s,float n){s->sr=(int)n;}
void sfizz_set_num_voices(sfizz_synth_t* s,int n){s->voices=n;}
void sfizz_set_sample_quality(sfizz_synth_t*,sfizz_process_mode_t,int){}
void sfizz_enable_freewheeling(sfizz_synth_t*){}
void sfizz_send_note_on(sfizz_synth_t* s,int,int note,int vel){s->note=note;s->velocity=vel;}
void sfizz_send_note_off(sfizz_synth_t* s,int,int note,int){if(s->note==note&&!s->sustain)s->note=-1;}
void sfizz_send_cc(sfizz_synth_t* s,int,int cc,int val){if(cc==64){s->sustain=val>=64;if(!s->sustain&&s->velocity==0)s->note=-1;} if(cc==121)s->sustain=false;}
void sfizz_send_pitch_wheel(sfizz_synth_t*,int,int){}
void sfizz_render_block(sfizz_synth_t* s,float** ch,int nc,int frames){
    if(nc!=2)return; const float pi=3.14159265358979323846f;
    for(int i=0;i<frames;++i){float x=0; if(s->note>=0){float f=440.0f*std::pow(2.0f,(s->note-69)/12.0f);x=0.1f*std::sin(s->phase);s->phase+=2*pi*f/s->sr;} ch[0][i]=x;ch[1][i]=x;}
}
unsigned int sfizz_get_offline_render_api_version(){return 1;}
void sfizz_set_offline_ram_loading(sfizz_synth_t*,bool){}
bool sfizz_seal_offline_instrument(sfizz_synth_t* s){if(!s->loaded)return false;s->baseline_phase=s->phase;s->baseline_sustain=s->sustain;return true;}
bool sfizz_begin_offline_task(sfizz_synth_t* s,unsigned int){if(!s->loaded)return false;s->note=-1;s->velocity=0;s->phase=s->baseline_phase;s->sustain=s->baseline_sustain;return true;}
int sfizz_get_num_active_voices(sfizz_synth_t* s){return s->note>=0?1:0;}
int sfizz_get_num_regions(sfizz_synth_t*){return 1;}
std::size_t sfizz_get_num_preloaded_samples(sfizz_synth_t*){return 1234;}
int sfizz_get_num_bytes(sfizz_synth_t*){return 5678;}
}
