import { normalizeOptionalTradeTime, validateTradeTimesForReview } from './brokerImport.js';

// UI identity and time provenance are deliberately not JournalTradeIn fields.
export function prepareBrokerReviewInput(selectedTrades = []) {
  if (!selectedTrades.length) throw new Error('복기할 거래를 선택해 주세요.');
  if (!validateTradeTimesForReview(selectedTrades).valid) {
    throw new Error('같은 날 같은 종목의 매수와 매도가 함께 선택되어 있습니다. 정확한 거래 순서를 위해 해당 거래의 체결시간을 입력해주세요.');
  }

  const bySymbol = new Map();
  selectedTrades.forEach((trade, index) => {
    const date = String(trade.tradeDate || '');
    const ticker = String(trade.symbol || '');
    const name = String(trade.stockName || '');
    const time = trade.timeUnknown === true ? null : normalizeOptionalTradeTime(trade.tradeTime);
    const price = Number(trade.price);
    const quantity = Number(trade.quantity);
    const fee = Number(trade.fee ?? 0);
    const tax = Number(trade.tax ?? 0);
    if (!/^\d{4}-\d{2}-\d{2}$/.test(date)
      || !Number.isFinite(Date.parse(`${date}T00:00:00Z`))
      || new Date(`${date}T00:00:00Z`).toISOString().slice(0, 10) !== date
      || !/^\d{6}$/.test(ticker) || !name.trim()
      || !['buy', 'sell'].includes(trade.side)
      || !Number.isFinite(price) || price <= 0 || !Number.isFinite(quantity) || quantity <= 0
      || !Number.isFinite(fee) || fee < 0 || !Number.isFinite(tax) || tax < 0
      || (trade.timeUnknown !== true && trade.tradeTime && !time)) {
      throw new Error('가져온 거래의 날짜, 종목, 가격, 수량과 체결시간을 확인해주세요.');
    }
    const input = {
      trade_date: time ? `${date}T${time}` : date,
      ticker, name, side: trade.side, price, quantity, fee, tax,
      memo: String(trade.memo ?? ''), source: 'broker_import',
    };
    if (!bySymbol.has(ticker)) {
      bySymbol.set(ticker, { key: `broker:${ticker}`, ticker, name, rows: [] });
    }
    bySymbol.get(ticker).rows.push({
      input,
      preview: { ...input, previewId: String(trade.id ?? `import-${index}`),
        tradeTime: time, timeUnknown: trade.timeUnknown === true },
      index,
    });
  });

  const groups = [...bySymbol.values()].map(({ rows, ...group }) => {
    // Only explicit date/time and stable selection order; never infer a round trip.
    rows.sort((left, right) => left.input.trade_date.localeCompare(right.input.trade_date) || left.index - right.index);
    return {
      ...group,
      trades: rows.map(row => row.input),
      previewTrades: rows.map(row => row.preview),
      firstTradeDate: rows[0].input.trade_date,
      lastTradeDate: rows.at(-1).input.trade_date,
      buyCount: rows.filter(row => row.input.side === 'buy').length,
      sellCount: rows.filter(row => row.input.side === 'sell').length,
      targetTradeId: null,
    };
  }).sort((left, right) => right.lastTradeDate.localeCompare(left.lastTradeDate));
  return { groups };
}
