import C from "../constants/colors";
import Knob from "./Knob";

const RELAY = "http://localhost:5010";

// Relay forwards each change to the artist's cue DSP over UDP.
export const sendCue = async (param, value) => {
  try {
    await fetch(`${RELAY}/cue/${param}/${value}`, { method: "POST" });
  } catch {}
};

const KNOBS = [
  ["Reverb",  "rev",    C.purple],
  ["Rev mix", "revMix", C.purple],
  ["Delay",   "del",    C.teal],
  ["Del mix", "delMix", C.teal],
  ["Comp",    "comp",   C.amber],
  ["Cue vol", "vol",    C.green],
];

// The six cue knobs in a 3-column grid. Rendered embedded in the main window
// or on its own in the detached cue window — the caller owns the state.
export default function CueMix({ cue, onChange }) {
  return (
    <div className="cue-grid">
      {KNOBS.map(([label, k, color]) => (
        <Knob key={k} label={label} value={cue[k]} color={color} onChange={v => onChange(k, v)} />
      ))}
    </div>
  );
}
