declare module "@chenglou/pretext" {
  export interface PreparedTextWithSegments {
    readonly __brand?: string;
  }

  export interface LayoutLine {
    text: string;
    width: number;
  }

  export interface LayoutLinesResult {
    lines: LayoutLine[];
    height: number;
  }

  export function prepareWithSegments(
    text: string,
    font: string
  ): PreparedTextWithSegments;

  export function layoutWithLines(
    prepared: PreparedTextWithSegments,
    maxWidth: number,
    lineHeight: number
  ): LayoutLinesResult;
}
