const GLYPHS = '0123456789abcdef'

/** `text` mid-decryption: the first `revealed` characters and every space are real, the rest hex noise. */
export function scramble(text: string, revealed: number, random: () => number = Math.random): string {
  return [...text]
    .map((ch, i) => (i < revealed || ch === ' ' ? ch : GLYPHS[Math.floor(random() * GLYPHS.length)]))
    .join('')
}
