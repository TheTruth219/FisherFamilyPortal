import React from "react";
export const FamilyMark = ({ className = "", testId }) => (
  <span className={`family-mark ${className}`} role="img" aria-label="Fisher family shield" data-testid={testId} style={{ WebkitMaskImage: "url('/brand/fisher-shield.svg')", maskImage: "url('/brand/fisher-shield.svg')" }} />
);

export const FamilyArtwork = ({ className = "" }) => (
  <div className={`family-artwork ${className}`} aria-hidden="true">
    <svg viewBox="0 0 440 440" fill="none">
      <circle cx="220" cy="220" r="192" className="art-orbit" />
      <circle cx="220" cy="220" r="157" className="art-orbit" />
      <g className="art-petals">
        {[0, 60, 120, 180, 240, 300].map((angle) => <ellipse key={angle} cx="220" cy="158" rx="71" ry="106" transform={`rotate(${angle} 220 220)`} />)}
      </g>
      <circle cx="220" cy="220" r="43" className="art-center" />
      <image href="/brand/fisher-shield.svg" x="201" y="194" width="38" height="52" data-testid={`artwork-symbol-${className}`} />
      <circle cx="385" cy="121" r="7" className="art-dot" />
      <circle cx="68" cy="337" r="5" className="art-dot" />
    </svg>
  </div>
);
