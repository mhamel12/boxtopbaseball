#########################################################################
#
# Obtain game logs for a team from the SQL Alchemy database.
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
#  1.0  MH  07/18/2019  Initial version
#
import argparse, csv, datetime, glob, re, sys
from collections import defaultdict
from bp_retrosheet_classes import GameInfo, Base
from sqlalchemy import or_, and_
from bp_utils import bp_load_roster_files

DEBUG_ON = False

def get_stat_as_string(stat_as_integer):
    if stat_as_integer >= 0:
        return str(stat_as_integer)
    # drop any -1 stat values on the floor
    return ("")
    
##########################################################
#
# Text output functions
#    
# Default is left-justified, use > for right-justified or ^ for centered.
# An extra space is added between all columns.

# Date,Tm,R,,Opp,R,In,WP,LP,Time,D/N,Start,Att,Comments
game_info_headers = ['10','3','>2','3','3','>2','>2','30','30','>5','>3','7','>6','50']

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
# Misc. functions
#
def get_pct_as_string(divisor_as_integer,dividend_as_integer,decimal_places,remove_leading_zero):
    # protect against divide by zero
    if dividend_as_integer == 0:
        pct = 0
    else:
        divisor_as_float = 1.0 * divisor_as_integer
        pct = divisor_as_float / dividend_as_integer
    
    # remove leading zero from averages
    pct = '{:.{prec}f}'.format(pct, prec=decimal_places)
    if remove_leading_zero:
        pct = pct.lstrip('0')
        
    return pct
    
    
# Convert outs into innings pitched where 1/3 of an inning = .333
# This value is appropriate to use in calcuations such as WHIP or ERA.    
def get_ip_as_float(outs_as_integer):
    return ((1.0*outs_as_integer)/3)    
    
# Convert outs into innings pitched where 1/3 of an inning = .1
# This value is appropriate to use for display purposes.
def get_ip(outs_as_integer):
    thirds_of_an_inning = str(outs_as_integer % 3)
    whole_innings = str(outs_as_integer // 3) # integer division works with python 3.x
    return (whole_innings + "." + thirds_of_an_inning)    

# Convert time of game into HH:MM format    
def get_time_in_hr_min(time_in_min):
    hours = int(time_in_min / 60)
    min = time_in_min % 60
    return str(hours) + ":" + str("%02d" % (min))
    
##########################################################
#
# Main program
#

parser = argparse.ArgumentParser(description='Obtain team game log from a SQL Alchemy database.') 
parser.add_argument('dbfile', help="DB file (input)")
parser.add_argument('outfile', help="Stats file (output)")
parser.add_argument('-format', '-f', help="Output format as CSV (default) or TEXT") 
parser.add_argument('-team', '-t', help="Team abbreviation or ALL for all teams (default). If a team is selected, that team name will always appear in left-most team column.")
parser.add_argument('-opponent', '-o', help="Team abbreviation or ALL for all teams (default - ignored if -team is set to ALL)")
parser.add_argument('-location', '-l', help="HOME, ROAD, or ALL (default - ignored if -team is set to ALL)")
parser.add_argument('-startdate', '-s', help="Report stats starting on YYYY/MM/DD (optional)")
parser.add_argument('-enddate', '-e', help="Report stats up through YYYY/MM/DD inclusive (optional)")
args = parser.parse_args()

output_file = open(args.outfile,'w')

output_format = "CSV"
if args.format:
    if args.format == "TEXT":
        output_format = "TEXT"
        
if args.team:
    s_team = args.team
else:
    s_team = "ALL"
    
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
            print("Got here")
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
            text_string = build_text_output_string(game_info_headers,"Date,Tm,R,,Opp,R,In,WP,LP,Time,D/N,Start,Att,Comments")
            output_file.write("%s\n" % (text_string))
        else:
            output_file.write("Date,Tm,R,,Opp,R,In,WP,LP,Time,D/N,Start,Att,Comments\n")
        header_printed = True
        
    # TBD - if we supply a team, would like to track W-L record OF THAT TEAM, but then we need another header string
        
    stat_string = game_record.date + "," 
    
    # If we supply a team, put that team in the LEFT column, and use at or vs in between.
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
    
    # TBD: Could use winning and losing team names to make this code cleaner
    if game_record.winning_pitcher_pid in player_info[game_record.road_team]:
        stat_string += "," + player_info[game_record.road_team][game_record.winning_pitcher_pid]
    elif game_record.winning_pitcher_pid in player_info[game_record.home_team]:
        stat_string += "," + player_info[game_record.home_team][game_record.winning_pitcher_pid]
    else:
        stat_string += ",TBD"
    if game_record.losing_pitcher_pid in player_info[game_record.road_team]:
        stat_string += "," + player_info[game_record.road_team][game_record.losing_pitcher_pid]
    elif game_record.losing_pitcher_pid in player_info[game_record.home_team]:
        stat_string += "," + player_info[game_record.home_team][game_record.losing_pitcher_pid]
    else:
        stat_string += ",TBD"
        
    stat_string += "," + get_time_in_hr_min(game_record.time_of_game)
    stat_string += "," + game_record.daynight_game
    if game_record.start_time == "00:00PM":
        stat_string += "," # omit if 00:00
    else:
        stat_string += "," + game_record.start_time
    stat_string += "," + get_stat_as_string(game_record.attendance)
    stat_string += "," + game_record.comments

    if output_format == "TEXT":
        text_string = build_text_output_string(game_info_headers,stat_string)
        output_file.write("%s\n" % (text_string))
    else:
        output_file.write("%s\n" % (stat_string))


output_file.close()

print("Done - saved %s" % (args.outfile))
