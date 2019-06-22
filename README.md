# boxtopbaseball
Baseball box score entry and generation scripts based on Retrosheet data formats

IMPORTANT NOTE: These scripts should be considered "Alpha" or early "Beta" versions.

These files are licensed by a Creative Commons Attribution-NonCommercial 4.0 International (CC BY-NC 4.0) license: https://creativecommons.org/licenses/by-nc/4.0/

General workflow:
1. Use bp_enter_data.py to enter one or more box scores and create/update an .EBA file
2. Use bp_cross_check.py to check the resulting .EBA file for problems
3. Use a text editor to edit the .EBA file as needed (repeat steps 2 and 3 as needed)
4. Use bp_generate_box.py to generate box scores from the .EBA file which look similar to those on the Retrosheet.org website (random example: https://www.retrosheet.org/boxesetc/1967/B04110NYN1967.htm)
