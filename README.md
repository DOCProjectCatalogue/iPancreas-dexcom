iPancreas-dexcom
================

Utilities for data from a Dexcom continuous glucose monitor.

### About

This is the repository where I'm moving all my utilities (previously found in my repository now known as [iPancreas-archive](https://github.com/jebeck/iPancreas-archive)) for dealing with the data from a Dexcom continuous glucose monitor. The eventual goal is a Python module (located in `dexcom/`) containing everything I use to read, munge, and analyze my own Dexcom data, from soup to nuts (i.e., from reading the raw Dexcom Studio output to final JSON). Perhaps I'll even add the package to `pip` eventually...

As of August 3rd, 2014, I have reimplemented iPancreas-archive's `dexcom_to_JSON.py` tool as `convert_to_JSON.py`, now including tooling for specifiying the timezone associated with segments of a dataset (whenever the date and time settings on the device appear to have changed) given an input timezone corresponding to the timezone of the most recent data.

In May 2014, I added a tool `merge_csv.py` (originally from [a gist of mine](https://gist.github.com/jebeck/11167866)) for merging any number of Dexcom Studio export files into a single Dexcom Studio or "terse"-formatted file without duplicates. Comments at the top of this file provide its documentation.

The file `example.py` provides usage examples for all of the components of the package.

### Disclaimer

The software tools in this repository are provided as aids for extracting and munging data from files exported from the Dexcom Studio software application that is provided as an accessory to a Dexcom continuous glucose monitor. Use at your own risk: none of the tools in this repository is intended to substitute for professional medical advice regarding your diabetes care. Consult with your health care provider before making any treatment decisions or changes.

### License

The software tools in this repository are free software: you can redistribute them and/or modify them under the terms of the GNU General Public License as published by the Free Software Foundation, either version 3 of the License, or (at your option) any later version.

These programs are distributed in the hope that they will be useful, but WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU General Public License for more details.

You should have received a copy of the GNU General Public License along with this program.  If not, see <http://www.gnu.org/licenses/>.
