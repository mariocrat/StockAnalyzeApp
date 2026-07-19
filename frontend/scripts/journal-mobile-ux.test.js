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
  assert.doesNotMatch(journalSource, /현재 동의 안내 버전/);
  assert.doesNotMatch(journalSource, /currentConsentVersion/);
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

test('advanced review shortage opens a Korean pass dialog instead of an inline AI error', () => {
  assert.match(journalSource, /err\.response\?\.status === 402 && reviewType === 'advanced'/);
  assert.match(journalSource, /심화 복기 이용권이 필요합니다/);
  assert.match(journalSource, /onClick=\{startAdvancedReview\}/);
  assert.match(journalSource, /showReviewPasses/);
});

test('journal notices use a Korean popup and never render raw messages inline', () => {
  assert.match(journalSource, /toKoreanUserMessage/);
  assert.match(journalSource, /className="journal-notice-backdrop"/);
  assert.match(journalSource, /role="alertdialog"/);
  assert.doesNotMatch(journalSource, /className="journal-message"/);
  assert.doesNotMatch(cssSource, /\.journal-message\s*\{/);
});

test('advanced review terminology and rewarded-ad ticket action are user-facing', () => {
  assert.doesNotMatch(journalSource, /심층/);
  assert.match(journalSource, /광고 보상 심화 복기 이용권/);
  assert.match(journalSource, /handleRewardedAdAdvancedTicket/);
  assert.match(journalSource, /광고 보고 심화 복기 이용권 받기/);
  assert.match(journalSource, /\/api\/journal\/ad-reward-claim/);
  assert.match(journalSource, /테스트 광고는 실제 심화 복기 이용권을 지급하지 않습니다/);
  assert.match(journalSource, /\/privacy/);
});

test('mobile header uses a graphical wordmark and masks scrolling content', () => {
  assert.match(appSource, /function AppWordmark\(\)/);
  assert.match(appSource, /<img src=\{appIcon\}/);
  assert.match(cssSource, /\.mobile-app-brand img \{[\s\S]*?drop-shadow/);
  assert.match(cssSource, /\.theme-sidebar-fixed \{[\s\S]*?margin: -12px -12px 0;[\s\S]*?background: #131722/);
  assert.match(cssSource, /\.mobile-app-bar > \* \{[\s\S]*?z-index: 1/);
});

test('theme and chart divider follows the collapsible mobile sidebar', () => {
  assert.match(cssSource, /\.app-container\.themes-view \.sidebar \{[\s\S]*?border-bottom: 2px solid #44506a/);
});

test('general review reruns use a fresh request while rapid double taps stay locked', () => {
  assert.match(journalSource, /BASIC_REVIEW_FOCUSES/);
  assert.match(journalSource, /if \(aiReviewInFlightRef\.current\) return/);
  assert.match(journalSource, /aiReviewInFlightRef\.current = true/);
  assert.match(journalSource, /aiReviewInFlightRef\.current = false/);
  assert.match(journalSource, /analysis_focus: analysisFocus/);
});
