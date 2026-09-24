import Knob from "./Knob";

const RELAY = "http://localhost:5010";

// Relay forwards each change to the artist's cue DSP over UDP.
export const sendCue = async (param, value) => {
  try {
    await fetch(`${RELAY}/cue/${param}/${value}`, { method: "POST" });
  } catch {}
};

const KNOBS = [
  ["Reverb",  "rev",    "#2dd4bf"],
  ["Rev mix", "revMix", "#2dd4bf"],
  ["Delay",   "del",    "#4f8fff"],
  ["Del mix", "delMix", "#4f8fff"],
  ["Comp",    "comp",   "#a78bfa"],
  ["Cue vol", "vol",    "#e8e8ea"],
];

// The six cue knobs. "embedded" = main window (3 columns, labels only);
// "popout" = detached window (2 columns, larger knobs with values).
// The caller owns the state.
export default function CueMix({ cue, onChange, variant = "embedded" }) {
  const popout = variant === "popout";
  return (
    <div className={popout ? "cue-grid cue-grid-pop" : "cue-grid"}>
      {KNOBS.map(([label, k, color]) => (
        <Knob
          key={k} label={label} value={cue[k]} color={color}
          size={popout ? 46 : 42} showValue={popout}
          onChange={v => onChange(k, v)}
        />
      ))}
    </div>
  );
}
