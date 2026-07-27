"""
Fixed, documented version stamps and the deterministic identity policy
for the Engineering Engine (Milestone 23A) - the same "fixed,
documented policy table" convention every upstream bounded context in
this pipeline establishes.

**Identity policy** (see ADR-0020 on planning determinism):

    WorkflowPlanId  = project_id:conversation_id:turn_id
                      :engineering_intent_id:workflow_id:workflow_version
    WorkflowStepId  = {plan_id}#{ordinal}:{step_type}
    ExecutionId     = exec:{plan_id}

None of these are random. Identical inputs under the same registry and
workflow-definition versions always produce the same plan, step, and
execution identities.
"""

from __future__ import annotations

ENGINE_VERSION = "1.0"
PLAN_POLICY_VERSION = "1.0"
WORKFLOW_REGISTRY_VERSION = "1.0"


def derive_workflow_plan_id(
    *,
    project_id: int,
    conversation_id: str,
    turn_id: str,
    engineering_intent_id: str,
    workflow_id: str,
    workflow_version: str,
) -> str:
    return (
        f"{project_id}:{conversation_id}:{turn_id}:{engineering_intent_id}"
        f":{workflow_id}:{workflow_version}"
    )


def derive_workflow_step_id(
    *, plan_id: str, ordinal: int, step_type: str
) -> str:
    return f"{plan_id}#{ordinal}:{step_type}"


def derive_execution_id(*, plan_id: str) -> str:
    return f"exec:{plan_id}"
