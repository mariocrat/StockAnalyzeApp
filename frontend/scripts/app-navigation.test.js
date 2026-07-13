import assert from 'node:assert/strict';
import test from 'node:test';

import { nextRootBackAction, requestNestedBack } from '../src/utils/appNavigation.js';

test('back navigation unwinds app views before asking to exit', () => {
  assert.equal(nextRootBackAction({ activeView: 'journal', hasThemeSelection: false }), 'themes');
  assert.equal(nextRootBackAction({ activeView: 'themes', hasThemeSelection: true }), 'clear-theme-selection');
  assert.equal(nextRootBackAction({ activeView: 'themes', hasThemeSelection: false }), 'confirm-exit');
});

test('nested fullscreen or history view can consume a back request', () => {
  const listeners = [];
  const fakeWindow = {
    dispatchEvent(event) {
      listeners.forEach(listener => listener(event));
    },
  };
  listeners.push(event => {
    event.detail.handled = true;
  });
  assert.equal(requestNestedBack(fakeWindow), true);
});
