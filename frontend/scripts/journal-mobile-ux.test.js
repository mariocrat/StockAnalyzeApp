import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const appSource = readFileSync(new URL('../src/App.jsx', import.meta.url), 'utf8');
const journalSource = readFileSync(new URL('../src/components/TradingJournal.jsx', import.meta.url), 'utf8');
const cssSource = readFileSync(new URL('../src/App.css', import.meta.url), 'utf8');

test('account management is reachable from both primary views', () => {
  assert.match(appSource, /className="mobile-app-account"[\s\S]*?onClick=\{openAccountPanel\}/);
  assert.match(appSource, /accountReturnViewRef/);
  assert.doesNotMatch(appSource, /activeView === 'journal' \? \([\s\S]{0,180}mobile-app-account/);
});

test('mobile chart controls use compact named grid areas', () => {
  assert.match(appSource, /controls-candles/);
  assert.match(appSource, /controls-count/);
  assert.match(cssSource, /grid-template-areas:[\s\S]*?"candles count"[\s\S]*?"period scale"/);
});

test('review UI hides internal model ids and consent versions', () => {
  assert.doesNotMatch(journalSource, /activeReviewHistory\.model/);
  assert.match(journalSource, /동의일 \$\{consentRecordedAt\.slice\(0, 10\)\}/);
  assert.match(journalSource, /<h3>AI 복기<\/h3>/);
});

test('trade time supports native selection and direct numeric entry', () => {
  assert.match(journalSource, /directTimeEntry/);
  assert.match(journalSource, /inputMode=\{directTimeEntry \? 'numeric'/);
  assert.match(journalSource, /normalizeDirectTime/);
});

test('account data export uses Android share sheet with JSON fallback download', () => {
  assert.match(journalSource, /navigator\.share/);
  assert.match(journalSource, /application\/json/);
  assert.match(journalSource, /link\.download = filename/);
});

test('mobile entitlement balances remain in a compact three-column grid', () => {
  assert.match(cssSource, /\.journal-entitlement-grid \{[\s\S]*?grid-template-columns: repeat\(3, minmax\(0, 1fr\)\)/);
});
