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

test('account data export uses Android share sheet and explains the backup location', () => {
  assert.match(journalSource, /navigator\.share/);
  assert.match(journalSource, /application\/json/);
  assert.match(journalSource, /link\.download = filename/);
  assert.match(journalSource, /내 파일 또는 Files/);
  assert.match(journalSource, /PC나 웹에서는 보통 다운로드 폴더/);
  assert.doesNotMatch(journalSource, /JSON 형식의 내 데이터 파일/);
});

test('saved review can restore its trade snapshot for another review', () => {
  assert.match(journalSource, /restoreReviewHistoryTrades/);
  assert.match(journalSource, /recent_trades_snapshot/);
  assert.match(journalSource, /당시 매매 묶음 불러오기/);
  assert.match(journalSource, /setJournalSubView\('review'\)/);
});

test('AI review sends only the explicitly selected trade episode', () => {
  assert.match(journalSource, /복기할 매매 선택/);
  assert.match(journalSource, /selectedReviewGroupKey/);
  assert.match(journalSource, /selectedReviewTrades/);
  assert.match(journalSource, /loadAiReview\(selectedReviewTrades, 'advanced'/);
  assert.match(journalSource, /trades: selectedReviewTrades/);
  assert.doesNotMatch(journalSource, /loadAiReview\(trades, 'advanced'/);
});

test('Luna and Terra comparison is isolated to the explicit QA build flag', () => {
  assert.match(journalSource, /VITE_QA_ADVANCED_COMPARISON/);
  assert.match(journalSource, /X-AlphaMate-QA-Comparison/);
  assert.match(journalSource, /luna-terra-v1/);
  assert.match(journalSource, /테스트 APK 전용 · 이용권 차감 없음/);
  assert.match(journalSource, /매매 차트 보기/);
  assert.match(journalSource, /setShowCurrentReviewDetails\(true\)/);
  assert.match(cssSource, /\.journal-ai-document h4/);
});

test('mobile entitlement balances remain in a compact three-column grid', () => {
  assert.match(cssSource, /\.journal-entitlement-grid \{[\s\S]*?grid-template-columns: repeat\(3, minmax\(0, 1fr\)\)/);
});

test('advanced review shortage opens a Korean pass dialog instead of an inline AI error', () => {
  assert.match(journalSource, /err\.response\?\.status === 402/);
  assert.match(journalSource, /reviewType === 'advanced' \? 'advanced' : 'basic'/);
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

test('general review balance distinguishes immediate free uses from rewarded-ad capacity', () => {
  assert.match(journalSource, /free_available_now/);
  assert.match(journalSource, /rewarded_ad_available/);
  assert.match(journalSource, /setReviewAccessDialog\(reviewType === 'advanced' \? 'advanced' : 'basic'\)/);
  assert.match(journalSource, /광고 보고 일반 복기/);
});

test('rewarded review waits for server-side verification without consuming it while polling', () => {
  assert.match(journalSource, /\/api\/journal\/ad-reward-status/);
  assert.match(journalSource, /waitForRewardedAdStatus\('basic_review'\)/);
  assert.match(journalSource, /waitForRewardedAdStatus\('advanced_ticket_progress'\)/);
  assert.match(journalSource, /getRewardedAdStatus\('basic_review'\)/);
});

test('saved journal entry does not reveal stock details until a review is selected or completed', () => {
  assert.match(journalSource, /setShowCurrentReviewDetails\(false\)/);
  assert.match(journalSource, /showCurrentReviewDetails && <section className="journal-panel">/);
});

test('successful AI review is not replaced by a failed follow-up refresh', () => {
  assert.match(journalSource, /Promise\.allSettled\(followUpRefreshes\)/);
  assert.match(journalSource, /<AiReviewSummary value=\{aiReview\.summary\} document=\{aiReview\.review_type === 'advanced'\} \/>/);
});

test('AI review loading is prominent and selected chart follows trade selection', () => {
  assert.match(journalSource, /className="journal-ai-loading" role="status" aria-live="polite"/);
  assert.match(journalSource, /AI 복기 분석 중/);
  assert.match(journalSource, /심화 복기 비교 분석 중/);

  const selectionIndex = journalSource.indexOf('복기할 매매 선택');
  const chartIndex = journalSource.indexOf('선택한 매매 차트');
  const actionIndex = journalSource.indexOf('journal-review-actions');
  assert.ok(selectionIndex >= 0);
  assert.ok(chartIndex > selectionIndex);
  assert.ok(actionIndex > chartIndex);
});

test('review output removes internal evidence labels and shows the first-login trial pass', () => {
  assert.match(journalSource, /replace\(\/\\\[\(\?:데이터 확인\|합리적 추론\)\\\]\/g, ''\)/);
  assert.match(journalSource, /signup_advanced: '첫 로그인 체험 이용권'/);
  assert.match(journalSource, /advanced\.signup_remaining/);
  assert.match(journalSource, /첫 로그인 체험 심화 복기/);
});
