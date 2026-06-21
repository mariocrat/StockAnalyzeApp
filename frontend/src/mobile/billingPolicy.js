const SERVER_FINAL_PURCHASE_STATUSES = new Set([
  'active',
  'already_applied',
  'applied',
  'consume_completed',
]);

export function shouldFinishGooglePlayTransaction(serverResponse) {
  const status = serverResponse?.purchase?.status || '';
  return SERVER_FINAL_PURCHASE_STATUSES.has(status);
}

export async function finishGooglePlayTransactionIfFinalized({ serverResponse, transaction }) {
  if (!shouldFinishGooglePlayTransaction(serverResponse)) {
    return { attempted: false, finished: false, error: '' };
  }
  if (typeof transaction?.finish !== 'function') {
    return { attempted: true, finished: false, error: 'Transaction finish function is unavailable.' };
  }
  try {
    await transaction.finish();
    return { attempted: true, finished: true, error: '' };
  } catch (err) {
    return {
      attempted: true,
      finished: false,
      error: err?.message || 'Transaction finish failed.',
    };
  }
}
