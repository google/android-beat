# Copyright 2025 Google Inc.
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

"""Utility functions related to Media operations."""

import datetime
import enum
from mobly.controllers import android_device
from android_beat.utils import test_utils

_GET_MEDIA_ROUTER_TYPE_TIMEOUT = datetime.timedelta(seconds=30)


@enum.unique
class VolumeDirection(enum.IntEnum):
  """The direction to adjust the volume.

  https://developer.android.com/reference/android/media/AudioManager#ADJUST_LOWER
  """

  ADJUST_LOWER = -1
  ADJUST_SAME = 0
  ADJUST_RAISE = 1
  ADJUST_MUTE = -100


@enum.unique
class MediaRouterType(enum.IntEnum):
  """Enum class for media device type.

  https://developer.android.com/reference/android/media/MediaRouter.RouteInfo
  """

  DEVICE_TYPE_UNKNOWN = 0
  DEVICE_TYPE_TV = 1
  DEVICE_TYPE_SPEAKER = 2
  DEVICE_TYPE_BLUETOOTH = 3


@enum.unique
class AudioUsage(enum.IntEnum):
  """Audio usage types from android.media.AudioAttributes.

  https://developer.android.com/reference/android/media/AudioAttributes

  Attributes:
    USAGE_MEDIA: Usage value to use when the usage is media, such as music, or
      movie soundtracks.
    USAGE_GAME: Usage value to use when the usage is for game audio.
  """

  USAGE_MEDIA = 1
  USAGE_GAME = 14


@enum.unique
class AudioContentType(enum.IntEnum):
  """Audio content types from android.media.AudioAttributes.

  https://developer.android.com/reference/android/media/AudioAttributes

  Attributes:
    CONTENT_TYPE_UNKNOWN: Content type value to use when the content type is
      unknown, or other than the ones defined.
    CONTENT_TYPE_MUSIC: Content type value to use when the content type is
      music.
    CONTENT_TYPE_MOVIE: Content type value to use when the content type is the
      audio typically accompanying a movie or TV program, containing a mix of
      dialogue, music and sound effects.
  """

  CONTENT_TYPE_UNKNOWN = 0
  CONTENT_TYPE_MUSIC = 2
  CONTENT_TYPE_MOVIE = 3


def get_media_router_type(ad: android_device.AndroidDevice) -> MediaRouterType:
  """Gets the specified media router type of device."""
  return MediaRouterType(ad.bt_snippet.mediaGetLiveAudioRouteType())


def wait_for_expected_media_router_type(
    ad: android_device.AndroidDevice,
    expected_media_router_type: MediaRouterType,
    postfix_error_msg: str | None = None,
    timeout: datetime.timedelta = _GET_MEDIA_ROUTER_TYPE_TIMEOUT,
) -> None:
  """Waits for media router type to be active or inactive."""
  test_utils.wait_until_or_assert(
      condition=lambda: get_media_router_type(ad) == expected_media_router_type,
      error_msg=(
          'Failed to get expected media router type'
          f' {expected_media_router_type}, actual type is'
          f' {get_media_router_type(ad)} {postfix_error_msg}'
      ),
      timeout=timeout,
  )
