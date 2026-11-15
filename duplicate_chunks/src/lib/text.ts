// Client-side copies of the analyzer's text features, so the compare view can
// score any two chunks, not only the pairs the analyzer reported.

export function normalize(text: string): string {
  return text
    .toLowerCase()
    .replace(/<[^>]+>/g, " ")
    .replace(/[#*_`>|~]+/g, " ")
    .replace(/-{2,}/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

const tokenize = (norm: string) => norm.match(/[a-z0-9]+(?:[.,][0-9]+)*%?/g) ?? [];

export function shingleSet(text: string, k: number): Set<string> {
  const tokens = tokenize(normalize(text));
  const out = new Set<string>();
  if (!tokens.length) return out;
  if (tokens.length < k) {
    out.add(tokens.join(" "));
    return out;
  }
  for (let i = 0; i + k <= tokens.length; i++) out.add(tokens.slice(i, i + k).join(" "));
  return out;
}

export function similarity(a: string, b: string, k: number) {
  const sa = shingleSet(a, k);
  const sb = shingleSet(b, k);
  const [small, large] = sa.size <= sb.size ? [sa, sb] : [sb, sa];
  let inter = 0;
  for (const x of small) if (large.has(x)) inter++;
  const union = sa.size + sb.size - inter;
  return {
    exact: normalize(a) === normalize(b),
    jaccard: union ? inter / union : 0,
    containment: small.size ? inter / small.size : 0,
    shared: inter,
  };
}

export const numbersIn = (text: string) =>
  new Set((text.match(/\$?\d[\d,]*(?:\.\d+)?(?:%|[A-Z](?![A-Za-z]))?/g) ?? []).map((n) => n.replace(/,/g, "")));

export function numberDiff(a: string, b: string) {
  const na = numbersIn(a);
  const nb = numbersIn(b);
  return {
    onlyA: [...na].filter((n) => !nb.has(n)),
    onlyB: [...nb].filter((n) => !na.has(n)),
  };
}
