import React from "react";

const STAGES = [
  { id: "01", label: "INK PLATE DROP", status: "READY" },
  { id: "02", label: "PRETEXT STREAM & JEV GATE", status: "STANDBY" },
  { id: "03", label: "PROOF SHEET RIBBON", status: "STANDBY" },
  { id: "04", label: "EPUB 3 / KFX PRESS", status: "STANDBY" },
] as const;

export default function HomePage() {
  return (
    <main className="mx-auto max-w-6xl px-6 py-10">
      {/* Broadsheet Masthead */}
      <header className="riso-card mb-8 bg-newsprint p-6">
        <div className="flex flex-wrap items-center justify-between gap-4 border-b-2 border-ink pb-4">
          <div className="flex items-center gap-3">
            <span className="inline-block border-2 border-ink bg-coral px-2.5 py-1 font-mono text-xs font-bold uppercase tracking-widest text-newsprint shadow-riso-sm">
              EDITION v0.1 • RISOGRAPH PRESS
            </span>
            <span className="inline-block border-2 border-ink bg-lime px-2.5 py-1 font-mono text-xs font-bold uppercase tracking-widest text-ink shadow-riso-sm">
              ZERO-SPOILER GUARANTEE
            </span>
          </div>
          <div className="font-mono text-xs uppercase tracking-wider">
            TARGET: KINDLE PAPERWHITE (.KFX / EPUB 3)
          </div>
        </div>

        <div className="mt-5 flex flex-col justify-between gap-4 md:flex-row md:items-end">
          <div>
            <h1 className="font-serif text-5xl font-black tracking-tight text-ink md:text-6xl">
              CairnBooks
            </h1>
            <p className="mt-2 max-w-2xl font-serif text-lg leading-relaxed text-ink/90">
              Kinetic EPUB 3 &amp; Kindle KFX compiler. Pinpoints character and
              lore reintroductions after long absences and injects native
              15-word spoiler-capped bottom-sheet footnote popups.
            </p>
          </div>
          <div className="border-2 border-ink bg-halftone px-4 py-3 font-mono text-xs">
            <div>TIER 1: TYPESAFE JEV / OPENROUTER</div>
            <div>TIER 2: MICRO-LLM (&lt;= 15 WORDS)</div>
          </div>
        </div>
      </header>

      {/* 4-Stage Compiler Registration Strip */}
      <section className="grid grid-cols-1 gap-4 md:grid-cols-4">
        {STAGES.map((stage) => (
          <div key={stage.id} className="riso-card bg-newsprint p-4">
            <div className="flex items-center justify-between font-mono text-xs font-bold">
              <span className="border border-ink bg-lime px-1.5 py-0.5">
                STAGE {stage.id}
              </span>
              <span className="text-ink/70">{stage.status}</span>
            </div>
            <h2 className="mt-3 font-mono text-sm font-bold uppercase tracking-wide">
              {stage.label}
            </h2>
          </div>
        ))}
      </section>
    </main>
  );
}
