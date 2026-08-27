/** Inline Jarvis SVG — matches design/onyx-logo-original-purple-jarvis.svg */
export default function JarvisLogo() {
  return (
    <svg viewBox="0 0 400 340" aria-hidden>
      <defs>
        <linearGradient id="jarvisP" x1="0%" y1="0%" x2="0%" y2="100%">
          <stop offset="0%" stopColor="#E0CCF5" />
          <stop offset="30%" stopColor="#FFFFFF" />
          <stop offset="60%" stopColor="#B09AD0" />
          <stop offset="100%" stopColor="#7A6BA0" />
        </linearGradient>
        <radialGradient id="jarvisGlow" cx="50%" cy="50%" r="50%">
          <stop offset="0%" stopColor="rgba(180,150,220,0.25)" />
          <stop offset="60%" stopColor="rgba(180,150,220,0.05)" />
          <stop offset="100%" stopColor="rgba(180,150,220,0)" />
        </radialGradient>
        <linearGradient id="jarvisSweep" x1="0%" y1="0%" x2="100%" y2="0%">
          <stop offset="0%" stopColor="rgba(255,255,255,0)" />
          <stop offset="70%" stopColor="rgba(255,255,255,0)" />
          <stop offset="95%" stopColor="rgba(255,255,255,0.5)" />
          <stop offset="100%" stopColor="rgba(255,255,255,0)" />
        </linearGradient>
      </defs>
      <style>{`
        .jv-ring-outer{animation:jv-rot-cw 24s linear infinite;transform-origin:200px 170px}
        .jv-ring-mid{animation:jv-rot-ccw 16s linear infinite;transform-origin:200px 170px}
        .jv-ring-inner{animation:jv-rot-cw 10s linear infinite;transform-origin:200px 170px}
        .jv-sweep{animation:jv-rot-cw 4s linear infinite;transform-origin:200px 170px}
        .jv-hex{animation:jv-pulse 3s ease-in-out infinite;transform-origin:200px 170px}
        @keyframes jv-rot-cw{from{transform:rotate(0deg)}to{transform:rotate(360deg)}}
        @keyframes jv-rot-ccw{from{transform:rotate(360deg)}to{transform:rotate(0deg)}}
        @keyframes jv-pulse{0%,100%{opacity:.65}50%{opacity:1}}
        .core.speaking .jv-hex{animation-duration:.8s}
      `}</style>
      <circle cx="200" cy="170" r="160" fill="url(#jarvisGlow)" />
      <g className="jv-ring-outer">
        <circle cx="200" cy="170" r="155" fill="none" stroke="url(#jarvisP)" strokeWidth="1" strokeDasharray="2,10" opacity="0.45" />
        <circle cx="200" cy="170" r="150" fill="none" stroke="url(#jarvisP)" strokeWidth="0.5" opacity="0.25" />
        <path d="M 200,15 A 155,155 0 0 1 355,170" fill="none" stroke="url(#jarvisP)" strokeWidth="2" opacity="0.6" />
        <path d="M 200,325 A 155,155 0 0 1 45,170" fill="none" stroke="url(#jarvisP)" strokeWidth="2" opacity="0.6" />
        <path d="M 200,8 L 200,22 M 8,170 L 22,170 M 392,170 L 378,170 M 200,332 L 200,318" stroke="url(#jarvisP)" strokeWidth="2" opacity="0.7" />
      </g>
      <g className="jv-ring-mid">
        <circle cx="200" cy="170" r="120" fill="none" stroke="url(#jarvisP)" strokeWidth="1" strokeDasharray="30,8,4,8" opacity="0.35" />
        <path d="M 80,170 A 120,120 0 0 1 200,50" fill="none" stroke="url(#jarvisP)" strokeWidth="1.5" opacity="0.5" />
        <path d="M 320,170 A 120,120 0 0 1 200,290" fill="none" stroke="url(#jarvisP)" strokeWidth="1.5" opacity="0.5" />
      </g>
      <g className="jv-ring-inner">
        <circle cx="200" cy="170" r="95" fill="none" stroke="url(#jarvisP)" strokeWidth="0.5" strokeDasharray="1,5" opacity="0.3" />
      </g>
      <g className="jv-sweep">
        <path d="M 200,170 L 200,15 A 155,155 0 0 1 310,75 Z" fill="url(#jarvisSweep)" opacity="0.15" />
        <line x1="200" y1="170" x2="200" y2="15" stroke="url(#jarvisP)" strokeWidth="1" opacity="0.5" />
      </g>
      <g className="jv-hex" transform="translate(50,30)" stroke="url(#jarvisP)" fill="none">
        <polygon points="150,40 240,90 240,190 150,240 60,190 60,90" strokeWidth="4" strokeLinejoin="round" />
        <line x1="150" y1="40" x2="150" y2="70" strokeWidth="3" />
        <line x1="150" y1="240" x2="150" y2="210" strokeWidth="2" />
        <line x1="60" y1="90" x2="90" y2="105" strokeWidth="2" />
        <line x1="240" y1="90" x2="210" y2="105" strokeWidth="2" />
        <line x1="60" y1="190" x2="90" y2="175" strokeWidth="2" />
        <line x1="240" y1="190" x2="210" y2="175" strokeWidth="2" />
        <polygon points="150,70 210,105 210,175 150,210 90,175 90,105" strokeWidth="1.5" strokeDasharray="2,2" />
        <polygon points="150,95 190,118 190,162 150,185 110,162 110,118" strokeWidth="3" />
      </g>
      <circle cx="200" cy="170" r="3" fill="url(#jarvisP)" />
    </svg>
  );
}
