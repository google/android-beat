"""The constants for BES devboard."""

import enum

_COMMAND_PREFIX = 'mobly_test:'


@enum.unique
class BESCommand(enum.StrEnum):
  """Serial commands to control BES Device."""

  REBOOT = 'reboot'
  FACTORY_RESET = 'factory_reset'
  GET_DEVICE_INFO = 'get_device_info'
  GET_SERIAL_NUMBER = 'get_wlt_sn'
  SET_NAME = 'set_name'
  SET_ADDRESS = 'set_address'
  SET_FP_MODEL_ID = 'set_model_id'
  SET_FP_PRIVATE_KEY = 'set_gfps_private_key'
  SET_MULTIPOINT = 'set_link_point'

  # TWS preparation
  SET_TWS_ENABLE = 'set_link_tws'
  SET_COMPONENT_NUMBER = 'set_lea_csip'
  TWS_PAIRING = 'tws_pairing'
  GET_BOX_STATE = 'get_box_state'
  OPEN_BOX = 'open_box'
  FETCH_OUT = 'fetch_out'
  WEAR_UP = 'wear_up'
  WEAR_DOWN = 'wear_down'
  PUT_IN = 'put_in'
  CLOSE_BOX = 'close_box'

  # Basic connection
  START_PAIRING_MODE = 'enable_pairing'
  STOP_PAIRING_MODE = 'disable_pairing'
  CONNECT = 'connect'
  DISCONNECT = 'disconnect'
  CLEAR_PAIRED_DEVICES = 'clear_paired_device'
  GET_PAIRED_DEVICES = 'get_paired_device'

  # Battery
  SET_BATTERY_LEVEL = 'set_battery_level'
  GET_BATTERY_LEVEL = 'get_battery_level'

  # Volume
  VOLUME_UP = 'volume_plus'
  VOLUME_DOWN = 'volume_dec'
  GET_VOLUME = 'get_volume'
  SET_VOLUME = 'set_volume'

  # Media
  MEDIA_PLAY = 'media_play'
  MEDIA_PAUSE = 'media_pause'
  MEDIA_NEXT = 'media_next'
  MEDIA_PREV = 'media_prev'

  # Call
  CALL_ACCEPT = 'call_accept'
  CALL_DECLINE = 'call_decline'
  CALL_HOLD = 'call_hold'
  CALL_REDIAL = 'call_redial'

  # ANC
  SET_ANC_MODE = 'set_anc'

  # Spatial Audio
  SET_SPATIAL_AUDIO_ENABLE = 'set_spatial_audio'

  def __str__(self):
    return f'{_COMMAND_PREFIX}{self.value}'


VALID_BLUETOOTH_ADDRESS_LEA = frozenset([
    '11:11:22:33:33:81',
    '11:22:23:33:33:61',
    '11:22:23:33:33:51',
    '11:22:23:33:33:81',
    '11:22:23:33:55:51',
])

VALID_BLUETOOTH_ADDRESS_CLASSIC = frozenset([
    '11:11:22:33:33:51',
    '11:11:22:33:33:72',
    '11:11:22:33:aa:88',
    '11:22:23:31:31:39',
    '11:22:23:31:31:44',
    '11:22:23:31:31:48',
    '11:22:23:31:31:52',
    '11:22:23:31:31:56',
    '11:22:23:33:33:39',
    '11:22:23:33:33:44',
    '11:22:23:33:33:56',
    '11:22:23:33:33:66',
    '11:22:23:33:33:6b',
    '11:22:23:33:33:71',
    '11:22:23:33:33:76',
    '11:22:23:33:33:86',
    '11:22:23:33:33:87',
    '11:22:23:33:33:90',
    '11:22:23:33:33:91',
    '11:22:23:33:33:96',
    '11:22:23:33:33:a5',
    '17:19:24:68:35:82',
    '18:66:66:66:66:16',
    '19:85:12:01:33:81',
    '27:66:66:66:66:25',
    '41:81:52:96:63:e3',
    '58:66:66:66:66:56',
    '83:66:66:66:66:63',
    '84:66:66:66:66:64',
    '85:66:66:66:66:65',
    '86:66:66:66:66:aa',
    '87:66:66:66:66:67',
])

VALID_BLUETOOTH_ADDRESS_ALL = (
    VALID_BLUETOOTH_ADDRESS_LEA | VALID_BLUETOOTH_ADDRESS_CLASSIC
)
