from __future__ import annotations

import pytest

from app.domain.project.project_exceptions import (
    InvalidProjectCodeError,
    InvalidProjectNameError,
)
from app.domain.project.project_validator import ProjectValidator


@pytest.mark.parametrize("name", ["", "   ", "\t"])
def test_validate_name_rejects_blank_values(name: str) -> None:
    with pytest.raises(InvalidProjectNameError):
        ProjectValidator.validate_name(name)


def test_validate_name_accepts_a_real_name() -> None:
    ProjectValidator.validate_name("Alpha Substation")


@pytest.mark.parametrize("code", ["", "   ", "\t"])
def test_validate_code_rejects_blank_values(code: str) -> None:
    with pytest.raises(InvalidProjectCodeError):
        ProjectValidator.validate_code(code)


def test_validate_code_accepts_a_real_code() -> None:
    ProjectValidator.validate_code("ALPHA-001")
