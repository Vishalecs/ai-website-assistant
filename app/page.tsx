import { Suspense } from "react"
import WebsiteSuggester from "@/components/website-suggester"

export default function Page() {
  return (
    <main className="min-h-dvh flex items-start justify-center px-4 py-10">
      <div className="w-full max-w-xl space-y-6">
        <header className="space-y-3 rounded-xl border bg-card p-6 shadow-sm">
          <h1 className="text-2xl md:text-3xl font-semibold text-balance">Find the best places to buy</h1>
          <p className="text-sm text-muted-foreground text-pretty">
            Describe what you want to buy. We’ll detect the category and suggest trusted websites with quick reasoning.
          </p>
        </header>
        <Suspense fallback={<div className="text-sm text-muted-foreground">Loading…</div>}>
          <WebsiteSuggester />
        </Suspense>
      </div>
    </main>
  )
}
