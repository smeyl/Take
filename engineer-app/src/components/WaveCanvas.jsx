import { useEffect, useRef } from "react";
import C from "../constants/colors";

export default function WaveCanvas({ width = 200, height = 40, color = C.blue, animated = false, progress = 1 }) {
  const ref = useRef();
  useEffect(() => {
    const canvas = ref.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    canvas.width = width; canvas.height = height;
    const bars = Math.floor(width / 3);
    let frame, t = 0;
    const draw = () => {
      ctx.clearRect(0, 0, width, height);
      const mid = height / 2;
      for (let i = 0; i < bars; i++) {
        const x = i * 3;
        const phase = animated ? Math.sin(i * 0.28 + t) * 0.6 + 0.4 : Math.abs(Math.sin(i * 0.43 + i * 0.11)) * 0.8 + 0.2;
        const amp = phase * (mid * 0.85) + 1;
        ctx.fillStyle = (x / width) < progress ? color + "bb" : C.dim;
        ctx.fillRect(x, mid - amp, 2, amp * 2);
      }
      if (animated) { t += 0.05; frame = requestAnimationFrame(draw); }
    };
    draw();
    return () => cancelAnimationFrame(frame);
  }, [width, height, color, animated, progress]);
  return <canvas ref={ref} style={{ display: "block", width: "100%", height }} />;
}
