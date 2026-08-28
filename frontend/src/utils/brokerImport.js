const DATE_PATTERN = /(20\d{2})[./-](\d{1,2})[./-](\d{1,2})/;
const TIME_PATTERN = /(?:^|\s)([01]?\d|2[0-3]):([0-5]\d)(?::([0-5]\d))?(?=\s|$)/;
const SIDE_PATTERN = /(매수|매도|\bbuy\b|\bsell\b)/i;
const SYMBOL_PATTERN = /^(?:[A-Za-z]?\d{6})$/;
const NUMBER_SOURCE = String.raw`\d[\d,]*(?:\.\d+)?`;
const QUANTITY_AT_PRICE_PATTERN = new RegExp(`^(${NUMBER_SOURCE})\\s*주\\s*@\\s*(${NUMBER_SOURCE})(?:\\s*원)?$`);
const PRICE_QUANTITY_PATTERN = new RegExp(`^(${NUMBER_SOURCE})\\s*원\\s+(${NUMBER_SOURCE})\\s*주$`);
const EXPLICIT_AMOUNT_TAIL_PATTERNS = [
  new RegExp(`^(.+?)\\s+(${NUMBER_SOURCE}\\s*주\\s*@\\s*${NUMBER_SOURCE}(?:\\s*원)?)$`),
  new RegExp(`^(.+?)\\s+(${NUMBER_SOURCE}\\s*원\\s+${NUMBER_SOURCE}\\s*주)$`),
];
const SENSITIVE_MARKER_PATTERN = /^(?:계좌|계좌번호|고객명|성명|이름|account|accountnumber|accountno|customer|name)$/i;

export const TRADE_SIDES = Object.freeze({
  BUY: 'buy',
  SELL: 'sell',
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
  return `${String(match[1]).padStart(2, '0')}:${match[2]}${match[3] ? `:${match[3]}` : ''}`;
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
