export type AlignmentChoice = "ally" | "adversary" | "neutral" | "ambiguous";

export type EntityCategory =
  | "character"
  | "faction"
  | "location"
  | "artifact_or_lore";

export type JobPhase =
  | "UPLOADED"
  | "SCANNING"
  | "PROOF_READY"
  | "BAKING"
  | "COMPLETED"
  | "ERROR";

export interface CairnFootnote {
  anchor_id: string;
  entity_slug: string;
  display_name: string;
  chapter_index: number;
  chapter_title: string;
  paragraph_index: number;
  pages_absent: number;
  first_seen_chapter: number;
  last_seen_chapter: number;
  alignment: AlignmentChoice;
  jev_prob: number;
  jev_score: number;
  synopsis_text: string;
  enabled: boolean;
}

export interface BakeJobState {
  job_id: string;
  filename: string;
  book_title: string;
  book_author: string;
  total_chapters: number;
  total_words: number;
  estimated_pages: number;
  min_page_gap: number;
  phase: JobPhase;
  scanned_chapters: number;
  entities_tracked: number;
  footnotes: CairnFootnote[];
  output_epub_path: string | null;
  output_kfx_path: string | null;
  error_message: string | null;
}

export interface SentenceChunkEvent {
  chapter_index: number;
  chapter_title?: string;
  text: string;
}

export interface ScanProgressEvent {
  scanned_chapters: number;
  total_chapters: number;
  entities_tracked: number;
  anchors_placed: number;
}

export interface ScanCompleteEvent {
  phase: JobPhase;
  total_anchors: number;
}

export interface PatchAnchorsResponse {
  job_id: string;
  enabled_anchors: number;
  disabled_anchors: number;
  total_anchors: number;
}

export interface BakeResponse {
  job_id: string;
  epub_download_url: string;
  kfx_download_url: string | null;
  kfx_available: boolean;
}
