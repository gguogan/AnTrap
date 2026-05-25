# Copyright 2025 The android_world Authors.

"""Tier F -- five more Simple Calendar Pro add-event date variants.

Each constrains target day to a different October 2023 window relative to
the device DT (Sun Oct 15), following the AndroidWorld pattern used by
SimpleCalendarAddOneEventTomorrow / InTwoWeeks.
"""

from android_world.env import device_constants
from android_world.task_evals.single.calendar.calendar import (
    SimpleCalendarAddOneEvent,
)
from android_world.task_evals.single.calendar import events_generator
from android_world.utils import datetime_utils


def _event_on_day(target_day: int):
  return events_generator.generate_event(
      datetime_utils.create_random_october_2023_unix_ts(target_day, target_day)
  )


class SimpleCalendarAddEventInThreeDays(SimpleCalendarAddOneEvent):
  complexity = 3.4
  template = (
      "In Simple Calendar Pro, create a calendar event in three days from"
      " today at {hour}h with the title '{event_title}' and the description"
      " '{event_description}'. The event should last for {duration_mins} mins."
  )

  @classmethod
  def _get_random_target_row(cls):
    return _event_on_day(device_constants.DT.day + 3)


class SimpleCalendarAddEventInFiveDays(SimpleCalendarAddOneEvent):
  complexity = 3.4
  template = (
      "In Simple Calendar Pro, create a calendar event in five days from"
      " today at {hour}h with the title '{event_title}' and the description"
      " '{event_description}'. The event should last for {duration_mins} mins."
  )

  @classmethod
  def _get_random_target_row(cls):
    return _event_on_day(device_constants.DT.day + 5)


class SimpleCalendarAddEventInTenDays(SimpleCalendarAddOneEvent):
  complexity = 3.4
  template = (
      "In Simple Calendar Pro, create a calendar event in ten days from"
      " today at {hour}h with the title '{event_title}' and the description"
      " '{event_description}'. The event should last for {duration_mins} mins."
  )

  @classmethod
  def _get_random_target_row(cls):
    return _event_on_day(device_constants.DT.day + 10)


class SimpleCalendarAddEventOnLastDayOfMonth(SimpleCalendarAddOneEvent):
  complexity = 3.4
  template = (
      "In Simple Calendar Pro, create a calendar event on October 31"
      " at {hour}h with the title '{event_title}' and the description"
      " '{event_description}'. The event should last for {duration_mins} mins."
  )

  @classmethod
  def _get_random_target_row(cls):
    return _event_on_day(31)


class SimpleCalendarAddEventOnHalloween(SimpleCalendarAddOneEvent):
  complexity = 3.4
  template = (
      "In Simple Calendar Pro, create a calendar event for Halloween"
      " (October 31) at {hour}h with the title '{event_title}' and the"
      " description '{event_description}'."
      " The event should last for {duration_mins} mins."
  )

  @classmethod
  def _get_random_target_row(cls):
    return _event_on_day(31)
