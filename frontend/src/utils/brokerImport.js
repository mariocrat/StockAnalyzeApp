const DATE_PATTERN = /(20\d{2})[./-](\d{1,2})[./-](\d{1,2})/;
const TIME_PATTERN = /(?:^|\s)([01]?\d|2[0-3]):([0-5]\d)(?::([0-5]\d))?(?=\s|$)/;
const SIDE_PATTERN = /(?:^|\s)(매수|매도|구매|판매|buy|sell)(?=\s|$)/i;
const SYMBOL_PATTERN = /^(?:[A-Za-z]?\d{6})$/;
const NUMBER_SOURCE = String.raw`\d[\d,]*(?:\.\d+)?`;
const QUANTITY_AT_PRICE_PATTERN = new RegExp(`^(${NUMBER_SOURCE})\\s*주\\s*@\\s*(${NUMBER_SOURCE})(?:\\s*원)?$`);
const PRICE_QUANTITY_PATTERN = new RegExp(`^(${NUMBER_SOURCE})\\s*원\\s+(${NUMBER_SOURCE})\\s*주$`);
const EXPLICIT_AMOUNT_TAIL_PATTERNS = [
  new RegExp(`^(.+?)\\s+(${NUMBER_SOURCE}\\s*주\\s*@\\s*${NUMBER_SOURCE}(?:\\s*원)?)$`),
  new RegExp(`^(.+?)\\s+(${NUMBER_SOURCE}\\s*원\\s+${NUMBER_SOURCE}\\s*주)$`),
];
const SENSITIVE_MARKER_PATTERN = /^(?:계좌|계좌번호|고객명|성명|이름|account|accountnumber|accountno|customer|name)$/i;
const TOSS_STATEMENT_PATTERN = /(?:토스증권|toss\s+securities)/i;
const TOSS_LAYOUT_MARKER_PATTERN = /(?:원화\s*-\s*외화\s*거래구분|종목명\s*\(\s*종목코드\s*\))/i;
const FOREIGN_SYMBOL_TOKEN_PATTERN = /(?:^|\s)(?:US|VG|KYG|CA)[A-Z0-9][A-Z0-9.-]*(?=\s|$)/i;
const FOREIGN_VALUE_PATTERN = /(?:\$|(?:^|\s)(?:USD|HKD|JPY|CNY)(?=\s|$)|환율|외화|달러)/i;
const DOMESTIC_SYMBOL_TOKEN_PATTERN = /(?:^|\s)\d{6}(?=\s|$)/;
const DOMESTIC_AMOUNT_PATTERN = new RegExp(`(?:${NUMBER_SOURCE}\\s*원|@\\s*${NUMBER_SOURCE})`);
const EMPTY_STATEMENT_PATTERN = /표시할\s*내역이\s*없습니다/;
const TOSS_DOMESTIC_ROW_PATTERN = /^20\d{2}[./-]\d{1,2}[./-]\d{1,2}\s+(?:매수|매도|구매|판매|\bbuy\b|\bsell\b)\s+.+?\s*\(A?\d{6}\)(?:\s|$)/i;
const DOMESTIC_MARKER_PATTERN = /(?:국내\s*주식|원화|\bKRW\b)/i;

export const TRADE_SIDES = Object.freeze({
  BUY: 'buy',
  SELL: 'sell',
});

function parseTradeSide(value) {
  const label = String(value || '').toLowerCase();
  if (['매수', '구매', 'buy'].includes(label)) return TRADE_SIDES.BUY;
  if (['매도', '판매', 'sell'].includes(label)) return TRADE_SIDES.SELL;
  return null;
}

export const BROKER_STATEMENT_STATUS = Object.freeze({
  READY: 'ready',
  NO_CANDIDATES: 'no-candidates',
  OVERSEAS_UNSUPPORTED: 'overseas-unsupported',
  TOSS_DOMESTIC_SAMPLE_REQUIRED: 'toss-domestic-sample-required',
  TOSS_INCOMPLETE: 'toss-incomplete',
});

export const BROKER_STATEMENT_MESSAGES = Object.freeze({
  OVERSEAS_UNSUPPORTED: '현재 증권사 거래내역 불러오기는 국내주식만 지원합니다.\n해외주식은 추후 지원 예정입니다.',
  TOSS_DOMESTIC_SAMPLE_REQUIRED: '토스증권 국내주식 거래내역서 형식은 국내주식 샘플 확인 후 지원할 예정입니다.',
  TOSS_INCOMPLETE: '일부 거래를 정확히 읽지 못해 가져오기를 중단했습니다. 거래 테이블과 모든 페이지가 포함된 텍스트 PDF인지 확인해주세요.',
});

export const REVIEW_TIME_VALIDATION_MESSAGES = Object.freeze({
  REQUIRED_GROUP: '같은 날 매수와 매도가 함께 선택되었습니다.\n정확한 거래 순서를 확인하려면 체결시간이 필요합니다.',
  BLOCKED: '체결시간을 확인해주세요.\n\n같은 날 매수와 매도가 포함된 거래는\n정확한 순서를 위해 체결시간이 필요합니다.',
});

function cleanToken(token) {
  return String(token || '').replace(/^[|·:;,()[\]{}]+|[|·:;,()[\]{}]+$/g, '');
}

function cleanCodeToken(token) {
  return String(token || '').replace(/^[^A-Za-z0-9]+|[^A-Za-z0-9]+$/g, '');
}

function isSymbolToken(token) {
  return SYMBOL_PATTERN.test(cleanCodeToken(token));
}

function parseNumber(token) {
  const value = Number(String(token).replaceAll(',', ''));
  return Number.isFinite(value) && value > 0 ? value : null;
}

function normalizeWhitespace(value) {
  return String(value || '')
    .replace(/\u00a0/g, ' ')
    .replace(/\s+/g, ' ')
    .trim();
}

function statementLines(value) {
  return String(value || '')
    .split(/\r?\n/)
    .map(normalizeWhitespace)
    .filter(Boolean);
}

function isEmptyStatementLine(line) {
  return EMPTY_STATEMENT_PATTERN.test(line);
}

function hasDomesticTradeEvidence(lines) {
  return lines.some(line => (
    !isEmptyStatementLine(line)
    && (
      (
        SIDE_PATTERN.test(line)
        && DOMESTIC_SYMBOL_TOKEN_PATTERN.test(line)
        && DOMESTIC_AMOUNT_PATTERN.test(line)
      )
      || TOSS_DOMESTIC_ROW_PATTERN.test(line)
    )
  ));
}

function hasActualOverseasTradeEvidence(lines) {
  return lines.some(line => {
    if (isEmptyStatementLine(line) || !SIDE_PATTERN.test(line)) return false;
    if (DOMESTIC_SYMBOL_TOKEN_PATTERN.test(line)) return false;
    const hasForeignCode = FOREIGN_SYMBOL_TOKEN_PATTERN.test(line);
    const hasForeignValue = FOREIGN_VALUE_PATTERN.test(line) && /\d/.test(line);
    return hasForeignCode || hasForeignValue;
  });
}

export function normalizeOptionalTradeTime(value) {
  const text = String(value || '').trim();
  if (!text) return null;
  const match = text.match(/^([01]\d|2[0-3]):([0-5]\d)$/);
  return match ? `${match[1]}:${match[2]}` : null;
}

export function createTradeTimeState(tradeTime = null) {
  const normalizedTradeTime = normalizeOptionalTradeTime(tradeTime);
  return {
    tradeTime: normalizedTradeTime,
    timeUnknown: normalizedTradeTime === null,
  };
}

export function updateTradeTimeState(state, value) {
  return {
    ...state,
    tradeTime: normalizeOptionalTradeTime(value),
    timeUnknown: false,
  };
}

export function setTradeTimeUnknownState(state, unknown) {
  return {
    ...state,
    tradeTime: unknown ? null : '',
    timeUnknown: Boolean(unknown),
  };
}

function tradeDateValue(trade) {
  return String(trade?.tradeDate || trade?.trade_date || '').trim().slice(0, 10);
}

function tradeSymbolValue(trade) {
  return String(trade?.symbol || trade?.ticker || '').trim();
}

export function getTradeTimeGroupKey(trade) {
  const tradeDate = tradeDateValue(trade);
  const symbol = tradeSymbolValue(trade);
  // A name-only fallback could combine different instruments with the same name.
  // Without a stable symbol, leave the trade outside the required-time grouping.
  return tradeDate && symbol ? tradeDate + '|' + symbol : null;
}

function hasKnownTradeTime(trade) {
  return trade?.timeUnknown !== true && Boolean(normalizeOptionalTradeTime(trade?.tradeTime));
}

export function getRequiredTradeTimeGroups(trades = []) {
  const groups = new Map();
  trades.forEach((trade, index) => {
    const key = getTradeTimeGroupKey(trade);
    if (!key) return;
    if (!groups.has(key)) {
      groups.set(key, {
        key,
        tradeDate: tradeDateValue(trade),
        symbol: tradeSymbolValue(trade),
        name: String(trade?.stockName || trade?.name || '').trim(),
        trades: [],
        buyCount: 0,
        sellCount: 0,
      });
    }
    const group = groups.get(key);
    group.trades.push({ trade, index });
    if (trade?.side === TRADE_SIDES.SELL) group.sellCount += 1;
    if (trade?.side === TRADE_SIDES.BUY) group.buyCount += 1;
  });

  return [...groups.values()]
    .filter(group => group.buyCount > 0 && group.sellCount > 0)
    .map(group => {
      const missingTrades = group.trades
        .filter(({ trade }) => !hasKnownTradeTime(trade))
        .map(({ trade }) => trade);
      return {
        ...group,
        trades: group.trades.map(({ trade }) => trade),
        missingTrades,
        requiredTradeIds: group.trades.map(({ trade }) => trade.id),
        missingTradeIds: missingTrades.map(trade => trade.id),
      };
    });
}

export function validateTradeTimesForReview(trades = []) {
  const requiredGroups = getRequiredTradeTimeGroups(trades);
  const missingGroups = requiredGroups.filter(group => group.missingTrades.length > 0);
  return {
    valid: missingGroups.length === 0,
    requiredGroups,
    missingGroups,
    requiredTradeIds: requiredGroups.flatMap(group => group.requiredTradeIds),
    missingTradeIds: missingGroups.flatMap(group => group.missingTradeIds),
  };
}

export function detectBrokerStatement(text) {
  const normalized = normalizeWhitespace(text);
  const lines = statementLines(text);
  const hasTossMarker = TOSS_STATEMENT_PATTERN.test(normalized) || TOSS_LAYOUT_MARKER_PATTERN.test(normalized);
  const hasDomesticTrade = hasDomesticTradeEvidence(lines);
  const hasActualOverseasTrade = hasActualOverseasTradeEvidence(lines);
  const hasOverseasMarker = hasActualOverseasTrade;
  const hasDomesticMarker = DOMESTIC_MARKER_PATTERN.test(normalized) || hasDomesticTrade;
  return {
    broker: hasTossMarker ? 'toss' : 'unknown',
    market: hasActualOverseasTrade ? 'overseas' : hasDomesticMarker ? 'domestic' : 'unknown',
    currency: hasActualOverseasTrade ? 'foreign' : hasDomesticMarker ? 'krw' : null,
    hasTossMarker,
    hasOverseasMarker,
    hasDomesticMarker,
  };
}

function parseDate(match) {
  const year = Number(match[1]);
  const month = Number(match[2]);
  const day = Number(match[3]);
  const date = new Date(Date.UTC(year, month - 1, day));
  if (
    date.getUTCFullYear() !== year
    || date.getUTCMonth() !== month - 1
    || date.getUTCDate() !== day
  ) {
    return null;
  }
  return `${String(year).padStart(4, '0')}-${String(month).padStart(2, '0')}-${String(day).padStart(2, '0')}`;
}

function parseTime(line, dateMatch) {
  const match = line.match(TIME_PATTERN);
  if (!match || match.index < dateMatch.index + dateMatch[0].length) return null;
  return normalizeOptionalTradeTime(`${String(match[1]).padStart(2, '0')}:${match[2]}`);
}

function stripMetadata(value) {
  return normalizeWhitespace(String(value || '')
    .replace(DATE_PATTERN, ' ')
    .replace(TIME_PATTERN, ' '));
}

function parseExplicitAmount(value) {
  const normalized = normalizeWhitespace(value);
  let match = normalized.match(QUANTITY_AT_PRICE_PATTERN);
  if (match) {
    const quantity = parseNumber(match[1]);
    const price = parseNumber(match[2]);
    return quantity === null || price === null ? null : { price, quantity };
  }

  match = normalized.match(PRICE_QUANTITY_PATTERN);
  if (match) {
    const price = parseNumber(match[1]);
    const quantity = parseNumber(match[2]);
    return quantity === null || price === null ? null : { price, quantity };
  }

  return null;
}

function parseInstrument(value) {
  const tokens = stripMetadata(value).split(/\s+/).filter(Boolean);
  if (tokens.length < 1 || tokens.length > 2) return null;

  const stockName = cleanToken(tokens[0]);
  const symbol = tokens.length === 2 && isSymbolToken(tokens[1])
    ? cleanCodeToken(tokens[1])
    : null;
  if (tokens.length === 2 && !symbol) return null;
  if (!stockName || /\d/.test(stockName) || SENSITIVE_MARKER_PATTERN.test(stockName)) return null;
  if (/[|·:;,()[\]{}]/.test(stockName)) return null;

  return { stockName, symbol };
}

function splitTrailingAmount(value) {
  const normalized = normalizeWhitespace(value);
  for (const pattern of EXPLICIT_AMOUNT_TAIL_PATTERNS) {
    const match = normalized.match(pattern);
    if (!match) continue;
    const amount = parseExplicitAmount(match[2]);
    if (amount) return { instrumentText: match[1], ...amount };
  }
  return null;
}

function parseTradeLine(line, sourceIndex) {
  const dateMatch = line.match(DATE_PATTERN);
  if (!dateMatch) return null;

  const tradeDate = parseDate(dateMatch);
  if (!tradeDate) return null;

  const sideMatch = line.match(SIDE_PATTERN);
  if (!sideMatch) return null;

  const side = parseTradeSide(sideMatch[1]);
  if (!side) return null;
  const beforeSide = normalizeWhitespace(line.slice(dateMatch.index + dateMatch[0].length, sideMatch.index));
  const afterSide = normalizeWhitespace(line.slice(sideMatch.index + sideMatch[0].length));
  if (SIDE_PATTERN.test(afterSide)) return null;
  const beforeInstrument = stripMetadata(beforeSide);
  let instrument;
  let amount;

  const directAmount = parseExplicitAmount(afterSide);
  if (directAmount) {
    instrument = parseInstrument(beforeInstrument);
    amount = directAmount;
  } else {
    const trailingAmount = splitTrailingAmount(afterSide);
    if (!trailingAmount || beforeInstrument) return null;
    instrument = parseInstrument(trailingAmount.instrumentText);
    amount = trailingAmount;
  }

  if (!instrument || !amount) return null;

  return {
    id: `pdf-trade-${sourceIndex + 1}`,
    broker: 'unidentified',
    tradeDate,
    tradeTime: parseTime(line, dateMatch),
    symbol: instrument.symbol,
    stockName: instrument.stockName,
    side,
    quantity: amount.quantity,
    price: amount.price,
    fee: null,
    tax: null,
    sourceIndex,
  };
}

export function sortTradesByDateDesc(trades) {
  return [...trades].sort((a, b) => {
    if (a.tradeDate !== b.tradeDate) return b.tradeDate.localeCompare(a.tradeDate);
    if (a.tradeTime && b.tradeTime && a.tradeTime !== b.tradeTime) {
      return b.tradeTime.localeCompare(a.tradeTime);
    }
    if (a.tradeTime !== b.tradeTime) return a.tradeTime ? -1 : 1;
    return (a.sourceIndex ?? 0) - (b.sourceIndex ?? 0);
  });
}

// Prototype-only fallback: recognize explicit text rows, not a broker-specific PDF layout.
// Amounts need explicit units/markers; ambiguous numeric-only rows and multi-token prefixes are rejected.
export function parseTradeCandidates(text) {
  const lines = String(text || '')
    .split(/\r?\n/)
    .map(normalizeWhitespace)
    .filter(Boolean);
  return sortTradesByDateDesc(
    lines
      .map((line, sourceIndex) => parseTradeLine(line, sourceIndex))
      .filter(Boolean),
  );
}

const TOSS_COLUMN_LABELS = Object.freeze({
  tradeDate: '거래일자',
  side: '거래구분',
  instrument: '종목명(종목코드)',
  exchangeRate: '환율',
  quantity: '거래수량',
  tradeAmount: '거래대금',
  settlementAmount: '정산금액',
  price: '단가',
  fee: '수수료',
  transactionTax: '거래세',
  tax: '제세금',
  adjustment: '변제/연체합',
  balance: '잔고',
  cashBalance: '잔액',
});

const TOSS_REQUIRED_COLUMN_KEYS = ['tradeDate', 'side', 'instrument', 'quantity', 'price'];

function layoutItemText(item) {
  return String(item?.str ?? item?.text ?? '').trim();
}

function layoutItemX(item) {
  return Number(item?.x ?? item?.transform?.[4]);
}

function layoutItemY(item) {
  return Number(item?.y ?? item?.transform?.[5]);
}

function compactLayoutText(value) {
  return normalizeWhitespace(value).replace(/\s+/g, '');
}

function groupLayoutItemsIntoRows(items) {
  const rows = [];
  (items || [])
    .filter(item => layoutItemText(item))
    .forEach(item => {
      const x = layoutItemX(item);
      const y = layoutItemY(item);
      if (!Number.isFinite(x) || !Number.isFinite(y)) return;
      let row = rows.find(candidate => Math.abs(candidate.y - y) <= 3);
      if (!row) {
        row = { y, items: [] };
        rows.push(row);
      }
      row.items.push({ x, y, text: layoutItemText(item), width: Number(item.width) });
    });

  return rows
    .sort((a, b) => b.y - a.y)
    .map(row => ({ ...row, items: row.items.sort((a, b) => a.x - b.x) }));
}

function findTossHeaderColumns(headerRow) {
  const columns = [];
  const labels = Object.entries(TOSS_COLUMN_LABELS).map(([key, label]) => [key, compactLayoutText(label)]);
  for (let index = 0; index < headerRow.items.length;) {
    const first = headerRow.items[index];
    let text = '';
    let role = null;
    while (index < headerRow.items.length && !role) {
      text += compactLayoutText(headerRow.items[index++].text);
      if (!labels.some(([, label]) => label.startsWith(text))) return null;
      role = labels.find(([, label]) => label === text);
    }
    if (!role || columns.some(column => column.key === role[0])) return null;
    columns.push({ key: role[0], x: first.x });
  }
  if (!TOSS_REQUIRED_COLUMN_KEYS.every(key => columns.some(column => column.key === key))
    || columns.some((column, index) => index > 0 && column.x <= columns[index - 1].x)) return null;
  // Voronoi bands come from adjacent observed header starts, not fixed PDF coordinates.
  return columns.map((column, index) => ({
    ...column,
    left: index ? (columns[index - 1].x + column.x) / 2 : column.x - (columns[1].x - column.x) / 2,
    right: index + 1 < columns.length ? (column.x + columns[index + 1].x) / 2
      : column.x + (column.x - columns[index - 1].x) / 2,
  }));
}

function assignLayoutCells(row, columns) {
  const cells = Object.fromEntries(columns.map(column => [column.key, []]));
  row.items.forEach(item => {
    const column = columns.find(column => item.x >= column.left && item.x < column.right);
    if (column) cells[column.key].push(item);
  });
  return cells;
}

function layoutCellText(cells, key) {
  return normalizeWhitespace((cells[key] || []).map(item => item.text).join(' '));
}

function layoutIdentityText(cells, key) {
  const runs = [];
  let previous = null;
  for (const item of cells[key] || []) {
    const advance = previous?.width / Array.from(previous?.text || '').length;
    const gap = previous ? item.x - (previous.x + previous.width) : NaN;
    // Join PDF.js fragments only within one observed character advance; distant prose is a separate run.
    if (previous?.width > 0 && item.width > 0 && Math.abs(gap) <= advance) {
      runs[runs.length - 1] += (gap > 0 ? ' ' : '') + item.text;
    } else runs.push(item.text);
    previous = item;
  }
  return runs.length === 1 ? normalizeWhitespace(runs[0]) : '';
}

function parseLayoutNumber(value) {
  const number = parseLayoutCost(value);
  return number !== null && number > 0 ? number : null;
}

function parseLayoutCost(value) {
  const text = String(value || '').trim();
  if (!/^(?:\d+|\d{1,3}(?:,\d{3})+)(?:\.\d+)?$/.test(text)) return null;
  const cost = Number(text.replaceAll(',', ''));
  return Number.isFinite(cost) && cost <= Number.MAX_SAFE_INTEGER ? cost : null;
}

function parseTossInstrumentCell(value) {
  const match = String(value || '').match(/^(.+?)\s*\(\s*(A?\d{6})\s*\)$/i);
  if (!match) return null;
  const stockName = normalizeWhitespace(match[1]);
  const rawSymbol = cleanCodeToken(match[2]).toUpperCase();
  const symbol = rawSymbol.replace(/^A/, '');
  if (
    !stockName
    || !/[A-Za-z가-힣]/.test(stockName)
    || SENSITIVE_MARKER_PATTERN.test(stockName)
    || /[|·:;,()[\]{}]/.test(stockName)
    || !/^\d{6}$/.test(symbol)
  ) return null;
  return { stockName, rawSymbol, symbol };
}

function parseTossLayoutTrade(cells, sourceIndex) {
  const dateMatch = layoutIdentityText(cells, 'tradeDate').match(/^(20\d{2})[./-](\d{1,2})[./-](\d{1,2})$/);
  const tradeDate = dateMatch ? parseDate(dateMatch) : null;
  const sideMatch = layoutIdentityText(cells, 'side').match(/^(매수|매도|구매|판매|buy|sell)$/i);
  const instrument = parseTossInstrumentCell(layoutIdentityText(cells, 'instrument'));
  const quantity = parseLayoutNumber(layoutCellText(cells, 'quantity'));
  const price = parseLayoutNumber(layoutCellText(cells, 'price'));
  if (!tradeDate || !sideMatch || !instrument || quantity === null || price === null) return null;

  const side = parseTradeSide(sideMatch[1]);
  if (!side) return null;
  const fee = parseLayoutCost(layoutCellText(cells, 'fee'));
  const transactionTax = parseLayoutCost(layoutCellText(cells, 'transactionTax'));
  const otherTax = parseLayoutCost(layoutCellText(cells, 'tax'));
  // These are separate charges; an absent component is not an explicit zero.
  const tax = transactionTax !== null && otherTax !== null ? transactionTax + otherTax : null;
  return {
    id: 'pdf-trade-' + (sourceIndex + 1),
    broker: 'toss',
    tradeDate,
    tradeTime: null,
    rawSymbol: instrument.rawSymbol,
    symbol: instrument.symbol,
    stockName: instrument.stockName,
    side,
    quantity,
    price,
    fee,
    tax: Number.isFinite(tax) && tax <= Number.MAX_SAFE_INTEGER ? tax : null,
    sourceIndex,
  };
}

function normalizeTossTableRow(row, columns) {
  const cells = assignLayoutCells(row, columns);
  const fields = Object.fromEntries(TOSS_REQUIRED_COLUMN_KEYS.map(key => [key, layoutIdentityText(cells, key)]));
  const occupied = TOSS_REQUIRED_COLUMN_KEYS.filter(key => fields[key]);
  return { cells, fields, occupied };
}

function classifyTossLayoutRow(row, columns, sourceIndex, hasPageHeader) {
  if (!columns) return { kind: 'non_transaction' };
  const { cells, fields, occupied } = normalizeTossTableRow(row, columns);
  const identityRoles = [DATE_PATTERN.test(fields.tradeDate), Boolean(parseTradeSide(fields.side)),
    Boolean(parseTossInstrumentCell(fields.instrument))];
  const numericSlots = ['quantity', 'price'].filter(key => /^[+-]?\d/.test(fields[key]));

  if (!hasPageHeader) {
    // Prior geometry admits only strong continuation evidence, never a parsed trade.
    const continuationShapes = [identityRoles.every(Boolean),
      occupied.length === 5 && identityRoles.filter(Boolean).length >= 2 && numericSlots.length === 2];
    return { kind: continuationShapes.some(Boolean) ? 'incomplete_transaction' : 'non_transaction' };
  }

  // Occupied table slots alone cannot distinguish a trade from a summary or balance row.
  const hasTransactionIdentity = identityRoles[1] || identityRoles[2];
  if (!hasTransactionIdentity) return { kind: 'non_transaction' };

  // Shape describes independent occupied slots, not successful mandatory-field parsing.
  const tableShapes = [
    occupied.length === 5,
    identityRoles.every(Boolean),
    occupied.length >= 3 && numericSlots.length > 0 && (identityRoles[0] || identityRoles[1])
      && (occupied.includes('side') || occupied.includes('instrument')),
  ];
  if (!tableShapes.some(Boolean)) return { kind: 'non_transaction' };
  const trade = parseTossLayoutTrade(cells, sourceIndex);
  return trade ? { kind: 'transaction', trade } : { kind: 'incomplete_transaction' };
}

function isTossTextTransactionLine(text) {
  const valueField = /^-?\d[\d,]*(?:\.\d+)?(?:원|주)?$/;
  const tradePrefix = /^(?:20\d{2}[./-]\d{1,2}[./-]\d{1,2}\s+)?(?:매수|매도|구매|판매|buy|sell)(?=\s)/i;
  const tail = text.split(/\(\s*A?\d{6}\s*\)\s*/i)[1]?.trim().split(/\s+/);
  const numericTail = tail?.length >= 2 && tail.every(value => valueField.test(value));
  const explicitAmounts = DOMESTIC_SYMBOL_TOKEN_PATTERN.test(text) && DOMESTIC_AMOUNT_PATTERN.test(text);
  return Boolean(((tradePrefix.test(text) && (tail ?? text.split(/\s+/)).some(value => valueField.test(value)))
    || numericTail || explicitAmounts) && [DATE_PATTERN.test(text), SIDE_PATTERN.test(text),
    /\(\s*A?\d{6}\s*\)/i.test(text) || explicitAmounts].filter(Boolean).length >= 2);
}

function parseTossDomesticLayout(extraction) {
  const { pages, pageCount } = extraction;
  const trades = [];
  let recognizedRows = 0;
  let incomplete = !pages.length || (pageCount !== undefined && pageCount !== pages.length);
  let recognitionColumns = null;
  pages.forEach((page, index) => {
    if (page?.pageNumber !== index + 1 || !Array.isArray(page.items)
      || page.items.some(item => layoutItemText(item)
        && (!Number.isFinite(layoutItemX(item)) || !Number.isFinite(layoutItemY(item))))) {
      incomplete = true;
      return;
    }
    const rows = groupLayoutItemsIntoRows(page.items);
    if (!rows.length) incomplete = true; // A blank/scanned page cannot prove completeness.
    let columns = null;
    for (const row of rows) {
      const header = findTossHeaderColumns(row);
      if (header) {
        columns = header;
        recognitionColumns = columns;
        continue;
      }
      const classified = classifyTossLayoutRow(row, columns || recognitionColumns, recognizedRows, Boolean(columns));
      if (classified.kind === 'non_transaction') continue;
      recognizedRows += 1;
      if (classified.kind === 'incomplete_transaction') incomplete = true;
      else trades.push(classified.trade);
    }
  });
  return { trades: sortTradesByDateDesc(trades), recognizedRows, incomplete };
}

export function parseTossDomesticStatement(text, extraction = null) {
  const detection = detectBrokerStatement(text);
  const hasLayout = Array.isArray(extraction?.pages);
  const result = hasLayout ? parseTossDomesticLayout(extraction) : {
    trades: parseTradeCandidates(text).filter(trade => /^\d{6}$/.test(trade.symbol || '')),
    recognizedRows: statementLines(text).filter(isTossTextTransactionLine).length,
    incomplete: false,
  };
  const completeness = { recognizedRows: result.recognizedRows, parsedRows: result.trades.length };
  if (result.incomplete || completeness.recognizedRows !== completeness.parsedRows) {
    return { status: BROKER_STATEMENT_STATUS.TOSS_INCOMPLETE, detection, trades: [], completeness };
  }
  return {
    status: detection.market === 'domestic' && result.trades.length
      ? BROKER_STATEMENT_STATUS.READY
      : BROKER_STATEMENT_STATUS.TOSS_DOMESTIC_SAMPLE_REQUIRED,
    detection,
    trades: detection.market === 'domestic' ? result.trades : [],
    completeness,
  };
}

export function parseBrokerStatement(text, extraction = null) {
  const detection = detectBrokerStatement(text);
  if (detection.market === 'overseas') {
    return {
      status: BROKER_STATEMENT_STATUS.OVERSEAS_UNSUPPORTED,
      detection,
      trades: [],
    };
  }
  if (detection.broker === 'toss') return parseTossDomesticStatement(text, extraction);

  const trades = parseTradeCandidates(text);
  return {
    status: trades.length ? BROKER_STATEMENT_STATUS.READY : BROKER_STATEMENT_STATUS.NO_CANDIDATES,
    detection,
    trades,
  };
}

export function formatTradeDate(tradeDate) {
  return String(tradeDate || '').replaceAll('-', '.');
}

export function formatTradeDateTime(trade) {
  return trade.tradeTime ? `${formatTradeDate(trade.tradeDate)} ${trade.tradeTime}` : formatTradeDate(trade.tradeDate);
}

export function formatTradeNumber(value) {
  if (!Number.isFinite(Number(value))) return '-';
  return Number(value).toLocaleString('ko-KR', { maximumFractionDigits: 8 });
}

export function tradeSideLabel(side) {
  return side === TRADE_SIDES.BUY ? '매수' : '매도';
}
