"use client"

import type React from "react"
import type { ReasonResponse } from "@/types/reason-response"

import { useMemo, useState } from "react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import categories from "@/data/categories.json"
import websites from "@/data/websites.json"
import { extractCategory } from "@/lib/category"

function hostFromUrl(url: string) {
  try {
    return new URL(url).hostname.replace(/^www\./, "")
  } catch {
    return ""
  }
}

function toSlug(s: string) {
  return s
    .toLowerCase()
    .trim()
    .replace(/[^a-z0-9\s-]/g, "")
    .replace(/\s+/g, "-")
    .replace(/-+/g, "-")
}

function cleanQuery(input: string) {
  // remove currency words/symbols but keep numeric values and intent words like "under"
  let q = input.toLowerCase().trim()
  q = q.replace(/₹/g, "")
  q = q.replace(/\b(rs\.?|inr|rupees)\b/gi, "")
  q = q.replace(/[,]/g, "")
  return q.replace(/\s+/g, " ").trim()
}

function buildDeepLink(baseUrl: string, siteName: string, userQuery: string) {
  const q = cleanQuery(userQuery)
  const host = hostFromUrl(baseUrl)

  if (host.endsWith("amazon.in")) {
    return `https://www.amazon.in/s?k=${encodeURIComponent(q)}`
  }
  if (host.endsWith("flipkart.com")) {
    return `https://www.flipkart.com/search?q=${encodeURIComponent(q)}`
  }
  if (host.endsWith("croma.com")) {
    return `https://www.croma.com/search/?text=${encodeURIComponent(q)}`
  }
  if (host.endsWith("ajio.com")) {
    return `https://www.ajio.com/search/?text=${encodeURIComponent(q)}`
  }
  if (host.endsWith("myntra.com")) {
    const slug = toSlug(q) || "search"
    return `https://www.myntra.com/${slug}?rawQuery=${encodeURIComponent(q)}&p=1`
  }
  if (host.endsWith("ikea.com")) {
    return `https://www.ikea.com/in/en/search/?q=${encodeURIComponent(q)}`
  }
  if (host.endsWith("pepperfry.com")) {
    return `https://www.pepperfry.com/site_search/search?q=${encodeURIComponent(q)}`
  }
  if (host.endsWith("urbanladder.com")) {
    return `https://www.urbanladder.com/catalogsearch/result?q=${encodeURIComponent(q)}`
  }
  return baseUrl
}

type RawSite = { name: string; url: string; strengths?: string[] }
type WebsiteRecord = Record<string, RawSite[]>
type MatchedSite = { name: string; url: string; notes: string }

export default function WebsiteSuggester() {
  const [query, setQuery] = useState("")
  const [status, setStatus] = useState<"idle" | "loading" | "done" | "error">("idle")
  const [error, setError] = useState<string | null>(null)
  const [reasons, setReasons] = useState<ReasonResponse["reasons"]>([])

  const category = useMemo(() => extractCategory(query, categories), [query])

  const matchedSites = useMemo<MatchedSite[]>(() => {
    if (!category) return []
    const record = websites as unknown as WebsiteRecord
    const list = Array.isArray(record[category]) ? record[category] : []
    return list.map((s) => ({
      name: s.name,
      url: buildDeepLink(s.url, s.name, query),
      notes: Array.isArray(s.strengths) ? s.strengths.join(", ") : "",
    }))
  }, [category, query])

  const examples = ["I want to buy a laptop under ₹50,000", "Summer dresses under ₹1500", "Sofa set under ₹30,000"]

  async function handleSuggest(e: React.FormEvent) {
    e.preventDefault()
    setError(null)
    setReasons([])
    if (!query.trim()) {
      setError("Please enter what you’re looking to buy.")
      setStatus("error")
      return
    }
    if (!category) {
      setError(
        "Sorry, I couldn’t recognize the product category. Try being more specific (e.g., “laptop under ₹50,000”).",
      )
      setStatus("error")
      return
    }
    if (matchedSites.length === 0) {
      setError("No sites found for this category yet. Try a different description.")
      setStatus("error")
      return
    }
    try {
      setStatus("loading")
      const res = await fetch("/api/reason", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          query,
          category,
          websites: matchedSites.map((s) => ({ name: s.name, url: s.url, notes: s.notes })),
        }),
      })
      if (!res.ok) throw new Error("Failed to fetch reasoning")
      const data = (await res.json()) as ReasonResponse
      setReasons(data.reasons)
      setStatus("done")
    } catch (err: any) {
      setError("Couldn’t get AI reasoning. Showing simple suggestions instead.")
      const fallback = matchedSites.map((s) => ({
        url: s.url,
        reason: s.notes || `Popular choice for ${category}. Check prices, reviews, and availability for "${query}".`,
      }))
      setReasons(fallback)
      setStatus("done")
    }
  }

  const showResults = status === "done" && reasons.length > 0
  const isLoading = status === "loading"

  return (
    <div className="space-y-6">
      <form onSubmit={handleSuggest} className="flex flex-col gap-3">
        <div className="flex items-center gap-2">
          <label htmlFor="buy-query" className="sr-only">
            Describe what you want to buy
          </label>
          <Input
            id="buy-query"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder='e.g., "I want to buy a laptop under ₹50,000"'
          />
          <Button type="submit" disabled={isLoading}>
            {isLoading ? "Thinking…" : "Suggest"}
          </Button>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-xs text-muted-foreground">Try:</span>
          {examples.map((ex) => (
            <button
              key={ex}
              type="button"
              onClick={() => setQuery(ex)}
              className="text-xs rounded-full border px-3 py-1 hover:bg-accent hover:text-accent-foreground transition-colors"
            >
              {ex}
            </button>
          ))}
        </div>
      </form>

      <div className="flex items-center gap-2">
        <span className="text-sm text-muted-foreground">Detected category:</span>
        <Badge variant={category ? "default" : "secondary"} className="capitalize">
          {category || "Unknown"}
        </Badge>
      </div>

      {error && (
        <Alert variant="destructive" role="status">
          <AlertTitle>Couldn’t complete request</AlertTitle>
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      {isLoading && (
        <Card>
          <CardHeader>
            <CardTitle className="text-balance">Assistant’s suggestions</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            {[0, 1, 2].map((i) => (
              <div key={i} className="flex items-start gap-3">
                <div className="h-9 w-9 rounded-full bg-muted animate-pulse" />
                <div className="flex-1 space-y-2">
                  <div className="h-4 w-40 bg-muted rounded animate-pulse" />
                  <div className="h-4 w-3/4 bg-muted rounded animate-pulse" />
                </div>
              </div>
            ))}
          </CardContent>
        </Card>
      )}

      {showResults && (
        <Card>
          <CardHeader>
            <CardTitle className="text-balance">Assistant’s suggestions</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <ul className="space-y-3">
              {reasons.map(({ url, reason }) => {
                const site = matchedSites.find((s) => s.url === url)
                const name = site?.name || url.replace(/^https?:\/\//, "")
                const initial = name?.[0]?.toUpperCase() || "•"
                return (
                  <li key={url} className="rounded-lg border p-4 hover:bg-accent/50 transition-colors">
                    <div className="flex items-start gap-3">
                      <div className="h-9 w-9 rounded-full bg-primary/10 text-primary flex items-center justify-center font-medium">
                        {initial}
                      </div>
                      <div className="flex-1 space-y-1">
                        <a
                          href={url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="font-medium text-primary underline underline-offset-4"
                        >
                          {name}
                        </a>
                        <p className="text-sm text-muted-foreground">{reason}</p>
                      </div>
                    </div>
                  </li>
                )
              })}
            </ul>
            <p className="text-xs text-muted-foreground">
              Tips are generated using AI and may not always be perfect. Please verify availability and price on the
              site.
            </p>
          </CardContent>
        </Card>
      )}
    </div>
  )
}
