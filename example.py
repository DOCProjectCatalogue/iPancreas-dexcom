# Copyright (c) 2014, Jana E. Beck
# Contact: jana.eliz.beck@gmail.com
# License: GPLv3 (http://www.gnu.org/licenses/gpl-3.0.txt)

from dexcom import merge_csv

def main():
  # example usage of merge_csv via the dexcom module instead of via command-line args
  args = {
    'csv': False,
    'device_gen': False,
    # change me to the path (optional), filename and extension where you'd like the output saved
    'output_file': '',
    # change me to the proper path to the directory where your Dexcom files are stored
    'dir_path': '',
    'terse': False
  }

  merge_csv.process(args)

if __name__ == '__main__':
  main()