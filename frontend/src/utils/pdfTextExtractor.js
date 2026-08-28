import { getDocument, GlobalWorkerOptions } from 'pdfjs-dist/legacy/build/pdf.mjs';
import pdfWorkerUrl from 'pdfjs-dist/legacy/build/pdf.worker.min.mjs?url';

GlobalWorkerOptions.workerSrc = pdfWorkerUrl;

export class LocalPdfPasswordRequiredError extends Error {
  constructor() {
    super('This PDF requires a password.');
    this.name = 'LocalPdfPasswordRequiredError';
  }
}

function groupTextItemsIntoLines(items) {
  const lines = [];

  items
    .filter(item => typeof item?.str === 'string' && item.str.trim())
    .forEach(item => {
      const x = Number(item.transform?.[4] || 0);
      const y = Number(item.transform?.[5] || 0);
      let line = lines.find(candidate => Math.abs(candidate.y - y) <= 3);
      if (!line) {
        line = { y, items: [] };
        lines.push(line);
      }
      line.items.push({ x, text: item.str });
    });

  return lines
    .sort((a, b) => b.y - a.y)
    .map(line => line.items
      .sort((a, b) => a.x - b.x)
      .map(item => item.text)
      .join(' ')
      .replace(/\s+/g, ' ')
      .trim())
    .filter(Boolean);
}

export async function extractPdfText(arrayBuffer) {
  if (!(arrayBuffer instanceof ArrayBuffer)) {
    throw new TypeError('A PDF ArrayBuffer is required.');
  }

  const data = new Uint8Array(arrayBuffer);
  const loadingTask = getDocument({
    data,
    useWorkerFetch: false,
    disableAutoFetch: true,
    stopAtErrors: true,
  });
  let pdfDocument = null;

  try {
    pdfDocument = await loadingTask.promise;
    const pages = [];
    let textItemCount = 0;

    for (let pageNumber = 1; pageNumber <= pdfDocument.numPages; pageNumber += 1) {
      const page = await pdfDocument.getPage(pageNumber);
      const content = await page.getTextContent();
      const lines = groupTextItemsIntoLines(content.items || []);
      textItemCount += content.items?.length || 0;
      pages.push({ pageNumber, lines });
      page.cleanup();
    }

    return {
      pageCount: pdfDocument.numPages,
      textItemCount,
      text: pages.flatMap(page => page.lines).join('\n'),
    };
  } catch (error) {
    if (error?.name === 'PasswordException') throw new LocalPdfPasswordRequiredError();
    throw error;
  } finally {
    try {
      if (pdfDocument) await pdfDocument.cleanup();
    } finally {
      await loadingTask.destroy();
    }
  }
}
