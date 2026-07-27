# LLM Invocation Runtime

**Status:** As-built reference, Milestone 17 (LLM Invocation Runtime).
Describes the invocation extension of the `app/application/**` +
`app/infrastructure/llm/**` capability as implemented - for the
decision record (why invocation is a runtime capability rather than a
new bounded context, why the runtime owns retry, why SDK retries are
disabled, why cancellation is real `asyncio` cancellation), see
[ADR-0014](adr/0014-llm-invocation-runtime.md). For the request-side
foundation this milestone extends, see
[llm_provider_abstraction.md](llm_provider_abstraction.md) and
[ADR-0013](adr/0013-llm-provider-abstraction-layer.md).

## Invocation lifecycle

```
PromptPackage
        |
   LLMRequest                   (Milestone 16 - unchanged)
        |
   AnthropicPreparedRequest      (Milestone 16 - unchanged)
        |
   LLMProviderPort.invoke()      (one provider call, one attempt)
        |
   LLM Invocation Runtime        (app/application/services/llm_runtime.py -
        |                         owns attempt sequencing, the total
        |                         deadline, retry decisions, cancellation)
   LLMResponseEnvelope           (normalized, provider-neutral)
```

`app/application/services/llm_invocation_service.py` orchestrates:
runtime enablement -> credential presence (never the credential's own
value) -> request preparation (delegated to Milestone 16's own
`llm_request_service.prepare_llm_request`, never re-derived) -> adapter
resolution -> `run_invocation`. No persistence, no provider fallback,
no engineering interpretation of the response.

## Port evolution

`LLMProviderPort` gains exactly one new async method, alongside
Milestone 16's three:

```python
async def invoke(
    self,
    request: LLMRequest,
    prepared_request: PreparedProviderRequest,
    invocation_context: LLMInvocationContext,
) -> LLMResponseEnvelope: ...
```

Performs exactly **one** provider call for **one** attempt. On
success, returns a normalized envelope; on failure, raises
`ProviderInvocationFailedError` carrying an already-normalized
`LLMProviderError` - never a raw SDK exception. An implementation must
never retry internally (retry decisions belong exclusively to the
runtime) and must never expose a provider SDK object or a credential.

## Runtime / service responsibilities

`llm_runtime.run_invocation` owns:

- **Attempt sequencing** - `attempt_number` increments once per loop
  iteration; every attempt (success, failure, or cancellation) becomes
  an `LLMInvocationAttempt`.
- **The total deadline** - computed once, at the start, from
  `LLMTimeoutPolicy.total_deadline_seconds`; checked at the top of
  every loop iteration before a new attempt begins. A deadline already
  exhausted before the first attempt yields zero attempts and a
  `TOTAL_DEADLINE_EXCEEDED` terminal error.
- **Retry decisions** - delegated entirely to
  `llm_retry_policy.LLMRetryDecisionMaker`, never decided inline.
- **Cancellation** - `asyncio.CancelledError` raised during an attempt
  is recorded as a `CANCELLED` attempt, then re-raised as
  `LLMInvocationCancelledError` (itself a `CancelledError` subclass, so
  it is never mistaken for an ordinary application exception).
- **Assembling the final envelope** - on success, the adapter's own
  per-attempt envelope stub is `dataclasses.replace()`-d with the
  runtime's own `started_at`/`completed_at`/`latency_seconds`/
  `attempts`/`attempt_count`, covering the *entire* invocation, not
  just the last attempt.

`clock`, `sleeper`, and `random_source` are always supplied by the
caller (the service, ultimately the router) - never read from the wall
clock, `asyncio.sleep`, or the global `random` module directly - so the
whole loop is deterministic and testable without any real delay.

`llm_invocation_service.invoke_llm` owns everything *before* the
runtime loop: validating runtime enablement, credential presence
(as a boolean only - see Security below), delegating to Milestone 16's
`prepare_llm_request`, resolving the adapter, and constructing the
`LLMInvocationPolicy` from `LLMRuntimeConfiguration`.

## Runtime configuration

`app/application/config/llm_configuration.py` extends Milestone 16's
env-var convention (plain `os.getenv`, no settings framework):

| Variable | Default |
|---|---:|
| `LLM_RUNTIME_ENABLED` | `false` |
| `LLM_CONNECT_TIMEOUT_SECONDS` | `5.0` |
| `LLM_READ_TIMEOUT_SECONDS` | `60.0` |
| `LLM_TOTAL_TIMEOUT_SECONDS` | `90.0` |
| `LLM_MAX_ATTEMPTS` | `3` |
| `LLM_RETRY_BASE_DELAY_SECONDS` | `1.0` |
| `LLM_RETRY_MAX_DELAY_SECONDS` | `20.0` |
| `LLM_RETRY_JITTER_ENABLED` | `true` |

Real invocation is **disabled by default** - a fresh deployment never
silently transmits project data to an external provider.
`LLMRuntimeConfiguration` never carries a credential; `ANTHROPIC_API_KEY`
(the same variable the legacy `ClaudeProvider` already reads - one
credential per provider, not two) is read separately by
`read_provider_credential`, called only at the composition root.

## Timeout model

Three distinct concepts, per `LLMTimeoutPolicy`:

- **Connect timeout** - per SDK call, passed to `httpx.Timeout(connect=...)`.
- **Read timeout** - per SDK call, passed to `httpx.Timeout(read=..., write=...)`.
- **Total deadline** - the *entire* invocation's budget (every attempt,
  every retry delay), tracked by the runtime, never by the SDK or the
  adapter.

A timeout is recorded with a `LLMTimeoutPhase` (`CONNECTION`, `READ`,
`TOTAL_DEADLINE`, or `UNKNOWN` when the SDK's own wrapped cause can't be
distinguished) so a caller can tell a local deadline expiry from a
genuine provider-side timeout.

## Retry decision table

`app/application/policies/llm_retry_policy.py`, `RETRY_POLICY_VERSION`:

**Retryable:** `CONNECTION_FAILURE`, `CONNECTION_TIMEOUT`,
`READ_TIMEOUT`, `RATE_LIMITED`, `PROVIDER_OVERLOADED`,
`TRANSIENT_PROVIDER_FAILURE`.

**Non-retryable (everything else):** `AUTHENTICATION_FAILURE`,
`AUTHORIZATION_FAILURE`, `INVALID_REQUEST`, `UNSUPPORTED_REQUEST`,
`MODEL_NOT_FOUND`, `REQUEST_TOO_LARGE`, `INVALID_CONFIGURATION`,
`RUNTIME_DISABLED`, `CANCELLED`, `CONTENT_POLICY_REJECTION`,
`TOTAL_DEADLINE_EXCEEDED`, and - deliberately, conservatively -
`UNKNOWN_PROVIDER_ERROR` (an error this runtime cannot even categorize
is never assumed transient).

Bounded exponential backoff: `delay = min(max(base * 2^(attempt-1),
retry_after_hint), max_delay)`, then +/-20% jitter when enabled
(injected `random.Random`, never the global `random` module). A retry
is refused if the computed delay would exceed the remaining total
deadline.

## Cancellation

`asyncio.CancelledError` raised inside `invoke_anthropic`'s awaited SDK
call propagates untouched (it is a `BaseException`, not caught by
`except Exception`). The runtime catches it exactly once, records a
`CANCELLED` attempt, and re-raises `LLMInvocationCancelledError` - a
`CancelledError` subclass, never converted into a retryable error and
never followed by a new attempt.

## Error taxonomy

`app/infrastructure/llm/anthropic/anthropic_error_mapper.py` maps every
SDK exception type into a normalized category - see the module's own
docstring for the full table (`AuthenticationError` ->
`AUTHENTICATION_FAILURE`, `RateLimitError` -> `RATE_LIMITED`,
`APITimeoutError` -> `CONNECTION_TIMEOUT`/`READ_TIMEOUT` depending on
the wrapped `httpx` cause, etc.). Every mapped error carries only safe,
already-extracted fields (`http_status`, `provider_error_type`,
`provider_request_id`, `retry_after_seconds`, `timeout_phase`) - never
the raw `httpx.Response`, the request payload, or a credential.

## Response normalization

`app/infrastructure/llm/anthropic/anthropic_response_mapper.py`:

- **Content** - each Anthropic content block becomes an
  `LLMResponseContent`. `type="text"` blocks map to
  `LLMResponseContentType.TEXT`; every other block type (tool use,
  thinking, ...) maps to `UNSUPPORTED` with an empty `text`, the
  provider's own block type preserved as safe metadata, and a
  structured warning - never silently reinterpreted as engineering
  text.
- **Finish reason** - Anthropic's `stop_reason` maps to
  `LLMFinishReason` (`end_turn` -> `COMPLETED`, `max_tokens` ->
  `MAXIMUM_OUTPUT_REACHED`, `stop_sequence` -> `STOP_SEQUENCE`,
  `tool_use` -> `TOOL_REQUEST`, `refusal` -> `REFUSAL`); an absent or
  unrecognized value maps to `UNKNOWN` with a warning, never treated as
  successful completion silently.
- **Usage** - `input_tokens`/`output_tokens`/`total_tokens` (derived)/
  `cached_input_tokens`/`cache_creation_tokens`; every value the
  provider does not report is `None`, never estimated or defaulted to
  zero.

## Attempt history

Every `LLMInvocationAttempt` (`attempt_number`, `status`, `started_at`,
`completed_at`, `latency_seconds`, `error`) is preserved on both
`LLMInvocationResult.attempts` and `LLMResponseEnvelope.attempts` - the
full record of what actually happened, inspectable after the fact
without correlating logs.

## Fake adapter

`app/infrastructure/llm/base/fake_llm_provider_adapter.py`'s
`FakeLLMProviderAdapter.invoke` consumes a scripted sequence of
`FakeInvocationOutcome`s (one per attempt, 1-indexed, the last
repeating if exhausted) - success, any normalized failure category,
`retry_after_seconds`, unsupported content, and a genuine, cancellable
`delay_seconds` await point (via an injectable sleeper) - proving the
runtime's retry/timeout/cancellation behavior without any Anthropic
dependency at all.

## Safe logging

`app.application.services.llm_runtime` logs (via the standard library
`logging` module, `logger = logging.getLogger(__name__)` - this
repository's existing convention): invocation started (provider,
model, correlation id), each attempt started/failed/succeeded, the
normalized error category and retry decision, retry delay scheduled,
and invocation completed (attempt count, total latency). **Never**
logged: API keys, authorization headers, full prompt/response content,
SDK objects, environment dumps, or raw exception reprs that might carry
request detail - only closed categories, counts, and identifiers.

## Metrics

`app/application/services/llm_runtime_metrics.py`'s
`LLMRuntimeMetrics` - a small, thread-safe, in-process counter set
(total invocations, successes, failures by category, retries,
timeouts, cancellations, total input/output tokens). Resets on process
restart; never persisted or exported to an external platform (none
exists in this repository yet) - deliberately not a telemetry
framework.

## Security and the external data boundary

**This milestone introduces this codebase's first external data
boundary.** Whenever `LLM_RUNTIME_ENABLED=true` and a credential is
configured, enabled `PromptPackage` content (which may include
project-scoped engineering information) is transmitted to the
configured external provider. Enforced:

- Runtime invocation is opt-in, disabled by default.
- Only the configured provider is ever called - no automatic fallback.
- No user-supplied provider import path, no dynamic code loading.
- Credentials are read only from trusted runtime configuration, never
  accepted as a request body field, never exposed in a response,
  never logged.
- The Milestone 16 preparation-only endpoint continues to perform zero
  invocation, regardless of runtime configuration.

No tenant consent workflow or data-residency routing exists yet -
recorded as explicit future product/security work, not solved
speculatively here.

## API

```
POST /projects/{project_id}/llm/prepare-request   (Milestone 16 - unchanged, still zero invocation)
POST /projects/{project_id}/llm/invoke            (Milestone 17 - may perform a real call)
```

`/invoke`'s body reuses `PromptPackageRead` (the same shape
`/prepare-request` accepts) plus optional `provider_id`/
`model_identifier` overrides, optional generation parameters, and an
optional client-supplied `request_correlation_id`. **Never** accepts an
API key or any other credential. Response: an `LLMInvocationResultRead`
- either a populated `envelope` or a populated `terminal_error`, plus
the full attempt history, never both, never neither.

### Errors

Every `LLMProviderAbstractionError` subtype (runtime disabled, missing
credential, unknown provider, provider mismatch, unsupported required
capability, invalid `PromptPackage`) maps to `422 Unprocessable Entity`.
An *expected* provider failure (rate limited, authentication failure,
...) is a `200 OK` response with `status="failed"` and a populated
`terminal_error` - never conflated with a request-validation error.

## Performance

Runtime orchestration (excluding external latency) is O(n) in
request/response content blocks and O(a) in the number of attempts,
bounded by `max_attempts` and the total deadline. See
[performance_baseline.md](performance_baseline.md) for recorded numbers
(`llm_invocation_fake_success`/`llm_invocation_transient_then_success`/
`anthropic_response_normalization` operations) - never the live
provider API, and never a real wall-clock sleep (an injected no-op
sleeper stands in for retry backoff in the benchmark).

## Optional live smoke test

`scripts/smoke_tests/llm_invocation_smoke_test.py` - a manual,
opt-in-only script proving a real Anthropic call actually works,
**never** run by pytest or CI. See the script's own module docstring
for the exact opt-in flag and safety requirements.

## Future provider additions

Adding a second provider's invocation requires only: implementing
`invoke()` on that provider's own adapter (its own client factory,
invoker, error mapper, response mapper - mirroring the `anthropic/`
package's own four-file shape), and registering it in the composition
root. The runtime, retry policy, timeout policy, cancellation handling,
and response validation are all already provider-neutral and require
no change.
