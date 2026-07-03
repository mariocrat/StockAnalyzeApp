# AI Review Monetization Plan

## Naming

Use simple user-facing names so subscription, analysis depth, and consumable credits do not blur together.

- Pro: monthly subscription plan.
- Standard Review: short single-trade AI review. Internal key: `basic`.
- Deep Review: richer review that compares the current trade with recent trades. Internal key: `advanced`.
- Review Credits: one-time consumable purchase packs.

Korean UI labels:

- 일반 복기: basic AI review.
- 심층 복기: advanced AI review.
- 일반 복기 이용권: consumable basic credits.
- 심층 복기 이용권: consumable advanced credits.

## AI Review Types

### Standard Review

- Model default: `gpt-5.4-mini`.
- Scope: one selected or latest trade.
- Output: one-line summary, one good point, one weak point, and three next-checklist items.

### Deep Review

- Model default: `gpt-5.5`.
- Configurable with `OPENAI_ADVANCED_REVIEW_MODEL` so the model can be changed later.
- Scope: current trade plus recent 5 to 10 trade summaries and chart context.
- Output focus: repeated mistakes, stop-loss criteria, entry hypothesis, response issues, and next trading rules.

## Free Policy

- Signup bonus: 5 Standard Reviews.
- Daily free grant: 1 Standard Review.
- Rewarded ads can add Standard Reviews.
- Daily max Standard Reviews: 5.
- Monthly max Standard Reviews: 50.
- Watching 5 rewarded ads grants 1 weekly Deep Review ticket.
- Weekly ad-reward Deep Review ticket max holding: 1.

The rewarded-ad policy is configurable on the server. The default remains one rewarded ad for one Standard Review, and five rewarded ads for one weekly Deep Review ticket. `ALPHAMATE_ADS_PER_ADVANCED_TICKET` can change the weekly Deep Review threshold later without changing the mobile app. `ALPHAMATE_FORCE_REWARDED_AD_CHAIN` is available as a server-side policy flag, but the recommended default is `false` so the app does not force several short ads in a row.

## Pro Policy

- Launch event price: KRW 3,900 monthly.
- Regular price: KRW 4,900 monthly.
- Monthly included usage: 150 Standard Reviews and 5 Deep Reviews.
- Pro users do not see non-rewarded ads anywhere in the app.
- Rewarded ads remain a free-user path for earning extra review access.

## One-Time Purchase Packs

These are consumable products, not subscriptions.

| Product ID | User Label | Quantity | Price |
| --- | --- | ---: | ---: |
| `basic_review_30` | 일반 복기 이용권 30회 | 30 | KRW 2,900 |
| `basic_review_100` | 일반 복기 이용권 100회 | 100 | KRW 6,900 |
| `advanced_review_5` | 심층 복기 이용권 5회 | 5 | KRW 2,900 |
| `advanced_review_10` | 심층 복기 이용권 10회 | 10 | KRW 4,900 |

Product IDs are constants in the backend and should be mapped to Google Play Console product IDs before production release.

## Deduction Priority

Standard Review:

1. Free signup/daily/monthly allowance.
2. Pro monthly Standard Review allowance.
3. Purchased Standard Review credits.
4. Rewarded-ad extra allowance.
5. Purchase prompt.

Deep Review:

1. Pro monthly Deep Review allowance.
2. Weekly Deep Review ticket earned from rewarded ads.
3. Purchased Deep Review credits.
4. Purchase prompt.

Standard Review credits and Deep Review credits are managed separately. Allowing Deep Review credits to pay for Standard Reviews is controlled by `ALPHAMATE_ALLOW_ADVANCED_TICKET_FOR_BASIC`; the default is disabled.

## Kakao/Naver Login And Storage

Kakao and Naver easy login can identify the user, but neither provider manages AlphaMate review credits. The server should verify the provider login token, map `(provider, provider_user_id)` to one internal user ID, and store subscription state, review credit balances, ad rewards, and usage counters in AlphaMate's database.

If the same person logs in with both Kakao and Naver later, account linking should require an explicit confirmation step. Do not automatically merge accounts only by email or phone number because providers can expose different verified fields.

Trade history storage should be opt-in. The default privacy-friendly mode can keep one-time analysis ephemeral, while a later "save my journal" setting can store trades per user with clear consent, export/delete controls, and retention rules.

## Production Replacement Points

- Replace `dev-token` with Kakao/Naver/OIDC token verification.
- Replace `dev-ad-reward` with AdMob rewarded ad server-side verification. Backend SSV storage and consumption are implemented.
- Mobile AdMob SDK integration is implemented for rewarded, interstitial, and banner ads. Production release still requires real AdMob app/ad unit IDs and SSV callback setup in the AdMob console.
- Replace `dev-pro-entitlement` and dev purchase endpoints with Google Play Billing server-side purchase verification.
- Replace in-memory wallets with a database or Redis-backed quota store.
- Keep the OpenAI API key only on the server or in a cloud secret manager.
