import { NextResponse } from "next/server"
import { generateText } from "ai"
import { openai } from "@ai-sdk/openai"

type Body = {
  query: string
  category: string
  websites: { name: string; url: string; notes?: string }[]
}

export async function POST(req: Request) {
  try {
    const body = (await req.json()) as Body
    const { query, category, websites } = body

    if (!query || !category || !Array.isArray(websites) || websites.length === 0) {
      return NextResponse.json({ error: "Invalid request" }, { status: 400 })
    }

    const siteList = websites
      .map((w, i) => `${i + 1}. ${w.name} (${w.url})${w.notes ? ` - ${w.notes}` : ""}`)
      .join("\n")

    const prompt = `
You are helping a shopper decide where to buy a product.
Task: For each website, write a single concise sentence explaining why it's a good place to buy for the user's request.

User query: "${query}"
Detected category: "${category}"

Websites:
${siteList}

Rules:
- Be specific and helpful (selection, prices, delivery, returns, warranty, filters, reviews, availability).
- Keep each reason under 18 words.
- Do not fabricate fees, delivery times, or policies.
- Output strict JSON array: [{"url":"...","reason":"..."}] in the same order as provided websites.
- No markdown, no extra text.
`

    let text: string
    try {
      const result = await generateText({
        model: openai("gpt-4o-mini"),
        prompt,
      })
      text = result.text
    } catch (err) {
      // Fallback when API key/model is unavailable
      const fallback = websites.map((w) => ({
        url: w.url,
        reason: w.notes || `Reliable option for ${category}; compare prices and reviews for "${query}".`,
      }))
      return NextResponse.json({ reasons: fallback })
    }

    // Try to parse model output
    let parsed: { url: string; reason: string }[] | null = null
    try {
      parsed = JSON.parse(text)
    } catch {
      parsed = null
    }

    // Validate and fallback if parsing fails
    if (!parsed || !Array.isArray(parsed)) {
      const fallback = websites.map((w) => ({
        url: w.url,
        reason: w.notes || `Popular store for ${category}; check availability and deals for "${query}".`,
      }))
      return NextResponse.json({ reasons: fallback })
    }

    // Basic sanitation and cap length just in case
    const sanitized = parsed.map((r) => ({
      url: String(r.url),
      reason: String(r.reason).slice(0, 300),
    }))

    return NextResponse.json({ reasons: sanitized })
  } catch (e) {
    return NextResponse.json({ error: "Unexpected error" }, { status: 500 })
  }
}
