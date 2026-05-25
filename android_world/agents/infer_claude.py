"""Claude (Anthropic) REST wrapper supporting two API surfaces.

Two endpoints, picked at construction time:

  api_style='anthropic'  -> POST {endpoint}/v1/messages
                            Headers: x-api-key, anthropic-version
                            Body shape: top-level `system`, `messages` with
                            content blocks {type:"text"|"image"}.

  api_style='openai'     -> POST {endpoint}/v1/chat/completions
                            Headers: Authorization: Bearer
                            Body shape: standard OpenAI messages, images as
                            {type:"image_url", image_url:{url:"data:image/..."}}.

Auto-detection: if the endpoint hostname contains `api.anthropic.com`, mode
defaults to anthropic; otherwise openai (e.g. api.example.com). Override via
constructor kwarg.

Same `predict_mm(text, images, messages=...)` signature as
``Gemini3RestWrapper`` so the agent can be plugged in interchangeably.
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
DEFAULT_MODEL = 'claude-sonnet-4-6'
DEFAULT_ANTHROPIC_VERSION = '2023-06-01'
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


def _array_to_jpeg_b64(image: np.ndarray, quality: int = 90) -> str:
    img = Image.fromarray(image)
    buf = io.BytesIO()
    img.save(buf, format='JPEG', quality=quality)
    return base64.b64encode(buf.getvalue()).decode('utf-8')


def _file_to_jpeg_b64(path: str, quality: int = 90) -> str:
    img = Image.open(path).convert('RGB')
    buf = io.BytesIO()
    img.save(buf, format='JPEG', quality=quality)
    return base64.b64encode(buf.getvalue()).decode('utf-8')


def _detect_api_style(endpoint: str) -> str:
    host = endpoint.lower()
    if 'api.anthropic.com' in host:
        return 'anthropic'
    return 'openai'


class ClaudeRestWrapper(LlmWrapper, MultimodalLlmWrapper):
    """Claude wrapper hitting either /v1/messages or /v1/chat/completions."""

    def __init__(
        self,
        api_key: str | None = None,
        model_name: str = DEFAULT_MODEL,
        endpoint: str = DEFAULT_ENDPOINT,
        api_style: str | None = None,
        anthropic_version: str = DEFAULT_ANTHROPIC_VERSION,
        max_retry: int = 15,
        temperature: float = 1.0,
        max_tokens: int = 4096,
        thinking_budget_tokens: int = 0,
        timeout: float = 120.0,
        capacity_retry_delay: float = 30.0,
        capacity_max_retry: int = 30,
    ):
        key = (
            api_key
            or os.environ.get('CLAUDE_API_KEY')
            or os.environ.get('ANTHROPIC_API_KEY')
        )
        if not key:
            raise RuntimeError(
                'Claude API key not provided. Pass api_key=... or set '
                'CLAUDE_API_KEY / ANTHROPIC_API_KEY env var.'
            )
        key = key.strip().strip('"').strip("'")
        if not key or key.startswith('PASTE_') or 'xxxx' in key:
            raise RuntimeError(
                f'Claude API key looks like a placeholder: {key[:8]}...  '
                'Fill in a real key in .env or export CLAUDE_API_KEY.'
            )
        self.api_key = key
        self.model = model_name
        self.endpoint = endpoint.rstrip('/')
        self.api_style = (api_style or _detect_api_style(self.endpoint)).lower()
        if self.api_style not in ('anthropic', 'openai'):
            raise ValueError(
                f'api_style must be "anthropic" or "openai", got {self.api_style!r}'
            )
        self.anthropic_version = anthropic_version
        masked = f'{key[:6]}...{key[-4:]}' if len(key) > 10 else '***'
        print(f'[Claude] endpoint={self.endpoint}  model={self.model}  '
              f'style={self.api_style}  key={masked} ({len(key)} chars)')
        self.max_retry = max(1, max_retry)
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.thinking_budget_tokens = thinking_budget_tokens
        self.timeout = timeout
        self.capacity_retry_delay = capacity_retry_delay
        self.capacity_max_retry = capacity_max_retry

    # ---------------------------------------------------------------- URLs
    def _url(self) -> str:
        if self.api_style == 'anthropic':
            return f'{self.endpoint}/v1/messages'
        return f'{self.endpoint}/v1/chat/completions'

    def _headers(self) -> dict[str, str]:
        if self.api_style == 'anthropic':
            return {
                'Content-Type': 'application/json',
                'x-api-key': self.api_key,
                'anthropic-version': self.anthropic_version,
            }
        return {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {self.api_key}',
        }

    # ----------------------------------------------------- payload builders
    def _build_payload_anthropic(
        self,
        text_prompt: Optional[str],
        images: list[np.ndarray],
        messages: Optional[list[dict[str, Any]]],
    ) -> dict[str, Any]:
        """Build /v1/messages body.

        Two input modes:
         (A) text + flat image list -> single user turn.
         (B) qwen-vl-style messages list with role + content[{text|image}].
             system role is hoisted to the top-level `system` field.
        """
        payload: dict[str, Any] = {
            'model': self.model,
            'max_tokens': self.max_tokens,
            'temperature': self.temperature,
        }
        if self.thinking_budget_tokens > 0:
            payload['thinking'] = {
                'type': 'enabled',
                'budget_tokens': self.thinking_budget_tokens,
            }

        if messages is None:
            content: list[dict[str, Any]] = [
                {'type': 'text', 'text': text_prompt or ''}
            ]
            for img in images or []:
                content.append({
                    'type': 'image',
                    'source': {
                        'type': 'base64',
                        'media_type': 'image/jpeg',
                        'data': _array_to_jpeg_b64(img),
                    },
                })
            payload['messages'] = [{'role': 'user', 'content': content}]
            return payload

        # Convert qwen-vl-style messages -> anthropic format.
        anthropic_messages: list[dict[str, Any]] = []
        system_text_chunks: list[str] = []
        for msg in messages:
            role = msg.get('role', 'user')
            blocks: list[dict[str, Any]] = []
            for item in msg.get('content', []) or []:
                if 'text' in item:
                    blocks.append({'type': 'text', 'text': item['text']})
                elif 'image' in item:
                    blocks.append({
                        'type': 'image',
                        'source': {
                            'type': 'base64',
                            'media_type': 'image/jpeg',
                            'data': _file_to_jpeg_b64(item['image']),
                        },
                    })
            if not blocks:
                continue
            if role == 'system':
                # Anthropic doesn't allow images in system; flatten text only.
                for b in blocks:
                    if b.get('type') == 'text':
                        system_text_chunks.append(b['text'])
                continue
            api_role = 'assistant' if role == 'assistant' else 'user'
            anthropic_messages.append({'role': api_role, 'content': blocks})

        if system_text_chunks:
            payload['system'] = '\n\n'.join(system_text_chunks)
        payload['messages'] = anthropic_messages
        return payload

    def _build_payload_openai(
        self,
        text_prompt: Optional[str],
        images: list[np.ndarray],
        messages: Optional[list[dict[str, Any]]],
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            'model': self.model,
            'max_tokens': self.max_tokens,
            'temperature': self.temperature,
        }

        if messages is None:
            content: list[dict[str, Any]] = [
                {'type': 'text', 'text': text_prompt or ''}
            ]
            for img in images or []:
                content.append({
                    'type': 'image_url',
                    'image_url': {
                        'url': f'data:image/jpeg;base64,{_array_to_jpeg_b64(img)}',
                    },
                })
            payload['messages'] = [{'role': 'user', 'content': content}]
            return payload

        oa_messages: list[dict[str, Any]] = []
        for msg in messages:
            role = msg.get('role', 'user')
            content_blocks: list[dict[str, Any]] = []
            for item in msg.get('content', []) or []:
                if 'text' in item:
                    content_blocks.append({'type': 'text', 'text': item['text']})
                elif 'image' in item:
                    content_blocks.append({
                        'type': 'image_url',
                        'image_url': {
                            'url': (
                                'data:image/jpeg;base64,'
                                + _file_to_jpeg_b64(item['image'])
                            ),
                        },
                    })
            if not content_blocks:
                continue
            oa_messages.append({'role': role, 'content': content_blocks})
        payload['messages'] = oa_messages
        return payload

    # ----------------------------------------------------- response parsing
    @staticmethod
    def _extract_text_anthropic(data: dict[str, Any]) -> str:
        out = []
        for block in data.get('content', []) or []:
            if block.get('type') == 'text':
                out.append(block.get('text', ''))
        return ''.join(out)

    @staticmethod
    def _extract_text_openai(data: dict[str, Any]) -> str:
        try:
            msg = data['choices'][0]['message']
        except (KeyError, IndexError, TypeError):
            return ''
        text = msg.get('content') or ''
        if isinstance(text, list):
            text = ''.join(
                p.get('text', '') for p in text if isinstance(p, dict)
            )
        return text or ''

    @staticmethod
    def _is_safety_block(data: dict[str, Any], api_style: str) -> bool:
        if api_style == 'anthropic':
            return data.get('stop_reason') in ('refusal',)
        try:
            return data['choices'][0].get('finish_reason') in (
                'content_filter', 'safety',
            )
        except (KeyError, IndexError, TypeError):
            return False

    # --------------------------------------------------------- public APIs
    def predict(self, text_prompt: str) -> tuple[str, Optional[bool], Any]:
        return self.predict_mm(text_prompt, [])

    def predict_mm(
        self,
        text_prompt: Optional[str],
        images: Optional[list[np.ndarray]] = None,
        messages: Optional[list[dict[str, Any]]] = None,
    ) -> tuple[str, Optional[bool], Any]:
        if self.api_style == 'anthropic':
            payload = self._build_payload_anthropic(
                text_prompt, images or [], messages,
            )
        else:
            payload = self._build_payload_openai(
                text_prompt, images or [], messages,
            )

        counter = self.max_retry
        capacity_budget = self.capacity_max_retry
        delay = 2.0
        last_resp_json: Any = None
        while counter > 0:
            capacity_retry = False
            try:
                r = requests.post(
                    self._url(), headers=self._headers(), json=payload,
                    timeout=self.timeout,
                )
                if r.ok:
                    data = r.json()
                    last_resp_json = data
                    if self._is_safety_block(data, self.api_style):
                        return ERROR_CALLING_LLM, False, data
                    if self.api_style == 'anthropic':
                        text = self._extract_text_anthropic(data)
                    else:
                        text = self._extract_text_openai(data)
                    if text:
                        return text, True, data
                    print(f'[Claude] Empty text; response: {data}')
                else:
                    try:
                        body = r.json()
                        err = (
                            body.get('error', {}).get('message')
                            or body.get('detail')
                            or r.text
                        )
                    except Exception:  # pylint: disable=broad-exception-caught
                        err = r.text
                    print(f'[Claude] HTTP {r.status_code}: {err}')
                    if r.status_code in (401, 403):
                        return ERROR_CALLING_LLM, None, None
                    if r.status_code in (429, 503, 529):
                        capacity_retry = True
            except Exception as e:  # pylint: disable=broad-exception-caught
                print(f'[Claude] Request failed: {e}')

            if capacity_retry:
                capacity_budget -= 1
                if capacity_budget <= 0:
                    print(f'[Claude] Capacity budget exhausted after '
                          f'{self.capacity_max_retry} tries; giving up.')
                    break
                print(f'[Claude] Capacity busy; sleeping '
                      f'{self.capacity_retry_delay:.0f}s '
                      f'({capacity_budget} capacity retries left)')
                time.sleep(self.capacity_retry_delay)
                continue

            counter -= 1
            if counter > 0:
                time.sleep(delay)
                delay = min(delay * 2, 60.0)
        return ERROR_CALLING_LLM, None, last_resp_json
