import { Capacitor } from '@capacitor/core';

const APP_ENV = import.meta.env.VITE_ALPHAMATE_ENV || (import.meta.env.PROD ? 'production' : 'development');
const PRODUCT_KIND = {
  basic_review_30: 'consumable',
  basic_review_100: 'consumable',
  advanced_review_5: 'consumable',
  advanced_review_10: 'consumable',
  pro_monthly_launch: 'subscription',
  pro_monthly: 'subscription',
};

let initialized = false;
let initPromise = null;
let currentProducts = [];
let pendingPurchase = null;
let purchaseModulePromise = null;
let purchaseModule = null;

async function loadPurchaseModule() {
  if (!purchaseModulePromise) {
    purchaseModulePromise = import('capacitor-plugin-cdv-purchase');
  }
  purchaseModule = purchaseModule || await purchaseModulePromise;
  return purchaseModule;
}

function productTypeFor(productId, ProductType) {
  return PRODUCT_KIND[productId] === 'subscription'
    ? ProductType.PAID_SUBSCRIPTION
    : ProductType.CONSUMABLE;
}

function productIdsFromCatalog(productCatalog) {
  const consumables = Object.entries(productCatalog?.consumables || {});
  const subscriptions = Object.entries(productCatalog?.subscriptions || {});
  return [...consumables, ...subscriptions].map(([localProductId, product]) => ({
    localProductId,
    googleProductId: product.google_play_product_id || localProductId,
  }));
}

function findPurchaseToken(transaction) {
  const { store } = purchaseModule || {};
  const receipt = transaction?.parentReceipt;
  if (receipt?.purchaseToken) return receipt.purchaseToken;
  const matchingReceipt = store.localReceipts?.find(item =>
    item?.purchaseToken && item?.transactions?.some(tx => tx.transactionId === transaction?.transactionId),
  );
  return matchingReceipt?.purchaseToken || '';
}

function waitForPurchase(localProductId, timeoutMs = 120000) {
  if (pendingPurchase) {
    window.clearTimeout(pendingPurchase.timeout);
    pendingPurchase.reject(new Error('Another purchase is already in progress.'));
  }

  return new Promise((resolve, reject) => {
    const timeout = window.setTimeout(() => {
      if (pendingPurchase?.localProductId === localProductId) pendingPurchase = null;
      reject(new Error('Purchase confirmation timed out.'));
    }, timeoutMs);

    pendingPurchase = { localProductId, resolve, reject, timeout };
  });
}

function resolvePendingPurchase(transaction) {
  if (!pendingPurchase) return;
  const productIds = transaction?.products?.map(product => product.id) || [];
  const localProductId = pendingPurchase.localProductId;
  const expected = currentProducts.find(item => item.localProductId === localProductId);
  if (!productIds.includes(expected?.googleProductId || localProductId)) return;

  window.clearTimeout(pendingPurchase.timeout);
  const purchaseToken = findPurchaseToken(transaction);
  const resolver = pendingPurchase.resolve;
  pendingPurchase = null;
  resolver({ purchaseToken, transaction });
}

function rejectPendingPurchase(error) {
  if (!pendingPurchase) return;
  window.clearTimeout(pendingPurchase.timeout);
  const rejecter = pendingPurchase.reject;
  pendingPurchase = null;
  rejecter(error instanceof Error ? error : new Error(error?.message || 'Purchase failed.'));
}

export function getBillingRuntimeStatus() {
  return {
    native: Capacitor.isNativePlatform(),
    platform: Capacitor.getPlatform(),
    available: Capacitor.isNativePlatform(),
  };
}

export async function initializeBilling(productCatalog) {
  if (!Capacitor.isNativePlatform()) return getBillingRuntimeStatus();

  const { ProductType, Platform, store } = await loadPurchaseModule();
  const products = productIdsFromCatalog(productCatalog);
  currentProducts = products;
  if (!products.length) return getBillingRuntimeStatus();

  if (!initialized) {
    store.verbosity = APP_ENV === 'production' ? 1 : 2;
    store.when().approved(resolvePendingPurchase);
    store.error(rejectPendingPurchase);
    initialized = true;
  }

  store.register(products.map(product => ({
    id: product.googleProductId,
    type: productTypeFor(product.localProductId, ProductType),
    platform: Platform.GOOGLE_PLAY,
  })));

  if (!initPromise) {
    initPromise = store.initialize([Platform.GOOGLE_PLAY]);
  }

  await initPromise;
  await store.update();
  return getBillingRuntimeStatus();
}

export async function purchaseGooglePlayProduct({ productCatalog, localProductId, userId }) {
  if (!Capacitor.isNativePlatform()) {
    throw new Error('Google Play purchases are available only in the mobile app.');
  }
  if (!userId) {
    throw new Error('A logged-in user is required before purchasing review credits.');
  }

  await initializeBilling(productCatalog);

  const { Platform, store } = await loadPurchaseModule();
  const product = currentProducts.find(item => item.localProductId === localProductId);
  const googleProductId = product?.googleProductId || localProductId;
  const storeProduct = store.get(googleProductId, Platform.GOOGLE_PLAY);
  const offer = storeProduct?.offers?.[0];
  if (!offer) {
    throw new Error('This product is not available from Google Play yet.');
  }

  const resultPromise = waitForPurchase(localProductId);
  const error = await offer.order({ applicationUsername: String(userId) });
  if (error) {
    rejectPendingPurchase(error);
  }

  const result = await resultPromise;
  if (!result.purchaseToken) {
    throw new Error('Google Play did not return a purchase token.');
  }
  return {
    purchaseToken: result.purchaseToken,
    transaction: result.transaction,
  };
}
