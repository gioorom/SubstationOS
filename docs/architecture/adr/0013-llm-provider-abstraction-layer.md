# ADR-0013: LLM Provider Abstraction Layer

## Status

Accepted.

## Context

By Milestone 15 (Prompt Builder Foundation, ADR-0012), the governed
knowledge pipeline can turn a `ContextPackage` into a deterministic,
provider-independent `PromptPackage` - structured sections, fixed
constraints/instructions, approximate token estimates. Nothing yet
turns "I have a provider-independent prompt" into "I have something
that could actually be sent to a real language-model provider." A real
invocation is not yet in scope (Milestone 17, LLM Invocation Runtime,
owns that) - but the shape of *what gets sent*, and to *which
provider*, needed a home before invocation could be built without
locking the platform to one vendor's API by construction.

A second, pre-existing fact shaped this milestone directly:
`app/services/ai/claude_provider.py` (predating EPIC 4, still used by
the legacy, ADR-0009-isolated `ingest_document` extraction path)
already hardcodes a hardcoded fallback model string
(`"claude-sonnet-4-20250514"`) and imports the `anthropic` SDK
directly inside its own constructor. This is exactly the anti-pattern
Milestone 16 exists to prevent for the governed EPIC 4 pipeline: a
model version baked into code, and a provider SDK reachable from
application logic with no seam between "what SubstationOS needs" and
"how Anthropic's API happens to be shaped." That legacy file is left
untouched (per this project's "do not redesign completed work without
a demonstrated defect in *this* milestone's scope" discipline - its own
defect is already tracked, isolated, and out of scope here) but is the
clearest concrete argument for why this ADR's separation matters.

Three temptations existed and were rejected before writing any code:

1. **Let a future LLM Invocation Runtime consume `PromptPackage`
   directly and format Anthropic's request itself, inline, when it is
   eventually built.** Rejected: this would mean the very first real
   invocation code ever written for this pipeline also has to invent
   the provider-neutral/provider-specific split under time pressure,
   with a working feature already riding on getting it right. Building
   the seam now, with no invocation pressure, produces a cleaner
   contract than building it retroactively around a Claude-specific
   implementation.
2. **Give `PromptPackage` itself Anthropic-shaped fields** (e.g. a
   `system_prompt: str`, a `messages: list[dict]`) so a future adapter
   could serialize it with minimal translation. Rejected outright by
   this milestone's own instructions ("do not modify PromptPackage to
   match Anthropic or OpenAI payloads") and rejected on the merits:
   Prompt Builder's entire reason to exist (ADR-0012) is a structured,
   inspectable artifact independent of any provider's message
   arrangement; reshaping it around one provider's API would undo that
   milestone's own decision one release later.
3. **Build a generic "AI capability" interface broad enough to cover
   invocation, streaming, tool use, and multimodal input right now,**
   since those are all real capabilities a language-model provider
   might eventually offer. Rejected: Milestone 16 has no invocation
   pressure yet (that is explicitly Milestone 17's job) and no
   demonstrated need for streaming/tool-use/multimodal support this
   pipeline does not yet use - a broader interface built speculatively
   would be exactly the kind of premature abstraction CLAUDE.md SS12
   (YAGNI) forbids.

## Decision

### 1. Three explicitly separated layers, not a new domain bounded context

```
PromptPackage (Prompt Builder's own artifact, unchanged)
        |
   app/application/**   - provider-neutral application contract
        |                 (LLMProviderPort, LLMRequest and its parts)
   app/infrastructure/llm/anthropic/**  - the first concrete adapter
        |                 (AnthropicPreparedRequest - local, never SDK)
   (a future HTTP call - explicitly out of this milestone's scope)
```

This is deliberately **not** a new bounded context under
`app/domain/**`. Every prior EPIC 4 milestone (Structured Retrieval,
Context Builder, Prompt Builder) modeled a governed *engineering*
concept; provider selection, request shaping, and capability
negotiation are an *infrastructure capability* the application needs,
not a new piece of engineering domain knowledge about substations. It
lives in `app/application/**` (provider-neutral contracts and
orchestration) and `app/infrastructure/llm/**` (concrete adapters),
following CLAUDE.md's Dependency Rule the same way every other
infrastructure adapter in this codebase already does - the adapter
depends on the contract, never the reverse.

### 2. Anthropic is the first production adapter, not the platform's identity

`AnthropicAdapter` (`app/infrastructure/llm/anthropic/`) is the first
concrete `LLMProviderPort` implementation because Anthropic Claude is
this project's intended first deployment choice - a fact about
`app/routers/llm_provider.py`'s own default configuration
(`DEFAULT_PROVIDER_ID = "anthropic"`), never a fact baked into
`app/application/**`. The provider-neutral layer has no
Anthropic-specific concept anywhere in it: no SDK type, no
`system`/`messages` shape, no Claude role vocabulary. A second
provider adapter (OpenAI, a local model runtime, anything else) is
addable by implementing `LLMProviderPort` and registering it under a
new provider identifier - zero changes to `app/application/**`, to
Prompt Builder, or to any earlier pipeline stage.

### 3. `PromptPackage` != `LLMRequest` != `AnthropicPreparedRequest` != an SDK object != an HTTP payload

Four distinct representations, each owned by the layer whose job it
actually is:

- `PromptPackage` (Prompt Builder, ADR-0012) - sections, constraints,
  instructions, provider-independent, already deterministic.
- `LLMRequest` (`app/application/models/llm_request.py`) - the same
  content, translated into provider-neutral semantic roles
  (`instruction`/`context`/`user`/`assistant`/`tool`) and typed content
  blocks (`text`/`structured_data`/`reference`), plus operational
  metadata and version traceability. Still no provider concept of any
  kind.
- `AnthropicPreparedRequest` (`app/infrastructure/llm/anthropic/anthropic_models.py`)
  - a **local, immutable** stand-in for what would become an Anthropic
  Messages API request body (`system`/`messages`/`max_tokens`/...) -
  the first place Anthropic's own shape is allowed to appear, and even
  here it is never an SDK object, never serialized, never sent.
- An Anthropic SDK request object and an HTTP payload - neither exists
  in this codebase yet; both are Milestone 17's responsibility.

Collapsing any two of the first three into one type would either leak
provider concepts upstream into Prompt Builder (reopening ADR-0012's
own decision) or leak provider-neutral vocabulary into the adapter
layer without a clean seam a second provider could reuse.

### 4. Provider and model selection are runtime configuration, never a static identity

`LLM_PROVIDER`/`LLM_MODEL` environment variables
(`app/application/config/llm_configuration.py`), read with the exact
same plain-`os.getenv` convention `app/services/ai/claude_provider.py`
already established - no settings framework introduced. Critically,
unlike that legacy file, `LLM_MODEL` has **no hardcoded fallback of any
kind**: an unset value yields an empty string, which
`llm_request_validator.py` rejects as a structurally invalid model
selection. No Claude Opus or Sonnet version, dated or otherwise, is
assumed to exist anywhere in this codebase's new code. Model
identifiers are never checked against a static "known models" list -
only structural validity (non-blank, bounded length) is ever verified,
so a newly released model name works the day it is configured, with no
code change.

### 5. Capabilities are declared, never assumed, and a missing required capability is a hard failure

`LLMProviderPort.provider_capabilities()` returns exactly the
capabilities that adapter's own `prepare_request()` genuinely
implements (`AnthropicAdapter` declares five of nine defined
`LLMCapability` values - explicitly not streaming, tool use, structured
output, or multimodal input, none of which this milestone's mapping
logic implements). A capability the caller *requires* but the resolved
provider does not support raises `UnsupportedCapabilityError` -
request preparation stops, it never silently proceeds with a degraded
request. An *optional*, merely-requested generation parameter the
provider does not support (e.g. `temperature` on a hypothetical
provider that ignores it) is reported as a warning on
`LLMRequestPreparationResult` instead - informational, never a reason
to fail preparation outright.

### 6. No provider fallback, ever, under any circumstance

`LLMProviderRegistry.resolve()` raises `UnknownProviderError` for an
unregistered provider id; there is no "try the next provider" logic
anywhere in `LLMRequestPreparationService`. A caller that asked for
`"anthropic"` and got an error was asking for Anthropic specifically -
silently substituting a different provider would violate the very
guarantee this ADR exists to give: the platform is provider-neutral in
its *architecture*, never in its *behavior toward a specific request a
caller actually made*.

### 7. Zero external provider dependency this milestone

`AnthropicAdapter` never imports the `anthropic` package. This
milestone performs no client construction, no HTTP request, no
response parsing - there is nothing yet that would need the SDK, and
adding the dependency before it is exercised would be exactly the kind
of premature complexity CLAUDE.md SS12 forbids. `FakeLLMProviderAdapter`
(`app/infrastructure/llm/base/`) proves the same `LLMProviderPort`
contract with zero dependency of any kind, existing solely so tests can
demonstrate genuine provider neutrality without needing Anthropic's own
adapter to be the only path through the abstraction.

## Consequences

**Easier:**
- A second provider adapter (OpenAI, a local model runtime, any
  future provider) is addable by implementing one interface and
  registering it under a new identifier - no change to Prompt Builder,
  to any earlier pipeline stage, or to the provider-neutral request
  contract itself.
- Every prepared request is inspectable via
  `POST /projects/{id}/llm/prepare-request` before any real invocation
  exists, for architecture validation, debugging, frontend inspection,
  and audit.
- Capability declarations make "can this provider actually do X"
  a checked, typed fact rather than an assumption discovered only when
  a real call fails.

**Harder / deferred:**
- No real invocation exists yet - `POST /projects/{id}/llm/prepare-request`
  never calls Anthropic or any other provider. Milestone 17 (LLM
  Invocation Runtime) owns adding that, behind this same
  `LLMProviderPort`.
- Today's mapping of provider-neutral roles onto Anthropic's own
  `system`/`messages` shape sends every `CONTEXT`-role section into a
  single synthetic `role="user"` message, since no real end-user
  question exists in a `PromptPackage` yet (Prompt Builder does not
  model a conversation turn). This is a reasonable, honest, documented
  provisional choice (`anthropic_mapper.py`), not a permanent design -
  Milestone 17 is expected to append a genuine user turn once one
  exists, not to redesign this system/conversational split.
- Token estimates inherited from Prompt Builder (ADR-0012) remain
  approximate; this milestone adds no exact, provider-specific
  counting (that would require the very SDK dependency this milestone
  deliberately avoids).
- No API key is read or stored by any code this milestone introduces.
  Milestone 17 will need to introduce that, behind this project's
  established secret-handling convention (never logged, never in a
  response body, optional until genuinely needed).

## Rejected Alternatives

- **Serialize directly to Anthropic's real Messages API shape as part
  of Prompt Builder or a future invocation runtime, skipping a neutral
  layer.** Rejected: commits every future provider adapter to
  reverse-engineering a provider-neutral contract out of
  Anthropic-shaped code after the fact - the same sequencing mistake
  ADR-0010/0011/0012 already avoided at each earlier layer of this
  pipeline.
- **Give `PromptPackage` Anthropic- or OpenAI-shaped fields.** Rejected
  explicitly by this milestone's own instructions and on the merits -
  it would undo ADR-0012's own decision that `PromptPackage` is
  provider-independent.
- **Introduce the `anthropic` SDK as a dependency now, since Anthropic
  is the intended first adapter anyway.** Rejected: nothing in this
  milestone constructs a client, sends a request, or parses a response
  - there is no code path that would use the dependency, so adding it
  now would be unused, unjustified surface area.
- **A broad "AI capability" port covering invocation, streaming, tool
  use, and multimodal input up front.** Rejected: no current
  requirement demonstrates a need for any of the four, and Milestone 16
  explicitly excludes all of them - the smallest useful interface
  (`prepare_request`/`validate_configuration`/`provider_capabilities`)
  is deliberately all this milestone builds.
- **Automatic provider fallback or cost-based routing.** Rejected: a
  caller that names a specific provider is choosing that provider
  deliberately; silently substituting another would break the
  predictability this abstraction exists to provide, and neither
  capability was ever requested by a real, demonstrated need.
- **A generic, dynamically-loaded plugin architecture for providers**
  (e.g. discovering adapters via entry points or a configurable module
  path). Rejected as overengineering for two adapters (Anthropic, plus
  a test-only fake) - `LLMProviderRegistry` is a small, explicit
  `dict`-backed mapping populated once, at the composition root,
  exactly matching this milestone's own "avoid plugin architecture
  overengineering at this stage" instruction.
