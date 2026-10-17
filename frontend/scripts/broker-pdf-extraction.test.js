import test, { after } from 'node:test';
import assert from 'node:assert/strict';
import { registerHooks } from 'node:module';
import { Buffer } from 'node:buffer';
import { BROKER_STATEMENT_STATUS, parseBrokerStatement } from '../src/utils/brokerImport.js';
import { rowDamageMatrix, transactionIdentityMatrix, tradeFields, validTrade } from './fixtures/broker-row-damage.js';

// Node text extraction never paints. Fail if the optional canvas/render APIs are used.
const platformKeys = ['DOMMatrix', 'Path2D'];
const platform = platformKeys.map(key => [key, Object.getOwnPropertyDescriptor(globalThis, key)]);
let identityMatrices = 0;
globalThis.DOMMatrix = class { constructor() { identityMatrices += 1; } };
globalThis.Path2D = class { constructor() { throw new Error('Canvas rendering is outside this text-only test'); } };
const worker = new URL('../node_modules/pdfjs-dist/legacy/build/pdf.worker.min.mjs', import.meta.url);
let workerUrlImports = 0;
let workerLoads = 0;
const hooks = registerHooks({
  resolve(specifier, context, nextResolve) {
    if (specifier === worker.href) workerLoads += 1;
    if (specifier === '@napi-rs/canvas') throw new Error('Optional native canvas is unavailable in isolated text extraction');
    if (specifier === 'pdfjs-dist/legacy/build/pdf.worker.min.mjs?url') {
      assert.equal(context.parentURL, new URL('../src/utils/pdfTextExtractor.js', import.meta.url).href);
      workerUrlImports += 1;
      return { url: 'data:text/javascript,export default ' + encodeURIComponent(JSON.stringify(worker.href)), shortCircuit: true };
    }
    return nextResolve(specifier, context);
  },
});
after(() => {
  hooks.deregister();
  for (const [key, descriptor] of platform) {
    if (descriptor) Object.defineProperty(globalThis, key, descriptor);
    else delete globalThis[key];
  }
});
const { extractPdfText, LocalPdfPasswordRequiredError } = await import('../src/utils/pdfTextExtractor.js');

// ASCII PDF syntax + explicit Unicode CMap; no installed/system font or external resource.
function syntheticPdf(pages, { imageOnly = false, encrypted = false } = {}) {
  const objects = ['<< /Type /Catalog /Pages 2 0 R >>', '',
    '<< /Type /Font /Subtype /Type0 /BaseFont /Synthetic /Encoding /Identity-H /DescendantFonts [4 0 R] /ToUnicode 5 0 R >>',
    '<< /Type /Font /Subtype /CIDFontType2 /BaseFont /Synthetic /CIDSystemInfo << /Registry (Adobe) /Ordering (Identity) /Supplement 0 >> /DW 500 /FontDescriptor 6 0 R /CIDToGIDMap /Identity >>',
    '', '<< /Type /FontDescriptor /FontName /Synthetic /Flags 4 /FontBBox [0 -200 1000 900] /ItalicAngle 0 /Ascent 900 /Descent -200 /CapHeight 700 /StemV 80 >>'];
  const stream = content => '<< /Length ' + Buffer.byteLength(content) + ' >>\nstream\n' + content + '\nendstream';
  objects[4] = stream('/CIDInit /ProcSet findresource begin\n12 dict begin\nbegincmap\n/CIDSystemInfo << /Registry (Adobe) /Ordering (UCS) /Supplement 0 >> def\n/CMapName /Synthetic def\n/CMapType 2 def\n1 begincodespacerange\n<0000> <FFFF>\nendcodespacerange\n1 beginbfrange\n<0000> <FFFF> <0000>\nendbfrange\nendcmap\nCMapName currentdict /CMap defineresource pop\nend\nend');
  const kids = [];
  for (const items of pages) {
    const pageId = objects.length + 1;
    kids.push(pageId + ' 0 R');
    objects.push('<< /Type /Page /Parent 2 0 R /MediaBox [0 0 840 600] /Resources << /Font << /F1 3 0 R >> >> /Contents ' + (pageId + 1) + ' 0 R >>');
    const content = imageOnly ? 'q 10 0 0 10 20 20 cm BI /W 1 /H 1 /CS /G /BPC 8 /F /AHx ID ff> EI Q'
      : items.map(({ str, x, y }) => 'BT /F1 5 Tf 1 0 0 1 ' + x + ' ' + y + ' Tm <'
        + Array.from(str, character => character.charCodeAt(0).toString(16).padStart(4, '0')).join('') + '> Tj ET').join('\n');
    objects.push(stream(content));
  }
  objects[1] = '<< /Type /Pages /Count ' + pages.length + ' /Kids [' + kids.join(' ') + '] >>';
  let encrypt = '';
  if (encrypted) {
    objects.push('<< /Filter /Standard /V 1 /R 2 /Length 40 /P -4 /O <' + '00'.repeat(32) + '> /U <' + '00'.repeat(32) + '> >>');
    encrypt = ' /Encrypt ' + objects.length + ' 0 R /ID [<0123456789abcdef0123456789abcdef> <0123456789abcdef0123456789abcdef>]';
  }
  let pdf = '%PDF-1.7\n';
  const offsets = [0];
  objects.forEach((object, index) => {
    offsets.push(Buffer.byteLength(pdf));
    pdf += (index + 1) + ' 0 obj\n' + object + '\nendobj\n';
  });
  const xref = Buffer.byteLength(pdf);
  pdf += 'xref\n0 ' + offsets.length + '\n0000000000 65535 f \n'
    + offsets.slice(1).map(offset => String(offset).padStart(10, '0') + ' 00000 n \n').join('')
    + 'trailer\n<< /Size ' + offsets.length + ' /Root 1 0 R' + encrypt + ' >>\nstartxref\n' + xref + '\n%%EOF';
  return new TextEncoder().encode(pdf);
}

function tablePage(date, side = '구매', price = '7,830', header = true) {
  const columns = [['거래일자', 40], ['거래구분', 100], ['종목명(종목코드)', 165], ['환율', 300],
    ['거래수량', 340], ['단가', 430], ['수수료', 500], ['거래세', 560], ['제세금', 620]];
  const values = [date, side, 'KODEX 200(A069500)', '', '2', price, '1', side === '판매' ? '15' : '0', '0'];
  return [{ str: '토스증권 원화 거래내역', x: 40, y: 560 },
    ...(header ? columns.map(([str, x]) => ({ str, x, y: 500 })) : []),
    ...columns.map(([, x], index) => ({ str: values[index], x, y: 470 })).filter(item => item.str)];
}

async function readPdf(pages, options) {
  const bytes = syntheticPdf(pages, options);
  assert.ok(bytes.byteLength < 25 * 1024 * 1024);
  const file = new File([bytes], 'sanitized-synthetic.pdf', { type: 'application/pdf' });
  return extractPdfText(await file.arrayBuffer());
}

test('real local PDF.js reads synthetic File bytes and repeated-page tables with costs and numeric names', async () => {
  try {
  const extraction = await readPdf([tablePage('2026.09.01'), tablePage('2026.09.02', '판매')]);
  assert.equal(extraction.pageCount, 2);
  assert.deepEqual(extraction.pages.map(page => page.pageNumber), [1, 2]);
  assert.ok(extraction.textItemCount > 20);
  assert.ok(extraction.pages.every(page => page.items.every(item => typeof item.str === 'string' && Number.isFinite(item.x) && Number.isFinite(item.y))));
  assert.ok(extraction.pages.every(page => page.items.every(item => Number.isFinite(item.width) && item.width > 0)));
  assert.ok(extraction.pages[0].lines.some(line => line.includes('KODEX 200')));
  const result = parseBrokerStatement(extraction.text, extraction);
  assert.equal(result.status, BROKER_STATEMENT_STATUS.READY);
  assert.deepEqual(result.completeness, { recognizedRows: 2, parsedRows: 2 });
  assert.deepEqual(result.trades.map(row => [row.tradeDate, row.symbol, row.stockName, row.side, row.price, row.quantity, row.fee, row.tax]), [
    ['2026-09-02', '069500', 'KODEX 200', 'sell', 7830, 2, 1, 15],
    ['2026-09-01', '069500', 'KODEX 200', 'buy', 7830, 2, 1, 0],
  ]);
  const { GlobalWorkerOptions } = await import('pdfjs-dist/legacy/build/pdf.mjs');
  assert.equal(GlobalWorkerOptions.workerSrc, worker.href);
  assert.equal(workerUrlImports, 1);
  assert.ok(workerLoads > 0, 'the real bundled local worker module was loaded');
  assert.equal(identityMatrices, 1, 'no canvas rendering path ran');
  for (const splitAll of [false, true]) {
    const repeated = tablePage('2026.09.03', '판매').flatMap(item => {
      if (item.y !== 500 || (!splitAll && item.str !== '종목명(종목코드)')) return [item];
      const at = item.str === '종목명(종목코드)' ? 3 : 1;
      return [{ ...item, str: item.str.slice(0, at) }, { ...item, str: item.str.slice(at), x: item.x + at * 2.5, y: item.y + 0.25 }];
    });
    const split = await readPdf([tablePage('2026.09.02'), repeated]);
    // Drawing fragments may coalesce; ordinary integration asserts text and parser output, not item count.
    assert.equal(split.pageCount, 2);
    assert.ok(split.pages[1].lines.some(line => line.replace(/\s+/g, '').includes('종목명(종목코드)')));
    const parsed = parseBrokerStatement(split.text, split);
    assert.equal(parsed.status, BROKER_STATEMENT_STATUS.READY, 'split repeated header');
    assert.deepEqual(parsed.completeness, { recognizedRows: 2, parsedRows: 2 });
    assert.deepEqual(parsed.trades.map(row => [row.side, row.fee, row.tax]), [['sell', 1, 15], ['buy', 1, 0]]);
  }
  for (const offset of [0, 23]) {
    const repeated = tablePage('2026.09.03', '판매').flatMap(item => item.str === '종목명(종목코드)'
      ? [{ ...item, str: '종목명' }, { ...item, str: '(종목코드)', x: item.x + 3 * 2.5 + 12, y: item.y + 0.25 }]
      : [item]);
    // The diagnosed 12px gap controls PDF.js segmentation, independently of any parser column coordinate.
    const pages = [tablePage('2026.09.02'), repeated].map(items => items.map(item => ({ ...item, x: item.x + offset })));
    const split = await readPdf(pages);
    const fragments = split.pages[1].items.map(item => item.str.trim())
      .filter(text => text === '종목명' || text === '(종목코드)');
    assert.deepEqual(fragments, ['종목명', '(종목코드)'], 'deliberately spaced header reaches the real split-item path');
    const parsed = parseBrokerStatement(split.text, split);
    assert.equal(parsed.status, BROKER_STATEMENT_STATUS.READY, 'deliberately split repeated header');
    assert.deepEqual(parsed.completeness, { recognizedRows: 2, parsedRows: 2 });
    assert.deepEqual(parsed.trades.map(row => [row.symbol, row.side, row.price, row.quantity, row.fee, row.tax]),
      [['069500', 'sell', 7830, 2, 1, 15], ['069500', 'buy', 7830, 2, 1, 0]]);
  }
  const splitName = tablePage('2026.09.02').flatMap(item => item.str === 'KODEX 200(A069500)'
    ? [{ ...item, str: 'KODEX' }, { ...item, str: '200(A069500)', x: item.x + 15 }] : [item]);
  const name = await readPdf([splitName]);
  assert.equal(parseBrokerStatement(name.text, name).trades[0].stockName, 'KODEX 200');
  const foreign = tablePage('2026.09.02', '판매');
  foreign.find(item => item.str === 'KODEX 200(A069500)').str = 'US0378331005';
  foreign.find(item => item.str === '7,830').str = '10 USD';
  const mixed = await readPdf([tablePage('2026.09.01'), foreign]);
  const rejected = parseBrokerStatement(mixed.text, mixed);
  assert.equal(rejected.status, BROKER_STATEMENT_STATUS.OVERSEAS_UNSUPPORTED);
  assert.deepEqual(rejected.trades, []);
  const withFooter = tablePage('2026.09.02');
  withFooter.push({ str: '2026.09.02', x: 40, y: 120 }, { str: '2', x: 340, y: 120 }, { str: '7,830', x: 430, y: 120 });
  const withProse = [tablePage('2026.09.02'), [
    { str: '2026.09.02 기준 KODEX 200(A069500) 안내입니다.', x: 40, y: 200 },
    { str: '2026.09.02 구매 시 KODEX 200 (A069500) 안내입니다.', x: 40, y: 180 },
  ]];
  const nonTransactions = [[withFooter], withProse];
  for (const side of ['구매', '판매']) {
    nonTransactions.push([tablePage('2026.09.02'), [
      { str: '2026.09.02', x: 40, y: 200 }, { str: side, x: 100, y: 200 },
      { str: '시', x: 135, y: 200 }, { str: 'KODEX 200(A069500)', x: 165, y: 200 },
      { str: '안내입니다.', x: 330, y: 200 },
    ]]);
    for (const [index, x] of [[1, 145], [2, 270]]) {
      const misplaced = [
        { str: '2026.09.02', x: 40, y: 200 }, { str: side, x: 100, y: 200 },
        { str: 'KODEX 200(A069500)', x: 165, y: 200 },
      ];
      misplaced[index].x = x;
      nonTransactions.push([tablePage('2026.09.02'), misplaced]);
    }
    for (const x of [120, 130, 145]) {
      nonTransactions.push([tablePage('2026.09.02'), [
        { str: '2026.09.02', x: 40, y: 200 }, { str: side, x: 100, y: 200 },
        { str: '시', x, y: 200 }, { str: 'KODEX 200(A069500)', x: 165, y: 200 },
        { str: '안내입니다.', x: 330, y: 200 },
      ]]);
    }
  }
  for (const pages of nonTransactions) {
    const extracted = await readPdf(pages);
    const result = parseBrokerStatement(extracted.text, extracted);
    assert.equal(result.status, BROKER_STATEMENT_STATUS.READY);
    assert.deepEqual(result.completeness, { recognizedRows: 1, parsedRows: 1 });
    assert.equal(result.trades.length, 1);
  }
  } catch (error) {
    throw error;
  }
});

test('real PDF.js malformed rows and headerless continuation never expose partial trades', async () => {
  for (const broken of [tablePage('2026.09.02', '판매', '불명'), tablePage('2026.09.02', '판매', '7,830', false),
    tablePage('2026.09.02', '교환', '7,830', false), []]) {
    const extraction = await readPdf([tablePage('2026.09.01'), broken]);
    const result = parseBrokerStatement(extraction.text, extraction);
    assert.equal(result.status, BROKER_STATEMENT_STATUS.TOSS_INCOMPLETE);
    assert.deepEqual(result.trades, []);
  }
  for (const side of ['구매', '판매']) for (const missing of [true, false])
    for (const shifts of [[0, 0, 0], [0.25, 0, 0], [0, 0.25, 0], [0, 0, 0.25],
      [-0.25, 0, 0], [0, -0.25, 0], [0, 0, -0.25], [0.25, 0.25, 0.25], [0, 20, 20]]) {
    const broken = [
      { str: '2026.09.03', x: 40 + shifts[0], y: 470 }, { str: side, x: 100 + shifts[1], y: 470.25 },
      { str: 'KODEX 200(A069500)', x: 165 + shifts[2], y: 469.75 },
      ...(missing ? [] : [{ str: '불명', x: 340, y: 470 }, { str: '불명', x: 430, y: 470 }]),
    ];
    const extraction = await readPdf([tablePage('2026.09.02'), broken]);
    const result = parseBrokerStatement(extraction.text, extraction);
    assert.equal(result.status, BROKER_STATEMENT_STATUS.TOSS_INCOMPLETE, JSON.stringify({ side, missing, shifts }));
    assert.deepEqual(result.trades, []);
    assert.deepEqual(result.completeness, { recognizedRows: 2, parsedRows: 1 });
  }
});

test('real PDF.js tri-state composite damage rejects whole imports', async () => {
  try {
    for (const { name, changes, kind, samePage } of [...rowDamageMatrix(), ...transactionIdentityMatrix()]) {
      const positions = [40, 100, 165, 340, 430];
      const page = tablePage('2026.09.03').filter(item => item.y !== 470);
      page.push(...tradeFields.flatMap((key, index) => {
        const value = Object.hasOwn(changes, key) ? changes[key] : validTrade[index];
        return value === null ? [] : [{ str: value, x: positions[index] + (samePage ? 0 : 0.25), y: 470 + index % 2 * 0.25 }];
      }));
      const extraction = await readPdf(samePage
        ? [[...tablePage('2026.09.02'), ...page.filter(item => item.y < 500).map(item => ({ ...item, y: item.y - 30 }))]]
        : [tablePage('2026.09.02'), page]);
      const result = parseBrokerStatement(extraction.text, extraction);
      const incomplete = kind === 'incomplete_transaction';
      const parsed = kind === 'transaction' ? 2 : 1;
      assert.equal(result.status, incomplete ? BROKER_STATEMENT_STATUS.TOSS_INCOMPLETE : BROKER_STATEMENT_STATUS.READY, name);
      assert.deepEqual(result.completeness, { recognizedRows: incomplete ? 2 : parsed, parsedRows: parsed }, name);
      assert.equal(result.trades.length, incomplete ? 0 : parsed, name);
      assert.equal(new Set(result.trades.map(row => row.id)).size, result.trades.length, name);
    }
  } catch (error) {
    throw error;
  }
});

test('real PDF.js image-only PDFs have no invented OCR trades and invalid bytes are rejected', async () => {
  const extraction = await readPdf([[]], { imageOnly: true });
  assert.equal(extraction.text, '');
  assert.deepEqual(extraction.pages[0].items, []);
  assert.equal(parseBrokerStatement(extraction.text, extraction).status, BROKER_STATEMENT_STATUS.NO_CANDIDATES);
  await assert.rejects(extractPdfText(new TextEncoder().encode('not a PDF').buffer), { name: 'InvalidPDFException' });
  await assert.rejects(extractPdfText(new Uint8Array()), /ArrayBuffer/);
});

test('real PDF.js password admission refuses encrypted input without a password exchange', async () => {
  await assert.rejects(readPdf([tablePage('2026.09.01')], { encrypted: true }), LocalPdfPasswordRequiredError);
  const recovery = await readPdf([tablePage('2026.09.01')]);
  assert.equal(parseBrokerStatement(recovery.text, recovery).status, BROKER_STATEMENT_STATUS.READY);
});
