"""Chat-completions wrapper for GPT-class models (gpt-5.4 / mini).

Targets ``POST {base_url}/v1/chat/completions`` against OpenAI-compatible
proxies (OpenAI-compat proxy).  Used by the SoM-based Gpt5 agent, which shares the
``llm.predict_mm(text, images)`` surface with AndroidWorld's M3A.

API surface:
    wrapper.predict_mm(text, [np.ndarray, ...])
      -> (content_text: str, is_safe: Optional[bool], raw_response: Any)

    wrapper.chat_completion(messages, tools=None, tool_choice=None)
      -> full response JSON dict (for callers that want to use function
         calls themselves)

Split retry budget (generic transient vs 429/503 capacity) matches
``infer_gemini3``.
"""

import abc
import base64
import io
import os
import time
from typing import Any, Optional

import numpy as np
from PIL import Image
import requests


DEFAULT_ENDPOINT = 'https://api.example.com'
DEFAULT_MODEL = 'gpt-5.4-mini'
ERROR_CALLING_LLM = 'Error calling LLM'


class LlmWrapper(abc.ABC):
    @abc.abstractmethod
    def predict(self, text_prompt: str) -> tuple[str, Optional[bool], Any]:
        ...


class MultimodalLlmWrapper(abc.ABC):
    @abc.abstractmethod
    def predict_mm(
        self, text_prompt: str, images: list[np.ndarray]
    ) -> tuple[str, Optional[bool], Any]:
        ...


def _array_to_jpeg_b64(image: np.ndarray, quality: int = 85) -> str:
    img = Image.fromarray(image)
    buf = io.BytesIO()
    img.save(buf, format='JPEG', quality=quality)
    return base64.b64encode(buf.getvalue()).decode('utf-8')


class Gpt5Wrapper(LlmWrapper, MultimodalLlmWrapper):
    """REST wrapper for OpenAI-compatible ``/v1/chat/completions``."""

    def __init__(
        self,
        api_key: str | None = None,
        model_name: str = DEFAULT_MODEL,
        endpoint: str = DEFAULT_ENDPOINT,
        max_retry: int = 15,
        temperature: float | None = None,
        top_p: float | None = None,
        max_tokens: int | None = 4096,
        timeout: float = 180.0,
        capacity_retry_delay: float = 30.0,
        capacity_max_retry: int = 30,
        image_detail: str = 'high',
    ):
        key = api_key or os.environ.get('OPENAI_API_KEY')
        if not key:
            raise RuntimeError(
                'OpenAI API key not provided. Pass api_key=... or set '
                'OPENAI_API_KEY env var.'
            )
        key = key.strip().strip('"').strip("'")
        if not key or key.startswith('PASTE_') or 'xxxx' in key:
            raise RuntimeError(
                f'OpenAI API key looks like a placeholder: {key[:8]}...  '
                'Fill in a real key in .env or export OPENAI_API_KEY.'
            )
        self.api_key = key
        self.model = model_name
        self.endpoint = endpoint.rstrip('/')
        masked = f'{key[:6]}...{key[-4:]}' if len(key) > 10 else '***'
        print(f'[Gpt5] endpoint={self.endpoint}  model={self.model}  '
              f'key={masked} ({len(key)} chars)')
        self.max_retry = max(1, max_retry)
        self.temperature = temperature
        self.top_p = top_p
        self.max_tokens = max_tokens
        self.timeout = timeout
        self.capacity_retry_delay = capacity_retry_delay
        self.capacity_max_retry = capacity_max_retry
        self.image_detail = image_detail

    def _url(self) -> str:
        return f'{self.endpoint}/v1/chat/completions'

    def _build_payload(
        self,
        messages: list[dict[str, Any]],
        tools: Optional[list[dict[str, Any]]],
        tool_choice: Optional[str | dict],
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            'model': self.model,
            'messages': messages,
        }
        if tools:
            payload['tools'] = tools
            payload['parallel_tool_calls'] = False
            if tool_choice is not None:
                payload['tool_choice'] = tool_choice
        if self.temperature is not None:
            payload['temperature'] = self.temperature
        if self.top_p is not None:
            payload['top_p'] = self.top_p
        if self.max_tokens is not None:
            payload['max_tokens'] = self.max_tokens
        return payload

    def _post(self, payload: dict[str, Any]) -> Optional[dict[str, Any]]:
        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {self.api_key}',
        }
        counter = self.max_retry
        capacity_budget = self.capacity_max_retry
        delay = 2.0
        while counter > 0:
            capacity_retry = False
            try:
                r = requests.post(
                    self._url(), headers=headers, json=payload,
                    timeout=self.timeout,
                )
                if r.ok:
                    return r.json()
                try:
                    err = r.json().get('error', {}).get('message', r.text)
                except Exception:  # pylint: disable=broad-exception-caught
                    err = r.text
                print(f'[Gpt5] HTTP {r.status_code}: {err}')
                if r.status_code in (401, 403):
                    return None
                if r.status_code in (429, 503):
                    capacity_retry = True
            except Exception as e:  # pylint: disable=broad-exception-caught
                print(f'[Gpt5] Request failed: {e}')

            if capacity_retry:
                capacity_budget -= 1
                if capacity_budget <= 0:
                    print(f'[Gpt5] Capacity budget exhausted after '
                          f'{self.capacity_max_retry} tries; giving up.')
                    break
                print(f'[Gpt5] Capacity busy; sleeping '
                      f'{self.capacity_retry_delay:.0f}s '
                      f'({capacity_budget} capacity retries left)')
                time.sleep(self.capacity_retry_delay)
                continue

            counter -= 1
            if counter > 0:
                time.sleep(delay)
                delay = min(delay * 2, 60.0)
        return None

    def chat_completion(
        self,
        messages: list[dict[str, Any]],
        tools: Optional[list[dict[str, Any]]] = None,
        tool_choice: Optional[str | dict] = 'auto',
    ) -> Optional[dict[str, Any]]:
        return self._post(self._build_payload(messages, tools, tool_choice))

    # ------------------------------------------------ M3A-compatible API
    def predict(self, text_prompt: str) -> tuple[str, Optional[bool], Any]:
        return self.predict_mm(text_prompt, [])

    def predict_mm(
        self,
        text_prompt: str,
        images: Optional[list[np.ndarray]] = None,
    ) -> tuple[str, Optional[bool], Any]:
        """Send text + optional images, return M3A-style tuple."""
        images = images or []
        content: list[dict[str, Any]] = [
            {'type': 'text', 'text': text_prompt or ''}
        ]
        for img in images:
            content.append({
                'type': 'image_url',
                'image_url': {
                    'url': f'data:image/jpeg;base64,{_array_to_jpeg_b64(img)}',
                    'detail': self.image_detail,
                },
            })
        messages = [{'role': 'user', 'content': content}]
        data = self._post(self._build_payload(messages, None, None))
        if data is None:
            return ERROR_CALLING_LLM, None, None
        try:
            msg = data['choices'][0]['message']
            finish = data['choices'][0].get('finish_reason')
        except (KeyError, IndexError, TypeError):
            print(f'[Gpt5] Malformed response: {data}')
            return ERROR_CALLING_LLM, None, data
        if finish in ('content_filter', 'safety'):
            return ERROR_CALLING_LLM, False, data
        text = msg.get('content') or ''
        if isinstance(text, list):
            text = ''.join(
                p.get('text', '') for p in text if isinstance(p, dict)
            )
        if not text:
            print(f'[Gpt5] Empty content in response: {data}')
        return text, True, data
