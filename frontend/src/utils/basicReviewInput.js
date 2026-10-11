import { validateReviewDisplay } from '../components/CanonicalReviewRenderer.js';
import { aiReviewChartSource } from './aiReviewChartSource.js';

// Capture request data, never semantic/display output or a later selection.
// Failure only removes the optional CTA; it does not change existing execution.
export function captureReviewInput(trades, targetTradeId = null) {
  try {
    if (!Array.isArray(trades) || !trades.length) return null;
    const copy = JSON.parse(JSON.stringify(trades));
    for (const trade of copy) {
      if (!trade || typeof trade !== 'object' || Array.isArray(trade)
        || typeof trade.trade_date !== 'string' || !trade.trade_date
        || typeof trade.name !== 'string' || !trade.name.trim()
        || typeof trade.ticker !== 'string'
        || !['buy', 'sell'].includes(trade.side)
        || !Number.isFinite(trade.price) || trade.price <= 0
        || !Number.isFinite(trade.quantity) || trade.quantity <= 0
        || (trade.id != null && (!Number.isSafeInteger(trade.id) || trade.id <= 0))
        || 'previewId' in trade || 'timeUnknown' in trade) return null;
      Object.freeze(trade);
    }
    if (targetTradeId !== null && (!Number.isSafeInteger(targetTradeId)
      || !copy.some(trade => trade.id === targetTradeId))) return null;
    return Object.freeze({ trades: Object.freeze(copy), targetTradeId });
  } catch {
    return null;
  }
}

export function basicReviewInput(review, source) {
  if (!source?.input || source.review !== review || review?.review_type !== 'basic'
    || !['ready', 'missing_key'].includes(review.status) || review.internal_status) return null;
  try {
    validateReviewDisplay(review.display_snapshot);
    if ('chart_display_snapshot' in review && aiReviewChartSource(review) !== review.chart_display_snapshot) return null;
    return source.input;
  } catch {
    return null;
  }
}
