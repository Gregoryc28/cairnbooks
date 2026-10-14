"use client";

import React from "react";
import { Sliders } from "lucide-react";

export interface SensitivityDialProps {
  value: number;
  onChange: (newGapPages: number) => void;
  disabled?: boolean;
}

interface PresetOption {
  id: string;
  label: string;
  pages: number;
  description: string;
  tag: string;
}

const PRESETS: PresetOption[] = [
  {
    id: "conservative",
    label: "CONSERVATIVE",
    pages: 50,
    description: "Major character returns after long 50+ page absences.",
    tag: "SPARSE INK",
  },
  {
    id: "balanced",
    label: "BALANCED",
    pages: 30,
    description: "Standard 30-page gap threshold for epic fantasy & sci-fi.",
    tag: "DEFAULT PRESS",
  },
  {
    id: "deep",
    label: "DEEP LORE",
    pages: 15,
    description: "Frequent refreshers for dense casts, factions & artifacts.",
    tag: "DENSE INDEX",
  },
];

export function SensitivityDial({
  value,
  onChange,
  disabled = false,
}: SensitivityDialProps) {
  return (
    <div className="riso-card bg-newsprint p-5">
      <div className="flex flex-wrap items-center justify-between gap-2 border-b-2 border-ink pb-3">
        <div className="flex items-center gap-2">
          <Sliders className="h-4 w-4 text-ink" />
          <h3 className="font-mono text-xs font-bold uppercase tracking-wider">
            Sensitivity Dial • Page Absence Gate
          </h3>
        </div>
        <span className="border-2 border-ink bg-lime px-2 py-0.5 font-mono text-xs font-bold">
          MIN GAP: {value} PAGES
        </span>
      </div>

      <div className="mt-4 grid grid-cols-1 gap-3 sm:grid-cols-3">
        {PRESETS.map((preset) => {
          const isSelected = value === preset.pages;
          return (
            <button
              key={preset.id}
              type="button"
              disabled={disabled}
              onClick={() => onChange(preset.pages)}
              className={`riso-button flex flex-col justify-between p-3 text-left ${
                isSelected
                  ? "bg-coral text-newsprint"
                  : "bg-newsprint text-ink hover:bg-halftone"
              } ${disabled ? "cursor-not-allowed opacity-60" : ""}`}
            >
              <div>
                <div className="flex items-center justify-between gap-1 font-mono text-[11px] font-bold">
                  <span>{preset.label}</span>
                  <span
                    className={`border border-ink px-1.5 py-0.5 text-[10px] ${
                      isSelected
                        ? "bg-ink text-lime"
                        : "bg-halftone text-ink"
                    }`}
                  >
                    {preset.pages}P
                  </span>
                </div>
                <p
                  className={`mt-2 font-serif text-xs leading-snug ${
                    isSelected ? "text-newsprint/95" : "text-ink/80"
                  }`}
                >
                  {preset.description}
                </p>
              </div>
              <div
                className={`mt-3 font-mono text-[10px] uppercase tracking-widest ${
                  isSelected ? "text-lime" : "text-ink/60"
                }`}
              >
                [{preset.tag}]
              </div>
            </button>
          );
        })}
      </div>

      <div className="mt-4 flex flex-wrap items-center justify-between gap-3 border-t-2 border-ink pt-3 font-mono text-xs">
        <label htmlFor="custom-gap-range" className="font-bold uppercase">
          Fine Caliper Adjustment (0–100 Pages):
        </label>
        <div className="flex items-center gap-3">
          <input
            id="custom-gap-range"
            type="range"
            min={0}
            max={100}
            step={5}
            disabled={disabled}
            value={value}
            onChange={(e) => onChange(Number(e.target.value))}
            className="h-2 w-36 cursor-pointer accent-coral"
          />
          <span className="w-12 border border-ink bg-halftone px-1.5 py-0.5 text-center font-bold">
            {value}p
          </span>
        </div>
      </div>
    </div>
  );
}
