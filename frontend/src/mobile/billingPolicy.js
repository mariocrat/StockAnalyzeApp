export function shouldFinishGooglePlayTransaction(serverResponse) {
  // The backend owns Google Play consume/acknowledge. Calling native finish here would duplicate it.
  void serverResponse;
  return false;
}

function productIdPairs(productCatalog) {
  const consumables = Object.entries(productCatalog?.consumables || {});
  const subscriptions = Object.entries(productCatalog?.subscriptions || {});
  return [...consumables, ...subscriptions].map(([localProductId, product]) => ({
    localProductId,
    googleProductId: product?.google_play_product_id || localProductId,
  }));
}

function productIdsFromReceipt(receipt) {
  const ids = [];
  for (const transaction of receipt?.transactions || []) {
    for (const product of transaction?.products || []) {
      if (product?.id) ids.push(product.id);
    }
  }
  return ids;
}

export function buildGooglePlayRecoveryCandidates({ productCatalog, localReceipts = [] } = {}) {
  const products = productIdPairs(productCatalog);
  const byGoogleProductId = new Map(products.map(product => [product.googleProductId, product.localProductId]));
  const seen = new Set();
  const candidates = [];

  for (const receipt of localReceipts || []) {
    const purchaseToken = String(receipt?.purchaseToken || '').trim();
    if (!purchaseToken) continue;

    const localProductId = productIdsFromReceipt(receipt)
      .map(productId => byGoogleProductId.get(productId))
      .find(Boolean);
    if (!localProductId) continue;

    const key = `${localProductId}:${purchaseToken}`;
    if (seen.has(key)) continue;
    seen.add(key);
    candidates.push({ localProductId, purchaseToken });
  }

  return candidates;
}
