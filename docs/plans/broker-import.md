# Broker Trade Import

## Goal

Allow StockBoda users to import broker transaction statements on-device, select individual trades, and use those objective transaction details as input for trade review without uploading the original financial document to the StockBoda server.

## Scope

Current scope:

- Toss Securities
- Domestic Korean stocks only
- Searchable/text-based PDF statements
- Android flow
- On-device PDF parsing with bundled PDF.js
- User-selected individual trades
- Optional manual execution-time input where the PDF does not provide time

Current scope does not include overseas-stock processing, OCR, automatic trade matching, or automatic position reconstruction.

## Confirmed Decisions

### Privacy

- The original broker PDF must remain on the user's device.
- The original PDF must not be uploaded to the StockBoda backend.
- The original PDF must not be stored in the app database, localStorage, or sessionStorage.
- Real financial PDFs containing personal information must not be committed to the repository.
- Automated tests should use sanitized synthetic fixtures.

### Trade identity

- One original transaction row remains one independent StockBoda trade.
- Do not merge repeated BUY or SELL transactions.
- Do not automatically calculate an average price in order to merge trades.
- Do not automatically match a BUY with a SELL.
- Do not perform FIFO/LIFO.
- Do not infer a round trip or position relationship.
- The user decides which individual trades to include in a review.

### Execution time

- Do not invent or infer an execution time when the PDF does not contain one.
- Price or ordering must not be used to fabricate a time.
- `tradeTime` and `timeUnknown` remain independent state.

For selected trades:

- Different dates: execution time is optional.
- Same date + same symbol + BUY only: execution time is optional.
- Same date + same symbol + SELL only: execution time is optional.
- Same date + same symbol containing both BUY and SELL: every trade in that mixed-side group without a time requires execution-time input before proceeding.

Execution time is used only to recover ordering. It must not trigger automatic BUY/SELL matching.

### Broker support

- Toss domestic-stock statements are supported.
- Overseas stocks remain unsupported.
- An empty foreign-currency section must not cause a domestic document to be classified as overseas.
- Ambiguous documents should fail safely rather than be guessed into a supported format.

## Actual Toss Domestic PDF Findings

Real Toss domestic PDF samples established:

- `원화-외화 거래구분` can be `원화`.
- Domestic codes can appear as `A` + six digits.
- Example raw code: `A032940`
- Normalized StockBoda symbol: `032940`
- `구매` maps to BUY.
- `판매` maps to SELL.
- The tested PDF statement does not contain execution time.
- The header can contain a `환율` column while a KRW transaction row has no exchange-rate value.
- Fixed flattened numeric token indexes are therefore unsafe.
- Toss domestic parsing uses PDF.js text-item/header x/y positioning for important columns such as quantity and unit price.

Verified real sample transactions:

- 2026-09-02 SELL 원익 / A032940 → 032940 / quantity 1 / price 7,710 / time null
- 2026-09-02 BUY 원익 / A032940 → 032940 / quantity 1 / price 7,830 / time null

The two transactions remain independent trades.

## Current Status

- [x] Separate `feature/broker-import` worktree
- [x] Broker import integrated inside the trade-review flow
- [x] Android PDF file selection
- [x] Bundled/local PDF.js extraction
- [x] PDF filename displayed
- [x] Domestic/overseas classification
- [x] Empty foreign-currency section no longer causes overseas misclassification
- [x] Real Toss domestic PDF samples tested
- [x] Toss domestic `A######` code support
- [x] `A032940 → 032940`
- [x] `구매 → BUY`
- [x] `판매 → SELL`
- [x] x/y based Toss table parsing
- [x] Independent transaction IDs
- [x] User multi-selection
- [x] No automatic execution-time generation
- [x] Same-date/same-symbol mixed BUY/SELL requires execution time
- [x] Invalid review state disables CTA
- [x] CTA text is `매매 복기로 가져오기`
- [x] Mobile broker-import UI/overflow improvements
- [x] Imported trades go to preview before persistence
- [x] Debug Android package remains `com.mariocrat.stockanalyze.debug`
- [x] Debug OAuth callback scheme separated from release scheme
- [x] Backend OAuth callback scheme allowlist/fallback implemented
- [x] Python regression tests cover allowed/rejected callback schemes
- [x] Common StockBoda AGENTS/plan workflow added to this branch

## Verification

### Broker import

Independently verified against two distinct real Toss domestic PDF files.

Each produced:

- 2 pages
- broker: toss
- market: domestic
- status: ready
- SELL 1 share at 7,710 KRW
- BUY 1 share at 7,830 KRW
- `A032940 → 032940`
- separate trade IDs
- no generated execution time

### Same-day BUY/SELL validation

Verified:

- different-date BUY/SELL can proceed without times
- same-day BUY-only can proceed without times
- same-day SELL-only can proceed without times
- same-day/same-symbol BUY+SELL is blocked while required times are missing
- BUY+SELL+BUY makes all missing times in that group required
- unrelated symbols are unaffected
- entering required times permits preview
- no trade matching or merging occurs

### UI

Verified at narrow mobile widths:

- no horizontal overflow
- symbol/date/side/price/quantity/time controls remain inside cards
- required-time warning is distinct from optional-time guidance
- CTA state follows validation
- selected trades can proceed to unsaved preview

### OAuth

Code and automated verification completed for:

- release scheme: `com.mariocrat.stockanalyze`
- debug scheme: `com.mariocrat.stockanalyze.debug`
- callback scheme allowlist/fallback
- OAuth state validation
- one-time ticket flow
- frontend app-return scheme validation
- direct Python regression tests for allowed/rejected schemes

### Android Debug

An independently inspected Debug APK confirmed:

- package: `com.mariocrat.stockanalyze.debug`
- label: `StockBoda Debug`
- production API: `https://api.alphamate.co.kr`
- API does not use `127.0.0.1:8002`
- API does not use `localhost:8002`
- debug OAuth callback resource uses `com.mariocrat.stockanalyze.debug`

This is not release APK/AAB verification.

## Remaining / Unverified

- [ ] Deploy the approved backend OAuth callback changes to production backend
- [ ] Verify Debug Kakao OAuth end-to-end on a physical Android device after backend deployment
- [ ] Verify Debug Naver OAuth end-to-end on a physical Android device after backend deployment
- [ ] Verify provider consent/code exchange and return to Debug app
- [ ] Verify release APK/AAB OAuth callback behavior
- [ ] Decide when broker-import is ready to merge into main
- [ ] Perform final release-oriented regression before integration

Do not describe OAuth as fully working in production until backend deployment and real provider/device callback verification are complete.

## Next Step

Prepare the production OAuth rollout as a separate controlled step.

Before deployment:

1. Confirm the exact backend diff that would be deployed.
2. Confirm the current production revision.
3. Confirm that only the already-reviewed OAuth backend change is required.
4. Report the deployment plan.
5. Wait for explicit user approval before deploying anything.

After explicit approval, deploy the backend OAuth callback change and perform real Debug Kakao/Naver login return testing on a physical Android device.

Listing this as the Next Step does not authorize production deployment.

## Out of Scope

Do not add these unless explicitly requested:

- overseas-stock import
- FX processing
- OCR/scanned PDF support
- MyData integration
- automatic BUY/SELL pairing
- FIFO/LIFO
- automatic position reconstruction
- automatic round-trip detection
- automatic execution-time inference
- automatic trade merging
- Google Play production release

## Git / Worktree Notes

Current feature branch:

`feature/broker-import`

Common repository rules:

`AGENTS.md`

The following generated Capacitor files can appear modified even when content equals HEAD:

- `frontend/android/app/capacitor.build.gradle`
- `frontend/android/capacitor.settings.gradle`

If their contents are identical to HEAD, do not stage/revert/commit them merely to clean status.

Real Toss PDF samples must remain outside the repository.
