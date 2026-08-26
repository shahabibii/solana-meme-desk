/** Browser speech helpers for Onyx voice command. */

export type VoiceSupport = {
  listen: boolean;
  speak: boolean;
};

type RecognitionLike = {
  continuous: boolean;
  interimResults: boolean;
  lang: string;
  start: () => void;
  stop: () => void;
  abort: () => void;
  onresult: ((ev: Event) => void) | null;
  onerror: ((ev: Event) => void) | null;
  onend: (() => void) | null;
};

function getRecognitionCtor(): (new () => RecognitionLike) | null {
  const w = window as Window & {
    SpeechRecognition?: new () => RecognitionLike;
    webkitSpeechRecognition?: new () => RecognitionLike;
  };
  return w.SpeechRecognition ?? w.webkitSpeechRecognition ?? null;
}

export function voiceSupport(): VoiceSupport {
  return {
    listen: Boolean(getRecognitionCtor()),
    speak: typeof window !== "undefined" && "speechSynthesis" in window,
  };
}

function pickOnyxVoice(voices: SpeechSynthesisVoice[]): SpeechSynthesisVoice | null {
  const rank = (v: SpeechSynthesisVoice): number => {
    const n = `${v.name} ${v.lang}`;
    if (/Google UK English Female/i.test(n)) return 100;
    if (/Microsoft (Sonia|Hazel|Susan)/i.test(n)) return 95;
    if (/Karen|Moira|Tessa|Fiona|Serena/i.test(n)) return 90;
    if (/Samantha|Victoria|Kathy|Allison|Ava|Zoe/i.test(n) && /en/i.test(v.lang)) return 80;
    if (/female|woman/i.test(n) && /^en(-|_|$)/i.test(v.lang)) return 70;
    if (/^en-GB|^en-AU|^en-IE/i.test(v.lang) && !/male|daniel|david|arthur|george/i.test(n))
      return 60;
    if (/^en/i.test(v.lang) && !/male|daniel|david|arthur|alex|fred|jorge/i.test(n)) return 40;
    return 0;
  };
  const scored = voices
    .map((v) => ({ v, s: rank(v) }))
    .filter((x) => x.s > 0)
    .sort((a, b) => b.s - a.s);
  return scored[0]?.v ?? null;
}

function stripMarkdownForSpeech(text: string): string {
  return text
    .replace(/\*\*?/g, "")
    .replace(/`+/g, "")
    .replace(/#{1,6}\s*/g, "")
    .replace(/\n+/g, ". ")
    .trim();
}

export function speakText(text: string, enabled: boolean): void {
  if (!enabled || !text.trim() || !("speechSynthesis" in window)) return;
  window.speechSynthesis.cancel();
  const clean = stripMarkdownForSpeech(text).slice(0, 520);
  if (!clean) return;

  const speakNow = () => {
    const u = new SpeechSynthesisUtterance(clean);
    u.rate = 0.92;
    u.pitch = 1.12;
    u.lang = "en-GB";
    const preferred = pickOnyxVoice(window.speechSynthesis.getVoices());
    if (preferred) {
      u.voice = preferred;
      u.lang = preferred.lang || "en-GB";
    }
    window.speechSynthesis.speak(u);
  };

  const voices = window.speechSynthesis.getVoices();
  if (!voices.length) {
    window.speechSynthesis.onvoiceschanged = () => {
      window.speechSynthesis.onvoiceschanged = null;
      speakNow();
    };
    window.setTimeout(speakNow, 250);
    return;
  }
  speakNow();
}

export function startListening(opts: {
  onInterim?: (text: string) => void;
  onFinal: (text: string) => void;
  onError: (message: string) => void;
  onEnd: () => void;
}): { stop: () => void } | null {
  const Ctor = getRecognitionCtor();
  if (!Ctor) {
    opts.onError("Voice not supported in this browser. Use Chrome or Edge.");
    return null;
  }
  const rec = new Ctor();
  rec.continuous = false;
  rec.interimResults = true;
  rec.lang = "en-US";

  rec.onresult = (ev: Event) => {
    const e = ev as unknown as {
      resultIndex: number;
      results: {
        length: number;
        [i: number]: { isFinal: boolean; 0: { transcript: string } };
      };
    };
    let interim = "";
    let finalText = "";
    for (let i = e.resultIndex; i < e.results.length; i++) {
      const t = e.results[i][0].transcript;
      if (e.results[i].isFinal) finalText += t;
      else interim += t;
    }
    if (interim) opts.onInterim?.(interim);
    if (finalText.trim()) opts.onFinal(finalText.trim());
  };

  rec.onerror = (ev: Event) => {
    const err = ev as unknown as { error?: string };
    if (err.error === "aborted" || err.error === "no-speech") {
      opts.onEnd();
      return;
    }
    opts.onError(err.error ?? "voice error");
  };

  rec.onend = () => opts.onEnd();

  try {
    rec.start();
  } catch {
    opts.onError("Could not start microphone.");
    return null;
  }

  return {
    stop: () => {
      try {
        rec.stop();
      } catch {
        /* ignore */
      }
    },
  };
}
