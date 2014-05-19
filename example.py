# Copyright (c) 2014, Jana E. Beck
# Contact: jana.eliz.beck@gmail.com
# License: GPLv3 (http://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import print_function

from dexcom import merge_csv
from dexcom.convert_to_JSON import DexcomJSON

def main():
  # example usage of merge_csv via the dexcom module instead of via command-line args
  example_output = 'example_output.csv'

  args = {
    'csv': True,
    'device_gen': True,
    # change me to the path (optional), filename and extension where you'd like the output saved
    'output_file': example_output,
    # change me to the proper path to the directory where your Dexcom files are stored
    'dir_path': '',
    'serial': True,
    'terse': True
  }

  merge_csv.process(args)

  with open(example_output, 'rU') as f:
    dex = DexcomJSON(f, {
      'format': 'tidepool',
      'file': 'example-output.json'
    })

    # bloodhound takes a timezone string - e.g., 'US/Eastern' 
    dex.bloodhound('').print_JSON()

if __name__ == '__main__':
  main()