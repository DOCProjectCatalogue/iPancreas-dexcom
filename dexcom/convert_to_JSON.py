# Copyright (c) 2014, Jana E. Beck
# Contact: jana.eliz.beck@gmail.com
# License: GPLv3 (http://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import print_function

import csv
from datetime import datetime as dt, timedelta as td, tzinfo
import json
from pytz import timezone as tz, UnknownTimeZoneError
import pytz
import uuid

DT_FORMAT = '%Y-%m-%d %H:%M:%S'

class DexcomTZ(tzinfo):

  def __init__(self, offset):
    self.__offset = td(hours=offset)

  def utcoffset(self, dt):
    return self.__offset

def datetime_difference(d1, d2):
  """Return the different between two datetimes."""

  return d2 - d1

def enlighten_datetime(obj):
  """Make a Dexcom object timezone-aware with utc_time and display_time attributes."""

  obj.utc_time = pytz.utc.localize(parse_datetime(obj.internal_time) - td(hours=obj.internal_offset)).isoformat()
  obj.display_time = parse_datetime(obj.user_time).replace(tzinfo=DexcomTZ(obj.display_offset)).isoformat()

def parse_datetime(dt_str):
  """Parse a Dexcom time and date string into a datetime object."""

  try:
    return dt.strptime(dt_str, DT_FORMAT)
  except ValueError:
    # gen 'SevenPlus' date and time info includes milliseconds
    # so we truncate to index -4
    return dt.strptime(dt_str[:-4], DT_FORMAT)

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
    self.utc_time = ''
    self.display_time = ''

  def _set_value(self, value):
    """Return the integer value for each possible Dexcom sensor reading."""
    try:
      value = int(value)
      # calibrations can go below 40
      if value >= 20 and value <= 400:
        return value
      else:
        raise Exception('Dexcom value out of range:', value)
    except ValueError:
      if value == 'Low':
        return 39
      elif value == 'High':
        return 401

  def as_tidepool(self):
    """Return a dict of the object conforming to Tidepool's data model."""

    return {
      'id': str(uuid.uuid4()),
      'deviceTime': parse_datetime(self.user_time).strftime('%Y-%m-%dT%H:%M:%S'),
      'timezoneAwareTime': self.display_time,
      'trueUtcTime': self.utc_time,
      'type': 'cbg' if self.subtype == 'sensor' else 'smbg',
      'value': self.value
    }

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

  def __init__(self, csv_file, output_opts, offsets = {}):
    """Parse input CSV file into appropriate Dexcom objects."""

    self.output = output_opts

    reader = csv.reader(csv_file)
    # skip the header
    reader.next()
    self.all = []
    for row in reader:
      self.all += self._parse_row(row)

    # make sure all is sorted!
    self.all.sort(key=lambda x: x.internal_time, reverse=True)

    if not offsets:
      self.offsets = {'SevenPlus': 0}
    else:
      self.offsets = offsets

    self.timezone_changes = []

  def sensors(self):
    """Return all and only sensor readings."""

    return [i for i in self.all if i.subtype == 'sensor']

  def calibrations(self):
    """Return all and only calibration readings."""

    return [i for i in self.all if i.subtype == 'calibration']

  def _add_timezone_change(self, diff_in_hours, obj, change_type, start = False):
    """Add a timezone change to the list."""

    try:
      offset = self.offsets[obj.serial]
    except KeyError:
      if obj.device_gen == 'SevenPlus':
        offset = self.offsets[obj.device_gen]
      else:
        offset = self._get_g4_offset(obj)
        if not offset:
          return

    self.timezone_changes.append({
      # timestamp of last (most recent) datum to which this offset is to be applied
      'datetime': obj.internal_time if start else '',
      'display_offset': diff_in_hours + offset,
      'internal_offset': offset,
      'type': change_type
    })

    return (offset, diff_in_hours + offset)

  def _get_g4_offset(self, obj):
    """Ask the user to input an offset for a particular Dexcom G4 Platinum CGM device."""

    if not obj.serial:
      print('Unknown serial number! Cannot proceed with bloodhound protocol.')
      print()
      return

    print('The G4 Platinum does not have a consistent internal timestamp offset from UTC.')
    print('The serial number of this device is', obj.serial)
    print('Here is the first internal timestamp from this device:', obj.internal_time)
    print('And here is the display time:', obj.user_time)
    print()
    # because raw_input got renamed in Python 3.something
    try:
      input = raw_input
    except NameError:
      pass
    res = input('Please enter the offset of the display time from UTC as an integer value: ')
    self.offsets[obj.serial] = int(res)

    # also return the value
    return int(res)

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

    SECONDS_IN_HOUR = 3600

    try:
      most_recent_timezone = tz(tz_str)
    except UnknownTimeZoneError:
      print('Unknown timezone! Cannot proceed with bloodhound protocol.')
      print()
      return

    initial_difference = ''

    for obj in self.all:
      user_time = parse_datetime(obj.user_time)
      internal_time = parse_datetime(obj.internal_time)

      diff = {'timedelta': datetime_difference(user_time, internal_time)}

      diff['hours'] = -diff['timedelta'].seconds/SECONDS_IN_HOUR
      # round up to nearest hour if within sixty seconds of an hour
      if diff['timedelta'].seconds % SECONDS_IN_HOUR < SECONDS_IN_HOUR/2:
        diff['hours'] += 1

      # bootstrap from most recent data known timezone and difference to internal timestamp offset from UTC
      if not initial_difference:
        offsets = self._add_timezone_change(diff['hours'], obj, 'input by user')
        initial_difference = diff
        current_difference = initial_difference
      # offset from UTC of internal timestamps isn't consistent across G4 receivers
      elif obj.serial != last_obj.serial and obj.device_gen == 'G4Platinum':
        offsets = self._add_timezone_change(diff['hours'], obj, 'changed G4 Platinum device', True)
        current_difference = diff
      # offset from UTC of internal timestamps isn't consistent across device generations
      elif obj.device_gen != last_obj.device_gen:
        offsets = self._add_timezone_change(diff['hours'], obj, 'changed to Seven Plus device', True)
        current_difference = diff
      # and sometimes the user actually changed the device's settings
      # fancy that!
      elif diff['hours'] != current_difference['hours'] \
          and abs(diff['timedelta'].seconds - current_difference['timedelta'].seconds) > 60:
        offsets = self._add_timezone_change(diff['hours'], obj, 'inferred via bloodhound protocol', True)
        current_difference = diff

      # add offsets to Dexcom object
      if offsets:
        obj.internal_offset = offsets[0]
        obj.display_offset = offsets[1]
        # make each Dexcom object timezone-aware
        enlighten_datetime(obj)

      last_obj = obj

    return self

  def print_JSON(self):
    """Print as JSON to specified output file in specified format."""

    to_print = {
      'tidepool': [obj.as_tidepool() for obj in self.all]
    }[self.output['format']]

    with open(self.output['file'], 'w') as f:
      print(json.dumps(to_print, separators=(',', ': '), indent=2), file=f)
