import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';

import { nextRootBackAction, requestNestedBack } from '../src/utils/appNavigation.js';

const journalSource = readFileSync(new URL('../src/components/TradingJournal.jsx', import.meta.url), 'utf8');

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

test('account management lives in a dismissible drawer without exposing a user id', () => {
  assert.match(journalSource, /journal-account-drawer/);
  assert.match(journalSource, /if \(accountPanelOpen\)/);
  assert.match(journalSource, /AI 복기 동의/);
  assert.doesNotMatch(journalSource, /사용자 \$\{String\(authSession\.user\?\.id/);
  assert.doesNotMatch(journalSource, /<span>계정 상태<\/span>/);
});
