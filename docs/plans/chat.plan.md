---
name: chat
overview: >
  Chat session lifecycle for AI-assisted recipe refinement. Users create a chat session
  scoped to a recipe, send messages, and the AI replies with optional in-place recipe updates.
  Covers session and message management, history listing, and cleanup.
todos:
  - id: chat-core
    content: >
      Core chat endpoints are implemented:
      POST /chat/recipes/{recipe_id}/chat-sessions (create session),
      GET /chat/chat-sessions/{session_id} (retrieve session with messages),
      POST /chat/chat-sessions/{session_id}/messages (send message → AI reply → optional
      recipe revision). chat_service.send_message() builds history, calls
      AIClientBase.chat_modify(), persists assistant ChatMessage, and applies revised_recipe
      to the Recipe row if returned.
    status: done

  - id: chat-session-list
    content: >
      Add GET /chat/recipes/{recipe_id}/chat-sessions to list all sessions for a recipe,
      ordered by created_at desc. Verify recipe belongs to current_user before querying.
      Return list[ChatSessionRead] (without nested messages — use a ChatSessionSummaryRead
      with id, title, created_at, message_count).
    status: pending
    dependencies:
      - chat-core

  - id: chat-session-delete
    content: >
      Add DELETE /chat/chat-sessions/{session_id}.
      Cascade removes all ChatMessage rows (verify cascade on ChatSession model).
      Does NOT affect the Recipe — deleting a chat history never reverts recipe changes
      that were already applied. Return 204.
    status: pending
    dependencies:
      - chat-core

  - id: chat-message-history
    content: >
      The current GET /chat/chat-sessions/{session_id} returns all messages.
      Add pagination support: query params offset + limit (default 50) so long conversations
      don't return unbounded payloads. Messages are always ordered by created_at asc.
    status: pending
    dependencies:
      - chat-core

  - id: chat-tests
    content: >
      Existing tests in test_chat.py cover create session, get session, and send message.
      Add tests for:
      - GET /chat/recipes/{recipe_id}/chat-sessions (list, empty, 404 cross-user)
      - DELETE /chat/chat-sessions/{session_id} (cascade messages, recipe unchanged)
      - Paginated message history (offset + limit)
      - Send message with revised_recipe: assert Recipe row updated in DB
      - Send message without revised_recipe: assert Recipe row unchanged
    status: pending
    dependencies:
      - chat-session-list
      - chat-session-delete
      - chat-message-history
---

## Conventions

Cross-cutting rules this plan follows (see [_conventions.md](_conventions.md)):
[CONV-AUTH-OWNERSHIP](_conventions.md#conv-auth-ownership),
[CONV-PAGINATION](_conventions.md#conv-pagination),
[CONV-SUMMARY-SCHEMA](_conventions.md#conv-summary-schema),
[CONV-DELETE-CASCADE](_conventions.md#conv-delete-cascade).

Task status is tracked in the `todos:` frontmatter above.

---

## Implementation notes

### Models involved
- `ChatSession` — id, recipe_id, user_id, title, timestamps; cascades to ChatMessage
- `ChatMessage` — id, chat_session_id, role (user/assistant), content, created_at

### Authorization
Follows [CONV-AUTH-OWNERSHIP](_conventions.md#conv-auth-ownership). ChatSession carries both
recipe_id and user_id, so verify `user_id == current_user.id` directly rather than joining
through Recipe.

### Recipe revision behavior
When chat_service applies a revised_recipe, it updates the Recipe row in place (same id).
The chat history remains intact and coherent — messages reference the session, not a recipe
snapshot. Deleting a chat session never reverts recipe changes already applied.

### ChatSessionSummaryRead schema
Per [CONV-SUMMARY-SCHEMA](_conventions.md#conv-summary-schema): fields id, title, created_at,
message_count (derived via len() or subquery). Used for the list endpoint to avoid loading all
messages for each session.

### Message pagination
offset/limit on GET /chat/chat-sessions/{session_id} applies to the messages subquery,
not to sessions. Default limit=50 is generous for most conversations; expose it so clients
can request more if needed.
