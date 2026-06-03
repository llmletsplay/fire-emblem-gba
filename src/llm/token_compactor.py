"""
Token compaction - extracted from llmdriver.py

Handles progressive reduction of context to stay within token budget.
"""

import logging
import datetime
from collections import deque

from src.core import config
from tools.token_counter import calculate_prompt_tokens

log = logging.getLogger(__name__)


def compact_context_to_budget(
    messages: list,
    chat_hist: list,
    mem_manager,
    chron_manager,
    max_tokens: int = None
) -> tuple:
    """
    Progressively reduce context until under token budget.
    Dropped content is archived to journal for later retrieval.

    Returns:
        tuple: (compacted_messages, compacted_chat_history, thumbnail_count)
    """
    from src.core.llmdriver import MAX_INPUT_TOKENS

    if max_tokens is None:
        max_tokens = MAX_INPUT_TOKENS

    current_tokens = calculate_prompt_tokens(messages)
    thumbnail_count = config.MEMORY_THUMBNAIL_COUNT

    if current_tokens <= max_tokens:
        return messages, chat_hist, thumbnail_count

    log.info(f"Token compaction needed: {current_tokens} > {max_tokens}")
    dropped_content = []

    # Level 1: Batch-drop all oldest non-system chat turns (keep COMPACTION_MIN_CHAT_HISTORY)
    non_system_indices = [i for i, msg in enumerate(chat_hist) if msg.get('role') != 'system']
    drop_count = max(0, len(non_system_indices) - config.COMPACTION_MIN_CHAT_HISTORY)
    if drop_count > 0:
        for idx in sorted(non_system_indices[:drop_count], reverse=True):
            dropped = chat_hist.pop(idx)
            content_preview = str(dropped.get("content", ""))[:config.DROPPED_CONTENT_PREVIEW_LENGTH]
            dropped_content.append({
                "type": "chat_turn",
                "role": dropped.get("role", "unknown"),
                "content": content_preview,
                "timestamp": datetime.datetime.now().isoformat()
            })
        messages = chat_hist + [messages[-1]] if messages else chat_hist
        current_tokens = calculate_prompt_tokens(messages)
        log.info(f"Compaction L1: Dropped {drop_count} chat turns, now at {current_tokens} tokens")

    # Level 2: Reduce memory window
    if current_tokens > max_tokens and mem_manager and len(mem_manager.entries) > config.COMPACTION_MIN_MEMORY_ENTRIES:
        dropped_entries = list(mem_manager.entries)[:-config.COMPACTION_MIN_MEMORY_ENTRIES]
        mem_manager.entries = deque(list(mem_manager.entries)[-config.COMPACTION_MIN_MEMORY_ENTRIES:], maxlen=mem_manager.entries.maxlen)
        for entry in dropped_entries:
            dropped_content.append({
                "type": "memory_entry",
                "turn": entry.turn_id,
                "action": entry.action_taken,
                "result": entry.result,
                "timestamp": entry.timestamp
            })
        log.info(f"Compaction L2: Reduced memory window to {config.COMPACTION_MIN_MEMORY_ENTRIES} entries")

    # Level 3: Reduce thumbnails
    if current_tokens > max_tokens:
        thumbnail_count = config.COMPACTION_REDUCED_THUMBNAILS
        log.info(f"Compaction L3: Reduced thumbnails to {thumbnail_count}")

    # Level 4: Remove thumbnails entirely
    if current_tokens > max_tokens:
        thumbnail_count = 0
        log.info(f"Compaction L4: Removed all thumbnails")

    # Archive dropped content to journal
    if dropped_content and chron_manager:
        chron_manager.archive_dropped_context(dropped_content)
        log.info(f"Archived {len(dropped_content)} dropped items to journal")

    return messages, chat_hist, thumbnail_count