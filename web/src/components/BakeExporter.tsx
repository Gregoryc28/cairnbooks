"use client";

import React, { useState } from "react";
import { Download, Hammer, CheckCircle, AlertCircle } from "lucide-react";
import { getDownloadUrl } from "@/lib/api";
import type { BakeResponse } from "@/lib/types";

export interface BakeExporterProps {
  jobId: string | null;
  enabledAnchorsCount: number;
  totalAnchorsCount: number;
  onBake: (compileKfx: boolean) => Promise<BakeResponse | null>;
  isBaking?: boolean;
}

export function BakeExporter({
  jobId,
  enabledAnchorsCount,
  totalAnchorsCount,
  onBake,
  isBaking = false,
}: BakeExporterProps) {
  const [compileKfx, setCompileKfx] = useState<boolean>(true);
  const [bakeResult, setBakeResult] = useState<BakeResponse | null>(null);
  const [bakeError, setBakeError] = useState<string | null>(null);

  const handleTriggerBake = async () => {
    setBakeError(null);
    try {
      const res = await onBake(compileKfx);
      if (res) {
        setBakeResult(res);
      }
    } catch (err) {
      setBakeError(
        err instanceof Error ? err.message : "Failed to bake manuscript."
      );
    }
  };

  return (
    <section className="riso-card bg-newsprint p-6">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b-2 border-ink pb-3">
        <div className="flex items-center gap-2">
          <span className="border-2 border-ink bg-lime px-2 py-0.5 font-mono text-xs font-bold text-ink">
            STAGE 04
          </span>
          <h2 className="font-mono text-sm font-bold uppercase tracking-wider">
            Final Risograph Press • EPUB 3 &amp; Kindle KFX Compiler
          </h2>
        </div>

        <span className="font-mono text-xs font-bold">
          READY TO INJECT: {enabledAnchorsCount} OF {totalAnchorsCount} CAIRNS
        </span>
      </div>

      <div className="mt-5 flex flex-col justify-between gap-5 md:flex-row md:items-center">
        <div className="space-y-2">
          <h3 className="font-serif text-2xl font-bold text-ink">
            Bind Bidirectional Footnotes into Manuscript DOM
          </h3>
          <p className="max-w-xl font-mono text-xs leading-relaxed text-ink/80">
            Wraps each first chapter mention in{" "}
            <code>epub:type=&quot;noteref&quot;</code> and appends{" "}
            <code>&lt;aside epub:type=&quot;footnote&quot;&gt;</code> cards with
            e-ink CSS rules.
          </p>

          <label className="mt-2 inline-flex cursor-pointer items-center gap-2 border-2 border-ink bg-halftone px-3 py-1.5 font-mono text-xs font-bold">
            <input
              type="checkbox"
              checked={compileKfx}
              onChange={(e) => setCompileKfx(e.target.checked)}
              className="h-4 w-4 accent-coral"
            />
            <span>
              Also invoke Calibre <code>ebook-convert</code> for Kindle
              Paperwhite (<code>.kfx</code>)
            </span>
          </label>
        </div>

        <div className="flex flex-wrap items-center gap-3">
          <button
            type="button"
            disabled={!jobId || isBaking}
            onClick={handleTriggerBake}
            className={`riso-button inline-flex items-center gap-2 bg-coral px-5 py-3 font-mono text-xs font-bold uppercase tracking-wider text-newsprint ${
              !jobId || isBaking ? "cursor-not-allowed opacity-50" : ""
            }`}
          >
            <Hammer className="h-4 w-4" />
            {isBaking
              ? "Pressing DOM & Compiling..."
              : `Bake ${enabledAnchorsCount} Cairns Now`}
          </button>
        </div>
      </div>

      {!jobId && (
        <p className="mt-3 font-mono text-[11px] text-ink/70">
          * Upload a real <code>.epub</code> in Stage 01 to unlock live binary
          EPUB 3 &amp; KFX downloads from the FastAPI compiler.
        </p>
      )}

      {bakeError && (
        <div className="mt-4 flex items-center gap-2 border-2 border-ink bg-coral p-3 font-mono text-xs font-bold text-newsprint">
          <AlertCircle className="h-4 w-4 shrink-0" />
          <span>{bakeError}</span>
        </div>
      )}

      {bakeResult && jobId && (
        <div className="mt-5 flex flex-wrap items-center justify-between gap-4 border-2 border-ink bg-lime p-4 shadow-riso-sm">
          <div className="flex items-center gap-2 font-mono text-xs font-bold text-ink">
            <CheckCircle className="h-5 w-5" />
            <span>
              MANUSCRIPT BAKED SUCCESSFULLY • JOB ID: {bakeResult.job_id}
            </span>
          </div>

          <div className="flex flex-wrap items-center gap-3">
            <a
              href={getDownloadUrl(jobId, "epub")}
              download
              className="riso-button inline-flex items-center gap-2 bg-newsprint px-4 py-2 font-mono text-xs font-bold uppercase text-ink"
            >
              <Download className="h-4 w-4" />
              Download Enhanced .EPUB
            </a>

            {bakeResult.kfx_available && bakeResult.kfx_download_url ? (
              <a
                href={getDownloadUrl(jobId, "kfx")}
                download
                className="riso-button inline-flex items-center gap-2 bg-ink px-4 py-2 font-mono text-xs font-bold uppercase text-lime"
              >
                <Download className="h-4 w-4" />
                Download Kindle .KFX
              </a>
            ) : (
              <span className="border border-ink bg-halftone px-3 py-2 font-mono text-[11px] text-ink/80">
                .KFX CLI skipped (Calibre not detected on host)
              </span>
            )}
          </div>
        </div>
      )}
    </section>
  );
}
