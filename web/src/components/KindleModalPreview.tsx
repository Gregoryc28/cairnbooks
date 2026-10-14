"use client";

import React from "react";
import { Smartphone, CornerDownLeft, CheckCircle2, XCircle } from "lucide-react";
import type { CairnFootnote } from "@/lib/types";

export interface KindleModalPreviewProps {
  footnote: CairnFootnote | null;
  contextSentence?: string;
  onToggleFootnote?: (anchorId: string) => void;
}

export function KindleModalPreview({
  footnote,
  contextSentence,
  onToggleFootnote,
}: KindleModalPreviewProps) {
  if (!footnote) {
    return (
      <div className="riso-card flex h-full flex-col justify-between bg-newsprint p-5">
        <div className="flex items-center justify-between border-b-2 border-ink pb-3">
          <div className="flex items-center gap-2">
            <Smartphone className="h-4 w-4 text-ink" />
            <h3 className="font-mono text-xs font-bold uppercase tracking-wider">
              Kindle Paperwhite KFX Bottom-Sheet Simulator
            </h3>
          </div>
          <span className="border border-ink bg-halftone px-2 py-0.5 font-mono text-[10px] font-bold">
            300 PPI E-INK
          </span>
        </div>
        <div className="my-auto py-12 text-center font-mono text-xs text-ink/70">
          SELECT ANY CAIRN CARD FROM THE PROOF RIBBON OR CANVAS RAIL TO PREVIEW
          ITS BIDIRECTIONAL KFX POPUP FOOTNOTE.
        </div>
      </div>
    );
  }

  const refId = `ref-${footnote.entity_slug}-ch${footnote.chapter_index + 1}`;
  const noteId = `note-${footnote.entity_slug}-ch${footnote.chapter_index + 1}`;

  const defaultSentence = `In ${footnote.chapter_title}, ${footnote.display_name} returned to the narrative after ${footnote.pages_absent} pages absent from the spine.`;
  const fullText = contextSentence || defaultSentence;
  const parts = fullText.split(footnote.display_name);

  return (
    <div className="riso-card flex flex-col justify-between bg-newsprint p-5">
      <div className="flex flex-wrap items-center justify-between gap-2 border-b-2 border-ink pb-3">
        <div className="flex items-center gap-2">
          <Smartphone className="h-4 w-4 text-ink" />
          <h3 className="font-mono text-xs font-bold uppercase tracking-wider">
            Kindle Paperwhite 300 PPI Popup Simulator
          </h3>
        </div>
        <span className="border border-ink bg-lime px-2 py-0.5 font-mono text-[10px] font-bold uppercase">
          epub:type=&quot;noteref&quot;
        </span>
      </div>

      {/* Simulated Kindle Bezel & E-Ink Viewport */}
      <div className="mt-4 border-4 border-ink bg-[#F4F1EA] p-4 shadow-riso">
        <div className="flex items-center justify-between border-b border-ink/30 pb-1.5 font-mono text-[10px] uppercase text-ink/70">
          <span>{footnote.chapter_title}</span>
          <span>FIRST SEEN: CH. {footnote.first_seen_chapter + 1}</span>
        </div>

        {/* E-Ink Book Body Paragraph */}
        <p className="mt-3 font-serif text-base leading-relaxed text-ink">
          {parts.length > 1 ? (
            <>
              {parts[0]}
              <span
                id={refId}
                className="border-b-2 border-dotted border-ink bg-lime/80 px-1 font-bold"
              >
                {footnote.display_name}
                <sup className="ml-0.5 font-mono text-[11px] font-bold text-coral">
                  [?]
                </sup>
              </span>
              {parts.slice(1).join(footnote.display_name)}
            </>
          ) : (
            <>
              <span
                id={refId}
                className="border-b-2 border-dotted border-ink bg-lime/80 px-1 font-bold"
              >
                {footnote.display_name}
                <sup className="ml-0.5 font-mono text-[11px] font-bold text-coral">
                  [?]
                </sup>
              </span>{" "}
              — {fullText}
            </>
          )}
        </p>

        {/* Simulated Native KFX Bottom-Sheet Footnote Popup Card */}
        <aside
          id={noteId}
          className="mt-5 border-2 border-ink bg-newsprint p-3.5 shadow-riso-sm"
        >
          <div className="flex items-center justify-between border-b border-ink/40 pb-1.5 font-mono text-[10px] font-bold uppercase">
            <span>
              FOOTNOTE POPUP • {footnote.alignment.toUpperCase()} •{" "}
              {footnote.pages_absent}P ABSENT
            </span>
            <span className="text-coral">#{noteId}</span>
          </div>

          <p className="mt-2 font-serif text-sm leading-snug text-ink">
            <strong>{footnote.display_name}</strong> (Last seen Ch.{" "}
            {footnote.last_seen_chapter + 1}): {footnote.synopsis_text}{" "}
            <span
              title={`Backlink to #${refId}`}
              className="inline-flex items-center font-mono text-xs font-bold text-coral"
            >
              <CornerDownLeft className="ml-1 inline h-3.5 w-3.5" />
            </span>
          </p>
        </aside>
      </div>

      {/* Footer Controls & Markup Inspector */}
      <div className="mt-4 flex flex-wrap items-center justify-between gap-2 font-mono text-xs">
        <code className="border border-ink bg-halftone px-2 py-1 text-[11px]">
          &lt;a id=&quot;{refId}&quot; href=&quot;#{noteId}&quot;&gt;
        </code>

        {onToggleFootnote && (
          <button
            type="button"
            onClick={() => onToggleFootnote(footnote.anchor_id)}
            className={`riso-button inline-flex items-center gap-1.5 px-3 py-1 font-bold uppercase ${
              footnote.enabled
                ? "bg-lime text-ink"
                : "bg-coral text-newsprint"
            }`}
          >
            {footnote.enabled ? (
              <>
                <CheckCircle2 className="h-3.5 w-3.5" />
                Anchor Enabled
              </>
            ) : (
              <>
                <XCircle className="h-3.5 w-3.5" />
                Anchor Muted
              </>
            )}
          </button>
        )}
      </div>
    </div>
  );
}
