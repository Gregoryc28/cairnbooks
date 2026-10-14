"use client";

import React from "react";
import { CheckSquare, Square, Eye, Layers } from "lucide-react";
import type { CairnFootnote } from "@/lib/types";

export interface ProofRibbonProps {
  footnotes: CairnFootnote[];
  selectedAnchorId: string | null;
  onSelectFootnote: (footnote: CairnFootnote) => void;
  onToggleFootnote: (anchorId: string) => void;
  onEnableAll?: () => void;
  disabled?: boolean;
}

function alignmentBadgeClasses(alignment: CairnFootnote["alignment"]): string {
  switch (alignment) {
    case "adversary":
      return "bg-coral text-newsprint";
    case "ally":
      return "bg-lime text-ink";
    case "ambiguous":
      return "bg-ink text-lime";
    default:
      return "bg-halftone text-ink";
  }
}

export function ProofRibbon({
  footnotes,
  selectedAnchorId,
  onSelectFootnote,
  onToggleFootnote,
  onEnableAll,
  disabled = false,
}: ProofRibbonProps) {
  const enabledCount = footnotes.filter((fn) => fn.enabled).length;

  return (
    <section className="riso-card bg-newsprint p-5">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b-2 border-ink pb-3">
        <div className="flex items-center gap-2">
          <span className="border-2 border-ink bg-coral px-2 py-0.5 font-mono text-xs font-bold text-newsprint">
            STAGE 03
          </span>
          <h2 className="font-mono text-sm font-bold uppercase tracking-wider">
            Interactive Proof Sheet Ribbon • Cairn Inspection
          </h2>
        </div>

        <div className="flex flex-wrap items-center gap-3 font-mono text-xs">
          <span className="border-2 border-ink bg-lime px-2.5 py-0.5 font-bold">
            ACTIVE ANCHORS: {enabledCount} / {footnotes.length}
          </span>
          {onEnableAll && footnotes.some((f) => !f.enabled) && (
            <button
              type="button"
              disabled={disabled}
              onClick={onEnableAll}
              className="riso-button bg-newsprint px-2.5 py-0.5 font-mono text-xs font-bold uppercase"
            >
              Restore All
            </button>
          )}
        </div>
      </div>

      {footnotes.length === 0 ? (
        <div className="mt-4 border-2 border-dashed border-ink bg-halftone/50 p-8 text-center font-mono text-xs text-ink/75">
          <Layers className="mx-auto mb-2 h-6 w-6 text-ink/60" />
          NO CAIRN ANCHORS QUEUED YET. UPLOAD AN .EPUB OR RUN THE 60FPS PRETEXT
          DEMO ABOVE TO POPULATE THE PROOF RIBBON.
        </div>
      ) : (
        <div className="mt-4 flex gap-4 overflow-x-auto pb-3 pt-1">
          {footnotes.map((fn) => {
            const isSelected = fn.anchor_id === selectedAnchorId;
            return (
              <div
                key={fn.anchor_id}
                onClick={() => onSelectFootnote(fn)}
                className={`riso-card flex w-72 shrink-0 cursor-pointer flex-col justify-between p-4 transition-transform ${
                  isSelected
                    ? "ring-2 ring-coral -translate-y-0.5"
                    : "hover:-translate-y-0.5"
                } ${fn.enabled ? "bg-newsprint" : "bg-halftone/70 opacity-65"}`}
              >
                <div>
                  <div className="flex items-center justify-between gap-2 border-b border-ink/40 pb-2 font-mono text-[11px]">
                    <span
                      className={`border border-ink px-1.5 py-0.5 font-bold uppercase ${alignmentBadgeClasses(
                        fn.alignment
                      )}`}
                    >
                      {fn.alignment}
                    </span>
                    <span className="font-bold text-ink/80">
                      CH.{fn.chapter_index + 1} • {fn.pages_absent}P ABSENT
                    </span>
                  </div>

                  <div className="mt-2.5 flex items-baseline justify-between gap-2">
                    <h3 className="font-serif text-xl font-black text-ink">
                      {fn.display_name}
                      <sup className="ml-0.5 font-mono text-xs font-bold text-coral">
                        [?]
                      </sup>
                    </h3>
                    <span className="font-mono text-[10px] text-ink/70">
                      JEV {Math.round(fn.jev_prob * 100)}% • S{fn.jev_score}/5
                    </span>
                  </div>

                  <p className="mt-2 font-serif text-sm leading-snug text-ink/90">
                    &ldquo;{fn.synopsis_text}&rdquo;
                  </p>
                </div>

                <div className="mt-4 flex items-center justify-between border-t border-ink/40 pt-2.5 font-mono text-xs">
                  <button
                    type="button"
                    disabled={disabled}
                    onClick={(e) => {
                      e.stopPropagation();
                      onToggleFootnote(fn.anchor_id);
                    }}
                    className={`inline-flex items-center gap-1.5 border border-ink px-2 py-1 font-bold uppercase ${
                      fn.enabled
                        ? "bg-lime text-ink"
                        : "bg-newsprint text-ink/70"
                    }`}
                  >
                    {fn.enabled ? (
                      <>
                        <CheckSquare className="h-3.5 w-3.5" />
                        KEEP PIN
                      </>
                    ) : (
                      <>
                        <Square className="h-3.5 w-3.5" />
                        MUTED
                      </>
                    )}
                  </button>

                  <span className="inline-flex items-center gap-1 text-[11px] font-bold uppercase text-ink/80">
                    <Eye className="h-3.5 w-3.5" />
                    Preview KFX
                  </span>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </section>
  );
}
