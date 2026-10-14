"use client";

import React, { useEffect, useRef } from "react";
import { prepareWithSegments, layoutWithLines } from "@chenglou/pretext";
import type {
  CairnFootnote,
  ScanProgressEvent,
  SentenceChunkEvent,
} from "@/lib/types";

export interface PretextCanvasProps {
  sentenceChunks: SentenceChunkEvent[];
  droppedCairns: CairnFootnote[];
  progress: ScanProgressEvent | null;
  isScanning: boolean;
  onSelectCairn?: (footnote: CairnFootnote) => void;
}

interface MeasuredParagraphBlock {
  chapterIndex: number;
  chapterTitle: string;
  lines: string[];
  height: number;
}

interface PinDropBadge {
  footnote: CairnFootnote;
  x: number;
  y: number;
  width: number;
  height: number;
}

const CANVAS_HEIGHT = 440;
const LINE_HEIGHT = 24;
const BODY_FONT = '16px Georgia, "Times New Roman", serif';
const MONO_FONT = 'bold 11px "JetBrains Mono", monospace';

function measureParagraphWithPretext(
  text: string,
  maxWidth: number
): { lines: string[]; height: number } {
  const safeWidth = Math.max(180, maxWidth);
  try {
    const prepared = prepareWithSegments(text, BODY_FONT);
    const result = layoutWithLines(prepared, safeWidth, LINE_HEIGHT);
    if (result && Array.isArray(result.lines) && result.lines.length > 0) {
      return {
        lines: result.lines.map((l) => l.text),
        height: result.height,
      };
    }
  } catch {
    // Fallback if font metrics are still initializing
  }

  const words = text.split(/\s+/);
  const approxCharsPerLine = Math.max(25, Math.floor(safeWidth / 8.5));
  const lines: string[] = [];
  let current = "";

  for (const word of words) {
    const candidate = current ? `${current} ${word}` : word;
    if (candidate.length > approxCharsPerLine && current) {
      lines.push(current);
      current = word;
    } else {
      current = candidate;
    }
  }
  if (current) lines.push(current);
  return {
    lines,
    height: lines.length * LINE_HEIGHT,
  };
}

export function PretextCanvas({
  sentenceChunks,
  droppedCairns,
  progress,
  isScanning,
  onSelectCairn,
}: PretextCanvasProps) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const pinBadgesRef = useRef<PinDropBadge[]>([]);
  const animStartRef = useRef<number>(0);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    let animationFrameId = 0;
    if (!animStartRef.current) {
      animStartRef.current = performance.now();
    }

    const renderFrame = (timestamp: number) => {
      const dpr = window.devicePixelRatio || 1;
      const clientWidth = canvas.clientWidth || 760;
      const clientHeight = CANVAS_HEIGHT;

      if (
        canvas.width !== Math.floor(clientWidth * dpr) ||
        canvas.height !== Math.floor(clientHeight * dpr)
      ) {
        canvas.width = Math.floor(clientWidth * dpr);
        canvas.height = Math.floor(clientHeight * dpr);
      }

      ctx.save();
      ctx.scale(dpr, dpr);

      // 1. Warm Newsprint background (#FAF7F0)
      ctx.fillStyle = "#FAF7F0";
      ctx.fillRect(0, 0, clientWidth, clientHeight);

      // 2. Subtle Risograph halftone dot grid (#E6E2D8)
      ctx.fillStyle = "#E6E2D8";
      for (let gx = 16; gx < clientWidth; gx += 20) {
        for (let gy = 16; gy < clientHeight; gy += 20) {
          ctx.fillRect(gx, gy, 1.5, 1.5);
        }
      }

      const textColumnWidth = Math.max(220, clientWidth - 280);
      const recentChunks = sentenceChunks.slice(-6);

      // 3. Measure streaming paragraphs via Cheng Lou's @chenglou/pretext
      const measuredBlocks: MeasuredParagraphBlock[] = recentChunks.map(
        (chunk) => {
          const measured = measureParagraphWithPretext(
            chunk.text,
            textColumnWidth
          );
          return {
            chapterIndex: chunk.chapter_index,
            chapterTitle:
              chunk.chapter_title || `Chapter ${chunk.chapter_index + 1}`,
            lines: measured.lines,
            height: measured.height,
          };
        }
      );

      // Compute vertical auto-scroll so newest ink streams smoothly into view
      const totalStreamHeight = measuredBlocks.reduce(
        (acc, b) => acc + b.height + 34,
        24
      );
      const scrollOffsetY = Math.max(0, totalStreamHeight - (clientHeight - 40));

      let cursorY = 24 - scrollOffsetY;

      if (measuredBlocks.length === 0) {
        ctx.font = MONO_FONT;
        ctx.fillStyle = "#121316";
        ctx.fillText(
          "AWAITING MANUSCRIPT STREAM • CHENG LOU PRETEXT ENGINE READY",
          24,
          clientHeight / 2
        );
      }

      for (const block of measuredBlocks) {
        // Chapter registration tag
        if (cursorY + block.height > 0 && cursorY < clientHeight) {
          ctx.font = MONO_FONT;
          ctx.fillStyle = "#FF4C38";
          ctx.fillText(
            `[CH. ${block.chapterIndex + 1}] ${block.chapterTitle.toUpperCase()}`,
            24,
            cursorY
          );
        }
        cursorY += 18;

        ctx.font = BODY_FONT;
        ctx.fillStyle = "#121316";
        for (const line of block.lines) {
          if (cursorY > -LINE_HEIGHT && cursorY < clientHeight + LINE_HEIGHT) {
            // Highlight entity names that have an active Cairn pin
            let matchedCairn: CairnFootnote | undefined;
            for (const fn of droppedCairns) {
              if (line.includes(fn.display_name)) {
                matchedCairn = fn;
                break;
              }
            }

            if (matchedCairn) {
              const highlightWidth = ctx.measureText(line).width;
              ctx.fillStyle = "#CEFF00";
              ctx.fillRect(22, cursorY - 14, highlightWidth + 6, 19);
              ctx.strokeStyle = "#121316";
              ctx.lineWidth = 1;
              ctx.strokeRect(22, cursorY - 14, highlightWidth + 6, 19);
            }

            ctx.fillStyle = "#121316";
            ctx.fillText(line, 24, cursorY);
          }
          cursorY += LINE_HEIGHT;
        }
        cursorY += 16;
      }

      // 4. Right-hand Risograph Pin Rail for dropped Cairn anchors
      const railX = clientWidth - 236;
      ctx.strokeStyle = "#121316";
      ctx.lineWidth = 2;
      ctx.beginPath();
      ctx.moveTo(railX - 14, 0);
      ctx.lineTo(railX - 14, clientHeight);
      ctx.stroke();

      ctx.font = MONO_FONT;
      ctx.fillStyle = "#121316";
      ctx.fillText("CAIRN PIN DROPS", railX, 24);

      const newBadges: PinDropBadge[] = [];
      const visibleCairns = droppedCairns.slice(-6);
      const pulse = Math.sin((timestamp - animStartRef.current) / 220) * 1.5;

      visibleCairns.forEach((fn, idx) => {
        const cardX = railX;
        const cardY = 40 + idx * 62 + (idx === visibleCairns.length - 1 ? pulse : 0);
        const cardW = 216;
        const cardH = 50;

        // Hard 4px Risograph offset shadow (#121316)
        ctx.fillStyle = "#121316";
        ctx.fillRect(cardX + 4, cardY + 4, cardW, cardH);

        // Card body: Coral for Adversary, Acid Lime for Ally/Neutral
        ctx.fillStyle = fn.alignment === "adversary" ? "#FF4C38" : "#CEFF00";
        ctx.fillRect(cardX, cardY, cardW, cardH);

        ctx.strokeStyle = "#121316";
        ctx.lineWidth = 2;
        ctx.strokeRect(cardX, cardY, cardW, cardH);

        ctx.font = MONO_FONT;
        ctx.fillStyle = fn.alignment === "adversary" ? "#FAF7F0" : "#121316";
        const headerText = `${fn.display_name.toUpperCase()} [?] • CH.${fn.chapter_index + 1}`;
        ctx.fillText(headerText.slice(0, 26), cardX + 8, cardY + 19);

        ctx.font = '10px "JetBrains Mono", monospace';
        const subText = `${fn.pages_absent}p absent • Jev ${Math.round(fn.jev_prob * 100)}%`;
        ctx.fillText(subText, cardX + 8, cardY + 37);

        newBadges.push({
          footnote: fn,
          x: cardX,
          y: cardY,
          width: cardW,
          height: cardH,
        });
      });

      pinBadgesRef.current = newBadges;
      ctx.restore();

      if (isScanning) {
        animationFrameId = window.requestAnimationFrame(renderFrame);
      }
    };

    animationFrameId = window.requestAnimationFrame(renderFrame);
    return () => {
      if (animationFrameId) {
        window.cancelAnimationFrame(animationFrameId);
      }
    };
  }, [sentenceChunks, droppedCairns, isScanning]);

  const handleCanvasClick = (e: React.MouseEvent<HTMLCanvasElement>) => {
    if (!onSelectCairn || !canvasRef.current) return;
    const rect = canvasRef.current.getBoundingClientRect();
    const clickX = e.clientX - rect.left;
    const clickY = e.clientY - rect.top;

    for (const badge of pinBadgesRef.current) {
      if (
        clickX >= badge.x &&
        clickX <= badge.x + badge.width &&
        clickY >= badge.y &&
        clickY <= badge.y + badge.height
      ) {
        onSelectCairn(badge.footnote);
        break;
      }
    }
  };

  return (
    <div className="riso-card bg-newsprint p-5">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b-2 border-ink pb-3">
        <div className="flex items-center gap-2">
          <span className="border-2 border-ink bg-lime px-2 py-0.5 font-mono text-xs font-bold text-ink">
            STAGE 02
          </span>
          <h2 className="font-mono text-sm font-bold uppercase tracking-wider">
            Cheng Lou Pretext Kinetic Stream &amp; Jev Gatekeeper
          </h2>
        </div>

        <div className="flex flex-wrap items-center gap-3 font-mono text-xs">
          <span className="border border-ink bg-halftone px-2 py-0.5">
            CHAPTERS: {progress?.scanned_chapters ?? 0} /{" "}
            {progress?.total_chapters ?? 0}
          </span>
          <span className="border border-ink bg-halftone px-2 py-0.5">
            ENTITIES: {progress?.entities_tracked ?? 0}
          </span>
          <span className="border-2 border-ink bg-coral px-2 py-0.5 font-bold text-newsprint">
            CAIRNS DROPPED: {droppedCairns.length}
          </span>
        </div>
      </div>

      <div className="mt-4 overflow-hidden border-2 border-ink bg-newsprint shadow-riso">
        <canvas
          ref={canvasRef}
          onClick={handleCanvasClick}
          className="block w-full cursor-pointer"
          style={{ height: `${CANVAS_HEIGHT}px` }}
        />
      </div>
    </div>
  );
}
