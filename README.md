# boxtopbaseball
Baseball box score entry and generation scripts based on Retrosheet data formats

IMPORTANT NOTE: These scripts should be considered "Alpha" or early "Beta" versions.

These files are licensed by a Creative Commons Attribution-NonCommercial 4.0 International (CC BY-NC 4.0) license: https://creativecommons.org/licenses/by-nc/4.0/

General workflow for entering and viewing box score data:
1. Use bp_enter_data.py to enter one or more box scores and create/update an .EBA file.
2. Use bp_cross_check.py to check the resulting .EBA file for problems.
3. Use a text editor to edit the .EBA file as needed (repeat steps 2 and 3 as needed).
4. Use bp_generate_box.py to generate box scores from the .EBA file which look similar to those on the Retrosheet.org website (random example: https://www.retrosheet.org/boxesetc/1967/B04110NYN1967.htm).


The scripts in the SQLA folder use SQLAlchemy to convert a .EBA file into a database file that can then be queried for various purposes. Use bp_create_db.py to create a .db file (this script uses the DB table definitions in the bp_retrosheet_classes.py file).

The following scripts query the .db file:
1. bp_dump_db.py - Dumps all tables from the database, useful for debugging purposes.
2. bp_game_log_db.py - Creates game-by-game log for a single player in .txt or .csv format. Supports filtering by team, opponent, home/road, and date range.
3. bp_splits_db.py - Creates report containing an entry for every player in the .db file. Supports filtering by team, opponent, home/road, and date range.
4. bp_team_game_log_db.py - Creates game-by-game log for a team or all teams, listing basic game information including the score, winning and losing pitcher, attendance, time of game, etc. Supports filtering by team, opponent, home/road, and date range.
