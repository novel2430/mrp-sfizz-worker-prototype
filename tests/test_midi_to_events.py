import sys, tempfile, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import mido
from midi_to_events import convert

class TestMidiToEvents(unittest.TestCase):
    def test_basic_timing_and_events(self):
        with tempfile.TemporaryDirectory() as td:
            td = Path(td); midi = td / "a.mid"; ev = td / "a.mrpev"
            mf = mido.MidiFile(ticks_per_beat=480); tr = mido.MidiTrack(); mf.tracks.append(tr)
            tr.append(mido.MetaMessage("set_tempo", tempo=500000, time=0))
            tr.append(mido.Message("note_on", note=60, velocity=64, time=0))
            tr.append(mido.Message("control_change", control=64, value=127, time=480))
            tr.append(mido.Message("note_off", note=60, velocity=0, time=480))
            mf.save(midi)
            info = convert(midi, ev, 48000)
            text = ev.read_text()
            self.assertIn("0 note_on 60 64", text)
            self.assertIn("24000 cc 64 127", text)
            self.assertIn("48000 note_off 60 0", text)
            self.assertEqual(info["end_frame"], 48000)

if __name__ == "__main__": unittest.main()
