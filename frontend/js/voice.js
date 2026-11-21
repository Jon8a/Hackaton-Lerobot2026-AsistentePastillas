// Voz del sistema (síntesis del navegador, sin internet).

let enabled = (() => {
  try { return localStorage.getItem('pastibot.voice') !== 'off'; } catch { return true; }
})();

export const voiceEnabled = () => enabled;

export function toggleVoice() {
  enabled = !enabled;
  try { localStorage.setItem('pastibot.voice', enabled ? 'on' : 'off'); } catch { /* da igual */ }
  if (!enabled && 'speechSynthesis' in window) speechSynthesis.cancel();
  return enabled;
}

export function speak(text) {
  if (!enabled || !('speechSynthesis' in window)) return;
  const u = new SpeechSynthesisUtterance(text);
  u.lang = 'es-ES';
  u.rate = 0.95;
  const voice = speechSynthesis.getVoices().find((v) => v.lang.toLowerCase().startsWith('es'));
  if (voice) u.voice = voice;
  speechSynthesis.cancel();
  speechSynthesis.speak(u);
}
