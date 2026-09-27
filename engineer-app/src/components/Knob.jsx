import { useEffect, useRef } from "react";

// One knob, identical to the artist app's (docs/artist-window.html): 42 px
// outer, 2 px border, a 2 x 13 px tick turning about the centre from 3 to
// 16 px out, 9.5 px label 5 px below. The popout also shows the value.
export default function Knob({ label, value, color, onChange, showValue = false }) {
  const angle = -135 + (value / 100) * 270;
  const isDragging = useRef(false);
  const startY = useRef(0);
  const startVal = useRef(0);
  const onDown = (e) => { isDragging.current = true; startY.current = e.clientY; startVal.current = value; e.preventDefault(); };
  useEffect(() => {
    const onMove = (e) => { if (!isDragging.current) return; const dy = startY.current - e.clientY; onChange(Math.min(100, Math.max(0, Math.round(startVal.current + dy)))); };
    const onUp = () => { isDragging.current = false; };
    window.addEventListener("mousemove", onMove);
    window.addEventListener("mouseup", onUp);
    return () => { window.removeEventListener("mousemove", onMove); window.removeEventListener("mouseup", onUp); };
  }, [onChange]);

  return (
    <div className="knob-wrap">
      <div className="knob" style={{ borderColor: color }} onMouseDown={onDown}>
        <div className="knob-tick" style={{ background: color, transform: `translateX(-50%) rotate(${angle}deg)` }} />
      </div>
      <span className="knob-lbl">{label}</span>
      {showValue && <span className="knob-val">{value}</span>}
    </div>
  );
}
