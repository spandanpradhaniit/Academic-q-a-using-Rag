import asyncio
import re

from langchain_core.messages import HumanMessage

from app.core.config import get_settings

_PRONOUNS = {
    "it",
    "this",
    "that",
    "these",
    "those",
    "they",
    "them",
    "he",
    "she",
    "their",
    "its",
}


def _is_standalone_question(question: str) -> bool:
    q = (question or "").strip()
    if not q:
        return True
    lowered = q.lower()
    if "..." in lowered or "…" in lowered:
        return False
    if re.match(r"^(what about|how about|tell me more|explain that|explain this|compare it|why is that|how does it|what are its|what are the benefits of this|summarize this|what about the)\b", lowered):
        return False
    has_pronoun = any(re.search(rf"\b{p}\b", lowered) for p in _PRONOUNS)
    if has_pronoun:
        return False
    if re.match(r"^(what|why|how|when|where|who|which|can|could|should|do|does|did|is|are|was|were|explain|describe|summarize|compare|list|tell|show)\b", lowered):
        return True
    return not has_pronoun


def _heuristic_rewrite(question: str, history: list[dict]) -> str:
    q = (question or "").strip()
    if not q:
        return q
    prior_user = [
        str(item.get("content", "")).strip()
        for item in history
        if item.get("sender_type") == "user" and str(item.get("content", "")).strip()
    ]
    if not prior_user:
        return q
    last_user = next(
        (item for item in reversed(prior_user) if _is_standalone_question(item)),
        prior_user[-1],
    )
    if not last_user:
        return q
    # Preserve explicit follow-up wording and add the last standalone subject
    # as context. This avoids dropping the user's original question while
    # preventing the fallback rewriter from inventing a new phrasing.
    has_context_pronoun = any(re.search(rf"\b{p}\b", q.lower()) for p in _PRONOUNS)
    if has_context_pronoun:
        cleaned_topic = last_user.strip().rstrip("?.!")
        return f"{q} (Context: {cleaned_topic})"

    normalized = q.strip().rstrip("?")
    for prefix in ("it", "this", "that", "these", "those", "they", "them"):
        if normalized.lower().startswith(prefix):
            normalized = normalized[len(prefix):].lstrip(" ,:;.-")
            break
    if not normalized:
        return last_user
    if normalized.lower().startswith("more"):
        return f"{last_user} {normalized}"
    if normalized.lower().startswith("about"):
        return f"{last_user} {normalized}"
    if normalized.lower().startswith("the") or normalized.lower().startswith("its"):
        return f"{last_user} {normalized}"
    return f"{last_user} {normalized}"


async def _rewrite_with_llm(question: str, history: list[dict]) -> str:
    settings = get_settings()
    provider = getattr(settings, "llm_provider", "openai")
    model_name = (
        getattr(settings, "llama_model", "openai/gpt-oss-120b")
        if provider == "groq"
        else getattr(settings, "rewrite_model", "gpt-4o-mini")
    )
    timeout = getattr(settings, "rewrite_timeout_seconds", 2)
    messages = []
    for item in history[-6:]:
        role = item.get("sender_type")
        content = str(item.get("content", "")).strip()
        if not content:
            continue
        if role == "user":
            messages.append({"role": "user", "content": content})
        elif role == "assistant":
            messages.append({"role": "assistant", "content": content})
    formatted_history = "\n".join(f"{m['role']}: {m['content']}" for m in messages)
    final_question = (question or "").strip()
    prompt = (
        "You rewrite follow-up questions into standalone questions. "
        "Do NOT answer the question. Keep the subject terms and technical context. "
        "Return only the rewritten question, with no extra text. "
        "If the question is already standalone, return it unchanged.\n\n"
        f"Conversation history:\n{formatted_history}\n\nCurrent question: {final_question}"
    )

    if provider == "groq":
        if not getattr(settings, "groq_api_key", ""):
            raise RuntimeError("GROQ_API_KEY is required for query rewriting")
        from langchain_groq import ChatGroq

        llm = ChatGroq(model=model_name, api_key=settings.groq_api_key, temperature=0, timeout=timeout)
    else:
        if not getattr(settings, "openai_api_key", ""):
            raise RuntimeError("OPENAI_API_KEY is required for query rewriting")
        from langchain_openai import ChatOpenAI

        llm = ChatOpenAI(model=model_name, api_key=settings.openai_api_key, temperature=0, timeout=timeout)

    response = await asyncio.wait_for(llm.ainvoke([HumanMessage(content=prompt)]), timeout=timeout)
    rewritten = str(response.content).strip()
    return rewritten if rewritten else final_question


def rewrite_question(question: str, history: list[dict] | None = None) -> str:
    q = (question or "").strip()
    history = history or []
    if not q:
        return q
    if not history or _is_standalone_question(q):
        return q
    settings = get_settings()
    has_llm_key = (
        getattr(settings, "llm_provider", "openai") == "groq" and bool(getattr(settings, "groq_api_key", ""))
    ) or (
        getattr(settings, "llm_provider", "openai") != "groq" and bool(getattr(settings, "openai_api_key", ""))
    )
    if not has_llm_key:
        return _heuristic_rewrite(q, history)
    try:
        rewritten = asyncio.run(_rewrite_with_llm(q, history))
        fallback = _heuristic_rewrite(q, history)

        # Do not accept an LLM rewrite that drops the original follow-up or
        # loses the standalone subject recovered from conversation history.
        prior_user = [
            str(item.get("content", "")).strip()
            for item in history
            if item.get("sender_type") == "user" and str(item.get("content", "")).strip()
        ]
        if prior_user:
            last_topic = next(
                (item for item in reversed(prior_user) if _is_standalone_question(item)),
                prior_user[-1],
            )
            topic_terms = [term for term in re.findall(r"[A-Za-z0-9-]+", last_topic.lower()) if len(term) >= 4]
            if topic_terms and not all(term in rewritten.lower() for term in topic_terms[:3]):
                return fallback
        return rewritten
    except Exception:
        return _heuristic_rewrite(q, history)
