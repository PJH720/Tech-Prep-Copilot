// pdf-parse ships CJS only; the ESM stub has no default export.
// eslint-disable-next-line @typescript-eslint/no-require-imports
const pdfParse = require("pdf-parse") as (buf: Buffer) => Promise<{ text: string }>;

export async function parsePDF(buffer: Buffer): Promise<string> {
  if (!buffer || buffer.length === 0) {
    throw new Error("PDF 버퍼가 비어있습니다.");
  }

  let data;
  try {
    data = await pdfParse(buffer);
  } catch (err) {
    throw new Error(`PDF 파싱 중 오류가 발생했습니다: ${(err as Error).message}`);
  }

  const text = data.text?.trim();
  if (!text) {
    throw new Error("PDF에서 추출된 텍스트가 없습니다.");
  }

  return text;
}
