# Copyright 2025 The android_world Authors.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Tier E -- additional Simple SMS Messenger send tasks.

Each task constrains the body of the message the agent must send: a
greeting, a question (must contain '?'), an urgent prefix, or a thank-you.
The constraint is applied at parameter-generation time so the evaluator
inherits the unchanged `was_sent` check from `SimpleSMSSendSms`.
"""

import random
from typing import Any

from android_world.task_evals.common_validators import sms_validators
from android_world.task_evals.utils import user_data_generation


class SimpleSmsSendGreeting(sms_validators.SimpleSMSSendSms):
  """Send a greeting-style SMS."""

  template = (
      "Send a friendly greeting using Simple SMS Messenger to {number} with"
      " message: {message}"
  )

  _GREETINGS = (
      'Hi there! Hope you are doing well today.',
      'Hello! Long time no see.',
      'Hey, how have you been?',
      'Good morning! Have a wonderful day ahead.',
      'Good evening! How was your day?',
      'Hi! Just thinking of you.',
  )

  @classmethod
  def generate_random_params(cls) -> dict[str, Any]:
    return {
        'number': user_data_generation.generate_random_number(),
        'message': random.choice(cls._GREETINGS),
    }


class SimpleSmsSendQuestion(sms_validators.SimpleSMSSendSms):
  """Send a question to a contact (message ends with '?')."""

  template = (
      "Send a text message using Simple SMS Messenger to {number} asking the"
      " following question: {message}"
  )

  _QUESTIONS = (
      'Are you free for lunch today?',
      'Did you finish the report?',
      'When does the meeting start?',
      'Can you call me back when you have time?',
      'What time should I pick you up?',
      'Have you seen the latest news?',
      'Where are you right now?',
      'Did you get my last message?',
  )

  @classmethod
  def generate_random_params(cls) -> dict[str, Any]:
    return {
        'number': user_data_generation.generate_random_number(),
        'message': random.choice(cls._QUESTIONS),
    }


class SimpleSmsSendUrgent(sms_validators.SimpleSMSSendSms):
  """Send an SMS prefixed with URGENT."""

  template = (
      "Send an urgent text message using Simple SMS Messenger to {number}."
      " The message must begin with the word URGENT followed by: {message}"
  )

  _URGENT_BODIES = (
      'URGENT: Please call back as soon as possible.',
      'URGENT: The meeting has been moved to 2pm today.',
      'URGENT: Your package is waiting at the front desk.',
      'URGENT: We need to reschedule for tomorrow morning.',
      'URGENT: Server is down, please look into it.',
      'URGENT: Flight is delayed, will land at 8pm.',
  )

  @classmethod
  def generate_random_params(cls) -> dict[str, Any]:
    return {
        'number': user_data_generation.generate_random_number(),
        'message': random.choice(cls._URGENT_BODIES),
    }


class SimpleSmsSendThanks(sms_validators.SimpleSMSSendSms):
  """Send a thank-you SMS."""

  template = (
      "Send a thank-you text message using Simple SMS Messenger to {number}"
      " with message: {message}"
  )

  _THANKS = (
      'Thank you so much for your help today!',
      'Thank you for the wonderful dinner last night.',
      'Thanks a lot for picking up the groceries.',
      'Thank you for covering my shift on Friday.',
      'Many thanks for the birthday gift, I love it!',
      'Thanks for sending the documents over so quickly.',
  )

  @classmethod
  def generate_random_params(cls) -> dict[str, Any]:
    return {
        'number': user_data_generation.generate_random_number(),
        'message': random.choice(cls._THANKS),
    }
