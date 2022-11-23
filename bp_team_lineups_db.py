#########################################################################
#
# Obtain starting lineups for a team from the SQL Alchemy database.
#
# CC License: Attribution-NonCommercial 4.0 International (CC BY-NC 4.0)
# https://creativecommons.org/licenses/by-nc/4.0/
#
# References:
# https://www.retrosheet.org/eventfile.htm
# https://www.retrosheet.org/boxfile.txt
# 
#
#  1.1  MH  01/10/2020  Remove "season" and use bp_load_roster_files()
#  1.0  MH  08/17/2019  Initial version
#
import argparse, csv, datetime, glob, re, sys
from collections import defaultdict
from bp_retrosheet_classes import GameInfo, BattingStats, PitchingStats, DefensiveStats, Base
from sqlalchemy import or_, and_
from bp_utils import bp_load_roster_files

DEBUG_ON = False

##########################################################
#
# Text output functions
#    
# Default is left-justified, use > for right-justified or ^ for centered.
# An extra space is added between all columns.

# Date,Tm,R,,Opp,R,,1,2,3,4,5,6,7,8,9,Pitcher
game_info_headers = ['10','3','>2','3','3','>2','2','25','25','25','25','25','25','25','25','25','25']

def build_text_output_string(format_widths_list,stats_strings_list):
    s = ""
    # Since the comments field can contain commas, we limit the split so the commas
    # that precedes the comment is the last one we split on. Any text after that
    # will appear in the comments column.
    for count,stat in enumerate(stats_strings_list.split(",",len(game_info_headers)-1)):
        s = s + '{:{w}s}'.format(stat, w=format_widths_list[count]) + " "
    return s
    
##########################################################
#
# Main program
#

parser = argparse.ArgumentParser(description='Obtain starting lineups from a SQL Alchemy database.') 
parser.add_argument('dbfile', help="DB file (input)")
parser.add_argument('outfile', help="Stats file (output)")
parser.add_argument('team', help="Team abbreviation.")
parser.add_argument('-format', '-f', help="Output format as CSV (default) or TEXT") 
parser.add_argument('-opponent', '-o', help="Team abbreviation or ALL for all teams (default)")
parser.add_argument('-location', '-l', help="HOME, ROAD, or ALL (default)")
parser.add_argument('-startdate', '-s', help="Report lineups starting on YYYY/MM/DD (optional)")
parser.add_argument('-enddate', '-e', help="Report lineups up through YYYY/MM/DD inclusive (optional)")
args = parser.parse_args()

output_file = open(args.outfile,'w')

output_format = "CSV"
if args.format:
    if args.format == "TEXT":
        output_format = "TEXT"
        
s_team = args.team
    
if args.opponent:
    s_opponent = args.opponent
else:
    s_opponent = "ALL"
    
if args.location:    
    s_location = args.location
else:
    s_location = "ALL"

if args.startdate:
    s_startdate = datetime.datetime.strptime(args.startdate, '%Y/%m/%d')
else:
    s_startdate = "NONE"

if args.enddate:
    s_enddate = datetime.datetime.strptime(args.enddate, '%Y/%m/%d')
else:
    s_enddate = "NONE"

# Read in all of the .ROS files up front so we can build dictionary of player ids and names, by team.
(player_info, list_of_teams) = bp_load_roster_files()
                
from sqlalchemy import create_engine
engine = create_engine('sqlite:///%s' % (args.dbfile), echo=False)
                       
from sqlalchemy.orm import sessionmaker
Session = sessionmaker(bind=engine)

session = Session() 

count = 0

filters = []

if s_team != "ALL":
    if s_opponent != "ALL":  
        # pick games only where the two teams are s_team and s_opponent
        if s_location == "HOME":
            filters.append(and_(GameInfo.home_team == s_team,GameInfo.road_team == s_opponent))
        elif s_location == "ROAD":
            filters.append(and_(GameInfo.road_team == s_team,GameInfo.home_team == s_opponent))
        else:
            filters.append(or_(and_(GameInfo.road_team == s_team,GameInfo.home_team == s_opponent),and_(GameInfo.home_team == s_team,GameInfo.road_team == s_opponent)))
    else:
        if s_location == "HOME":
            filters.append(GameInfo.home_team == s_team)
        elif s_location == "ROAD":
            filters.append(GameInfo.road_team == s_team)
        else:
            filters.append(or_(GameInfo.road_team == s_team,GameInfo.home_team == s_team))
    
if s_startdate != "NONE":
    filters.append(GameInfo.date_as_dt >= s_startdate)
    print("Stats beginning on %s" % (args.startdate))
   
if s_enddate != "NONE":
    filters.append(GameInfo.date_as_dt <= s_enddate)
    print("Stats through %s" % (args.enddate))
    
##########################################################
#
# Game information
#    

header_printed = False    
for game_record in session.query(GameInfo).filter(*filters).order_by(GameInfo.date_as_dt,GameInfo.game_number_that_day):
    count += 1
    if not header_printed:
        if output_format == "TEXT":    
            text_string = build_text_output_string(game_info_headers,"Date,Tm,R,,Opp,R,,1,2,3,4,5,6,7,8,9,Pitcher")
            output_file.write("%s\n" % (text_string))
        else:
            output_file.write("Date,Tm,R,,Opp,R,,1,2,3,4,5,6,7,8,9,Pitcher\n")
        header_printed = True

    stat_string = game_record.date + "," 
    
    if s_team != "ALL" and s_team == game_record.home_team : 
        # list team of interest followed by other team
        stat_string += game_record.home_team + "," + str(game_record.home_team_runs) + ",vs" + "," + game_record.road_team + "," + str(game_record.road_team_runs)
    else: 
        # list road team followed by home team
        stat_string += game_record.road_team + "," + str(game_record.road_team_runs) + ",at" + "," + game_record.home_team + "," + str(game_record.home_team_runs)
    
    if game_record.innings != 9:
        stat_string += "," + str(game_record.innings)
    else:
        stat_string += ","

    # Query Batting and Pitcher stats
    # TBD - More complex DB tables would make these kinds of queries simpler.
    p_filters = []
    p_filters.append(BattingStats.date_as_dt == game_record.date_as_dt)
    p_filters.append(BattingStats.game_number_that_day == game_record.game_number_that_day)
    p_filters.append(BattingStats.my_team == s_team)
    p_filters.append(BattingStats.sequence_number == 0) # starters only
    
    for batter in session.query(BattingStats).filter(*p_filters).order_by(BattingStats.batting_order_number):
        # Add position info from the DefensiveStats table
        d_filters = []
        d_filters.append(DefensiveStats.date_as_dt == batter.date_as_dt)
        d_filters.append(DefensiveStats.game_number_that_day == batter.game_number_that_day)
        d_filters.append(DefensiveStats.my_team == batter.my_team)
        d_filters.append(DefensiveStats.pid == batter.pid) 
        defensive_info = session.query(DefensiveStats).filter(*d_filters).first()
        if re.search("-",defensive_info.position_list):
            starting_pos = defensive_info.position_list.split("-")[0]
        else:
            starting_pos = defensive_info.position_list
        stat_string += "," + starting_pos + " " + player_info[batter.my_team][batter.pid]

    p_filters = []
    p_filters.append(PitchingStats.date_as_dt == game_record.date_as_dt)
    p_filters.append(PitchingStats.game_number_that_day == game_record.game_number_that_day)
    p_filters.append(PitchingStats.my_team == s_team)
    p_filters.append(PitchingStats.sequence_number == 0) # starters only
    
    # should be a single pitcher
    for pitcher in session.query(PitchingStats).filter(*p_filters):
        stat_string += "," + player_info[pitcher.my_team][pitcher.pid]
        
    if output_format == "TEXT":
        text_string = build_text_output_string(game_info_headers,stat_string)
        output_file.write("%s\n" % (text_string))
    else:
        output_file.write("%s\n" % (stat_string))


output_file.close()

print("Done - saved %s" % (args.outfile))
