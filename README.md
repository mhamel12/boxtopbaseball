# boxtopbaseball
Baseball box score entry and generation scripts based on Retrosheet data formats

IMPORTANT NOTE: These scripts should be considered "Alpha" or early "Beta" versions. Tested with Python 3.6.0 on Windows.

These files are licensed by a Creative Commons Attribution-NonCommercial 4.0 International (CC BY-NC 4.0) license: https://creativecommons.org/licenses/by-nc/4.0/

General workflow for entering and viewing box score data:
1. Create .ROS files for every team in the league. The bp_make_team_files.py script is an example of how to do this in an automated way; it uses rosters downloaded from StatsCrew.com as input, but you could write a similar script to use roster information from Baseball-Reference.com or other sites.
2. Use bp_enter_data.py to enter one or more box scores and create/update an .EBA file.
3. Use bp_cross_check.py to check the resulting .EBA file for problems.
4. Use a text editor to edit the .EBA file as needed (repeat steps 3 and 4 as needed).
5. Use bp_generate_box.py to generate box scores from the .EBA file which look similar to those on the Retrosheet.org website (random example: https://www.retrosheet.org/boxesetc/1967/B04110NYN1967.htm).


The scripts in the SQLA folder use SQLAlchemy (https://www.sqlalchemy.org/) to convert a .EBA file into a database file that can then be queried for various purposes. These scripts can help with proofing box score data by identifying missing statistics (game log reports) or by providing data that can be compared against "official" season statistics available from Baseball-Reference.com and other sources (splits). 

Get started by using bp_create_db.py to create a .db file (this script uses the DB table definitions in the bp_retrosheet_classes.py file).

The following scripts query the .db file:
1. bp_dump_db.py - Dumps all tables from the database, useful for debugging purposes but not easy to read.
2. bp_game_log_db.py - Creates game-by-game log for a single player in .txt or .csv format. Supports filtering by team, opponent, home/road, and date range.
3. bp_splits_db.py - Designed to generate 'season statistics' for every player in the .db, or every player on a given team, or "splits" such as home/road, games versus a particular opponent, etc. Output in .txt or .csv format. Supports filtering by team, opponent, home/road, and date range.
4. bp_team_game_log_db.py - Creates game-by-game log for a team or all teams, listing basic game information including the score, winning and losing pitcher, attendance, time of game, etc. Output in .txt or .csv format. Supports filtering by team, opponent, home/road, and date range.
5. bp_position_summary_db.py - Create summary of games played by position for a team or all teams. Output in .txt or .csv format. Supports filtering by team, opponent, home/road, and date range.
6. bp_team_lineups_db.py - Create game log-style summary of starting lineups for a single team. Output in .txt or .csv format. Supports filtering by opponent, home/road, and date range.
