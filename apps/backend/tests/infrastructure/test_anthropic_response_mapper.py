from __future__ import annotations

from anthropic.types import TextBlock, ToolUseBlock

from app.application.models.llm_invocation import (
    LLMFinishReason,
    LLMResponseContentType,
)
from app.infrastructure.llm.anthropic.anthropic_response_mapper import (
    map_content,
    map_finish_reason,
    map_usage,
)
from tests.infrastructure._anthropic_test_support import make_message


def test_text_content_is_mapped_to_text_blocks_in_order():
    message = make_message(
        content=[
            TextBlock(type="text", text="first"),
            TextBlock(type="text", text="second"),
        ]
    )
    content, warnings = map_content(message)

    assert [c.sequence_index for c in content] == [0, 1]
    assert [c.text for c in content] == ["first", "second"]
    assert all(c.content_type is LLMResponseContentType.TEXT for c in content)
    assert warnings == ()


def test_unsupported_content_block_produces_a_warning_not_reinterpreted_text():
    message = make_message(
        content=[
            TextBlock(type="text", text="visible answer"),
            ToolUseBlock(type="tool_use", id="tool_1", name="lookup", input={}),
        ]
    )
    content, warnings = map_content(message)

    assert content[0].content_type is LLMResponseContentType.TEXT
    assert content[1].content_type is LLMResponseContentType.UNSUPPORTED
    assert content[1].text == ""
    assert content[1].provider_block_type == "tool_use"
    assert len(warnings) == 1
    assert "tool_use" in warnings[0]


def test_finish_reason_end_turn_maps_to_completed():
    reason, warnings = map_finish_reason("end_turn")
    assert reason is LLMFinishReason.COMPLETED
    assert warnings == ()


def test_finish_reason_max_tokens_maps_to_maximum_output_reached():
    reason, warnings = map_finish_reason("max_tokens")
    assert reason is LLMFinishReason.MAXIMUM_OUTPUT_REACHED
    assert warnings == ()


def test_finish_reason_stop_sequence_maps_correctly():
    reason, _warnings = map_finish_reason("stop_sequence")
    assert reason is LLMFinishReason.STOP_SEQUENCE


def test_finish_reason_tool_use_maps_to_tool_request():
    reason, _warnings = map_finish_reason("tool_use")
    assert reason is LLMFinishReason.TOOL_REQUEST


def test_finish_reason_refusal_maps_correctly():
    reason, _warnings = map_finish_reason("refusal")
    assert reason is LLMFinishReason.REFUSAL


def test_unrecognized_finish_reason_maps_to_unknown_with_a_warning():
    reason, warnings = map_finish_reason("pause_turn")
    assert reason is LLMFinishReason.UNKNOWN
    assert len(warnings) == 1


def test_missing_finish_reason_maps_to_unknown_with_a_warning():
    reason, warnings = map_finish_reason(None)
    assert reason is LLMFinishReason.UNKNOWN
    assert len(warnings) == 1


def test_usage_is_normalized_with_derived_total():
    message = make_message(input_tokens=12, output_tokens=8)
    usage = map_usage(message)

    assert usage.input_tokens == 12
    assert usage.output_tokens == 8
    assert usage.total_tokens == 20
