"""Extracted mixin for StepFun realtime handler responsibilities."""

from __future__ import annotations

# pyright: reportAttributeAccessIssue=false, reportArgumentType=false, rclass StepFunRealtimeSalesStageMixin:
    async def _ensure_sales_stage_context(self) -> None:
        """Initialize sales-stage capability context once per handler session."""
        if self._sales_stage_context is not None:
            return

        self._sales_stage_context = AgentContext(
            session_id=self.session_id or "",
            agent_id=self._session_agent_id or "unknown-agent",
            persona_id=self._session_persona_id or "unknown-persona",
            user_id=self._session_user_id or "unknown-user",
            state={},
            conversation_history=[],
            agent_config={
                "capabilities_config": {"sales_stage": self._sales_stage_runtime_config}
            },
            persona_config={},
            turn_count=max(0, self.turn_count),
        )
        await self._sales_stage_capability.on_session_start(self._sales_stage_context)

    async def _analyze_and_emit_sales_stage(
        self,
        *,
        user_text: str,
        turn_number: int,
    ) -> str | None:
        """
        Analyze sales stage from user text and emit stage_update only when needed.

        Returns:
            Current stage id for persistence, or None when unavailable.
        """
        normalized_text = user_text.strip()
        if not normalized_text:
            return None

        if not self._sales_stage_enabled:
            return None

        try:
            async with self._sales_stage_lock:
                await self._ensure_sales_stage_context()
                if self._sales_stage_context is None:
                    return None

                self._sales_stage_context.turn_count = max(
                    self._sales_stage_context.turn_count,
                    turn_number,
                )
                result = await self._sales_stage_capability.execute(
                    self._sales_stage_context,
                    normalized_text,
                )
                if not result.success or not isinstance(result.data, dict):
                    return None

                stage_data = result.data
                current_stage = stage_data.get("current_stage")
                if not isinstance(current_stage, str) or not current_stage:
                    return None

                self._latest_stage_data = copy.deepcopy(stage_data)
                stage_changed = bool(stage_data.get("stage_changed", False))
                should_emit = (
                    self._last_emitted_stage is None
                    or stage_changed
                    or current_stage != self._last_emitted_stage
                )
                if should_emit:
                    await self._send_stage_update(stage_data)
                    self._last_emitted_stage = current_stage

                self._append_sales_stage_context_message(
                    role="user",
                    content=normalized_text,
                    turn_number=turn_number,
                )
                return current_stage
        except (RuntimeError, ValueError, KeyError) as exc:
            logger.warning(
                "Sales stage analysis degraded on StepFun path",
                session_id=self.session_id,
                turn_number=turn_number,
                error=str(exc),
            )
            return None

    def _append_sales_stage_context_message(
        self,
        *,
        role: str,
        content: str,
        turn_number: int,
    ) -> None:
        """Append message into sales-stage context history for next-turn analysis."""
        if self._sales_stage_context is None:
            return
        text = content.strip()
        if not text:
            return

        self._sales_stage_context.turn_count = max(
            self._sales_stage_context.turn_count,
            turn_number,
        )
        self._sales_stage_context.add_message(role=role, content=text)

    async def _send_stage_update(self, stage_data: dict[str, Any]) -> None:
        """Send stage update event with unified websocket envelope."""
        await self.manager.send_json(
            self.websocket,
            build_stage_update_event(stage_data=stage_data, trace_id=get_trace_id()),
        )

    async def _update_existing_message_sales_stage(
        self,
        *,
        turn_number: int,
        role: str,
        content: str,
        sales_stage: str | None,
        fuzzy_words: list[dict[str, Any]] | None = None,
        score_snapshot: dict[str, Any] | None = None,
        ai_feedback: str | None = None,
        transcript_metadata: dict[str, Any] | None = None,
        objection_ledger: dict[str, Any] | None = None,
    ) -> None:
        """Patch analysis fields for an already persisted duplicate message."""
        if not self.session_id:
            return

        await patch_existing_message_analysis(
            session_id=self.session_id,
            turn_number=turn_number,
            role=role,
            content=content,
            sales_stage=sales_stage,
            fuzzy_words=fuzzy_words,
            score_snapshot=score_snapshot,
            ai_feedback=ai_feedback,
            transcript_metadata=transcript_metadata,
            objection_ledger=objection_ledger,
            db_lock=self._db_lock,
        )

    async def _persist_message(
        self,
        *,
        turn_number: int,
        role: str,
        content: str,
        sales_stage: str | None = None,
        analysis_data: dict[str, Any] | None = None,
    ) -> None:
        """Persist one conversation message for replay/report consistency."""
        if not self.session_id:
            return

        normalized_payload = normalize_message_persistence_payload(
            turn_number=turn_number,
            content=content,
            sales_stage=sales_stage,
            analysis_data=analysis_data,
        )
        if normalized_payload is None:
            return

        normalized_turn, normalized_content, analysis_payload = normalized_payload
        message_key = (normalized_turn, role, normalized_content)

        if message_key in self._persisted_message_keys:
            if analysis_payload:
                patch_fields = extract_analysis_patch_fields(analysis_payload)
                patch_kwargs: dict[str, Any] = {
                    "turn_number": normalized_turn,
                    "role": role,
                    "content": normalized_content,
                    "sales_stage": patch_fields["sales_stage"],
                    "fuzzy_words": patch_fields["fuzzy_words"],
                    "score_snapshot": patch_fields["score_snapshot"],
                    "ai_feedback": patch_fields["ai_feedback"],
                }
                if patch_fields["transcript_metadata"] is not None:
                    patch_kwargs["transcript_metadata"] = patch_fields[
                        "transcript_metadata"
                    ]
                if patch_fields["objection_ledger"] is not None:
                    patch_kwargs["objection_ledger"] = patch_fields["objection_ledger"]
                await self._update_existing_message_sales_stage(
                    **patch_kwargs,
                )
            return

        self._persisted_message_keys.add(message_key)
        saved = await save_stepfun_message(
            session_id=self.session_id,
            turn_number=normalized_turn,
            role=role,
            content=normalized_content,
            analysis_payload=analysis_payload,
            db_lock=self._db_lock,
        )
        if not saved:
            self._persisted_message_keys.discard(message_key)

    def _resolve_user_turn_number_for_transcript(self) -> int:
        """
        Resolve turn_number for final ASR transcript persistence.

        `transcription.completed` may arrive before or after `_create_response(count_turn=True)`.
        - If response state already exists, `turn_count` has advanced to current turn.
        - Otherwise, transcript belongs to the next turn (`turn_count + 1`).
        """
        if self._active_response is not None:
            return max(1, self.turn_count)
        return max(1, self.turn_count + 1)

    async def _send_transcript(self, text: str, is_final: bool):
        """Send ASR transcript in existing frontend message format."""
        await self.manager.send_json(
            self.websocket,
            build_asr_transcript_event(text=text, is_final=is_final),
        )

    async def _send_status(self, ai_state: str):
        self.ai_state = ai_state
        await self.manager.send_json(
            self.websocket,
            build_status_event(
                session_status=self.session_status,
                ai_state=ai_state,
                turn_count=self.turn_count,
                trace_id=get_trace_id(),
            ),
        )

    async def _send_heartbeat(self):
        await self.manager.send_json(
            self.websocket,
            build_heartbeat_event(),
        )

    async def _send_error(self, code: str, message: str):
        self._record_runtime_error(code, message)
        await self.manager.send_json(
            self.websocket,
            build_error_event(
                code=code,
                message=message,
                session_status=self.session_status,
                ai_state=self.ai_state,
                turn_count=self.turn_count,
                trace_id=get_trace_id(),
            ),
        )

    @staticmethod
    def _extract_text_payload(data: dict) -> str:
        """Extract text payload from websocket data with legacy fallback."""
        return extract_text_payload(data)

    @staticmethod
    def _extract_response_text(response_done_event: dict) -> str:
        """Extract assistant text from response.done payload."""
        return extract_response_text(response_done_event)
