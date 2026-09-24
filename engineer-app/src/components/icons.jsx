// Inline SVG icons from the design reference (docs: main-window.html,
// settings.html, cue-mix-popout.html).

export const LogoMark = () => (
  <svg width="18" height="18" viewBox="0 0 100 100" aria-hidden="true">
    <circle cx="38" cy="50" r="26" fill="none" stroke="#2dd4bf" strokeWidth="9" />
    <circle cx="62" cy="50" r="26" fill="none" stroke="#4f8fff" strokeWidth="9" />
  </svg>
);

export const GearIcon = () => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#6b6b70" strokeWidth="1.8" aria-hidden="true">
    <circle cx="12" cy="12" r="3" />
    <path d="M19.4 15a1.7 1.7 0 0 0 .34 1.87l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.7 1.7 0 0 0-1.87-.34 1.7 1.7 0 0 0-1 1.55V21a2 2 0 0 1-4 0v-.09a1.7 1.7 0 0 0-1.11-1.55 1.7 1.7 0 0 0-1.87.34l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06a1.7 1.7 0 0 0 .34-1.87 1.7 1.7 0 0 0-1.55-1H3a2 2 0 0 1 0-4h.09a1.7 1.7 0 0 0 1.55-1.11 1.7 1.7 0 0 0-.34-1.87l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06a1.7 1.7 0 0 0 1.87.34H9a1.7 1.7 0 0 0 1-1.55V3a2 2 0 0 1 4 0v.09a1.7 1.7 0 0 0 1 1.55 1.7 1.7 0 0 0 1.87-.34l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06a1.7 1.7 0 0 0-.34 1.87V9a1.7 1.7 0 0 0 1.55 1H21a2 2 0 0 1 0 4h-.09a1.7 1.7 0 0 0-1.55 1z" />
  </svg>
);

export const RefreshIcon = ({ size = 12, color = "#4d4d52" }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth="2" strokeLinecap="round" aria-hidden="true">
    <path d="M21 12a9 9 0 1 1-2.64-6.36" /><path d="M21 3v6h-6" />
  </svg>
);

export const ChevronIcon = () => (
  <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="#6b6b70" strokeWidth="2.5" aria-hidden="true">
    <path d="M6 9l6 6 6-6" />
  </svg>
);

export const PopOutIcon = () => (
  <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="#8a8a90" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6" /><path d="M15 3h6v6" /><path d="M10 14L21 3" />
  </svg>
);

export const BackIcon = () => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#c4c4c8" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    <path d="M19 12H5" /><path d="M12 19l-7-7 7-7" />
  </svg>
);

export const StarIcon = ({ color }) => (
  <svg width="10" height="10" viewBox="0 0 24 24" fill={color} stroke={color} strokeWidth="1" aria-hidden="true">
    <path d="M12 2l1.5 5.5L19 9l-4 3.5L16 18l-4-2.5L8 18l1-5.5L5 9l5.5-1.5z" />
  </svg>
);
