type CategoryDef = { id: string; keywords: string[] }

function normalizeQuery(q: string) {
  return ` ${q.toLowerCase()} `
}

function toCategoryArray(defs: { categories: CategoryDef[] } | Record<string, string[]>): CategoryDef[] {
  // If the old shape is provided, return it directly
  if (defs && typeof defs === "object" && "categories" in defs && Array.isArray((defs as any).categories)) {
    return (defs as { categories: CategoryDef[] }).categories
  }
  // Otherwise, convert from Record<string, string[]> to CategoryDef[]
  const rec = defs as Record<string, string[]>
  return Object.entries(rec).map(([id, keywords]) => ({
    id,
    keywords: Array.isArray(keywords) ? keywords : [],
  }))
}

// Normalize and test if any keyword appears in the query string
export function extractCategory(
  query: string,
  categoryDefs: { categories: CategoryDef[] } | Record<string, string[]>,
): string | null {
  const q = normalizeQuery(query)
  let best: { id: string; hits: number } | null = null

  const list = toCategoryArray(categoryDefs)
  for (const c of list) {
    let hits = 0
    for (const kw of c.keywords) {
      // Simple substring match on lowercase with spacing to reduce false positives
      const k = ` ${kw.toLowerCase()} `
      if (q.includes(k)) hits++
      // Basic fallback: allow direct includes without padding for multi-word phrases
      else if (q.includes(kw.toLowerCase())) hits++
    }
    if (hits > 0) {
      if (!best || hits > best.hits) best = { id: c.id, hits }
    }
  }
  return best?.id ?? null
}
