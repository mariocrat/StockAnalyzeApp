export const APP_BACK_REQUEST_EVENT = 'alphamate:back-request';

export function requestNestedBack(targetWindow = window) {
  const detail = { handled: false };
  targetWindow.dispatchEvent(new CustomEvent(APP_BACK_REQUEST_EVENT, { detail }));
  return detail.handled;
}

export function nextRootBackAction({ activeView, hasThemeSelection }) {
  if (activeView !== 'themes') return 'themes';
  if (hasThemeSelection) return 'clear-theme-selection';
  return 'confirm-exit';
}
