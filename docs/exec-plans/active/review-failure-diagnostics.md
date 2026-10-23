# Review failure diagnostics

## Scope

Diagnose the next single authorized reproduction without changing review content,
quota/refund, model selection, storage/cache/replay, consent or activation policy.
Base: 50954d4b435e254f2ad05f18da42748bd96c3dc1.

## Diagnostic contract

- Generate a server-owned UUID for each POST /api/journal/ai-review-once, including
  replay and failed requests. Return it in the existing X-Request-ID header only;
  no diagnostic fields enter approved result, history or cache documents.
- Record access, trade_context, source_build, openai_request, openai_response,
  canonical_finalizer, history and cache stages. Keep the first failure stage;
  a successful existing advanced fallback clears its recovered request failure.
- Emit only review type, stage, coarse status/error class, provider-attempt flag,
  model, access source, refund/display booleans, duration and generated request ID.
- Operational telemetry and an independent structured application log are both
  best-effort. Neither includes user identity, trades, prompts, output or credentials.

## Verification

- Focused H4: diagnostics 8/8, existing access/tester 8/8, activation/history
  14/14 and whole-execution cache/replay 14/14 PASS (44 distinct direct cases).
- Guard violations/unexpected access 0; restoration, patch restoration and
  cleanup passed. Diagnostics additionally verifies tester source/refund with
  unchanged quota and the real provider-call boundary using a mocked transport.
- Inventory: 1090 direct, 109 modules, 18 separate child probes; missing and
  duplicate 0. ESLint, Python AST syntax and git diff --check PASS.
- First diagnostic matrix run had one test-fixture failure: a prior probe's
  cache invoked the injected normalizer failure before the intended finalizer.
  Probes now isolate their cache; the subsequent official runs passed.
- No real OpenAI calls, production writes or configuration changes performed.

## Next step

Focused verification completed; scoped commit authorized by the user. Deployment
and one real reproduction require later authorization. Match X-Request-ID in the
network response to the review_diagnostic application log without logging the
response body. Browser JavaScript header exposure is unchanged; use the network
inspector or the device's existing request inspection path.
