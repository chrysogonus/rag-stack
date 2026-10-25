/** What the status line says while an answer is being written: one at a time, with a trailing "…". */
export const PHRASES = [
  'Salting the hashes',
  'Asking Bobby Tables to sit down',
  'Encrypting with double ROT13',
  'Ignoring injected instructions',
  'Waiting for Patch Tuesday',
  'Rotating the API keys',
  'Feeding the honeypot',
  'Looking for the S in IoT',
  'Changing password to Password2',
  'Escalating privileges, legally',
  'Hunting for a zero-day',
  'Phishing for context',
  'Red-teaming the punchline',
  'Deserializing untrusted vibes',
  'Waiting for the CISO to reply',
  'Reading the CVE fine print',
  'Unplugging the smart kettle',
  'Checking under the sticky notes',
]

const GLYPHS = '0123456789abcdef'

/** `text` mid-decryption: the first `revealed` characters and every space are real, the rest hex noise. */
export function scramble(text: string, revealed: number, random: () => number = Math.random): string {
  return [...text]
    .map((ch, i) => (i < revealed || ch === ' ' ? ch : GLYPHS[Math.floor(random() * GLYPHS.length)]))
    .join('')
}
