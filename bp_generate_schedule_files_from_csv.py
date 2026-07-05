#########################################################################
#
# Creates two schedule-based files based on an Excel/.csv input file.
#
# 1. Day-by-day list of games that were actually played or postponed.
# 2. Day-by-day list of games that were originally scheduled.
#
# A game could be postponed more than once, resulting in a PPD game in the
# original_schedule_file.csv AND a PPD game in the actual_schedule_file.csv
#
# CC License: Attribution-NonCommercial 4.0 International (CC BY-NC 4.0)
# https://creativecommons.org/licenses/by-nc/4.0/
#
# Requirements:
# 1. Must have a TEAM<Season_as_YYYY>.txt file, that maps team abbreviations to their full names, in the same folder.
#
#  1.0  MH  06/30/2026  Initial version
#
import argparse, csv, datetime, glob, math, os, re, sys
from collections import defaultdict
from bp_utils import bp_load_roster_files
from datetime import datetime, timedelta

# Use this to catch cases where our spreadsheet does not have the "Game1" / "Game2" indicators for doubleheaders
list_of_game_ids = []

##########################################################
#
# Main program
#

parser = argparse.ArgumentParser(description='Create schedule files based on a .csv input file.') 
parser.add_argument('inputfile', help="Schedule info extracted from Excel file in .csv format")
parser.add_argument('original_schedule_file', help="Original schedule data (output)")
parser.add_argument('actual_schedule_file', help="Actual schedule data (output)")

args = parser.parse_args()

# Read in team full name file
team_abbrev_to_full_name = defaultdict()
team_city_name_to_abbrev = defaultdict()

search_string = "TEAM[0-9][0-9][0-9][0-9].txt"
list_of_files = glob.glob(search_string)
filename = list_of_files[0] # should only be one such file in the folder, so pick the first one
print("Using %s to derive team names\n" % (filename))

with open(filename,'r') as csvfile: # file is automatically closed when this block completes
    items = csv.reader(csvfile)
    for row in items:    
        # COL,AA,Columbus,Red Birds
        if len(row) > 0:
            team_abbrev_to_full_name[row[0]] = row[2] + " " + row[3]
            league_classification = row[1]
            team_city_name_to_abbrev[row[2]] = row[0]
            if row[2] == "Cranston": # Hack because I use Cranston and Providence interchangeably
                team_city_name_to_abbrev["Providence"] = "PRV"

# This will create the file if it does not exist already, and will overwrite file if it already exists.
original_schedule_fh = open(args.original_schedule_file,'w')
actual_schedule_fh = open(args.actual_schedule_file,'w')
            
#original_schedule_dict = defaultdict(lambda: defaultdict(list))
#actual_schedule_dict = defaultdict(lambda: defaultdict(list))
#game_count = 0
with open(args.inputfile,'r') as ifile:
    # Date,Day,Time,Road,RunsRoad,Home,RunsHome,Innings,DH,OriginalScheduleReference,Rescheduled,LinescoreReference,BoxscoreReference,Notes,Winner,Loser,Tie
    items = csv.reader(ifile) # Default is delimiter=','
    for record in items:
        if len(record) > 14:
            if record[0] != "Date" and len(record[0]) > 0:
                date = record[0]
                time = record[2]
                
                road_team = team_city_name_to_abbrev[record[3]]
                road_runs = record[4]
                if road_runs == "":
                    road_runs = "PPD"
                    
                home_team = team_city_name_to_abbrev[record[5]]
                home_runs = record[6]
                if home_runs == "":
                    home_runs = "PPD"
                    
                if (home_runs == "PPD" and road_runs != "PPD") or (home_runs != "PPD" and road_runs == "PPD"):
                    print("ERROR: Found runs for one team and not the other (%s)\n" % (record))
                
                innings = record[7]
                doubleheader = record[8]
                original_schedule = record[9] # blank if NOT in original schedule
                rescheduled = record[10]
                
                if len(rescheduled) == 0 and (home_runs == "PPD" or road_runs == "PPD"):
                    print("ERROR: No reason for postponement found (%s)\n" % (record))
                
                postponed_reason = record[13] 
                shortened_reason = record[14] 
                neutral_site_info = record[15] 
                
                if doubleheader == "":
                    game_number = 0
                elif doubleheader == "Game1":
                    game_number = 1
                elif doubleheader == "Game2":
                    game_number = 2
                else:
                    print("WARN: Unexpected data in doubleheader column. Using zero as game number. (%s)\n" % (record))
                    
                g_month = date.split("/")[0]
                g_day = date.split("/")[1]
                g_year = date.split("/")[2]
                game_id = home_team + g_year + ("%02d" % int(g_month)) + ("%02d" % int(g_day)) + str(game_number)
                
                if game_id in list_of_game_ids:
                    print("Duplicate game id detected %s\n" % (game_id))
                else:
                    list_of_game_ids.append(game_id)
                
                if len(original_schedule) > 0:
                    original_schedule_fh.write("%s,%s,%s,%s,%s,%s\n" % (game_id,road_team,road_runs,home_team,home_runs,innings))
                
                if re.match("MOVED",rescheduled):
                    print("MOVED game not included in actual_schedule file: (%s)" % (record))
                else:
                    # Games that were moved will get included in the original_schedule above, but
                    # should not be considered a "postponed" game in the actual_schedule.
                    if re.match("PROTESTEDSUCCESSFULLY",rescheduled):
                        print("NOTE: PROTESTED game that was overturned is included in actual_schedule file: (%s)" % (record))
                        
                    actual_schedule_fh.write("%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s\n" % (game_id,road_team,road_runs,home_team,home_runs,innings,time,rescheduled,postponed_reason,shortened_reason,neutral_site_info))
            
original_schedule_fh.close()
actual_schedule_fh.close()