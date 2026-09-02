const DATE_PATTERN = /(20\d{2})[./-](\d{1,2})[./-](\d{1,2})/;
const TIME_PATTERN = /(?:^|\s)([01]?\d|2[0-3]):([0-5]\d)(?::([0-5]\d))?(?=\s|$)/;
const SIDE_PATTERN = /(매수|매도|구매|판매|\bbuy\b|\bsell\b)/i;
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

export const BROKER_STATEMENT_STATUS = Object.freeze({
  READY: 'ready',
  NO_CANDIDATES: 'no-candidates',
  OVERSEAS_UNSUPPORTED: 'overseas-unsupported',
  TOSS_DOMESTIC_SAMPLE_REQUIRED: 'toss-domestic-sample-required',
});

export const BROKER_STATEMENT_MESSAGES = Object.freeze({
  OVERSEAS_UNSUPPORTED: '현재 증권사 거래내역 불러오기는 국내주식만 지원합니다.\n해외주식은 추후 지원 예정입니다.',
  TOSS_DOMESTIC_SAMPLE_REQUIRED: '토스증권 국내주식 거래내역서 형식은 국내주식 샘플 확인 후 지원할 예정입니다.',
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

  const normalizedSide = sideMatch[1].toLowerCase();
  const side = normalizedSide === '매수' || normalizedSide === 'buy'
    ? TRADE_SIDES.BUY
    : TRADE_SIDES.SELL;
  const beforeSide = normalizeWhitespace(line.slice(dateMatch.index + dateMatch[0].length, sideMatch.index));
  const afterSide = normalizeWhitespace(line.slice(sideMatch.index + sideMatch[0].length));
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
  return Number(item?.x ?? item?.transform?.[4] ?? 0);
}

function layoutItemY(item) {
  return Number(item?.y ?? item?.transform?.[5] ?? 0);
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
      row.items.push({ x, y, text: layoutItemText(item) });
    });

  return rows
    .sort((a, b) => b.y - a.y)
    .map(row => ({ ...row, items: row.items.sort((a, b) => a.x - b.x) }));
}

function findTossHeaderRow(rows) {
  return rows.find(row => TOSS_REQUIRED_COLUMN_KEYS.every(key => (
    row.items.some(item => compactLayoutText(item.text).includes(compactLayoutText(TOSS_COLUMN_LABELS[key])))
  )));
}

function findTossHeaderColumns(headerRow) {
  return Object.entries(TOSS_COLUMN_LABELS)
    .map(([key, label]) => {
      const item = headerRow.items.find(candidate => (
        compactLayoutText(candidate.text).includes(compactLayoutText(label))
      ));
      return item ? { key, x: item.x } : null;
    })
    .filter(Boolean);
}

function assignLayoutCells(row, columns) {
  const cells = Object.fromEntries(columns.map(column => [column.key, []]));
  row.items.forEach(item => {
    const nearest = columns.reduce((best, column) => {
      const distance = Math.abs(item.x - column.x);
      return !best || distance < best.distance ? { column, distance } : best;
    }, null);
    if (nearest) cells[nearest.column.key].push(item.text);
  });
  return cells;
}

function layoutCellText(cells, key) {
  return normalizeWhitespace((cells[key] || []).join(' '));
}

function parseLayoutNumber(value) {
  const match = String(value || '').match(/^\s*(\d[\d,]*(?:\.\d+)?)\s*$/);
  return match ? parseNumber(match[1]) : null;
}

function parseTossInstrumentCell(value) {
  const match = String(value || '').match(/^(.+?)\s*\(\s*(A?\d{6})\s*\)$/i);
  if (!match) return null;
  const stockName = normalizeWhitespace(match[1]);
  const rawSymbol = cleanCodeToken(match[2]).toUpperCase();
  const symbol = rawSymbol.replace(/^A/, '');
  if (
    !stockName
    || /\d/.test(stockName)
    || SENSITIVE_MARKER_PATTERN.test(stockName)
    || /[|·:;,()[\]{}]/.test(stockName)
    || !/^\d{6}$/.test(symbol)
  ) return null;
  return { stockName, rawSymbol, symbol };
}

function parseTossLayoutTrade(row, columns, sourceIndex) {
  const cells = assignLayoutCells(row, columns);
  const dateMatch = layoutCellText(cells, 'tradeDate').match(DATE_PATTERN);
  const tradeDate = dateMatch ? parseDate(dateMatch) : null;
  const sideMatch = layoutCellText(cells, 'side').match(/^(매수|매도|구매|판매|buy|sell)$/i);
  const instrument = parseTossInstrumentCell(layoutCellText(cells, 'instrument'));
  const quantity = parseLayoutNumber(layoutCellText(cells, 'quantity'));
  const price = parseLayoutNumber(layoutCellText(cells, 'price'));
  if (!tradeDate || !sideMatch || !instrument || quantity === null || price === null) return null;

  const normalizedSide = sideMatch[1].toLowerCase();
  const side = normalizedSide === '매수' || normalizedSide === '구매' || normalizedSide === 'buy'
    ? TRADE_SIDES.BUY
    : TRADE_SIDES.SELL;
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
    fee: null,
    tax: null,
    sourceIndex,
  };
}

function parseTossDomesticLayout(pages) {
  if (!Array.isArray(pages)) return [];
  const trades = [];
  let sourceIndex = 0;
  pages.forEach(page => {
    const rows = groupLayoutItemsIntoRows(page?.items || []);
    const headerRow = findTossHeaderRow(rows);
    if (!headerRow) return;
    const columns = findTossHeaderColumns(headerRow);
    if (!TOSS_REQUIRED_COLUMN_KEYS.every(key => columns.some(column => column.key === key))) return;
    rows.forEach(row => {
      const trade = parseTossLayoutTrade(row, columns, sourceIndex);
      if (!trade) return;
      trades.push(trade);
      sourceIndex += 1;
    });
  });
  return sortTradesByDateDesc(trades);
}

export function parseTossDomesticStatement(text, extraction = null) {
  const detection = detectBrokerStatement(text);
  const hasLayout = Array.isArray(extraction?.pages);
  const layoutTrades = hasLayout ? parseTossDomesticLayout(extraction.pages) : [];
  const fallbackTrades = hasLayout
    ? []
    : parseTradeCandidates(text).filter(trade => /^\d{6}$/.test(trade.symbol || ''));
  const domesticTrades = layoutTrades.length ? layoutTrades : fallbackTrades;
  return {
    status: detection.market === 'domestic' && domesticTrades.length
      ? BROKER_STATEMENT_STATUS.READY
      : BROKER_STATEMENT_STATUS.TOSS_DOMESTIC_SAMPLE_REQUIRED,
    detection,
    trades: detection.market === 'domestic' ? domesticTrades : [],
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
