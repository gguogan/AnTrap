# Copyright 2025 The android_world Authors.
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

"""Registers the task classes."""

import types
from typing import Any, Final

from android_world.task_evals import task_eval
from android_world.task_evals.composite import markor_sms
from android_world.task_evals.composite import system as system_composite
from android_world.task_evals.information_retrieval import information_retrieval
from android_world.task_evals.information_retrieval import information_retrieval_registry
from android_world.task_evals.miniwob import miniwob_registry
from android_world.task_evals.single import audio_recorder
from android_world.task_evals.single import browser
from android_world.task_evals.single import browser_games
from android_world.task_evals.single import browser_games_extra
from android_world.task_evals.single import camera
from android_world.task_evals.single import clock
from android_world.task_evals.single import contacts
from android_world.task_evals.single import expense
from android_world.task_evals.single import files
from android_world.task_evals.single import files_extras
from android_world.task_evals.single import files_extras_f
from android_world.task_evals.single import markor
from android_world.task_evals.single import markor_extras
from android_world.task_evals.single import markor_extras_f
from android_world.task_evals.single import osmand
from android_world.task_evals.single import recipe
from android_world.task_evals.single import retro_music
from android_world.task_evals.single import simple_draw_pro
from android_world.task_evals.single import simple_gallery_pro
from android_world.task_evals.single import sms
from android_world.task_evals.single import sms_extras
from android_world.task_evals.single import system
from android_world.task_evals.single import system_extras
from android_world.task_evals.single import system_extras_f
from android_world.task_evals.single import vlc
from android_world.task_evals.single.calendar import calendar
from android_world.task_evals.single.calendar import calendar_extras
from android_world.task_evals.single.calendar import calendar_extras_f


def get_information_retrieval_task_path() -> None:
  return None


def get_families() -> list[str]:
  return [
      TaskRegistry.ANDROID_WORLD_FAMILY,
      TaskRegistry.ANDROID_FAMILY,
      TaskRegistry.MINIWOB_FAMILY,
      TaskRegistry.MINIWOB_FAMILY_SUBSET,
      TaskRegistry.INFORMATION_RETRIEVAL_FAMILY,
  ]


class TaskRegistry:
  """Registry of tasks."""

  # The AndroidWorld family.
  ANDROID_WORLD_FAMILY: Final[str] = 'android_world'  # Entire suite.
  ANDROID_FAMILY: Final[str] = 'android'  # Subset.
  INFORMATION_RETRIEVAL_FAMILY: Final[str] = 'information_retrieval'  # Subset.

  # The MiniWoB family.
  MINIWOB_FAMILY: Final[str] = 'miniwob'
  MINIWOB_FAMILY_SUBSET: Final[str] = 'miniwob_subset'

  # Task registries; they contain a mapping from each task name to its class,
  # to construct instances of a task.
  ANDROID_TASK_REGISTRY = {}
  INFORMATION_RETRIEVAL_TASK_REGISTRY = (
      information_retrieval_registry.InformationRetrievalRegistry[
          information_retrieval.InformationRetrieval
      ](filename=get_information_retrieval_task_path()).registry
  )

  MINIWOB_TASK_REGISTRY = miniwob_registry.TASK_REGISTRY

  def get_registry(self, family: str) -> Any:
    """Gets the task registry for the given family.

    Args:
      family: The family.

    Returns:
      Task registry.

    Raises:
      ValueError: If provided family doesn't exist.
    """
    if family == self.ANDROID_WORLD_FAMILY:
      return {
          **self.ANDROID_TASK_REGISTRY,
          **self.INFORMATION_RETRIEVAL_TASK_REGISTRY,
      }
    elif family == self.ANDROID_FAMILY:
      return self.ANDROID_TASK_REGISTRY
    elif family == self.MINIWOB_FAMILY:
      return self.MINIWOB_TASK_REGISTRY
    elif family == self.MINIWOB_FAMILY_SUBSET:
      return miniwob_registry.TASK_REGISTRY_SUBSET
    elif family == self.INFORMATION_RETRIEVAL_FAMILY:
      return self.INFORMATION_RETRIEVAL_TASK_REGISTRY
    else:
      raise ValueError(f'Unsupported family: {family}')

  _TASKS = (
      # keep-sorted start
      audio_recorder.AudioRecorderRecordAudio,
      audio_recorder.AudioRecorderRecordAudioWithFileName,
      browser.BrowserDraw,
      browser.BrowserMaze,
      browser.BrowserMultiply,
      browser_games.BrowserAgreeTerms,
      browser_games.BrowserCheckBoxes,
      browser_games.BrowserClickLargest,
      browser_games.BrowserClickN,
      browser_games.BrowserCopyCode,
      browser_games.BrowserDismissCards,
      browser_games.BrowserDropdown,
      browser_games.BrowserFillName,
      browser_games.BrowserHeartIcon,
      browser_games.BrowserMatchColor,
      browser_games.BrowserOrderClick,
      browser_games.BrowserPickColor,
      browser_games.BrowserPickEven,
      browser_games.BrowserRadioPick,
      browser_games.BrowserResetPassword,
      browser_games.BrowserSearch,
      browser_games.BrowserSlider,
      browser_games.BrowserSum,
      browser_games.BrowserToggleAll,
      browser_games.BrowserUnsubscribe,
      calendar.SimpleCalendarAddOneEvent,
      calendar.SimpleCalendarAddOneEventInTwoWeeks,
      calendar.SimpleCalendarAddOneEventRelativeDay,
      calendar.SimpleCalendarAddOneEventTomorrow,
      calendar.SimpleCalendarAddRepeatingEvent,
      calendar.SimpleCalendarDeleteEvents,
      calendar.SimpleCalendarDeleteEventsOnRelativeDay,
      calendar.SimpleCalendarDeleteOneEvent,
      calendar_extras.SimpleCalendarAddEventEvening,
      calendar_extras.SimpleCalendarAddEventNextWeek,
      calendar_extras.SimpleCalendarAddEventThisWeekend,
      camera.CameraTakePhoto,
      camera.CameraTakeVideo,
      clock.ClockStopWatchPausedVerify,
      clock.ClockStopWatchRunning,
      clock.ClockTimerEntry,
      contacts.ContactsAddContact,
      contacts.ContactsNewContactDraft,
      expense.ExpenseAddMultiple,
      expense.ExpenseAddMultipleFromGallery,
      expense.ExpenseAddMultipleFromMarkor,
      expense.ExpenseAddSingle,
      expense.ExpenseDeleteDuplicates,
      expense.ExpenseDeleteDuplicates2,
      expense.ExpenseDeleteMultiple,
      expense.ExpenseDeleteMultiple2,
      expense.ExpenseDeleteSingle,
      files.FilesDeleteFile,
      files.FilesMoveFile,
      files_extras.FilesCopyFile,
      files_extras.FilesCreateFolder,
      files_extras.FilesDeleteEmptyFolder,
      files_extras.FilesMoveFileToNewFolder,
      files_extras.FilesRenameFile,
      markor.MarkorAddNoteHeader,
      markor.MarkorChangeNoteContent,
      markor.MarkorCreateFolder,
      markor.MarkorCreateNote,
      markor.MarkorCreateNoteFromClipboard,
      markor.MarkorDeleteAllNotes,
      markor.MarkorDeleteNewestNote,
      markor.MarkorDeleteNote,
      markor.MarkorEditNote,
      markor.MarkorMergeNotes,
      markor.MarkorMoveNote,
      markor.MarkorTranscribeReceipt,
      markor.MarkorTranscribeVideo,
      markor_extras.MarkorAddTimestamp,
      markor_extras.MarkorAppendLine,
      markor_extras.MarkorInsertMiddleLine,
      markor_extras.MarkorPrependLine,
      markor_extras.MarkorRemoveLastLine,
      markor_extras.MarkorRenameNote,
      markor_extras.MarkorReplaceWord,
      markor_extras.MarkorWrapInBrackets,
      # Markor composite tasks.
      markor_sms.MarkorCreateNoteAndSms,
      # OsmAnd.
      osmand.OsmAndFavorite,
      osmand.OsmAndMarker,
      osmand.OsmAndTrack,
      recipe.RecipeAddMultipleRecipes,
      recipe.RecipeAddMultipleRecipesFromImage,
      recipe.RecipeAddMultipleRecipesFromMarkor,
      recipe.RecipeAddMultipleRecipesFromMarkor2,
      recipe.RecipeAddSingleRecipe,
      recipe.RecipeDeleteDuplicateRecipes,
      recipe.RecipeDeleteDuplicateRecipes2,
      recipe.RecipeDeleteDuplicateRecipes3,
      recipe.RecipeDeleteMultipleRecipes,
      recipe.RecipeDeleteMultipleRecipesWithConstraint,
      recipe.RecipeDeleteMultipleRecipesWithNoise,
      recipe.RecipeDeleteSingleRecipe,
      recipe.RecipeDeleteSingleWithRecipeWithNoise,
      retro_music.RetroCreatePlaylist,
      retro_music.RetroPlayingQueue,
      retro_music.RetroPlaylistDuration,
      retro_music.RetroSavePlaylist,
      simple_draw_pro.SimpleDrawProCreateDrawing,
      simple_gallery_pro.SaveCopyOfReceiptTaskEval,
      sms.SimpleSmsReply,
      sms.SimpleSmsReplyMostRecent,
      sms.SimpleSmsResend,
      sms.SimpleSmsSend,
      sms.SimpleSmsSendClipboardContent,
      sms.SimpleSmsSendReceivedAddress,
      sms_extras.SimpleSmsSendGreeting,
      sms_extras.SimpleSmsSendQuestion,
      sms_extras.SimpleSmsSendThanks,
      sms_extras.SimpleSmsSendUrgent,
      system.OpenAppTaskEval,
      system.SystemBluetoothTurnOff,
      system.SystemBluetoothTurnOffVerify,
      system.SystemBluetoothTurnOn,
      system.SystemBluetoothTurnOnVerify,
      system.SystemBrightnessMax,
      system.SystemBrightnessMaxVerify,
      system.SystemBrightnessMin,
      system.SystemBrightnessMinVerify,
      system.SystemCopyToClipboard,
      system.SystemWifiTurnOff,
      system.SystemWifiTurnOffVerify,
      system.SystemWifiTurnOn,
      system.SystemWifiTurnOnVerify,
      system_extras.SystemAirplaneTurnOff,
      system_extras.SystemAirplaneTurnOn,
      system_extras.SystemAutoRotateTurnOff,
      system_extras.SystemAutoRotateTurnOn,
      system_extras.SystemDarkModeTurnOff,
      system_extras.SystemDarkModeTurnOn,
      system_extras.SystemLocationTurnOff,
      system_extras.SystemLocationTurnOn,
      system_composite.TurnOffWifiAndTurnOnBluetooth,
      system_composite.TurnOnWifiAndOpenApp,
      # keep-sorted end
      # VLC media player tasks.
      vlc.VlcCreatePlaylist,
      vlc.VlcCreateTwoPlaylists,
      # Phone operations are flaky and the root cause is not known. Disabling
      # until resolution.
      # phone.MarkorCallApartment,
      # phone.PhoneAnswerCall,
      # phone.PhoneCallTextSender,
      # phone.PhoneMakeCall,
      # phone.PhoneRedialNumber,
      # phone.PhoneReturnMissedCall,
      # sms.SimpleSmsSendAfterCall,
      # Tier F variants.
      browser_games_extra.BrowserClick10,
      browser_games_extra.BrowserClick3,
      browser_games_extra.BrowserClick4,
      browser_games_extra.BrowserClick5,
      browser_games_extra.BrowserClick6,
      browser_games_extra.BrowserClick7,
      browser_games_extra.BrowserClick8,
      browser_games_extra.BrowserClick9,
      browser_games_extra.BrowserFillBob,
      browser_games_extra.BrowserFillCharlie,
      browser_games_extra.BrowserFillDiana,
      browser_games_extra.BrowserFillEdward,
      browser_games_extra.BrowserFillFiona,
      browser_games_extra.BrowserFillGrace,
      browser_games_extra.BrowserPickBlue,
      browser_games_extra.BrowserPickGreen,
      browser_games_extra.BrowserPickOrange,
      browser_games_extra.BrowserPickPink,
      browser_games_extra.BrowserPickPurple,
      browser_games_extra.BrowserPickYellow,
      markor_extras_f.MarkorPrependAuthorLine,
      markor_extras_f.MarkorPrependDivider,
      markor_extras_f.MarkorPrependDoneHeader,
      markor_extras_f.MarkorPrependDraftTag,
      markor_extras_f.MarkorPrependTodoHeader,
      markor_extras_f.MarkorReplaceBlackWhite,
      markor_extras_f.MarkorReplaceCatDog,
      markor_extras_f.MarkorReplaceHotCold,
      markor_extras_f.MarkorReplaceLeftRight,
      markor_extras_f.MarkorReplaceLightDark,
      markor_extras_f.MarkorReplaceMonTue,
      markor_extras_f.MarkorReplaceNorthSouth,
      markor_extras_f.MarkorReplaceUpDown,
      markor_extras_f.MarkorReplaceWinSummer,
      markor_extras_f.MarkorReplaceYesNo,
      markor_extras_f.MarkorWrapInAngles,
      markor_extras_f.MarkorWrapInBackticks,
      markor_extras_f.MarkorWrapInDoubleQ,
      markor_extras_f.MarkorWrapInDoubleStars,
      markor_extras_f.MarkorWrapInHash,
      markor_extras_f.MarkorWrapInParens,
      markor_extras_f.MarkorWrapInPipes,
      markor_extras_f.MarkorWrapInStars,
      markor_extras_f.MarkorWrapInTildes,
      markor_extras_f.MarkorWrapInUnderscores,
      files_extras_f.FilesCopyAudioToMusic,
      files_extras_f.FilesCopyDocToDownload,
      files_extras_f.FilesCopyMovieToDcim,
      files_extras_f.FilesCopyMusicToAlarms,
      files_extras_f.FilesCopyPicToDcim,
      files_extras_f.FilesCreate2024Folder,
      files_extras_f.FilesCreateArchiveFolder,
      files_extras_f.FilesCreateProjectsFolder,
      files_extras_f.FilesMoveToNewInDocuments,
      files_extras_f.FilesMoveToNewInMusic,
      files_extras_f.FilesMoveToNewInPictures,
      files_extras_f.FilesRenameInDcim,
      files_extras_f.FilesRenameInDocuments,
      files_extras_f.FilesRenameInDownload,
      files_extras_f.FilesRenameInMusic,
      system_extras_f.SystemAdaptiveBrightnessTurnOff,
      system_extras_f.SystemAdaptiveBrightnessTurnOn,
      system_extras_f.SystemMobileDataTurnOff,
      system_extras_f.SystemMobileDataTurnOn,
      system_extras_f.SystemNfcTurnOff,
      system_extras_f.SystemNfcTurnOn,
      system_extras_f.SystemScreenTimeoutLong,
      system_extras_f.SystemScreenTimeoutShort,
      calendar_extras_f.SimpleCalendarAddEventInFiveDays,
      calendar_extras_f.SimpleCalendarAddEventInTenDays,
      calendar_extras_f.SimpleCalendarAddEventInThreeDays,
      calendar_extras_f.SimpleCalendarAddEventOnHalloween,
      calendar_extras_f.SimpleCalendarAddEventOnLastDayOfMonth,
  )

  def register_task(
      self, task_registry: dict[Any, Any], task_class: type[task_eval.TaskEval]
  ) -> None:
    """Registers the task class.

    Args:
      task_registry: The registry to register the task in.
      task_class: The class to register.
    """
    task_registry[task_class.__name__] = task_class

  def __init__(self):
    for task in self._TASKS:
      self.register_task(self.ANDROID_TASK_REGISTRY, task)

  # Add names with "." notation for autocomplete in Colab.
  names = types.SimpleNamespace(**{
      k: k
      for k in {
          **ANDROID_TASK_REGISTRY,
          **INFORMATION_RETRIEVAL_TASK_REGISTRY,
          **MINIWOB_TASK_REGISTRY,
          **MINIWOB_TASK_REGISTRY,
      }
  })
