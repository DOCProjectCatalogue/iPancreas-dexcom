# usage: merge_csv.py [-h] [-c] [-d] [-o OUTPUT_FILE] [-p DIR_PATH] [-s] [-t]
#
# Merge a set of Dexcom .csv exports (from Dexcom Studio) into one .csv file.
#
# optional arguments:
#   -h, --help            show this help message and exit
#   -c, --csv             comma- (instead of tab-)delimited output
#   -d, --device-gen      include a column for device generation information
#   -o OUTPUT_FILE, --output-file OUTPUT_FILE
#                         path and/or name of output file
#   -p DIR_PATH, --path DIR_PATH
#                         path to the directory where all your Dexcom Studio
#                         .csv exports are stored
#   -s, --serial-number   include a column for device serial number
#   -t, --terse           output only glucose and timestamps columns
#
# Copyright (c) 2014, Jana E. Beck
# Contact: jana.eliz.beck@gmail.com
# License: GPLv3 (http://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import print_function

import argparse
import csv
import os
import re

class DexcomSet:
  """Construct a set of non-duplicate Dexcom records from a group of Dexcom files."""

  def __init__(self, files):
    """Call _add_rows_from_file(f) to fill the set with non-duplicate records."""

    self.set = set([])

    self.files = files

    self.serials = []

    # only used for terminal logging
    self.total_so_far = 0

    for f in self.files:
      self._add_rows_from_file(f)

  def _add_rows_from_file(self, this_file):
    """Add the records from a file to the DexcomSet."""

    # compile regexes for Dexcom Seven Plus vs. G4 Platinum device serial numbers
    seven_plus = re.compile('\d.+')
    g4_platinum = re.compile('SM\d.+')

    count = 0
    missing = 0

    # have to fill a list with items to add to the set first
    # in case we need to append the serial number, which doesn't appear until the 3rd row
    add_to_set = []

    with open(this_file['file'], 'rU') as f:
      rdr = csv.reader(f, delimiter='\t')
      # exclude header
      next(rdr)
      for row in rdr:
        # sniff out serial number, which occurs in column to the right of label 'SerialNumber'
        if row[0] == 'SerialNumber':
          this_SN = row[1]
        # replace first two cols with '' because want to avoid duplicates with rows that have ID info
        row[0] = ''
        row[1] = ''
        add_to_set.append(row)
        count += 1

    # search for a match between the serial number and one of the pre-compiled regexes
    if seven_plus.match(this_SN):
      generation = 'SevenPlus'
    elif g4_platinum.match(this_SN):
      generation = 'G4Platinum'
    else:
      generation = 'Unknown'

    for item in add_to_set:
      # if adding device generation info is desire, append it to saved rows
      if this_file['add_generation_info']:
        item.append(generation)
      if this_file['add_sn_info']:
        item.append(this_SN)
      # set uses a hash internally and hash keys must be immutable types
      # i.e., tuple, not list
      self.set.add(tuple(item))

    # give the command-line user some insight into what's going on
    print("%i readings in %s." %(count, this_file['file']))
    print("%i items in DexcomSet." %(len(self.set)))
    if len(self.set) - self.total_so_far != count:
      duplicates = ((self.total_so_far + count) - len(self.set))
      print("%i duplicate records in this file." %(duplicates))
    print()
    self.total_so_far = len(self.set)

  def _sort(self):
    """Sort the DexcomSet by GlucoseInternalTime."""

    return sorted(self.set, key=lambda t: t[2])

  def print_set(self, header, delimiter, output_file = 'merged-dexcom.csv'):
    """Print the DexcomSet row-by-row to file."""

    count = 0

    with open(output_file, 'w') as f:
      wrtr = csv.writer(f, delimiter=delimiter)
      print("### Writing to new file %s..." %(output_file))
      print()
      wrtr.writerow(header)
      for item in self._sort():
        # header for terse can be 6 if no device gen, 7 if device gen
        if len(header) == 6:
          to_write = list(item)[2:8]
        elif len(header) == 7:
          # device gen is in very last column
          to_write = list(item)[2:8] + [list(item)[-1]]
        elif len(header) == 8:
          # serial number is in very last column
          to_write = list(item)[2:8] + list(item)[-2:]
        else:
          to_write = list(item)
        wrtr.writerow(to_write)
        count += 1

    print("%i non-duplicate records printed to %s." %(count, output_file))
    print()

def get_header(this_file):
  """Get the header of a Dexcom file."""

  with open(this_file, 'rU', newline='') as f:
    rdr = csv.reader(f, delimiter='\t')
    return next(rdr)

def get_file_list(path = ""):
  """Get the list of files with .csv or .txt extensions in the target directory."""

  all_files = []

  for root, dirs, files in os.walk(path):
    # compile a list of all non-OS .txt and .csv files for consideration as possible Dexcom files
    all_files += [os.path.join(root, f) for f in files if (f.endswith('.txt') or f.endswith('.csv') and not (f.startswith('$') or f.startswith('._')))]

  return all_files

def process(args):

  # first, get the list of files accessible from the given or current path
  if args['dir_path']:
    files = get_file_list(args['dir_path'])
  else:
    files = get_file_list()

  # check each file to see if it might be a Dexcom file; remove those that aren't
  expected_header = ['PatientInfoField', 'PatientInfoValue', 'GlucoseInternalTime', 'GlucoseDisplayTime', 'GlucoseValue', 'MeterInternalTime', 'MeterDisplayTime', 'MeterValue', 'EventLoggedInternalTime', 'EventLoggedDisplayTime', 'EventTime', 'EventType', 'EventDescription']

  to_remove = []

  for f in files:
    if get_header(f) != expected_header:
      print()
      print("!!! This file doesn't look like a Dexcom file: \n%s \nI'm skipping it. :(" %(f))
      print()
      to_remove.append(f)

  [files.remove(f) for f in to_remove]

  # set new header if output format is 'terse'
  if args['terse']:
    header = ['GlucoseInternalTime', 'GlucoseDisplayTime', 'GlucoseValue', 'MeterInternalTime', 'MeterDisplayTime', 'MeterValue']

  else:
    try:
      header = get_header(files[0])
    except IndexError:
      print()
      print("Sorry, I couldn't find any Dexcom files in this directory. Try giving me a path to the directory where you've stored them.")
      print()
      exit(0)

  # append a column label for device generation if desired in output
  if args['device_gen']:
    header.append('DeviceGeneration')
  if args['serial']:
    header.append('SerialNumber')
  # create a DexcomSet instance to merge records
  print()
  print('### Merging the following files:')
  [print(f) for f in files]
  print()

  dex = DexcomSet([{
    'add_generation_info': args['device_gen'],
    'add_sn_info': args['serial'],
    'file': f
  } for f in files])

  # set the delimiter to csv if desired; default is tab
  delimiter = ',' if args['csv'] else '\t'

  # pass the header, delimiter, and output file if provided to the DexcomSet's print function
  if args['output_file']:
    dex.print_set(header, delimiter, args['output_file'])
  else:
    dex.print_set(header, delimiter)

def main():

  parser = argparse.ArgumentParser(description='Merge a set of Dexcom .csv exports (from Dexcom Studio) into one .csv file.')

  parser.add_argument('-c', '--csv', action='store_true', help='comma- (instead of tab-)delimited output')
  parser.add_argument('-d', '--device-gen', action='store_true', dest='device_gen', help='include a column for device generation information')
  parser.add_argument('-o', '--output-file', action='store', dest="output_file", help='path and/or name of output file')
  parser.add_argument('-p', '--path', action='store', dest="dir_path", help='path to the directory where all your Dexcom Studio .csv exports are stored')
  parser.add_argument('-s', '--serial-number', action='store_true', dest='serial', help='include a column for device serial number')
  parser.add_argument('-t', '--terse', action='store_true', help='output only glucose and timestamps columns')

  args = parser.parse_args()

  # force adding of device gen info when adding serial, to keep things simpler
  if args.serial:
    args.device_gen = True

  process(args.__dict__)

if __name__ == '__main__':
  main()