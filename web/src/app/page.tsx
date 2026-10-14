"use client";

import React, { useState } from "react";
import { BakeExporter } from "@/components/BakeExporter";
import { InkDropZone } from "@/components/InkDropZone";
import { KindleModalPreview } from "@/components/KindleModalPreview";
import { PretextCanvas } from "@/components/PretextCanvas";
import { ProofRibbon } from "@/components/ProofRibbon";
import { SensitivityDial } from "@/components/SensitivityDial";
import {
  bakeBook,
  subscribeToScanStream,
  updateDisabledAnchors,
  uploadBook,
} from "@/lib/api";
import type {
  BakeJobState,
  BakeResponse,
  CairnFootnote,
  ScanProgressEvent,
  SentenceChunkEvent,
} from "@/lib/types";

const DEMO_SENTENCES: SentenceChunkEvent[] = [
  {
    chapter_index: 0,
    chapter_title: "Chapter One: The Siege Begins",
    text: "The dawn broke crimson over the ramparts of Oakhaven. High Marshal Vasquez stood atop the north bastion, his scarred iron gauntlets resting upon the battlements.",
  },
  {
    chapter_index: 1,
    chapter_title: "Chapter Two: The Ashen Wastes",
    text: "Three leagues beyond the river valley lay the silent expanse of the Ashen Wastes. Scout Jennifer trudged through grey dunes under a leaden sky.",
  },
  {
    chapter_index: 2,
    chapter_title: "Chapter Three: Archive of Whispers",
    text: "Deep within the subterranean chambers of Morndun, Scholar Cheryl studied the ancient codices of the First Faction.",
  },
  {
    chapter_index: 3,
    chapter_title: "Chapter Four: The Battle of Red Ridge",
    text: "High Marshal Vasquez charged into the breach at the head of five hundred armored cataphracts. His silver cloak billowed in the tempest.",
  },
  {
    chapter_index: 4,
    chapter_title: "Chapter Five: Council of the Spire",
    text: "In the high chamber of the Spire, High Marshal Vasquez met with Chancellor Dennis and Scout Jennifer to draft terms after the Obsidian Banner retreated.",
  },
];

const DEMO_CAIRNS: CairnFootnote[] = [
  {
    anchor_id: "cairn-high-marshal-vasquez-ch4",
    entity_slug: "high-marshal-vasquez",
    display_name: "Vasquez",
    chapter_index: 3,
    chapter_title: "Chapter Four: The Battle of Red Ridge",
    paragraph_index: 1,
    pages_absent: 45,
    first_seen_chapter: 0,
    last_seen_chapter: 0,
    alignment: "ally",
    jev_prob: 0.91,
    jev_score: 5,
    synopsis_text:
      "Oakhaven garrison commander who ordered troops to hold the north bastion in Ch. 1.",
    enabled: true,
  },
  {
    anchor_id: "cairn-scout-jennifer-ch5",
    entity_slug: "scout-jennifer",
    display_name: "Jennifer",
    chapter_index: 4,
    chapter_title: "Chapter Five: Council of the Spire",
    paragraph_index: 0,
    pages_absent: 35,
    first_seen_chapter: 1,
    last_seen_chapter: 1,
    alignment: "ally",
    jev_prob: 0.86,
    jev_score: 4,
    synopsis_text:
      "Wilderness scout who trekked across the grey dunes of the Ashen Wastes in Ch. 2.",
    enabled: true,
  },
  {
    anchor_id: "cairn-obsidian-banner-ch5",
    entity_slug: "obsidian-banner",
    display_name: "Obsidian Banner",
    chapter_index: 4,
    chapter_title: "Chapter Five: Council of the Spire",
    paragraph_index: 1,
    pages_absent: 48,
    first_seen_chapter: 0,
    last_seen_chapter: 0,
    alignment: "adversary",
    jev_prob: 0.89,
    jev_score: 4,
    synopsis_text:
      "Besieging enemy legion surveyed by Commander Thorne outside Oakhaven's ramparts in Ch. 1.",
    enabled: true,
  },
];

export default function HomePage() {
  const [minPageGap, setMinPageGap] = useState<number>(30);
  const [jobState, setJobState] = useState<BakeJobState | null>(null);
  const [isUploading, setIsUploading] = useState<boolean>(false);
  const [isScanning, setIsScanning] = useState<boolean>(false);
  const [isBaking, setIsBaking] = useState<boolean>(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [sentenceChunks, setSentenceChunks] = useState<SentenceChunkEvent[]>(
    []
  );
  const [droppedCairns, setDroppedCairns] = useState<CairnFootnote[]>([]);
  const [progress, setProgress] = useState<ScanProgressEvent | null>(null);
  const [selectedCairn, setSelectedCairn] = useState<CairnFootnote | null>(
    null
  );

  const handleFileUpload = async (file: File) => {
    setErrorMessage(null);
    setIsUploading(true);
    setSentenceChunks([]);
    setDroppedCairns([]);
    setProgress(null);
    setSelectedCairn(null);

    try {
      const createdJob = await uploadBook(file, minPageGap);
      setJobState(createdJob);
      setIsUploading(false);
      setIsScanning(true);

      subscribeToScanStream(createdJob.job_id, {
        onSentenceChunk: (chunk) => {
          setSentenceChunks((prev) => [...prev, chunk]);
        },
        onCairnDropped: (footnote) => {
          setDroppedCairns((prev) => [...prev, footnote]);
          setSelectedCairn((prev) => prev ?? footnote);
        },
        onProgress: (prog) => {
          setProgress(prog);
        },
        onComplete: (done) => {
          setIsScanning(false);
          setJobState((prev) =>
            prev ? { ...prev, phase: done.phase } : prev
          );
        },
        onError: () => {
          setIsScanning(false);
          setErrorMessage(
            "SSE stream interrupted. Ensure the FastAPI server is running on port 8000."
          );
        },
      });
    } catch (err) {
      setIsUploading(false);
      setIsScanning(false);
      setErrorMessage(
        err instanceof Error ? err.message : "Failed to upload EPUB."
      );
    }
  };

  const handleRunSyntheticDemo = () => {
    setErrorMessage(null);
    setJobState(null);
    setSentenceChunks([]);
    setDroppedCairns([]);
    setIsScanning(true);

    DEMO_SENTENCES.forEach((chunk, index) => {
      window.setTimeout(() => {
        setSentenceChunks((prev) => [...prev, chunk]);
        setProgress({
          scanned_chapters: index + 1,
          total_chapters: DEMO_SENTENCES.length,
          entities_tracked: 9,
          anchors_placed: index >= 3 ? index - 1 : 0,
        });
        if (index === 3) {
          setDroppedCairns([DEMO_CAIRNS[0]]);
          setSelectedCairn(DEMO_CAIRNS[0]);
        } else if (index === 4) {
          setDroppedCairns(DEMO_CAIRNS);
          setSelectedCairn(DEMO_CAIRNS[0]);
          setIsScanning(false);
        }
      }, index * 240);
    });
  };

  const handleToggleFootnote = async (anchorId: string) => {
    const nextList = droppedCairns.map((fn) =>
      fn.anchor_id === anchorId ? { ...fn, enabled: !fn.enabled } : fn
    );
    setDroppedCairns(nextList);
    setSelectedCairn((prev) =>
      prev && prev.anchor_id === anchorId
        ? { ...prev, enabled: !prev.enabled }
        : prev
    );

    if (jobState?.job_id) {
      const disabledIds = nextList
        .filter((fn) => !fn.enabled)
        .map((fn) => fn.anchor_id);
      try {
        await updateDisabledAnchors(jobState.job_id, disabledIds);
      } catch (err) {
        setErrorMessage(
          err instanceof Error ? err.message : "Failed to sync anchor toggle."
        );
      }
    }
  };

  const handleEnableAll = async () => {
    const nextList = droppedCairns.map((fn) => ({ ...fn, enabled: true }));
    setDroppedCairns(nextList);
    setSelectedCairn((prev) => (prev ? { ...prev, enabled: true } : null));
    if (jobState?.job_id) {
      await updateDisabledAnchors(jobState.job_id, []);
    }
  };

  const handleBake = async (
    compileKfx: boolean
  ): Promise<BakeResponse | null> => {
    if (!jobState?.job_id) return null;
    setIsBaking(true);
    try {
      const disabledIds = droppedCairns
        .filter((fn) => !fn.enabled)
        .map((fn) => fn.anchor_id);
      await updateDisabledAnchors(jobState.job_id, disabledIds);
      const res = await bakeBook(jobState.job_id, compileKfx);
      setJobState((prev) => (prev ? { ...prev, phase: "COMPLETED" } : prev));
      return res;
    } finally {
      setIsBaking(false);
    }
  };

  const activeContextSentence = selectedCairn
    ? sentenceChunks.find(
        (c) =>
          c.chapter_index === selectedCairn.chapter_index &&
          c.text.includes(selectedCairn.display_name)
      )?.text
    : undefined;

  const enabledCount = droppedCairns.filter((fn) => fn.enabled).length;

  return (
    <main className="mx-auto max-w-6xl space-y-6 px-6 py-10">
      {/* Broadsheet Masthead */}
      <header className="riso-card bg-newsprint p-6">
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
            <div>
              BOOK: {jobState ? jobState.book_title : "THE SIEGE OF OAKHAVEN"}
            </div>
            <div>
              PHASE:{" "}
              {jobState
                ? jobState.phase
                : isScanning
                  ? "SCANNING"
                  : droppedCairns.length > 0
                    ? "PROOF_READY"
                    : "READY"}
            </div>
          </div>
        </div>
      </header>

      {/* Stage 1 + Sensitivity Dial */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-12">
        <div className="lg:col-span-7">
          <InkDropZone
            onFileSelected={handleFileUpload}
            onRunSyntheticDemo={handleRunSyntheticDemo}
            isUploading={isUploading}
            errorMessage={errorMessage}
          />
        </div>
        <div className="lg:col-span-5">
          <SensitivityDial
            value={minPageGap}
            onChange={setMinPageGap}
            disabled={isUploading || isScanning}
          />
        </div>
      </div>

      {/* Stage 2: Cheng Lou Pretext Kinetic Stream */}
      <PretextCanvas
        sentenceChunks={sentenceChunks}
        droppedCairns={droppedCairns}
        progress={progress}
        isScanning={isScanning}
        onSelectCairn={setSelectedCairn}
      />

      {/* Stage 3: Proof Ribbon + Kindle Paperwhite Bottom-Sheet Simulator */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-12">
        <div className="lg:col-span-7">
          <ProofRibbon
            footnotes={droppedCairns}
            selectedAnchorId={selectedCairn?.anchor_id ?? null}
            onSelectFootnote={setSelectedCairn}
            onToggleFootnote={handleToggleFootnote}
            onEnableAll={handleEnableAll}
            disabled={isScanning || isBaking}
          />
        </div>
        <div className="lg:col-span-5">
          <KindleModalPreview
            footnote={selectedCairn}
            contextSentence={activeContextSentence}
            onToggleFootnote={handleToggleFootnote}
          />
        </div>
      </div>

      {/* Stage 4: Final EPUB 3 & KFX Press */}
      <BakeExporter
        jobId={jobState?.job_id ?? null}
        enabledAnchorsCount={enabledCount}
        totalAnchorsCount={droppedCairns.length}
        onBake={handleBake}
        isBaking={isBaking}
      />
    </main>
  );
}
