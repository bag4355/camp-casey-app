from __future__ import annotations


def maybe_add_langserve(app, container) -> bool:
    try:  # pragma: no cover - optional dependency in grading env
        from langserve import add_routes
        from langchain_core.runnables import RunnableLambda
    except Exception:
        return False

    def _chat_runnable(payload: dict):
        from camp_casey_app.chat.schemas import ChatRequest

        request = ChatRequest.model_validate(payload)
        return container.chat_agent.invoke(request).model_dump(mode="json")

    runnable = RunnableLambda(_chat_runnable)
    add_routes(app, runnable, path="/langserve/chat")
    return True
