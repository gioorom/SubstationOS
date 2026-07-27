# ADR-0014: LLM Invocation Runtime

## Status

Accepted.

## Context

By Milestone 16 (LLM Provider Abstraction Layer, ADR-0013), a
`PromptPackage` maps deterministically into a provider-neutral
`LLMRequest`, and an `AnthropicAdapter` translates it into a local,
never-sent `AnthropicPreparedRequest` - request preparation, with zero
network I/O and zero external provider dependency. Nothing yet actually
calls a language-model provider. This milestone is the first one in
this codebase's governed EPIC 4 pipeline allowed to perform a real
external network call - and the first time project-scoped engineering
data leaves the process boundary at all.

A pre-existing fact shaped this milestone's design directly:
`app/services/ai/claude_provider.py` (the legacy, ADR-0009-isolated
adapter behind the unreviewed `ingest_document` extraction path)
already performs a real Anthropic invocation, with no runtime-owned
retry policy, no timeout policy beyond whatever the SDK defaults to,
and no normalized error taxonomy - a raw `Exception` wraps whatever the
SDK raised. This is exactly the shape of risk a governed invocation
path must not repeat: stacked, uncoordinated retries; timeouts that
silently vary with SDK defaults; and provider errors indistinguishable
from programmer errors. That file is left untouched (per this
project's discipline: no redesign of existing behavior without a
demonstrated defect in *this* milestone's own scope, and this milestone
is explicitly barred from routing new behavior through it) but is the
clearest concrete argument for the discipline below.

Three temptations existed and were rejected before writing any code:

1. **Let the Anthropic SDK's own built-in retry logic handle transient
   failures**, since it already implements a documented backoff
   strategy. Rejected: a second, independent retry layer competing
   with a runtime-owned one would silently multiply the effective
   number of attempts and delays neither layer accounts for, making
   "how many times did we actually call the provider" unanswerable
   from either layer alone. The runtime disables SDK retries entirely
   (`max_retries=0`) so exactly one layer ever decides to retry.
2. **Let `AnthropicAdapter.invoke()` own its own retry loop**, since it
   is the layer closest to the actual failure. Rejected: retry
   decisions (which error categories are safe to retry, how long to
   wait, how many attempts remain) are provider-*independent* policy
   questions - baking them into one adapter would mean every future
   provider adapter re-derives the same policy, with no shared,
   testable, cross-provider guarantee. The adapter's `invoke()`
   performs exactly one provider call per invocation and normalizes
   exactly one outcome (success or a typed failure); the runtime
   (`app.application.services.llm_runtime`) is the only place that
   decides whether attempt N+1 happens at all.
3. **Return the Anthropic SDK's `Message` object (or a thin wrapper
   around it) directly from the invocation path**, since normalizing it
   is extra work for a first version. Rejected outright by this
   milestone's own instructions and rejected on the merits: it would
   leak an SDK type into `app/application/**`, forcing every future
   caller (a Prompt Builder... no, wrong direction - every future
   *consumer* of a response) to depend on Anthropic's own response
   shape, defeating the entire point of a provider-neutral runtime.

## Decision

### 1. Four distinct representations, never collapsed

```
PromptPackage (Prompt Builder, unchanged)
        |
   LLMRequest                   - provider-neutral request (Milestone 16)
        |
   AnthropicPreparedRequest      - local, provider-shaped, never sent (Milestone 16)
        |
   (a real Anthropic Messages API call - this milestone)
        |
   LLMResponseEnvelope           - provider-neutral response (this milestone)
```

`AnthropicPreparedRequest` != an `anthropic` SDK request object != the
SDK's own `Message` response != `LLMResponseEnvelope`. The SDK's own
types are constructed and consumed entirely inside
`app/infrastructure/llm/anthropic/anthropic_invoker.py` and never cross
back into `app/application/**` - every field the application layer ever
sees has already been normalized (safe status codes, safe error type
strings, safe message summaries; never a raw `httpx.Response`, never an
SDK exception, never a credential).

### 2. Still not a bounded context - the LLM Invocation Runtime extends the same application/infrastructure capability

`app/application/services/llm_runtime.py` (the attempt/retry/deadline
loop), `app/application/policies/llm_retry_policy.py`,
`app/application/validation/llm_response_validator.py`, and
`app/infrastructure/llm/anthropic/{anthropic_client,anthropic_invoker,
anthropic_error_mapper,anthropic_response_mapper}.py` all extend
Milestone 16's existing `app/application/**`/`app/infrastructure/llm/**`
placement - never a new `app/domain/llm_runtime/`. Invocation lifecycle
management is an application/infrastructure capability, the same
reasoning ADR-0013 already gave for request preparation; nothing about
*executing* a request changes what kind of knowledge this is.

### 3. The runtime owns every retry decision; the SDK and the adapter own none

`AsyncAnthropic` is constructed with `max_retries=0`
(`anthropic_client.py`). `AnthropicAdapter.invoke()`/`invoke_anthropic()`
perform exactly one SDK call and either return a normalized
`LLMResponseEnvelope` or raise `ProviderInvocationFailedError` carrying
an already-normalized `LLMProviderError` - no loop, no delay, no
awareness of "attempt number" beyond what it needs to label its own
single attempt. `llm_runtime.run_invocation` is the **only** place that
decides whether to retry, informed by
`llm_retry_policy.LLMRetryDecisionMaker`'s fixed, documented,
version-stamped classification of every `LLMProviderErrorCategory`
into retryable or not (see `llm_retry_policy.py`'s own module
docstring for the full table) - bounded exponential backoff, capped by
`LLMRetryPolicy.max_delay_seconds` regardless of the provider's own
`Retry-After` hint, with injectable jitter so tests are fully
deterministic.

### 4. The total deadline bounds the whole invocation, not each call

`LLMTimeoutPolicy` separates connect/read timeouts (per SDK call,
configured on the `httpx.Timeout` passed to `AsyncAnthropic`) from a
single **total invocation deadline** computed once, at the start of
`run_invocation`, covering every attempt and every retry delay
combined. A new attempt never starts once that deadline has passed
(`app.application.policies.llm_timeout_policy.is_deadline_exceeded`) -
checked at the top of every loop iteration, before any new attempt
context is even constructed.

### 5. Cancellation is real `asyncio` cancellation, never disguised as a retryable provider error

`asyncio.CancelledError` raised during an awaited SDK call propagates
untouched through `invoke_anthropic` (it is a `BaseException`, not an
`Exception`, in this Python version, so the invoker's own
`except Exception` never intercepts it). `llm_runtime.run_invocation`
catches it exactly once, records a `CANCELLED` attempt for
observability, and re-raises `LLMInvocationCancelledError` - itself a
subclass of `asyncio.CancelledError`, not of
`LLMProviderAbstractionError`, so it is never accidentally caught by
the router's own `except LLMProviderAbstractionError` translation
logic and continues propagating as genuine cancellation all the way to
the ASGI layer.

### 6. Expected provider failures are data, not exceptions

`LLMInvocationResult` carries either a populated `envelope`
(`status=SUCCEEDED`) or a populated `terminal_error`
(`status=FAILED`/`CANCELLED`) - never both, never neither. A rate
limit, a transient server error, an authentication failure: all of
these are *expected*, inspectable outcomes of calling an external
system, returned as data through the same success path a caller
already inspects, never raised as an exception. Exceptions in this
milestone are reserved for genuinely invalid input or impossible states
(`LLMRuntimeDisabledError`, `MissingCredentialError`,
`UnknownProviderError`, `ProviderMismatchError`,
`UnsupportedCapabilityError`) and for cancellation, which Python's own
async model requires to propagate as an exception.

## Consequences

**Easier:**
- A future second provider adapter (OpenAI, a local runtime, anything
  else) inherits the entire retry/timeout/cancellation/validation
  machinery for free - it only has to implement `invoke()` for one
  provider call and normalize that provider's own errors, never
  reimplement backoff, deadline tracking, or attempt bookkeeping.
- Every invocation's full attempt history
  (`LLMInvocationResult.attempts`) is inspectable after the fact,
  making "why did this fail" answerable from the response alone,
  without correlating logs across the SDK, the adapter, and the
  runtime.
- The preparation-only endpoint (Milestone 16) is untouched and
  continues to perform zero invocation - proving the two concerns
  (what would we send vs. did we actually send it) remain genuinely
  separable.

**Harder / deferred:**
- This milestone introduces this codebase's first external data
  boundary: enabled `PromptPackage` content leaves the process and
  reaches Anthropic's servers whenever `LLM_RUNTIME_ENABLED=true` and a
  credential is configured. No tenant consent workflow, no
  data-residency routing, and no per-project opt-out exists yet -
  recorded as explicit future product/security work, not solved
  speculatively here.
- Today's `PromptPackage` models no real end-user question or prior
  conversation turn, so every `CONTEXT`-role section is folded into one
  synthetic `role="user"` Anthropic message
  (`anthropic_mapper.py`, inherited unchanged from Milestone 16). A
  genuine multi-turn conversation is Milestone 18's concern
  (Engineering Response Foundation) and beyond, not this one's.
- Usage/token counts are exactly what the provider reports, never
  estimated when absent - a provider that omits usage data yields
  `None` fields, not a computed guess. No cost calculation exists;
  usage is operational telemetry only.
- Metrics are a small, in-process, non-persisted counter set
  (`llm_runtime_metrics.py`) - reset on every process restart, never
  exported to an external monitoring platform. Adequate for this
  milestone's own "avoid building a large telemetry framework"
  instruction; a real observability platform is out of scope.

## Rejected Alternatives

- **Rely on the Anthropic SDK's own retry logic instead of a
  runtime-owned policy.** Rejected: produces two independent,
  uncoordinated retry layers, making total attempt count and total
  elapsed time unpredictable from either layer's own configuration
  alone.
- **Let each provider adapter own its own retry loop.** Rejected: retry
  policy (which errors are retryable, backoff shape, deadline
  enforcement) is provider-independent; duplicating it per adapter
  would mean every future provider reimplements the same policy with
  no shared guarantee of consistent behavior across providers.
- **Return the Anthropic SDK's `Message` object, or a thin wrapper
  around it, as this milestone's response contract.** Rejected
  explicitly by this milestone's own instructions, and on the merits:
  it would leak a provider SDK type into the application layer,
  coupling every future response consumer to Anthropic's own response
  shape.
- **Convert `asyncio.CancelledError` into a normal, retryable
  `LLMProviderError`.** Rejected: cancellation is the caller
  withdrawing the request, not a transient provider condition: retrying
  after cancellation would ignore the caller's own explicit signal that
  the result is no longer wanted.
- **Persist requests, responses, or invocation attempts.** Rejected,
  for the same reason ADR-0011/0012/0013 rejected persisting their own
  artifacts: no requirement demonstrated a need for it this milestone,
  and every artifact here is cheaply reconstructable from its own
  inputs (a `PromptPackage` and a configuration) - persisting it would
  be a second, potentially stale copy of derived data with no clear
  owner, and would introduce exactly the kind of audit-database-table
  scope this milestone's own non-goals explicitly exclude.
- **Build a full external observability/metrics platform integration.**
  Rejected: no such platform exists in this repository yet, and
  introducing one is a project-wide decision far outside this
  milestone's scope - a small, in-process counter set satisfies the
  "lightweight telemetry" requirement without that scope creep.
