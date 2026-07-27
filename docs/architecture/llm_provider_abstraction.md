# LLM Provider Abstraction Layer

**Status:** As-built reference, Milestone 16 (LLM Provider Abstraction
Layer). Describes the `app/application/**` + `app/infrastructure/llm/**`
capability as implemented - for the decision record (why this is not a
new bounded context, why Anthropic is an adapter and not the platform's
identity, why `PromptPackage` != `LLMRequest` != `AnthropicPreparedRequest`),
see [ADR-0013](adr/0013-llm-provider-abstraction-layer.md). For where
this sits in the wider pipeline, see
[knowledge_pipeline_overview.md](knowledge_pipeline_overview.md) and
[prompt_builder.md](prompt_builder.md).

## Flow

```
PromptPackage
        |
   LLMProviderPort            (app/application/ports/llm_provider_port.py)
        |
   LLMRequest                  (app/application/models/llm_request.py -
        |                       built by prompt_package_to_llm_request_mapper.py)
   Provider Adapter            (app/infrastructure/llm/anthropic/**,
        |                       or app/infrastructure/llm/base/ for tests)
   Provider-native prepared request  (AnthropicPreparedRequest - local,
                                       never an SDK object, never sent)
```

`app/application/services/llm_request_service.py` orchestrates every
stage; nothing under `app/application/**` performs I/O, imports a
provider SDK, or calls Graph Query/Structured Retrieval/Context
Builder/Prompt Builder's own service or router. **This is deliberately
not a new bounded context** under `app/domain/**` - provider selection
and request shaping are an application/infrastructure capability, not
new engineering domain knowledge.

## Provider-neutral request contract

`app/application/models/llm_request.py` defines the shared vocabulary
every provider adapter consumes - never a provider SDK type, never a
provider-native role or payload shape:

- `LLMMessageRole` - `instruction`/`context`/`user`/`assistant`/`tool`.
  Only `INSTRUCTION` and `CONTEXT` are produced by this milestone's
  mapper (no real end-user question or assistant turn exists yet); the
  other three are declared for Milestone 17 (LLM Invocation Runtime).
- `LLMContentType` - `text`/`structured_data`/`reference`. Only `TEXT`
  and `REFERENCE` are produced today; `STRUCTURED_DATA` is reserved.
- `LLMContentBlock`, `LLMMessage`, `LLMGenerationParameters`,
  `LLMProviderSelection`, `LLMModelSelection`,
  `LLMCapabilityRequirements`, `LLMRequestMetadata`, `LLMRequestVersion`,
  `LLMRequest`, `LLMRequestPreparationResult` - see the module
  docstrings for the full contract. All frozen, `slots=True` dataclasses.
- `PreparedProviderRequest` - a `typing.Protocol` (not an ABC) requiring
  only a `provider_id: str` attribute, so each adapter's own local
  dataclass (`AnthropicPreparedRequest`, `FakePreparedRequest`) can
  satisfy it structurally without a shared base class.

## LLMProviderPort

`app/application/ports/llm_provider_port.py` - the smallest useful
interface, deliberately with no `generate`/`invoke` method this
milestone:

```python
class LLMProviderPort(ABC):
    def provider_id(self) -> str: ...
    def provider_capabilities(self) -> LLMProviderCapabilities: ...
    def validate_configuration(self) -> tuple[str, ...]: ...
    def prepare_request(self, request: LLMRequest) -> PreparedProviderRequest: ...
```

`validate_configuration` checks only structural configuration (e.g. a
non-blank model identifier) - never an API key's presence or validity,
since no network call exists to authenticate.

## PromptPackage -> LLMRequest mapping

`app/application/services/prompt_package_to_llm_request_mapper.py` -
deterministic, O(n) in enabled sections/content lines/references:

- Only **enabled** `PromptSection`s become `LLMMessage`s, in the
  package's own canonical order; disabled sections are recorded in
  `LLMRequestMetadata.excluded_section_types`, never silently dropped.
- Fixed role assignment: `SYSTEM_CONTEXT`/`CONSTRAINTS`/
  `FORMATTING_RULES`/`EXPECTED_OUTPUT` -> `INSTRUCTION`;
  `ENGINEERING_CONTEXT`/`SELECTED_KNOWLEDGE`/`EVIDENCE_REFERENCES`/
  `WARNINGS`/`METADATA` -> `CONTEXT`.
- `EVIDENCE_REFERENCES` content becomes `REFERENCE`-typed content
  blocks; every other section becomes `TEXT`.
- `PromptPackage.references`, `project_id`, and every version string
  (`context_builder_version`, `prompt_builder_version`,
  `composition_policy_version`, `prompt_package_version`) are preserved
  onto `LLMRequest`/`LLMRequestMetadata` unchanged.
- `now` and `request_correlation_id` are always caller-supplied
  parameters, never read from the wall clock or generated internally -
  given identical inputs, mapping is byte-for-byte deterministic.

## Anthropic adapter

`app/infrastructure/llm/anthropic/` - the first production-oriented
adapter (Anthropic Claude is this project's intended first deployment
choice, not the platform's architectural identity):

- `anthropic_models.py` - `AnthropicContentBlock`, `AnthropicMessage`,
  `AnthropicPreparedRequest`: local, immutable, never an SDK object.
- `anthropic_mapper.py` - `INSTRUCTION`-role message content is
  concatenated into `AnthropicPreparedRequest.system`; every other
  role's content becomes content blocks on **one synthetic
  `role="user"` message** (Anthropic's Messages API requires at least
  one message, starting with `user`, and today's `PromptPackage` never
  produces a real end-user question or assistant turn - a documented,
  provisional choice Milestone 17 is expected to extend, not redesign).
  Raises `ProviderRequestMappingError` if no conversational content
  exists at all (nothing to populate the required `messages` array).
- `anthropic_adapter.py` - `AnthropicAdapter` declares support for
  `TEXT_INPUT`, `STRUCTURED_TEXT_INPUT`, `CONFIGURABLE_MAX_OUTPUT`,
  `TEMPERATURE`, `STOP_SEQUENCES` - never `STREAMING`/`TOOL_USE`/
  `STRUCTURED_OUTPUT`/`MULTIMODAL_INPUT`, none of which this
  milestone's mapping logic implements. **Imports nothing from the
  `anthropic` package** - no client, no HTTP, no response parsing.

## Fake adapter

`app/infrastructure/llm/base/fake_llm_provider_adapter.py` -
`FakeLLMProviderAdapter`, a deterministic, in-memory adapter used only
by tests. Implements the exact same `LLMProviderPort` contract with a
prepared-request shape (`FakePreparedRequest`) deliberately unrelated
to `AnthropicPreparedRequest`, proving the application layer is
genuinely provider-neutral rather than secretly Anthropic-shaped.
Never registered by the real application router.

## Capability model

`app/application/models/llm_capabilities.py` - `LLMCapability` (a
closed, nine-value enum), `LLMProviderCapabilities` (what one adapter
actually declares), `LLMCapabilityValidationResult` (whether every
*required* capability was satisfied). A missing **required** capability
raises `UnsupportedCapabilityError` - preparation stops outright. An
unsupported but merely **requested/optional** generation parameter
(e.g. `temperature` on a provider that ignores it) becomes a warning on
`LLMRequestPreparationResult.warnings` instead - never a silent
downgrade, never a hard failure.

## Configuration

`app/application/config/llm_configuration.py` - plain `os.getenv`, the
same convention `app/services/ai/claude_provider.py` already
established (no settings framework introduced):

| Variable | Required | Default |
|---|---|---|
| `LLM_PROVIDER` | No | `anthropic` |
| `LLM_MODEL` | No hardcoded fallback | `""` (rejected by validation if still unset when a request is prepared) |
| `LLM_DEFAULT_MAX_OUTPUT_TOKENS` | No | `4096` |
| `LLM_TEMPERATURE` | No | unset (provider's own default applies) |

No API key is read by this module in this milestone - pure request
preparation needs no credential. `LLM_MODEL` has no hardcoded model
name of any kind (no Claude Opus/Sonnet version, no dated identifier);
an unset value is a structurally invalid model selection, rejected
loudly at request-preparation time, never silently patched with a
guessed default.

## Registry and composition root

`app/application/services/llm_provider_registry.py`'s
`LLMProviderRegistry` is a small, explicit `provider_id -> LLMProviderPort`
mapping - `register`/`resolve` only, no business logic, no automatic
fallback. It never imports a concrete adapter itself:
`app/routers/llm_provider.py` is the composition root that constructs
`AnthropicAdapter` from runtime configuration and registers it, per
request (adapters are cheap, stateless, and hold no client or
connection, so per-request construction avoids any global mutable
state).

## Validation and error model

`app/application/services/llm_request_validator.py` validates only
structurally invalid input - project id positivity and project-scope
match against the `PromptPackage`, `PromptPackage` structural validity
(reusing Prompt Builder's own `validate_package`), provider/model
selection presence and structural validity, and generation-parameter
sanity (temperature range, positive max tokens, non-blank stop
sequences). Every problem raises a typed `LLMProviderAbstractionError`
subtype (`app/application/models/llm_exceptions.py`), mapped to
`422 Unprocessable Entity` at the router - no provider SDK exception is
ever raised or wrapped, since no SDK is called.

## Metadata and secret handling

`LLMRequestMetadata` carries `project_id`, every upstream version
string, `provider_id`, `model_identifier`, a per-request
`request_correlation_id`, `excluded_section_types`, and `prepared_at` -
operational metadata only, never engineering knowledge. **No API key,
credential, or environment value ever appears in any request, result,
or API response this milestone produces** - enforced by dedicated
OpenAPI schema tests (`test_llm_provider_schemas_have_no_credential_fields`)
scanning every response schema for a credential-shaped field name.

## API

```
POST /projects/{project_id}/llm/prepare-request
```

`project_id` in the path is authoritative. The body's `prompt_package`
field is exactly the `package` object a prior `/prompt-builder/build`
call returned; `provider_id`/`model_identifier` are optional and fall
back to runtime configuration when omitted. Response: an
`LLMRequestPreparationResultRead` (the neutral request, declared
provider capabilities, capability validation, the prepared
Anthropic-shaped request, and any warnings). **Never calls an LLM** -
this endpoint exists for architecture validation, debugging, frontend
inspection, audit, and future integration testing only.

### Errors

Every `LLMProviderAbstractionError` subtype (unknown provider, missing
provider/model selection, invalid model identifier, invalid generation
parameters, invalid `PromptPackage`, provider mismatch, unsupported
required capability, provider request mapping failure) maps to
`422 Unprocessable Entity`.

## Performance

Request preparation is O(n) in enabled prompt sections, content
blocks, references, and generation parameters - a small, constant
number of linear passes, never a second retrieval and never a database
query. See [performance_baseline.md](performance_baseline.md) for
recorded numbers (`llm_request_mapping`/
`llm_anthropic_request_preparation` operations).

## Future providers

Adding a second provider (OpenAI, a local inference runtime, any
other) requires only: a new `app/infrastructure/llm/<provider>/`
package implementing `LLMProviderPort`, and one new
`registry.register(...)` call in the composition root
(`app/routers/llm_provider.py`) - zero changes to `app/application/**`,
Prompt Builder, or any earlier pipeline stage. The API's
`prepared_request` response schema is currently shaped for Anthropic
specifically (this milestone's only production-registered adapter); a
second provider reaching the real router will need its own
discriminated response shape, a known, documented extension point, not
solved speculatively here.
