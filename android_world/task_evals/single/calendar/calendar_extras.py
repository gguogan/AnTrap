# Copyright 2025 The android_world Authors.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Tier E -- additional Simple Calendar Pro add-event variants.

These follow the same `_get_random_target_row` override pattern as the
existing `SimpleCalendarAddOneEventTomorrow` and
`SimpleCalendarAddOneEventInTwoWeeks` baseline classes: each constrains
the target date or time window to a new region, which makes the resulting
event row, noise events, and evaluator success surface materially
different from the parent class.
"""

from android_world.env import device_constants
from android_world.task_evals.single.calendar.calendar import (
    SimpleCalendarAddOneEvent,
)
from android_world.task_evals.single.calendar import events_generator
from android_world.utils import datetime_utils


class SimpleCalendarAddEventNextWeek(SimpleCalendarAddOneEvent):
  """Add a calendar event exactly one week (7 days) from today."""

  complexity = 3.4
  template = (
      "In Simple Calendar Pro, create a calendar event for next week"
      " (7 days from today) at {hour}h with the title '{event_title}'"
      " and the description '{event_description}'."
      " The event should last for {duration_mins} mins."
  )

  @classmethod
  def _get_random_target_row(cls):
    target_day = device_constants.DT.day + 7
    return events_generator.generate_event(
        datetime_utils.create_random_october_2023_unix_ts(
            target_day, target_day,
        )
    )


class SimpleCalendarAddEventThisWeekend(SimpleCalendarAddOneEvent):
  """Add a calendar event on this coming Saturday or Sunday."""

  complexity = 3.4
  template = (
      "In Simple Calendar Pro, create a calendar event for this weekend"
      " (Saturday or Sunday) at {hour}h with the title '{event_title}'"
      " and the description '{event_description}'."
      " The event should last for {duration_mins} mins."
  )

  @classmethod
  def _get_random_target_row(cls):
    # Device DT is set to 2023-10-15 (a Sunday). The upcoming weekend is
    # 2023-10-21 (Sat) and 2023-10-22 (Sun) -- one week from the device DT.
    return events_generator.generate_event(
        datetime_utils.create_random_october_2023_unix_ts(21, 22)
    )


class SimpleCalendarAddEventEvening(SimpleCalendarAddOneEvent):
  """Add a calendar event in the evening (hour 18-22)."""

  complexity = 3.4
  template = (
      "In Simple Calendar Pro, create a calendar event on {year}-{month}-{day}"
      " in the evening (after 6pm) at {hour}h with the title"
      " '{event_title}' and the description '{event_description}'."
      " The event should last for {duration_mins} mins."
  )

  @classmethod
  def _get_random_target_row(cls):
    return events_generator.generate_event(
        datetime_utils.create_random_october_2023_unix_ts(
            start_hour=18,
        )
    )
