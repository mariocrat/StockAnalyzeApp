function tradeSymbolKey(trade) {
  const ticker = String(trade?.ticker || '').trim();
  const name = String(trade?.name || '').trim();
  return ticker ? `ticker:${ticker}` : `name:${name || 'unknown'}`;
}

function tradeSortKey(trade, index) {
  return `${String(trade?.trade_date || '')}\u0000${String(trade?.id ?? index).padStart(20, '0')}`;
}

function tradeIdentity(trade, index = 0) {
  if (trade?.id != null) return `id:${trade.id}`;
  return [
    tradeSymbolKey(trade),
    String(trade?.trade_date || ''),
    String(trade?.side || ''),
    String(trade?.price || ''),
    String(trade?.quantity || ''),
    String(index),
  ].join('|');
}

function sameTrade(left, right) {
  if (!left || !right) return false;
  if (left.id != null && right.id != null) return String(left.id) === String(right.id);
  return tradeSymbolKey(left) === tradeSymbolKey(right)
    && String(left.trade_date || '') === String(right.trade_date || '')
    && String(left.side || '') === String(right.side || '')
    && Number(left.price || 0) === Number(right.price || 0)
    && Number(left.quantity || 0) === Number(right.quantity || 0);
}

export function buildReviewTradeGroups(trades = []) {
  const indexed = trades
    .map((trade, index) => ({ trade, index }))
    .sort((left, right) => tradeSortKey(left.trade, left.index).localeCompare(tradeSortKey(right.trade, right.index)));
  const activeBySymbol = new Map();
  const groups = [];

  indexed.forEach(({ trade, index }) => {
    const symbolKey = tradeSymbolKey(trade);
    let group = activeBySymbol.get(symbolKey);
    if (!group) {
      group = {
        key: `${symbolKey}|episode:${tradeIdentity(trade, index)}`,
        ticker: String(trade?.ticker || '').trim(),
        name: String(trade?.name || trade?.ticker || '종목 미입력').trim(),
        trades: [],
        position: 0,
        buyCount: 0,
        sellCount: 0,
      };
      groups.push(group);
      activeBySymbol.set(symbolKey, group);
    }

    const quantity = Math.max(0, Number(trade?.quantity || 0));
    group.trades.push(trade);
    if (trade?.side === 'sell') {
      group.position -= quantity;
      group.sellCount += 1;
    } else {
      group.position += quantity;
      group.buyCount += 1;
    }

    if (trade?.side === 'sell' && group.position <= 0) {
      group.position = 0;
      activeBySymbol.delete(symbolKey);
    }
  });

  return groups.map(group => {
    const first = group.trades[0] || {};
    const last = group.trades[group.trades.length - 1] || {};
    return {
      ...group,
      firstTradeDate: String(first.trade_date || ''),
      lastTradeDate: String(last.trade_date || ''),
      targetTradeId: last.id ?? null,
      openQuantity: group.position,
    };
  }).sort((left, right) => right.lastTradeDate.localeCompare(left.lastTradeDate));
}

export function findReviewTradeGroup(groups = [], targetTrade = null) {
  if (!targetTrade) return null;
  return groups.find(group => group.trades.some(trade => sameTrade(trade, targetTrade))) || null;
}

export function reviewTradesForGroup(groups = [], groupKey = '') {
  return groups.find(group => group.key === groupKey)?.trades || [];
}
