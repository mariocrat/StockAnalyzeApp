import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';

import { nextRootBackAction, requestNestedBack } from '../src/utils/appNavigation.js';

const journalSource = readFileSync(new URL('../src/components/TradingJournal.jsx', import.meta.url), 'utf8');
const appSource = readFileSync(new URL('../src/App.jsx', import.meta.url), 'utf8');
const appCssSource = readFileSync(new URL('../src/App.css', import.meta.url), 'utf8');

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
  assert.match(appSource, /onImportToJournal=\{handleImportedTrades\}/);
  assert.doesNotMatch(appSource, />PDF 가져오기<\/button>/);
  const appNavBlock = appCssSource.match(/\.app-nav \{[\s\S]*?\n\}/)?.[0] || '';
  assert.match(appNavBlock, /grid-template-columns:\s*repeat\(2,\s*minmax\(0,\s*1fr\)\)/);
  assert.doesNotMatch(appNavBlock, /repeat\(3/);
  assert.match(journalSource, /복기 시작하기/);
  assert.match(journalSource, /<h3 id="journal-start-title">매매 내역 입력 방식<\/h3>/);
  assert.match(journalSource, /setJournalInputMode\('direct'\)/);
  assert.match(journalSource, /setJournalInputMode\('broker'\)/);
  assert.match(journalSource, /const \[journalInputMode, setJournalInputMode\] = useState\('direct'\)/);
  assert.match(journalSource, /const \[form, setForm\] = useState\(emptyForm\)/);
  assert.doesNotMatch(journalSource, /changeActiveView\('broker-import'\)/);
  assert.match(journalSource, /journalInputMode === 'direct'/);
  assert.match(journalSource, /journalInputMode === 'broker'/);
  assert.match(journalSource, /BrokerImportPanel/);
  assert.match(journalSource, /증권사 거래내역 불러오기/);
  assert.match(journalSource, /onImportedTradesChange/);
  assert.match(journalSource, /시간을 모름/);
  assert.match(journalSource, /journal-import-time-warning/);
  assert.match(journalSource, /체결시간\(필수\)/);
  assert.match(journalSource, /aria-invalid={missingRequiredTime}/);
  assert.match(journalSource, /submitManual/);
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
