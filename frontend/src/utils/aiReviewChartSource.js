import { validateReviewDisplay } from '../components/CanonicalReviewRenderer.js';
import { validateReviewBody } from '../components/ReviewBodyRenderer.js';
import { REVIEW_DISPLAY_V2 } from './reviewDisplayV2.js';

const EMPTY_CHART_SOURCE = Object.freeze({ charts: Object.freeze([]), chart_cards: Object.freeze([]) });

export function aiReviewChartSource(review, historyRecord = null) {
  if (!review || review.status === 'error' || review.status === 'empty' || review.internal_status) {
    return EMPTY_CHART_SOURCE;
  }
  if (historyRecord && !['canonical', 'adapted'].includes(historyRecord.history_read_status)) {
    return EMPTY_CHART_SOURCE;
  }
  if (!historyRecord && !['ready', 'missing_key'].includes(review.status)) return EMPTY_CHART_SOURCE;
  try {
    validateReviewBody(review.display_snapshot, review.review_type);
  } catch {
    return EMPTY_CHART_SOURCE;
  }
  if ('chart_display_snapshot' in review) {
    const snapshot = review.chart_display_snapshot;
    if (!Array.isArray(snapshot?.charts) || !Array.isArray(snapshot?.chart_cards)) return EMPTY_CHART_SOURCE;
    try {
      // Reuse the canonical document contract before any chart/card enters JSX.
      // Admission only: keep every approved document and its text unchanged.
      for (const chart of snapshot.charts) {
        validateReviewDisplay(chart.header, 'chart_header');
        validateReviewDisplay(chart.tab, 'chart_tab');
        if (!Array.isArray(chart.markers)) return EMPTY_CHART_SOURCE;
        for (const marker of chart.markers) {
          validateReviewDisplay(marker.label, 'marker_label');
          if (marker.tooltip !== null) validateReviewDisplay(marker.tooltip, 'marker_tooltip');
        }
      }
      for (const card of snapshot.chart_cards) validateReviewDisplay(card.display, 'chart_card');
      return snapshot;
    } catch {
      return EMPTY_CHART_SOURCE;
    }
  }
  // Only the whole-record history adapter can admit older stored chart surfaces.
  // Missing/invalid live snapshots never use general charts or raw AI extras.
  if (!historyRecord || review.display_snapshot?.schema_version === REVIEW_DISPLAY_V2) return EMPTY_CHART_SOURCE;
  return {
    charts: historyRecord.chart_snapshot?.charts || [],
    chart_cards: review.chart_reviews || historyRecord.chart_snapshot?.chart_reviews || [],
  };
}
