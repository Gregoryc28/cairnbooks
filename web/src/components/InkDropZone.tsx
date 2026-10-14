"use client";

import React, { useRef, useState } from "react";
import { BookOpen, FileUp, Sparkles, AlertTriangle } from "lucide-react";

export interface InkDropZoneProps {
  onFileSelected: (file: File) => Promise<void> | void;
  onRunSyntheticDemo?: () => void;
  isUploading?: boolean;
  errorMessage?: string | null;
}

export function InkDropZone({
  onFileSelected,
  onRunSyntheticDemo,
  isUploading = false,
  errorMessage = null,
}: InkDropZoneProps) {
  const inputRef = useRef<HTMLInputElement | null>(null);
  const [isDragging, setIsDragging] = useState(false);
  const [selectedName, setSelectedName] = useState<string | null>(null);

  const handleFile = async (file: File | undefined) => {
    if (!file) return;
    setSelectedName(file.name);
    await onFileSelected(file);
  };

  const handleDrop = async (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);
    if (isUploading) return;
    const file = e.dataTransfer.files?.[0];
    await handleFile(file);
  };

  return (
    <div className="riso-card bg-newsprint p-6">
      <div className="flex flex-wrap items-center justify-between gap-2 border-b-2 border-ink pb-3">
        <div className="flex items-center gap-2">
          <span className="border-2 border-ink bg-coral px-2 py-0.5 font-mono text-xs font-bold text-newsprint">
            STAGE 01
          </span>
          <h2 className="font-mono text-sm font-bold uppercase tracking-wider">
            Printing-Plate EPUB Drop Zone
          </h2>
        </div>
        <span className="font-mono text-xs text-ink/70">
          MAX PLATE SIZE: 50MB • FORMAT: .EPUB
        </span>
      </div>

      <div
        onDragOver={(e) => {
          e.preventDefault();
          if (!isUploading) setIsDragging(true);
        }}
        onDragLeave={() => setIsDragging(false)}
        onDrop={handleDrop}
        onClick={() => {
          if (!isUploading) inputRef.current?.click();
        }}
        className={`mt-5 cursor-pointer border-2 border-dashed border-ink p-8 text-center transition-colors ${
          isDragging
            ? "bg-lime text-ink"
            : "bg-halftone/60 hover:bg-halftone"
        } ${isUploading ? "pointer-events-none opacity-60" : ""}`}
      >
        <input
          ref={inputRef}
          type="file"
          accept=".epub,application/epub+zip"
          className="hidden"
          onChange={(e) => {
            const file = e.target.files?.[0];
            void handleFile(file);
          }}
        />

        <div className="mx-auto flex h-14 w-14 items-center justify-center border-2 border-ink bg-newsprint shadow-riso-sm">
          <FileUp className="h-7 w-7 text-ink" />
        </div>

        <h3 className="mt-4 font-serif text-2xl font-bold text-ink">
          {isUploading
            ? "Locking Printing Plate & Unpacking Spine..."
            : "Drop your .EPUB manuscript onto the press plate"}
        </h3>

        <p className="mx-auto mt-2 max-w-xl font-mono text-xs leading-relaxed text-ink/80">
          {selectedName
            ? `LOADED PLATE: ${selectedName}`
            : "Click to browse local files or drag an unencrypted EPUB 3 archive here. CairnBooks indexes chapters strictly in reading order."}
        </p>

        <div className="mt-5 flex flex-wrap items-center justify-center gap-3">
          <span className="riso-button inline-flex items-center gap-2 bg-newsprint px-4 py-2 font-mono text-xs font-bold uppercase">
            <BookOpen className="h-4 w-4" />
            Select .EPUB File
          </span>

          {onRunSyntheticDemo && (
            <button
              type="button"
              disabled={isUploading}
              onClick={(e) => {
                e.stopPropagation();
                onRunSyntheticDemo();
              }}
              className="riso-button inline-flex items-center gap-2 bg-lime px-4 py-2 font-mono text-xs font-bold uppercase text-ink"
            >
              <Sparkles className="h-4 w-4" />
              Run 60FPS Pretext Press Demo
            </button>
          )}
        </div>
      </div>

      {errorMessage && (
        <div
          role="alert"
          className="mt-4 flex items-center gap-3 border-2 border-ink bg-coral p-3 font-mono text-xs font-bold text-newsprint shadow-riso-sm"
        >
          <AlertTriangle className="h-5 w-5 shrink-0" />
          <span>PRESS FAULT: {errorMessage}</span>
        </div>
      )}
    </div>
  );
}
