/** Tiny keyword helpers: lowercase words ≥ 3 letters, no filler words, simple plural stripping. */
const STOP = new Set(["the", "and", "for", "can", "any", "anyone", "have", "does", "someone", "who", "with", "need", "borrow",
  "near", "me", "my", "dorm", "available", "this", "next", "that", "you", "your", "use", "could", "would", "please", "help",
  "looking", "want", "lend", "some", "get", "tonight", "today", "tomorrow", "weekend", "week", "in", "a", "an", "i", "of", "to"]);

function singular(t: string): string {
  if (t.length > 4 && /(x|ch|sh|ss)es$/.test(t)) return t.slice(0, -2);
  if (t.length > 3 && t.endsWith("s") && !t.endsWith("ss")) return t.slice(0, -1);
  return t;
}

export function tokens(text: string): string[] {
  return text.toLowerCase().replace(/[^a-z0-9\s-]/g, " ").split(/\s+/)
    .map(singular)
    .filter((t) => t.length >= 3 && !STOP.has(t));
}

export function overlap(a: string[], b: string[]): number {
  const set = new Set(b);
  return a.filter((t) => set.has(t)).length;
}

