"""
Manual, opt-in-only live smoke test for the LLM Invocation Runtime
(EPIC 4, Milestone 17). Proves that a real Anthropic call actually
works end to end through this codebase's own governed path
(`app.application.services.llm_invocation_service.invoke_llm`) - never
run by `pytest`, never run by CI, never imported by
`app/main.py` or any application startup path. `pytest.ini`'s own
`testpaths = tests` already excludes everything under `scripts/`; this
script additionally requires an explicit, separate opt-in below so it
can never fire by accident even if invoked incorrectly.

Usage (from `apps/backend`, with a real `ANTHROPIC_API_KEY` and
`LLM_MODEL` already exported in the environment):

    LLM_RUNTIME_ENABLED=true python -m scripts.smoke_tests.llm_invocation_smoke_test --confirm

Requires, and fails loudly before any network access if any of the
following is missing:
- ``--confirm`` on the command line (no default, no env-var substitute
  - a human must type it deliberately every time).
- ``LLM_RUNTIME_ENABLED=true`` in the environment.
- ``ANTHROPIC_API_KEY`` set to a real credential.
- ``LLM_MODEL`` set to a real, existing model identifier (this
  codebase never assumes a default Claude model - see
  ``docs/architecture/llm_provider_abstraction.md``).

Sends exactly one synthetic, non-project prompt (an empty
``KnowledgeCandidateCollection`` composed through the real Context
Builder and Prompt Builder, the same construction
``tests/application/test_llm_invocation_service.py`` uses for its own
fake-adapter tests) - no real project data ever leaves the process
through this script. Prints only safe, already-normalized fields
(status, error category, attempt count, latency, response content
length) - never the credential, never an environment dump, never the
full prompt or response text, never a raw SDK object or stack trace.
"""

from __future__ import annotations

import argparse
import asyncio
import random
import sys
import uuid
from datetime import datetime

from app.application.config.llm_configuration import (
    PROVIDER_CREDENTIAL_ENV_VARS,
    load_llm_runtime_configuration_from_env,
    read_provider_credential,
)
from app.application.models.llm_invocation import LLMInvocationStatus
from app.application.services.llm_invocation_service import invoke_llm
from app.application.services.llm_provider_registry import LLMProviderRegistry
from app.domain.structured_retrieval.structured_retrieval_models import (
    KnowledgeCandidateCollection,
)
from app.infrastructure.llm.anthropic.anthropic_adapter import (
    ANTHROPIC_PROVIDER_ID,
    AnthropicAdapter,
)
from app.infrastructure.llm.anthropic.anthropic_client import build_anthropic_client
from app.services import context_builder_service, prompt_builder_service

_SMOKE_TEST_PROJECT_ID = 0


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Manual, opt-in live smoke test for the LLM Invocation "
            "Runtime. Performs one real Anthropic API call."
        )
    )
    parser.add_argument(
        "--confirm",
        action="store_true",
        help=(
            "Required. Confirms you intend to perform a real, "
            "billable Anthropic API call using the credentials and "
            "model currently configured in your environment."
        ),
    )
    return parser.parse_args()


def _synthetic_prompt_package(now: datetime):
    empty_candidates = KnowledgeCandidateCollection(
        candidates=(), total_before_limit=0, returned_count=0, applied_limit=1
    )
    context_result = context_builder_service.build_context_package(
        project_id=_SMOKE_TEST_PROJECT_ID, candidates=empty_candidates, now=now
    )
    prompt_result = prompt_builder_service.build_prompt_package(
        project_id=_SMOKE_TEST_PROJECT_ID,
        context_package=context_result.package,
        now=now,
    )
    return prompt_result.package


async def _run() -> int:
    args = _parse_args()
    if not args.confirm:
        print(
            "Refusing to run: this script performs a real, billable "
            "Anthropic API call. Re-run with --confirm to proceed.",
            file=sys.stderr,
        )
        return 1

    runtime_configuration = load_llm_runtime_configuration_from_env()
    if not runtime_configuration.enabled:
        print(
            "Refusing to run: LLM_RUNTIME_ENABLED is not set to true "
            "in the current environment.",
            file=sys.stderr,
        )
        return 1

    if not runtime_configuration.model_identifier:
        print(
            "Refusing to run: LLM_MODEL is not set. This codebase "
            "never assumes a default Claude model identifier.",
            file=sys.stderr,
        )
        return 1

    provider_id = runtime_configuration.provider_id
    credential = read_provider_credential(provider_id)
    if credential is None:
        env_var_name = PROVIDER_CREDENTIAL_ENV_VARS.get(provider_id, "")
        print(
            f"Refusing to run: no credential configured for provider "
            f"'{provider_id}' (expected environment variable "
            f"'{env_var_name}').",
            file=sys.stderr,
        )
        return 1

    registry = LLMProviderRegistry()
    client = build_anthropic_client(
        api_key=credential,
        connect_timeout_seconds=runtime_configuration.connect_timeout_seconds,
        read_timeout_seconds=runtime_configuration.read_timeout_seconds,
    )
    registry.register(
        ANTHROPIC_PROVIDER_ID,
        AnthropicAdapter(
            model_identifier=runtime_configuration.model_identifier,
            default_max_output_tokens=runtime_configuration.default_max_output_tokens,
            client=client,
        ),
    )

    now = datetime.utcnow()
    prompt_package = _synthetic_prompt_package(now)
    correlation_id = f"smoke-test-{uuid.uuid4()}"

    print(
        f"Invoking provider='{provider_id}' "
        f"model='{runtime_configuration.model_identifier}' "
        f"correlation_id='{correlation_id}' ..."
    )

    result = await invoke_llm(
        registry=registry,
        runtime_configuration=runtime_configuration,
        credential_present=True,
        credential_environment_variable_name=(
            PROVIDER_CREDENTIAL_ENV_VARS.get(provider_id, "")
        ),
        prompt_package=prompt_package,
        project_id=_SMOKE_TEST_PROJECT_ID,
        request_correlation_id=correlation_id,
        clock=lambda: datetime.utcnow(),
        sleeper=asyncio.sleep,
        random_source=random.Random(),
        now=now,
    )

    print(f"status={result.status.value} attempt_count={len(result.attempts)}")

    if result.status is LLMInvocationStatus.SUCCEEDED and result.envelope is not None:
        content_length = sum(
            len(block.text) for block in result.envelope.content
        )
        print(
            f"finish_reason={result.envelope.finish_reason.value} "
            f"latency_seconds={result.envelope.latency_seconds:.3f} "
            f"response_content_blocks={len(result.envelope.content)} "
            f"response_content_length={content_length}"
        )
        print("Live Anthropic invocation verified.")
        return 0

    if result.terminal_error is not None:
        print(
            f"terminal_error_category={result.terminal_error.category.value} "
            f"message={result.terminal_error.message}"
        )
    print("Live invocation did not succeed - see the fields above.")
    return 1


def main() -> int:
    return asyncio.run(_run())


if __name__ == "__main__":
    sys.exit(main())
