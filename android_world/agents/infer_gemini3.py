"""Gemini (v1beta) REST wrapper.

Targets the `/v1beta/models/{model}:generateContent` endpoint exposed by
third-party proxies such as ``https://api.example.com`` that authenticate
with ``Authorization: Bearer sk-...``. API key comes from an explicit arg or
the ``GEMINI_API_KEY`` env var.

Self-contained: does NOT import ``infer`` so it works in environments where
``google.generativeai`` isn't installed.
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
DEFAULT_MODEL = 'gemini-3-pro-preview'
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


def _array_to_jpeg_b64(image: np.ndarray) -> str:
    img = Image.fromarray(image)
    buf = io.BytesIO()
    img.save(buf, format='JPEG')
    return base64.b64encode(buf.getvalue()).decode('utf-8')


def _file_to_jpeg_b64(path: str) -> str:
    img = Image.open(path).convert('RGB')
    buf = io.BytesIO()
    img.save(buf, format='JPEG')
    return base64.b64encode(buf.getvalue()).decode('utf-8')


class Gemini3RestWrapper(LlmWrapper, MultimodalLlmWrapper):
    """Gemini 3 wrapper hitting :generateContent via REST.

    Args:
      api_key: Google AI Studio API key. Falls back to GEMINI_API_KEY env var.
      model_name: Model id to call (default: gemini-3-pro-preview).
      endpoint: Base URL. Default is the public generativelanguage host.
      max_retry: Retries on transient failures.
      temperature: Generation temperature. Keep ~1.0 for Gemini 3 thinking
        models (lower values are discouraged by the model card).
      thinking_level: 'low' | 'medium' | 'high'. 'high' recommended for agents.
      media_resolution: 'media_resolution_low' | '_medium' | '_high'. 'high'
        (~1120 tokens/image) recommended for UI screenshots.
      max_output_tokens: Cap on response length.
      timeout: Per-request timeout in seconds.
    """

    def __init__(
        self,
        api_key: str | None = None,
        model_name: str = DEFAULT_MODEL,
        endpoint: str = DEFAULT_ENDPOINT,
        max_retry: int = 15,
        temperature: float = 1.0,
        thinking_level: str = 'high',
        media_resolution: str = 'media_resolution_high',
        max_output_tokens: int = 4096,
        timeout: float = 120.0,
        capacity_retry_delay: float = 30.0,
        capacity_max_retry: int = 30,
    ):
        key = api_key or os.environ.get('GEMINI_API_KEY')
        if not key:
            raise RuntimeError(
                'Gemini API key not provided. Pass api_key=... or set '
                'GEMINI_API_KEY env var.'
            )
        # Strip stray whitespace/CR (common when pasting into .env on Windows).
        key = key.strip().strip('"').strip("'")
        if not key or key.startswith('PASTE_') or 'xxxx' in key:
            raise RuntimeError(
                f'Gemini API key looks like a placeholder: {key[:8]}...  '
                'Fill in a real key in .env or export GEMINI_API_KEY.'
            )
        self.api_key = key
        self.model = model_name
        self.endpoint = endpoint.rstrip('/')
        masked = f'{key[:6]}...{key[-4:]}' if len(key) > 10 else '***'
        print(f'[Gemini3] endpoint={self.endpoint}  model={self.model}  '
              f'key={masked} ({len(key)} chars)')
        self.max_retry = max(1, max_retry)
        self.temperature = temperature
        self.thinking_level = thinking_level
        self.media_resolution = media_resolution
        self.max_output_tokens = max_output_tokens
        self.timeout = timeout
        self.capacity_retry_delay = capacity_retry_delay
        self.capacity_max_retry = capacity_max_retry

    def _url(self) -> str:
        return f'{self.endpoint}/v1beta/models/{self.model}:generateContent'

    def _gen_cfg(self) -> dict[str, Any]:
        cfg: dict[str, Any] = {
            'temperature': self.temperature,
            'maxOutputTokens': self.max_output_tokens,
        }
        if self.thinking_level:
            cfg['thinkingConfig'] = {'thinkingLevel': self.thinking_level}
        if self.media_resolution:
            cfg['mediaResolution'] = self.media_resolution
        return cfg

    def _build_payload(
        self,
        text_prompt: str,
        images: list[np.ndarray],
    ) -> dict[str, Any]:
        parts: list[dict[str, Any]] = [{'text': text_prompt}]
        for img in images:
            parts.append({
                'inlineData': {
                    'mimeType': 'image/jpeg',
                    'data': _array_to_jpeg_b64(img),
                }
            })
        return {
            'contents': [{'role': 'user', 'parts': parts}],
            'generationConfig': self._gen_cfg(),
        }

    def _build_payload_from_messages(
        self,
        messages: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Convert qwen3vl-style messages to Gemini generateContent payload.

        Input format (identical to what qwen3vl builds):
          [{'role': 'system', 'content': [{'text': ...}]},
           {'role': 'user',   'content': [{'text': ...}, {'image': '/path'}]},
           {'role': 'assistant', 'content': [{'text': ...}]},
           ...]

        Output format (Gemini REST):
          {'systemInstruction': {'parts': [{'text': ...}]},
           'contents': [{'role': 'user'|'model', 'parts': [...]}],
           'generationConfig': ...}
        """
        payload: dict[str, Any] = {'generationConfig': self._gen_cfg()}
        contents: list[dict[str, Any]] = []
        for msg in messages:
            role = msg.get('role', 'user')
            parts: list[dict[str, Any]] = []
            for item in msg.get('content', []) or []:
                if 'text' in item:
                    parts.append({'text': item['text']})
                elif 'image' in item:
                    path = item['image']
                    parts.append({
                        'inlineData': {
                            'mimeType': 'image/jpeg',
                            'data': _file_to_jpeg_b64(path),
                        }
                    })
            if not parts:
                continue
            if role == 'system':
                payload['systemInstruction'] = {'parts': parts}
            else:
                # Gemini uses 'user' and 'model' as the only content roles.
                gemini_role = 'model' if role == 'assistant' else 'user'
                contents.append({'role': gemini_role, 'parts': parts})
        payload['contents'] = contents
        return payload

    @staticmethod
    def _extract_text(resp_json: dict[str, Any]) -> str:
        try:
            parts = resp_json['candidates'][0]['content']['parts']
        except (KeyError, IndexError, TypeError):
            return ''
        out = []
        for p in parts:
            if 'text' in p and p.get('text'):
                out.append(p['text'])
        return ''.join(out)

    @staticmethod
    def _is_safety_block(resp_json: dict[str, Any]) -> bool:
        try:
            return resp_json['candidates'][0].get('finishReason') == 'SAFETY'
        except (KeyError, IndexError, TypeError):
            return False

    def predict(self, text_prompt: str) -> tuple[str, Optional[bool], Any]:
        return self.predict_mm(text_prompt, [])

    def predict_mm(
        self,
        text_prompt: Optional[str],
        images: Optional[list[np.ndarray]] = None,
        messages: Optional[list[dict[str, Any]]] = None,
    ) -> tuple[str, Optional[bool], Any]:
        # Third-party proxies (e.g. api.example.com) authenticate via
        # `Authorization: Bearer sk-...`.
        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {self.api_key}',
        }
        if messages is not None:
            payload = self._build_payload_from_messages(messages)
        else:
            payload = self._build_payload(text_prompt or '', images or [])

        # Two separate retry budgets:
        #  - `counter` covers generic transient failures (network, 5xx non-cap)
        #  - `capacity_budget` covers 429 / 503 "capacity exhausted" which
        #    typically need a longer, flat wait rather than exponential backoff.
        counter = self.max_retry
        capacity_budget = self.capacity_max_retry
        delay = 2.0
        last_resp_json: Any = None
        while counter > 0:
            capacity_retry = False
            try:
                r = requests.post(
                    self._url(), headers=headers, json=payload,
                    timeout=self.timeout,
                )
                if r.ok:
                    data = r.json()
                    last_resp_json = data
                    if self._is_safety_block(data):
                        return ERROR_CALLING_LLM, False, data
                    text = self._extract_text(data)
                    if text:
                        return text, True, data
                    print(f'[Gemini3] Empty text; response: {data}')
                else:
                    try:
                        err = r.json().get('error', {}).get('message', r.text)
                    except Exception:  # pylint: disable=broad-exception-caught
                        err = r.text
                    print(f'[Gemini3] HTTP {r.status_code}: {err}')
                    # 401/403: auth issue — no point retrying
                    if r.status_code in (401, 403):
                        return ERROR_CALLING_LLM, None, None
                    # 429/503: upstream capacity — don't burn the regular budget
                    if r.status_code in (429, 503):
                        capacity_retry = True
            except Exception as e:  # pylint: disable=broad-exception-caught
                print(f'[Gemini3] Request failed: {e}')

            if capacity_retry:
                capacity_budget -= 1
                if capacity_budget <= 0:
                    print(f'[Gemini3] Capacity budget exhausted after '
                          f'{self.capacity_max_retry} tries; giving up.')
                    break
                print(f'[Gemini3] Capacity busy; sleeping '
                      f'{self.capacity_retry_delay:.0f}s '
                      f'({capacity_budget} capacity retries left)')
                time.sleep(self.capacity_retry_delay)
                continue

            counter -= 1
            if counter > 0:
                time.sleep(delay)
                delay = min(delay * 2, 60.0)
        return ERROR_CALLING_LLM, None, last_resp_json
