import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';

import { nextRootBackAction, requestNestedBack } from '../src/utils/appNavigation.js';

const journalSource = readFileSync(new URL('../src/components/TradingJournal.jsx', import.meta.url), 'utf8');
const appSource = readFileSync(new URL('../src/App.jsx', import.meta.url), 'utf8');

test('billing and refund policy is available from account management and the purchase area', () => {
  assert.match(journalSource, /구매 및 환불 정책/);
  assert.match(journalSource, /구매 및 환불 정책 보기/);
  assert.match(journalSource, /무료 이용자는 가입 체험·일일 무료·광고 보상을 먼저, Pro 이용자는 Pro 월 제공량을 먼저 사용한 뒤 구매 주문 순서대로 사용합니다/);
  assert.doesNotMatch(journalSource, /만료가 가까운 무료·광고·Pro 제공량/);
  assert.match(journalSource, /부분 환불은 고객지원 수동 검토/);
  assert.match(journalSource, /전액 환불·취소·차지백/);
  assert.match(journalSource, /setAccountBillingPolicyOpen\(true\)/);
});

test('back navigation unwinds app views before asking to exit', () => {
  assert.equal(nextRootBackAction({ activeView: 'journal', hasThemeSelection: false }), 'themes');
  assert.equal(nextRootBackAction({ activeView: 'broker-import', hasThemeSelection: false }), 'journal');
  assert.equal(nextRootBackAction({ activeView: 'themes', hasThemeSelection: true }), 'clear-theme-selection');
  assert.equal(nextRootBackAction({ activeView: 'themes', hasThemeSelection: false }), 'confirm-exit');
});

test('broker PDF import is registered as an independent app view', () => {
  assert.match(appSource, /const BrokerImport = lazy\(\(\) => import\('\.\/components\/BrokerImport'\)\)/);
  assert.match(appSource, /view === 'journal' \|\| view === 'broker-import'/);
  assert.match(appSource, /nextView === 'journal' \|\| nextView === 'broker-import'/);
  assert.match(appSource, /activeView === 'broker-import'/);
  assert.match(appSource, /onOpenBrokerImport=\{openBrokerImport\}/);
  assert.match(appSource, /onImportToJournal=\{handleImportedTrades\}/);
  assert.doesNotMatch(appSource, />PDF 가져오기<\/button>/);
  assert.match(journalSource, /증권사 거래내역 불러오기/);
  assert.match(journalSource, /거래내역서 불러오기/);
  assert.match(journalSource, /onImportedTradesChange/);
  assert.match(journalSource, /시간을 모름/);
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
