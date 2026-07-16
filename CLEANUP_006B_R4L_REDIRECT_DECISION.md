# REDIRECT-ARCH-001 — Installed-App Loopback Redirect Decision

**Status:** frozen architecture; documentation-only decision
**Authorized write:** this file only
**Scope:** installed Windows desktop OAuth client, local loopback callback architecture
**No live action:** no authorization request, browser consent, callback, exchange, Google Console change, credential-file access, runtime mutation, gateway action, publication, push, or merge occurred while making this decision.

## 1. Decision

**VERIFIED — client class:** supplied BASE-001 evidence classifies the client as an installed application. The supplied recovery specification requires an installed-app loopback design.

**VERIFIED — authoritative Google guidance checked on 2026-07-15:**

- Google’s [OAuth 2.0 for iOS & Desktop Apps](https://developers.google.com/identity/protocols/oauth2/native-app) documents loopback IP redirects for desktop applications as `http://127.0.0.1:port` or `http://[::1]:port`, and says to start an HTTP listener on a random available port before substituting the actual port.
- Google’s [Loopback IP Address flow Migration Guide](https://developers.google.com/identity/protocols/oauth2/resources/loopback-migration) says the loopback flow continues to be supported for Desktop app OAuth clients.
- Google Cloud Console Help, [Manage OAuth Clients](https://support.google.com/cloud/answer/15549257?hl=en), says desktop apps require no additional information to create OAuth credentials. Its redirect-registration rules are described under the separate Web Applications section.

**DECISION — Console action:** **No Google Console redirect-registration action is required for this installed Desktop client architecture.** Do not add a fixed redirect, convert to a web client, or change the client solely to accommodate the OS-assigned local port. This is a decision from the verified client type plus the current Google desktop-specific guidance; it does not claim that a live authorization has been accepted.

**UNTESTED — live acceptance:** this task did not inspect the live Console, generate an authorization request, or contact Google. A later authorized flow may proceed only after the independent redirect checker passes. Any future live configuration error is a stop condition for that separately authorized operation; it is not permission to alter the Console during this task.

## 2. Frozen callback shape

**PROPOSED implementation contract:**

```text
client type: installed application
family: IPv4 loopback primary
host: 127.0.0.1
bind port request: 0
bound port: operating-system-assigned available port
path: /
canonical redirect: http://127.0.0.1:<actual-bound-port>/
listener: one short-lived local HTTP listener
browser: system browser on the same Windows PC that owns the listener
```

The port is not chosen, guessed, cached for reuse, or represented by a placeholder. The OS selects it by binding `127.0.0.1` with port `0`; only the resulting bound port is used to form the canonical redirect.

**INFERRED — why this addresses the failure class:** the historical helper used a fixed loopback destination without a listener and required manual copy-back. Binding first establishes an actual destination before any redirect value exists, eliminating the fixed-port/manual-callback mismatch class without changing the OAuth client family.

## 3. System model and ownership

### State owners

| State | Owner | Lifetime | Durable? |
|---|---|---:|---|
| Bound socket and listener handle | one-shot callback listener | from successful bind to terminal cleanup | No |
| Canonical redirect string | redirect resolver, then session record | one authorization attempt | Yes, restricted session record only |
| Expected state nonce and PKCE verifier | session creator | one authorization attempt | Yes, restricted session record only |
| Callback disposition and terminal reason | callback consumer | one authorization attempt | Yes, redacted terminal metadata only |
| Browser status page | listener response path | one HTTP response | No |

**Boundary:** the redirect string is created from the successful bind result. It is immutable after persistence. Socket handles, browser request objects, raw query strings, raw callback material, and generated pages are runtime-only and must never be serialized.

### Inputs and outputs

| Interface boundary | Input | Output | Failure behavior |
|---|---|---|---|
| Redirect resolver | installed-client assertion; IPv4 host; port request `0`; root-path requirement | bound listener and canonical redirect | terminate with `LOOPBACK_BIND_FAILED`; persist nothing usable |
| Authorization builder | canonical redirect and fresh request material | one browser-launchable authorization request | do not launch if contract validation fails |
| Callback receiver | one local HTTP request | terminal accepted/rejected disposition and minimal browser status | never expose received values in logs, reports, chat, or browser page |
| Exchange guard | accepted one-shot callback disposition and persisted canonical redirect | permission to perform the separately authorized one-time exchange | do not contact the exchange service unless every invariant holds |
| Cleanup | terminal disposition or timeout | closed listener and removed session artifact | cleanup must be idempotent and leave no listener |

### Invariants

1. Only the installed client is eligible: otherwise return `CLIENT_TYPE_NOT_INSTALLED`.
2. The IPv4 primary listener binds only to `127.0.0.1`; no wildcard, non-loopback, or externally reachable address is permitted.
3. The bind request uses port `0`; no fixed port is permitted.
4. The root path is exactly `/`, including its trailing slash in the canonical redirect.
5. The listener is successfully bound before authorization construction.
6. Exactly one canonical redirect is constructed from that bound socket and persisted unchanged.
7. The authorization request, callback-destination validation, and exchange request each use that exact canonical string with no host, port, path, scheme, or trailing-slash normalization.
8. A callback must target the expected root destination and contain the exact expected state before it can be accepted.
9. Exactly one callback reaches a terminal disposition. A later callback is rejected, never exchanged, and never replaces the first disposition.
10. A terminal callback, timeout, bind error, or internal terminal error closes the listener and removes restricted session state.
11. The authorization browser runs on the same Windows PC as the listener. A phone, Telegram, copied callback, or out-of-band transfer is not a callback transport.
12. Errors are stable codes and redacted metadata only. They must not contain secret material, raw callback data, or generated authorization material.

## 4. Exact implementation interface

The redirect implementation must expose these exact entry points from the designated redirect module:

```python
resolve_installed_redirect(host="127.0.0.1", port=0)
start_one_shot_callback_listener(...)
validate_redirect_contract(...)
consume_callback_once(...)
```

### `resolve_installed_redirect(host="127.0.0.1", port=0)`

- Accepts only the primary host and a port request of `0` in normal production flow.
- Performs the socket bind before creating the redirect string.
- Returns a structured bound-listener result containing the live listener handle and the exact canonical redirect.
- Rejects `localhost`, `::1`, wildcard addresses, non-loopback addresses, explicit fixed ports, a non-root path, userinfo, query, or fragment in a redirect candidate.
- Does not create browser, request, exchange, credential, or application records.

### `start_one_shot_callback_listener(...)`

- Owns the bound listener created by the resolver and accepts at most one request at the root path.
- Receives the expected immutable redirect, expected state, and expiry deadline; it does not derive or replace them.
- Returns a terminal disposition rather than raw callback content.
- Emits a minimal local browser status page that contains neither secrets nor callback/query values.
- Always invokes terminal cleanup, including after bind-adjacent error, timeout, browser disconnect, invalid callback, or accepted callback.

### `validate_redirect_contract(...)`

- Requires installed-client classification, the exact primary host, an explicit bound port, root path, and literal equality among the persisted, authorization, callback-destination, and exchange redirect values.
- Does not normalize host aliases, omit ports, append/remove a slash, accept a fallback silently, or coerce a mismatched value.
- Returns `REDIRECT_ACCEPTED` only when every redirect invariant is true; otherwise it returns the specific stable failure below.

### `consume_callback_once(...)`

- Requires the listener to be live, unexpired, and not already terminal.
- Validates destination before processing values; validates state with an exact constant-time comparison; rejects absent authorization result and provider-denied/error responses.
- Atomically records one terminal disposition before scheduling cleanup, so concurrent/late requests cannot obtain a second successful path.
- Returns redacted status only. Raw request data stays in memory only as long as needed to evaluate the callback and is then discarded.

## 5. Timing, randomness, and persistence contract

**Timing model — PROPOSED:**

```text
bind -> obtain OS-selected port -> construct canonical redirect -> persist restricted session ->
build authorization request -> same-PC browser -> one callback or expiry ->
validate -> terminal disposition -> listener shutdown + session cleanup
```

- The listener must already be accepting connections before authorization construction.
- Expiry is a short, implementation-configured deadline measured from the completed bind/session creation, not from browser launch. The implementation must inject or control time in tests.
- There is no automatic retry, second authorization request, or second exchange attempt.
- Cleanup is terminal and idempotent. It runs on every error path and on expiry.

**Randomness — PROPOSED:**

- Port selection is delegated to the operating system by port `0`, not application randomness.
- State and PKCE material must come from a cryptographically secure source created per session.
- Test seams must inject deterministic state/clock sources without changing production random-call order.
- No visual, UI, telemetry, or logging randomness may share or consume the security-randomness stream.

**Serialization boundary — PROPOSED:**

- Persist only the minimum restricted session record needed to reconnect the callback and exchange guards: canonical redirect, expected state, verifier, creation/expiry metadata, and terminal marker.
- Do not serialize listener/socket handles, browser/DOM objects, raw callback queries, request objects, browser status pages, retry queues, caches, or generated artifacts.
- The canonical redirect is durable within one session; its parsed components are derived values and must be regenerated from the exact stored string rather than independently reconstructed.
- Validation occurs before any live credential or application mutation. On validation failure, cleanup removes the session record and leaves the operational credential unchanged.

## 6. Callback outcomes and stable contracts

| Condition | Required code | Required action |
|---|---|---|
| Client is not installed | `CLIENT_TYPE_NOT_INSTALLED` | Do not bind or construct an authorization request. |
| Bind error or invalid bind request | `LOOPBACK_BIND_FAILED` | Do not construct a redirect; close any partial resource; emit redacted diagnostics. |
| Missing persisted or supplied redirect | `REDIRECT_URI_MISSING` | Do not launch browser or exchange. |
| Authorization and exchange redirects differ | `AUTH_EXCHANGE_REDIRECT_MISMATCH` | Do not exchange; terminal cleanup. |
| Callback destination differs in scheme, host, port, path, or trailing slash | `CALLBACK_REDIRECT_MISMATCH` | Reject callback; do not exchange; terminal cleanup. |
| Callback arrives after deadline | `CALLBACK_EXPIRED` | Reject callback; terminal cleanup. |
| Callback has no authorization result | `CALLBACK_MISSING_CODE` | Reject callback; terminal cleanup. |
| Callback reports a provider error or denial | `CALLBACK_OAUTH_ERROR` | Reject callback; terminal cleanup. |
| Callback state differs | `STATE_MISMATCH` | Reject callback; terminal cleanup. |
| A callback was already terminal | `SECOND_CALLBACK_REJECTED` | Reject later callback; preserve first terminal disposition; do not exchange. |
| Every contract holds for the single callback | `REDIRECT_ACCEPTED` | Permit the separate one-time exchange gate; then terminal cleanup according to its outcome. |

**Bind contract:** bind failure must not leave a partial session, an active server, an authorization request, or a stale canonical redirect.

**Expiry contract:** expiry is terminal, removes the listener and restricted session record, and makes any later callback a rejection. It never restarts the flow.

**Missing-result contract:** missing authorization result is terminal and cannot be converted into manual input.

**State contract:** state comparison is exact; a mismatch is terminal. No callback-derived state may overwrite the expected state.

**Wrong-destination contract:** destination equality is literal against the persisted canonical redirect. `localhost` and `127.0.0.1` are distinct; a root path and a missing trailing slash are distinct; an alternate port is distinct.

**Second-callback contract:** only the first terminal request may establish the disposition. Late, repeated, or concurrent requests cannot replace it or trigger a second exchange.

**Pending-cleanup contract:** every terminal path deletes restricted session material and closes the listener. A cleanup failure is recorded as a redacted operational failure and must block any follow-on exchange rather than leave the session reusable.

**No-secret-output contract:** console output, logs, reports, Kanban notes, browser pages, tests, and exception text may contain stable codes and non-sensitive lifecycle booleans only. They must not emit client secrets, authorization material, PKCE material, raw callback data, raw request URLs, headers, credential JSON, or provider payloads.

## 7. IPv6 policy

**PROPOSED — tested fallback only:** `::1` may be supported only by an explicit fallback branch that is independently tested for bind, exact canonical formatting, destination equality, state validation, one-shot behavior, and cleanup.

- IPv6 must never silently replace the frozen IPv4 primary architecture.
- A primary IPv4 bind failure is `LOOPBACK_BIND_FAILED`; it does not automatically retry on IPv6.
- Any operator-requested IPv6 fallback requires explicit selection and produces a separately persisted exact IPv6 canonical redirect for that one session.
- No dual-stack listener, host aliasing, or host normalization is allowed.

## 8. Explicit rejections

The following are incompatible with this decision and must be rejected by implementation tests and review:

- `localhost:1` or any other fixed/manual callback-port design;
- a redirect formed before a listener binds;
- `localhost` in place of the frozen IPv4 primary address;
- a fake, placeholder, guessed, cached, or fixed port;
- manual code entry, pasted callback URLs, or out-of-band authorization;
- forwarding a callback through Telegram or approving from a phone under this architecture;
- web-client substitution, wildcard redirect patterns, external callback services, or public relay endpoints;
- an authorization request from a browser not running on the listener-owning Windows PC;
- automatic retries, silent IPv6 fallback, second callback acceptance, or exchange after any validation failure.

If phone consent, remote browser consent, public callbacks, or a different client type are required, stop and request a separate architecture decision. None is authorized by this document.

## 9. Verification plan for the implementation worker and checker

**PROPOSED deterministic tests:**

1. Installed-client success with an IPv4 listener bound on port `0`.
2. Authorization and exchange use byte-for-byte identical canonical redirects.
3. Bind occurs before authorization construction.
4. The actual OS-selected port, not a configured placeholder, is used.
5. Host mismatch, port mismatch, `localhost` versus `127.0.0.1`, path mismatch, trailing-slash mismatch, non-loopback address, wildcard, userinfo, query, and fragment are rejected.
6. State mismatch, expiry, missing result, provider error, wrong destination, and second callback return their required codes and never permit exchange.
7. Listener cleanup occurs after every terminal path, and no background listener remains.
8. The historical fixed-port regression is covered without generating a live authorization request.
9. IPv6 fallback tests run only when explicitly selected; they prove it cannot silently replace the IPv4 primary path.
10. Tests prove redacted output by asserting that diagnostics contain only approved codes/booleans and not raw callback or secret-bearing fields.

**UNTESTED performance:** no benchmark is applicable to this architecture-only document. The implementation must measure only if it introduces a meaningful listener startup or request-processing performance concern; it must not trade correctness, exact URI equality, or cleanup for latency.

## 10. Boundaries and next gate

**VERIFIED:** this document changes no runtime behavior. It does not authorize live OAuth, credential replacement, scope change, gateway restart, plugin deployment, publication, push, merge, or CLEANUP-007B.

**PROPOSED next gated work:** implement and test the frozen interface in the authorized redirect implementation task, then obtain an independent redirect/ACL checker PASS before any fresh authorization session is created.

**UNTESTED:** actual Google response behavior, local browser reachability, live Console state, firewall behavior, credential acceptance, and end-to-end callback handling remain untested until their separately authorized stages.

## 11. Architecture acceptance checklist

- [x] Installed client, IPv4 `127.0.0.1`, port `0`, and root path are frozen.
- [x] Listener-before-authorization and exact URI reuse are frozen.
- [x] One callback, strict state/destination validation, terminal timeout, and cleanup are frozen.
- [x] Same-PC system browser boundary is frozen.
- [x] IPv6 is fallback-only and never silent.
- [x] Fixed fake ports, manual/out-of-band flow, Telegram callback transport, phone consent, web-client workaround, wildcard, and external services are rejected.
- [x] Console decision is recorded with authoritative current Google sources and live-state limitation.
- [x] Bind/error/expiry/missing-result/state/wrong-destination/second-callback/cleanup/no-secret-output contracts are recorded.
- [x] No live Google or credential operation occurred.
