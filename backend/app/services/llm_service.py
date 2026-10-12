import time
import httpx
from typing import Optional, Dict, Any
from app.core.config import settings
from app.models.schemas import AdvisoryExplainResponse, ExecutionResponse


class LLMProviderError(Exception):
    pass


def redact_sensitive_strings(text: str) -> str:
    # Redact any keys or tokens
    import re
    cleaned = re.sub(r'(?:sk-[a-zA-Z0-9_-]{20,}|ghp_[a-zA-Z0-9]{30,})', '[REDACTED_SECRET]', text)
    return cleaned


async def generate_advisory_explanation(
    execution: ExecutionResponse,
    prompt_hint: Optional[str] = None,
    client: Optional[httpx.AsyncClient] = None,
) -> AdvisoryExplainResponse:
    """
    Opt-in advisory analysis grounded strictly in actual execution records.
    Deterministic offline mode operates when LLM_API_KEY is not configured.
    """
    start_ts = time.time()
    advisory_notice = "ADVISORY ONLY: Automatically generated analysis grounded in execution output. Inspect actual records before executing remedial operations."

    system_prompt = (
        "You are an AI developer tools advisory agent. Explain the following tool execution failure or output concisely, "
        "highlighting the root cause and concrete next steps. Do not invent facts."
    )
    user_prompt = (
        f"Command: {execution.command}\n"
        f"Exit Code: {execution.exit_code}\n"
        f"Duration: {execution.duration_ms:.1f}ms\n"
        f"Preview:\n{execution.preview_summary}\n"
        f"Operator Hint: {prompt_hint or 'None provided'}"
    )

    # Offline deterministic explanation if no API key is provided
    if not settings.LLM_API_KEY:
        offline_analysis = (
            f"[Offline Advisory Mode] Command '{execution.command}' exited with code {execution.exit_code}. "
            f"Output was sandboxed ({execution.raw_bytes} bytes). "
            f"Review the preview summary or query specific lines using ctx_search."
        )
        latency = (time.time() - start_ts) * 1000.0
        return AdvisoryExplainResponse(
            execution_id=execution.id,
            provider="offline-deterministic",
            model="built-in-heuristics",
            explanation=offline_analysis,
            advisory_notice=advisory_notice,
            latency_ms=round(latency, 2),
        )

    # Server-side provider adapters
    provider = settings.LLM_PROVIDER
    model = settings.LLM_MODEL
    base_url = settings.LLM_BASE_URL.rstrip("/") if settings.LLM_BASE_URL else ""

    http_client = client or httpx.AsyncClient(timeout=30.0)
    should_close = client is None

    try:
        if provider == "openai-compatible":
            url = f"{base_url}/v1/chat/completions" if base_url else "https://api.openai.com/v1/chat/completions"
            headers = {
                "Authorization": f"Bearer {settings.LLM_API_KEY}",
                "Content-Type": "application/json",
            }
            payload = {
                "model": model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                "temperature": 0.2,
            }
            resp = await http_client.post(url, headers=headers, json=payload)
            if resp.status_code != 200:
                raise LLMProviderError(f"OpenAI adapter returned HTTP {resp.status_code}: {redact_sensitive_strings(resp.text)}")
            data = resp.json()
            explanation = data["choices"][0]["message"]["content"]

        elif provider == "anthropic":
            url = f"{base_url}/v1/messages" if base_url else "https://api.anthropic.com/v1/messages"
            headers = {
                "x-api-key": settings.LLM_API_KEY,
                "anthropic-version": "2023-06-01",
                "Content-Type": "application/json",
            }
            payload = {
                "model": model or "claude-3-5-sonnet-20241022",
                "system": system_prompt,
                "messages": [{"role": "user", "content": user_prompt}],
                "max_tokens": 1024,
            }
            resp = await http_client.post(url, headers=headers, json=payload)
            if resp.status_code != 200:
                raise LLMProviderError(f"Anthropic adapter returned HTTP {resp.status_code}: {redact_sensitive_strings(resp.text)}")
            data = resp.json()
            explanation = data["content"][0]["text"]

        elif provider == "gemini":
            target_model = model or "gemini-1.5-flash"
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{target_model}:generateContent?key={settings.LLM_API_KEY}"
            if base_url:
                url = f"{base_url}/v1beta/models/{target_model}:generateContent?key={settings.LLM_API_KEY}"
            headers = {"Content-Type": "application/json"}
            payload = {
                "contents": [{"parts": [{"text": f"{system_prompt}\n\n{user_prompt}"}]}]
            }
            resp = await http_client.post(url, headers=headers, json=payload)
            if resp.status_code != 200:
                raise LLMProviderError(f"Gemini adapter returned HTTP {resp.status_code}: {redact_sensitive_strings(resp.text)}")
            data = resp.json()
            explanation = data["candidates"][0]["content"]["parts"][0]["text"]

        elif provider == "ollama":
            url = f"{base_url}/api/generate" if base_url else "http://127.0.0.1:11434/api/generate"
            payload = {
                "model": model or "llama3",
                "prompt": f"{system_prompt}\n\n{user_prompt}",
                "stream": False,
            }
            resp = await http_client.post(url, json=payload)
            if resp.status_code != 200:
                raise LLMProviderError(f"Ollama adapter returned HTTP {resp.status_code}: {redact_sensitive_strings(resp.text)}")
            data = resp.json()
            explanation = data["response"]
        else:
            raise LLMProviderError(f"Unsupported provider: {provider}")

    except Exception as e:
        if isinstance(e, LLMProviderError):
            raise
        raise LLMProviderError(f"Provider connection error: {redact_sensitive_strings(str(e))}") from e
    finally:
        if should_close:
            await http_client.aclose()

    latency = (time.time() - start_ts) * 1000.0
    return AdvisoryExplainResponse(
        execution_id=execution.id,
        provider=provider,
        model=model,
        explanation=explanation,
        advisory_notice=advisory_notice,
        latency_ms=round(latency, 2),
    )
