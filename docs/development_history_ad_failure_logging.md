# Mobile ad failure logging

Date: 2026-07-03

## What changed

- Mobile ad failures are now reported through the existing `/api/client-events` operational log endpoint.
- Logged placements include app-resume interstitial ads, chart-detail interstitial ads, bottom banner show/remove failures, and review-history entry interstitial ads.
- The original user action remains non-blocking when an ad fails, so chart detail and review history access continue.

## Why

AdMob delivery can fail because of network state, invalid ad unit setup, platform availability, or SDK runtime issues. These failures should be visible for troubleshooting without making the app feel broken to users.

## Safety

- The existing client event reporter redacts secret-like fields before sending details.
- Logs include runtime context such as placement, plan, native availability, platform, and sanitized error name/message.
- Pro users are still excluded from non-rewarded ad display by the ad policy layer.
