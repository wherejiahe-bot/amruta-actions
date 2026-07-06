"""
step2_llm_utils.py — LLM 调用通用工具

- API 封装（urllib POST）
- 重试机制（最多 3 次，指数退避）
- JSON 验证和多层解析
- 并发调用控制（max 8 并发）

与现有 step2_translate.py 中的 llm_sentence_align 调用方式保持一致。
"""

import json
import os
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed

API_URL = "https://apihub.agnes-ai.com/v1/chat/completions"
MODEL = "agnes-2.0-flash"
API_KEY = os.environ.get("AGNES_API_KEY", "") or os.environ.get("AGNES_AI_KEY", "")

MAX_RETRIES = 3
BASE_DELAY = 2
MAX_CONCURRENT = 8


def call_llm_api(messages: list, max_tokens: int = 2048, timeout: int = 60) -> str | None:
    """单次 LLM 调用，返回 response content 或 None。"""
    if not API_KEY:
        print("[llm_utils] AGNES_API_KEY not set")
        return None

    data = json.dumps({
        "model": MODEL,
        "messages": messages,
        "temperature": 0.0,
        "max_tokens": max_tokens,
    }).encode("utf-8")

    req = urllib.request.Request(
        API_URL,
        data=data,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {API_KEY}",
        },
    )

    try:
        resp = urllib.request.urlopen(req, timeout=timeout)
        result = json.loads(resp.read().decode("utf-8"))
        content = result["choices"][0]["message"]["content"].strip()
        return content
    except Exception as e:
        print(f"[llm_utils] API error: {e}")
        return None


def validate_and_parse_json(text: str):
    """
    多层解析 LLM 返回的文本，尝试提取 JSON。

    解析顺序：
    1. 直接解析
    2. 提取 ```json ... ``` 块
    3. 提取 ``` ... ``` 块
    4. 正则提取 [ 开头的 JSON

    返回解析后的对象，失败返回 None。
    """
    if text is None:
        return None

    text = text.strip()
    if not text:
        return None

    # 1. 直接解析
    try:
        return json.loads(text)
    except (json.JSONDecodeError, ValueError):
        pass

    # 2. 提取 ```json ... ```
    if "```json" in text:
        try:
            inner = text.split("```json")[1].split("```")[0].strip()
            return json.loads(inner)
        except (json.JSONDecodeError, ValueError, IndexError):
            pass

    # 3. 提取 ``` ... ```
    if "```" in text:
        try:
            inner = text.split("```")[1].split("```")[0].strip()
            return json.loads(inner)
        except (json.JSONDecodeError, ValueError, IndexError):
            pass

    # 4. 正则提取 [ 或 { 开头的 JSON
    import re
    for pattern in [r'\[.*\]', r'\{.*\}']:
        try:
            match = re.search(pattern, text, re.DOTALL)
            if match:
                return json.loads(match.group())
        except (json.JSONDecodeError, ValueError):
            pass

    print(f"[llm_utils] Failed to parse JSON from: {text[:200]}")
    return None


def call_llm_with_retry(prompt_builder, max_retries: int = MAX_RETRIES,
                         base_delay: float = BASE_DELAY,
                         max_tokens: int = 2048, timeout: int = 60):
    """
    带重试的 LLM 调用包装器。

    Args:
        prompt_builder: callable() -> {"model", "messages", "temperature", "max_tokens"} dict
        max_retries: 最大重试次数
        base_delay: 基础延迟（秒），指数退避 = base_delay * 2^attempt
        max_tokens: 最大 token 数
        timeout: 单次调用超时（秒）

    Returns:
        解析后的 JSON 对象，或 None（全部失败）
    """
    for attempt in range(max_retries):
        try:
            payload = prompt_builder()
            response = call_llm_api(
                payload["messages"],
                max_tokens=payload.get("max_tokens", max_tokens),
                timeout=timeout,
            )
            if response:
                parsed = validate_and_parse_json(response)
                if parsed is not None:
                    return parsed
                print(f"[llm_utils] Invalid JSON on attempt {attempt + 1}")
            else:
                print(f"[llm_utils] Empty response on attempt {attempt + 1}")
        except Exception as e:
            print(f"[llm_utils] Error on attempt {attempt + 1}: {e}")

        if attempt < max_retries - 1:
            delay = base_delay * (2 ** attempt)
            print(f"[llm_utils] Retrying in {delay}s...")
            time.sleep(delay)

    return None


def call_llm_batch(prompts: list, max_tokens: int = 2048,
                   max_concurrent: int = MAX_CONCURRENT,
                   timeout: int = 60) -> list:
    """
    批量并行调用 LLM，返回结果列表（与输入顺序一致）。

    Args:
        prompts: list of callable(), each returns a prompt dict
        max_tokens: max tokens per call
        max_concurrent: 最大并发数
        timeout: 单次调用超时

    Returns:
        list of parsed JSON results (None for failed calls)
    """
    results = [None] * len(prompts)

    with ThreadPoolExecutor(max_workers=max_concurrent) as executor:
        futures = {}
        for i, prompt_builder in enumerate(prompts):
            future = executor.submit(
                call_llm_with_retry,
                prompt_builder,
                max_tokens=max_tokens,
                timeout=timeout,
            )
            futures[future] = i

        for future in as_completed(futures):
            idx = futures[future]
            results[idx] = future.result()

    return results
