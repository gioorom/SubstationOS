"""
The fixed, documented version stamps for Conversation (Milestone 20) -
the same "fixed, documented policy table" convention every upstream
bounded context in this pipeline establishes. Bump the relevant
``*_VERSION`` constant whenever the state machines or timeline event
vocabulary change, so ``ConversationMetadata``/``ConversationVersion``
can record which policy produced a given ``Conversation``.
"""

from __future__ import annotations

CONVERSATION_VERSION = "1.0"
CONVERSATION_POLICY_VERSION = "1.0"
CONVERSATION_PACKAGE_VERSION = "1.0"
