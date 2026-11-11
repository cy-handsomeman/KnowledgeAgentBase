import httpx

from core.settings import settings


class LLMError(Exception):
    pass


def is_llm_configured() -> bool:
    return bool(settings.llm_api_key) and settings.llm_api_key != "replace_me"


def chat_completion(
    messages: list[dict],
    temperature: float = 0.2,
    timeout: float = 60.0,
    json_mode: bool = False,
) -> str:
    if not is_llm_configured():
        raise LLMError("尚未配置大模型 API Key，请在 .env 中填写 LLM_API_KEY")

    url = settings.llm_base_url.rstrip("/") + "/chat/completions"
    payload = {
        "model": settings.llm_model,
        "messages": messages,
        "temperature": temperature,
    }
    if json_mode:
        payload["response_format"] = {"type": "json_object"}

    try:
        response = httpx.post(
            url,
            json=payload,
            headers={"Authorization": f"Bearer {settings.llm_api_key}"},
            timeout=timeout,
        )
    except httpx.HTTPError as error:
        raise LLMError(f"调用大模型失败：{error}") from error

    if response.status_code != 200:
        raise LLMError(f"大模型返回错误：{response.status_code} {response.text[:200]}")

    data = response.json()
    try:
        return data["choices"][0]["message"]["content"]
    except (KeyError, IndexError) as error:
        raise LLMError("大模型返回格式异常") from error
