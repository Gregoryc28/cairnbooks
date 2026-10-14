import type {
  BakeJobState,
  BakeResponse,
  CairnFootnote,
  PatchAnchorsResponse,
  ScanCompleteEvent,
  ScanProgressEvent,
  SentenceChunkEvent,
} from "./types";

export const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL?.replace(/\/$/, "") ||
  "http://127.0.0.1:8000";

export async function uploadBook(
  file: File,
  minPageGap: number = 30
): Promise<BakeJobState> {
  const formData = new FormData();
  formData.append("file", file);
  formData.append("min_page_gap", String(minPageGap));

  const res = await fetch(`${API_BASE_URL}/api/v1/books/upload`, {
    method: "POST",
    body: formData,
  });

  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || `Upload failed with status ${res.status}`);
  }
  return res.json() as Promise<BakeJobState>;
}

export async function fetchProofSheet(jobId: string): Promise<BakeJobState> {
  const res = await fetch(`${API_BASE_URL}/api/v1/books/${jobId}/proof-sheet`);
  if (!res.ok) {
    throw new Error(`Failed to fetch proof sheet (${res.status})`);
  }
  return res.json() as Promise<BakeJobState>;
}

export async function updateDisabledAnchors(
  jobId: string,
  disabledAnchorIds: string[]
): Promise<PatchAnchorsResponse> {
  const res = await fetch(`${API_BASE_URL}/api/v1/books/${jobId}/anchors`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ disabled_anchor_ids: disabledAnchorIds }),
  });
  if (!res.ok) {
    throw new Error(`Failed to update anchors (${res.status})`);
  }
  return res.json() as Promise<PatchAnchorsResponse>;
}

export async function bakeBook(
  jobId: string,
  compileKfx: boolean = false
): Promise<BakeResponse> {
  const res = await fetch(`${API_BASE_URL}/api/v1/books/${jobId}/bake`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ compile_kfx: compileKfx }),
  });
  if (!res.ok) {
    throw new Error(`Failed to bake book (${res.status})`);
  }
  return res.json() as Promise<BakeResponse>;
}

export function getDownloadUrl(
  jobId: string,
  format: "epub" | "kfx"
): string {
  return `${API_BASE_URL}/api/v1/books/${jobId}/download/${format}`;
}

export interface StreamHandlers {
  onSentenceChunk?: (chunk: SentenceChunkEvent) => void;
  onCairnDropped?: (footnote: CairnFootnote) => void;
  onProgress?: (progress: ScanProgressEvent) => void;
  onComplete?: (complete: ScanCompleteEvent) => void;
  onError?: (err: Event) => void;
}

export function subscribeToScanStream(
  jobId: string,
  handlers: StreamHandlers,
  options?: { testMode?: boolean; refreshJev?: boolean }
): () => void {
  const params = new URLSearchParams();
  if (options?.testMode !== undefined) {
    params.set("test_mode", String(options.testMode));
  }
  if (options?.refreshJev) {
    params.set("refresh_jev", "true");
  }
  const query = params.toString() ? `?${params.toString()}` : "";
  const url = `${API_BASE_URL}/api/v1/books/${jobId}/stream${query}`;

  const es = new EventSource(url);

  es.addEventListener("sentence_chunk", (ev: MessageEvent) => {
    handlers.onSentenceChunk?.(JSON.parse(ev.data) as SentenceChunkEvent);
  });

  es.addEventListener("cairn_dropped", (ev: MessageEvent) => {
    handlers.onCairnDropped?.(JSON.parse(ev.data) as CairnFootnote);
  });

  es.addEventListener("progress", (ev: MessageEvent) => {
    handlers.onProgress?.(JSON.parse(ev.data) as ScanProgressEvent);
  });

  es.addEventListener("complete", (ev: MessageEvent) => {
    handlers.onComplete?.(JSON.parse(ev.data) as ScanCompleteEvent);
    es.close();
  });

  es.onerror = (err) => {
    handlers.onError?.(err);
    es.close();
  };

  return () => es.close();
}
