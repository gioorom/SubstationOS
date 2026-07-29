"""
The fixed policy of evidence evaluation (Milestone 28.2).

Small on purpose: everything here is recorded on a stored report so that
a historical evaluation stays interpretable, and none of it is a knob to
tune per run.
"""

from __future__ import annotations

from app.domain.evidence_evaluation.evaluation_models import (
    ProvenanceMatchPolicy,
)

# The evaluation framework's own version. Bumped when the *comparison*
# changes - a new outcome, a different pairing rule - so a stored report
# says which definition of "match" produced it. It is not the extraction
# policy version, which the report records separately: the same rules can
# be judged by two framework versions, and the same framework can judge
# two rule catalogues.
EVALUATION_FRAMEWORK_VERSION = "1.0"

# Exact, and deliberately not configurable per call site. A coarser
# policy has to be passed explicitly, at the point somebody decided to
# accept it.
DEFAULT_PROVENANCE_POLICY = ProvenanceMatchPolicy.EXACT
