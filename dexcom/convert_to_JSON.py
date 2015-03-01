# Copyright (c) 2014, Jana E. Beck
# Contact: jana.eliz.beck@gmail.com
# License: GPLv3 (http://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import print_function
# because raw_input got renamed in Python 3.something
try:
  input = raw_input
except NameError:
  pass

import csv
from datetime import datetime as dt, timedelta as td, tzinfo
import json
from pytz import timezone as tz, UnknownTimeZoneError
import pytz
import uuid

DEX_FORMAT = '%Y-%m-%d %H:%M:%S'

SECONDS_IN_HOUR = 3600

GLUCOSE_MOLAR_MASS = 18.01559

class DexcomTZ(tzinfo):

  def __init__(self, offset):
    self.__offset = td(hours=offset)

  def utcoffset(self, dt):
    return self.__offset

def datetime_difference(d1, d2):
  """Return the difference between two datetimes."""

  return d2 - d1

def enlighten_datetime(obj):
  """Make a Dexcom object timezone-aware on its `time` attribute."""

  obj.time = parse_datetime(obj.user_time).replace(tzinfo=DexcomTZ(obj.display_offset)).isoformat()

def parse_datetime(dt_str):
  """Parse a Dexcom time and date string into a datetime object."""

  try:
    return dt.strptime(dt_str, DEX_FORMAT)
  except ValueError:
    # gen 'SevenPlus' date and time info includes milliseconds
    # so we truncate to index -4
    return dt.strptime(dt_str[:-4], DEX_FORMAT)

class Dexcom:
  # NB: despite what one might think, this doesn't actually want to be a general CGM data model
  # because it's specific to Dexcom's date and time info
  """iPancreas Dexcom data model."""

  def __init__(self, dct):

    self.user_time = dct['user']
    self.internal_time = dct['internal']
    self.device_gen = dct['generation']
    self.serial = dct['serial']
    self.value = self._set_value(dct['value'])
    self.type = 'bg'

    # set by enlighten_datetime, if bloodhound protocol succeeds
    self.time = ''

  def _set_value(self, value):
    """Return the integer value for each possible Dexcom sensor reading."""
    try:
      value = int(value)
      # calibrations can go below 40 and over 400
      if value >= 20 and value <= 600:
        self.annotations = None
        return value
      else:
        raise Exception('Dexcom value out of range:', value)
    except ValueError:
      if value == 'Low':
        self.annotations = [{
          'code': 'bg/out-of-range',
          'threshold': 40,
          'value': 'low'
        }]
        return 39
      elif value == 'High':
        self.annotations = [{
          'code': 'bg/out-of-range',
          'threshold': 400,
          'value': 'high'
        }]
        return 401

  def _convert_mgdl_to_mmoll(self, value):
    """Convert a blood glucose value given in mg/dL to mmol/L."""

    return float(value/GLUCOSE_MOLAR_MASS)

  def as_tidepool(self):
    """Return a dict of the object conforming to Tidepool's data model."""

    tidepool_obj = {
        'deviceId': self.device_gen + '-=-' + self.serial,
        'deviceTime': parse_datetime(self.user_time).strftime('%Y-%m-%dT%H:%M:%S'),
        'deviceValue': str(self.value),
        'id': str(uuid.uuid4()),
        'source': 'dexcom',
        'time': self.time,
        'units': 'mg/dL',
        'value': self._convert_mgdl_to_mmoll(self.value)
      }
    if self.subtype == 'sensor':
      tidepool_obj['type'] = 'cbg'
    elif self.subtype == 'calibration':
      tidepool_obj['type'] = 'deviceMeta'
      tidepool_obj['subType'] = 'calibration'
    if self.annotations != None:
      tidepool_obj['annotations'] = self.annotations

    return tidepool_obj

class DexcomSensor(Dexcom):
  """iPancreas Dexcom data model for sensor readings."""

  def __init__(self, dct):

    Dexcom.__init__(self, dct)
    self.subtype = 'sensor'

class DexcomCalibration(Dexcom):
  # TODO: at a later date this will probably need to inherit from a SMBG data model object as well
  """iPancreas Dexcom data model for sensor readings."""

  def __init__(self, dct):

    Dexcom.__init__(self, dct)
    self.subtype = 'calibration'

class DexcomJSON:
  """Convert input 'terse' CSV to JSON."""

  def __init__(self, csv_file, output_opts):
    """Parse input CSV file into appropriate Dexcom objects."""

    self.output = output_opts

    reader = csv.reader(csv_file)
    # skip the header
    next(reader)
    self.all = []
    for row in reader:
      self.all += self._parse_row(row)

    # make sure all is sorted!
    self.all.sort(key=lambda x: x.internal_time, reverse=True)

    self.offsets = {'SevenPlus': 0}

    try:
      with open(output_opts['bloodhound'], 'rU') as f:
        changes = json.load(f)
        dated_changes = []
        for change in changes:
          if change['effective_at']['internal_time'] != '':
            dated_changes.append(change)
        self.offset_changes = dated_changes
    except (FileNotFoundError, KeyError, ValueError):
      self.offset_changes = []

  def sensors(self):
    """Return all and only sensor readings."""

    return [i for i in self.all if i.subtype == 'sensor']

  def calibrations(self):
    """Return all and only calibration readings."""

    return [i for i in self.all if i.subtype == 'calibration']

  def _add_offset_change(self, diff_in_hours, obj, change_type, notstart = False):
    """Add a timezone change to the list."""

    tz_res = self._get_timezone(obj, change_type)
    offset = tz_res['offset']
    timezone = tz_res['timezone']
    if tz_res['offset'] is None:
      return

    if notstart:
      self.offset_changes.append({
        'display_offset': offset,
        # timestamp of last (most recent) datum to which this offset is to be applied
        'effective_at': {
          'internal_time': parse_datetime(obj.internal_time).isoformat(),
          'display_time': parse_datetime(obj.user_time).isoformat()
        },
        'reason': tz_res['type'],
        'subtype': 'timezone offset',
        'timezone': timezone,
        'type': 'meta'
      })

    return (offset, timezone)

  def _get_offset_change(self, effective_at):
    """Retrieve the correct offset change from the internal time effective at."""

    for change in self.offset_changes:
      if change['effective_at']['internal_time'] == parse_datetime(effective_at).isoformat():
        return change

  def _get_timezone(self, obj, change_type):
    """Ask the user to input an offset for a particular Dexcom G4 Platinum CGM device."""

    res = input('What timezone were you in at %s? ' %(obj.user_time))
    dst = input('Do you think this was a shift to/from DST? (y/n) ')
    td_offset = tz(res).utcoffset(parse_datetime(obj.user_time))
    offset = td_offset.days * 24 + td_offset.seconds/SECONDS_IN_HOUR
    timezone = res
    if dst == 'y':
      change_type += '; shift to/from DST'
      # fall back is -1; reverse it to undo change
      if parse_datetime(obj.user_time).month > 6:
        offset += 1
      # spring forward is +1; reverse it to undo change
      else:
        offset -= 1

    print('Offset from UTC is %d.' %offset)
    print()
    return {
      'timezone': timezone,
      'offset': offset,
      'type': change_type
    }

  def _parse_row(self, row):
    """Parse a CSV row into DexcomSensor and DexcomCalibration readings as appropriate."""

    # all rows should have a device generation
    try:
      gen = row[6]
    except IndexError:
      gen = ''

    # and a serial
    try:
      serial = row[7]
    except IndexError:
      serial = ''

    # but definitely a sensor reading
    sensor = self._parse_sensor(row)
    sensor['generation'] = gen
    sensor['serial'] = serial

    objs = [DexcomSensor(sensor)]

    # check first if calibration before trying to create one
    if row[3] != '':
      objs.append(DexcomCalibration({
        'generation': gen,
        'serial': serial,
        'internal': row[3],
        'user': row[4],
        'value': row[5]
      }))

    return objs

  def _parse_sensor(self, row):
    """Parse just the first three columns of a Dexcom CSV row as a sensor reading."""

    return {
      'user': row[1],
      'internal': row[0],
      'value': row[2]
    }

  def bloodhound(self, tz_str):
    """Sniff out changes to Dexcom time and date settings."""

    initial_difference = ''

    effective_ats = [offset['effective_at']['internal_time'] for offset in self.offset_changes]
    current_effective_at = ''

    for obj in self.all:
      if parse_datetime(obj.internal_time).isoformat() in effective_ats:
        current_effective_at = obj.internal_time
        change = self._get_offset_change(obj.internal_time)
        offsets = (change['display_offset'], change['timezone'])
      elif obj.internal_time < current_effective_at:
        change = self._get_offset_change(current_effective_at)
        offsets = (change['display_offset'], change['timezone'])
      else:
        user_time = parse_datetime(obj.user_time)
        internal_time = parse_datetime(obj.internal_time)

        diff = {'timedelta': datetime_difference(user_time, internal_time)}

        diff['hours'] = round(-diff['timedelta'].seconds/SECONDS_IN_HOUR)

        # bootstrap from most recent data known timezone and difference to internal timestamp offset from UTC
        if not initial_difference:
          offsets = self._add_offset_change(diff['hours'], obj, 'input by user')
          initial_difference = diff
          current_difference = initial_difference
        # offset from UTC of internal timestamps isn't consistent across G4 receivers
        elif obj.serial != last_obj.serial and obj.device_gen == 'G4Platinum':
          offsets = self._add_offset_change(diff['hours'], obj, 'changed G4 Platinum device', True)
          current_difference = diff
        # offset from UTC of internal timestamps isn't consistent across device generations
        elif obj.device_gen != last_obj.device_gen:
          offsets = self._add_offset_change(diff['hours'], obj, 'changed to Seven Plus device', True)
          current_difference = diff
        # and sometimes the user actually changed the device's settings
        # fancy that!
        elif diff['hours'] != current_difference['hours']:
          offsets = self._add_offset_change(diff['hours'], obj, 'inferred via bloodhound protocol', True)
          current_difference = diff

      # add offsets to Dexcom object
      if offsets:
        obj.display_offset = offsets[0]
        obj.timezone = offsets[1]
        # make each Dexcom object timezone-aware
        enlighten_datetime(obj)

      last_obj = obj

    with open('bloodhound.log', 'w') as f:
      [print(self._printable_timezone_change(change), file=f) for change in self.offset_changes]

    with open('bloodhound.json', 'w') as f:
      sorted_changes = sorted(self.offset_changes, key=lambda x: x['effective_at']['internal_time'])
      sorted_changes.reverse()
      print(json.dumps(sorted_changes, indent=2, separators=(',', ': '), sort_keys=True), file=f)

    return self

  def _printable_timezone_change(self, change):
    """Return a multiline string reflecting a timezone change in human-readable format for printing."""

    return """Offset effective at internal time %s, display time %s:
\tDisplay offset from UTC = %d
\tTimezone = %s
\tType of change = %s\n""" %('(most recent)' if not change['effective_at']['internal_time'] else change['effective_at']['internal_time'],
  change['effective_at']['display_time'], change['display_offset'], change['timezone'], change['reason'])

  def print_JSON(self):
    """Print as JSON to specified output file in specified format."""

    to_print = {
      'tidepool': [obj.as_tidepool() for obj in self.all]
    }[self.output['format']]

    with open(self.output['file'], 'w') as f:
      print(json.dumps(to_print, separators=(',', ': '), indent=2, sort_keys=True), file=f)

    return self
