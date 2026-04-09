from __future__ import annotations

import json
from typing import Any

from camp_casey_app.config import Settings

try:  # pragma: no cover - optional dependency in local grading env
    from openai import OpenAI
except Exception:  # pragma: no cover
    OpenAI = None


class OpenAIService:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.client = OpenAI(api_key=settings.openai_api_key) if (OpenAI and settings.openai_api_key) else None

    def is_available(self) -> bool:
        return self.client is not None

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        if not self.client:
            raise RuntimeError("OpenAI client is not configured.")
        response = self.client.embeddings.create(
            model=self.settings.openai_embedding_model,
            input=texts,
        )
        return [[float(value) for value in item.embedding] for item in response.data]

    def complete_text(self, *, system_prompt: str, user_prompt: str) -> str:
        return self.complete_text_with_history(
            system_prompt=system_prompt,
            history=[],
            user_prompt=user_prompt,
        )

    def complete_text_with_history(
        self,
        *,
        system_prompt: str,
        history: list[dict],
        user_prompt: str,
    ) -> str:
        """
        대화 히스토리를 포함하여 텍스트를 생성한다.

        history: [{"role": "user"|"assistant", "content": str}, ...]
        """
        if not self.client:
            raise RuntimeError("OpenAI client is not configured.")

        def _msg(role: str, text: str) -> dict:
            return {"role": role, "content": [{"type": "input_text", "text": text}]}

        messages: list[dict] = [_msg("system", system_prompt)]
        for h in history:
            role = h.get("role", "user")
            content = h.get("content", "")
            if role in ("user", "assistant") and content:
                messages.append(_msg(role, content))
        messages.append(_msg("user", user_prompt))

        response = self.client.responses.create(
            model=self.settings.openai_chat_model,
            input=messages,
        )
        if hasattr(response, "output_text"):
            return response.output_text
        if hasattr(response, "output") and response.output:
            parts = []
            for item in response.output:
                for content in getattr(item, "content", []):
                    text = getattr(content, "text", None)
                    if text:
                        parts.append(text)
            return "\n".join(parts)
        return str(response)

    def complete_json(self, *, system_prompt: str, user_prompt: str) -> dict[str, Any]:
        text = self.complete_text(system_prompt=system_prompt, user_prompt=user_prompt)
        return json.loads(text)
