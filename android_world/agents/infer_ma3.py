# Copyright 2024 The android_world Authors.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Some LLM inference interface."""

import abc
import time
from typing import Any, Optional
import numpy as np
from PIL import Image
from openai import OpenAI
from io import BytesIO
import base64

ERROR_CALLING_LLM = 'Error calling LLM'

def pil_to_base64(image):
    buffer = BytesIO()
    image.save(buffer, format="PNG") 
    return base64.b64encode(buffer.getvalue()).decode("utf-8")

def image_to_base64(image_path):
  """Convert image to base64 with smart_resize (matching original MobileAgent v3).

  Uses the same max_pixels=10035200 as update_image_size_ / fetch_resized_image
  so that the image sent to the model matches the prompt resolution.
  The vLLM server's --mm-processor-kwargs must also use max_pixels=10035200.
  """
  from android_world.agents.coordinate_resize import smart_resize
  dummy_image = Image.open(image_path)
  MIN_PIXELS = 3136
  MAX_PIXELS = 10035200
  resized_height, resized_width = smart_resize(
      dummy_image.height, dummy_image.width,
      factor=28, min_pixels=MIN_PIXELS, max_pixels=MAX_PIXELS)
  dummy_image = dummy_image.resize((resized_width, resized_height))
  return f"data:image/png;base64,{pil_to_base64(dummy_image)}"

class LlmWrapper(abc.ABC):
  """Abstract interface for (text only) LLM."""

  @abc.abstractmethod
  def predict(
      self,
      text_prompt: str,
  ) -> tuple[str, Optional[bool], Any]:
    """Calling multimodal LLM with a prompt and a list of images.

    Args:
      text_prompt: Text prompt.

    Returns:
      Text output, is_safe, and raw output.
    """

class MultimodalLlmWrapper(abc.ABC):
  """Abstract interface for Multimodal LLM."""

  @abc.abstractmethod
  def predict_mm(
      self, text_prompt: str, images: list[np.ndarray], messages = None
  ) -> tuple[str, Optional[bool], Any]:
    """Calling multimodal LLM with a prompt and a list of images.

    Args:
      text_prompt: Text prompt.
      images: List of images as numpy ndarray.

    Returns:
      Text output and raw output.
    """

class GUIOwlWrapper(LlmWrapper, MultimodalLlmWrapper):

    RETRY_WAITING_SECONDS = 20

    def __init__(
            self,
            api_key: str,
            base_url: str,
            model_name: str,
            max_retry: int = 10,
            temperature: float = None,
            top_p: float = None,
            top_k: int = None,
            max_tokens: int = None,
            presence_penalty: float = None,
    ):
        if max_retry <= 0:
            max_retry = 10
            print('Max_retry must be positive. Reset it to 3')
        self.max_retry = min(max_retry, 10)
        self.temperature = temperature
        self.top_p = top_p
        self.top_k = top_k
        self.max_tokens = max_tokens
        self.presence_penalty = presence_penalty
        self.model = model_name
        urls = [u.strip() for u in base_url.split(",")]
        self._bots = [OpenAI(api_key=api_key, base_url=u, timeout=60) for u in urls]
        self._bot_idx = 0

    @property
    def bot(self):
        b = self._bots[self._bot_idx % len(self._bots)]
        self._bot_idx += 1
        return b

    def convert_messages_format_to_openaiurl(self, messages):
      converted_messages = []
      for message in messages:
          new_content = []
          for item in message['content']:
              if list(item.keys())[0] == 'text':
                  new_content.append({'type': 'text', 'text': item['text']})
              elif list(item.keys())[0] == 'image':
                new_content.append({'type': 'image_url', 'image_url': {'url': image_to_base64(item['image'])}})
          converted_messages.append({'role': message['role'], 'content': new_content})

      return converted_messages
    
    def predict(
            self,
            text_prompt: str,
    ) -> tuple[str, Optional[bool], Any]:
        return self.predict_mm(text_prompt, [])

    def predict_mm(
            self, text_prompt: str, images: list[np.ndarray], messages = None
    ) -> tuple[str, Optional[bool], Any]:
        
        if messages is None:
          payload = [
              {
                  "role": "user",
                  "content": [
                      {"text": text_prompt},
                  ]
              }
          ]
          
          for image in images:
            payload[0]['content'].append({
                'image': image
            })
        else:
          payload = messages
            
        payload = self.convert_messages_format_to_openaiurl(payload)

        counter = self.max_retry
        wait_seconds = self.RETRY_WAITING_SECONDS
        while counter > 0:
            try:
              # Build kwargs: only include parameters that are explicitly set (not None).
              # This lets each model use its own defaults — GUI-Owl passes nothing,
              # Qwen3-VL-Thinking passes temperature=1.0/top_p=0.95/etc.
              kwargs = {}
              if self.temperature is not None:
                  kwargs['temperature'] = self.temperature
              if self.top_p is not None:
                  kwargs['top_p'] = self.top_p
              if self.max_tokens is not None:
                  kwargs['max_tokens'] = self.max_tokens
              if self.presence_penalty is not None:
                  kwargs['presence_penalty'] = self.presence_penalty
              extra_body = {}
              if self.top_k is not None:
                  extra_body['top_k'] = self.top_k
              if extra_body:
                  kwargs['extra_body'] = extra_body
              chat_completion_from_url = self.bot.chat.completions.create(
                  model=self.model, messages=payload, **kwargs
              )
              return (chat_completion_from_url.choices[0].message.content, payload, chat_completion_from_url)
            except Exception as e:
                time.sleep(wait_seconds)
                wait_seconds *= 1
                counter -= 1
                print('Error calling LLM, will retry soon...')
                print(e)
        return ERROR_CALLING_LLM, None, None
