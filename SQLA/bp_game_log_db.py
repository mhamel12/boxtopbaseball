#########################################################################
#
# Obtain game logs for a player from the SQL Alchemy database.
#
# CC License: Attribution-NonCommercial 4.0 International (CC BY-NC 4.0)
# https://creativecommons.org/licenses/by-nc/4.0/
#
# References:
# https://www.retrosheet.org/eventfile.htm
# https://www.retrosheet.org/boxfile.txt
# 
#
#  1.0  MH  07/17/2019  Initial version
#
import argparse, csv, datetime, glob, re, sys
from collections import defaultdict
from bp_retrosheet_classes import BattingStats, PitchingStats, Base

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

# Date,Team,,Opp,AB,R,H,2B,3B,HR,RBI,SB,CS,BB,IBB,SO,TB,GDP,HBP,SH,SF,INT
batting_headers = ['10','3','2','3','>3','>3','>3','>3','>3','>3','>3','>3','>3','>3','>3','>3','>3','>3','>3','>3','>3','>3']
# Date,Team,,Opp,W,L,GS,IP,H,R,ER,HR,BB,IBB,SO,HBP,BK,WP,BFP"
pitching_headers = ['10','3','2','3','>2','>2','>2','>3','>3','>3','>3','>3','>3','>3','>3','>3','>3','>3','>3']

def build_text_output_string(format_widths_list,stats_strings_list):
    s = ""
    for count,stat in enumerate(stats_strings_list.split(",")):
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
    
##########################################################
#
# Main program
#

parser = argparse.ArgumentParser(description='Obtain player game log from a SQL Alchemy database.') 
parser.add_argument('dbfile', help="DB file (input)")
parser.add_argument('outfile', help="Stats file (output)")
parser.add_argument('player', help="Retrosheet-style id or player name. In the case of duplicate names, the script will print the corresponding id's and then return.")
parser.add_argument('-format', '-f', help="Output format as CSV (default) or TEXT") 
parser.add_argument('-team', '-t', help="Team abbreviation or ALL for all teams (default)")
parser.add_argument('-opponent', '-o', help="Team abbreviation or ALL for all teams (default)")
parser.add_argument('-location', '-l', help="HOME, ROAD, or ALL (default)")
parser.add_argument('-startdate', '-s', help="Report stats starting on YYYY/MM/DD (optional)")
parser.add_argument('-enddate', '-e', help="Report stats up through YYYY/MM/DD inclusive (optional)")
args = parser.parse_args()

output_file = open(args.outfile,'w')

playerid = args.player # TBD - not yet supporting 'name' option

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

# read in all .ROS files so we can lookup pid and get full name
season = "1938"
list_of_teams = []    
    
# Read in all of the .ROS files up front so we can find player name
player_info = defaultdict(dict)
search_string = "*" + season + ".ROS"
    
player_name = ""
list_of_roster_files = glob.glob(search_string)
for filename in list_of_roster_files:
    with open(filename,'r') as csvfile: # file is automatically closed when this block completes
        items = csv.reader(csvfile)
        for row in items:    
            # beanb101,Bean,Belve,R,R,MIN,X
            if playerid == row[0]:
                player_name = row[2] + " " + row[1]
                
from sqlalchemy import create_engine
engine = create_engine('sqlite:///%s' % (args.dbfile), echo=False)
                       
from sqlalchemy.orm import sessionmaker
Session = sessionmaker(bind=engine)

session = Session() 

count = 0

filters = []

filters.append(BattingStats.pid == playerid)

if s_team != "ALL":
    filters.append(BattingStats.my_team == s_team)
    
if s_opponent != "ALL":   
    filters.append(BattingStats.opponent == s_opponent)
    
if s_location == "HOME":
    filters.append(BattingStats.home == True)
elif s_location == "ROAD":
    filters.append(BattingStats.road == True)
    
if s_startdate != "NONE":
    filters.append(BattingStats.date_as_dt >= s_startdate)
    print("Stats beginning on %s" % (args.startdate))
   
if s_enddate != "NONE":
    filters.append(BattingStats.date_as_dt <= s_enddate)
    print("Stats through %s" % (args.enddate))
    
##########################################################
#
# Batting stats
#    

header_printed = False    
for game_record in session.query(BattingStats).filter(*filters).order_by(BattingStats.date_as_dt,BattingStats.game_number_that_day):
    count += 1
    if not header_printed:
        if output_format == "TEXT":    
            output_file.write("%s\n" % (player_name))
            text_string = build_text_output_string(batting_headers,"Date,Tm,,Opp,AB,R,H,2B,3B,HR,RBI,SB,CS,BB,IBB,SO,GDP,HBP,SH,SF,INT")
            output_file.write("%s\n" % (text_string))
        else:
            output_file.write("Date,Tm,,Opp,AB,R,H,2B,3B,HR,RBI,SB,CS,BB,IBB,SO,GDP,HBP,SH,SF,INT\n")
        header_printed = True
        
    stat_string = game_record.date + "," + game_record.my_team
    if game_record.home:
        stat_string += ",vs"
    else:
        stat_string += ",at"
    stat_string += "," + game_record.opponent
    stat_string += "," + get_stat_as_string(game_record.ab)
    stat_string += "," + get_stat_as_string(game_record.runs)
    stat_string += "," + get_stat_as_string(game_record.hits)
    stat_string += "," + get_stat_as_string(game_record.doubles)
    stat_string += "," + get_stat_as_string(game_record.triples)
    stat_string += "," + get_stat_as_string(game_record.hr)
    stat_string += "," + get_stat_as_string(game_record.rbi)
    stat_string += "," + get_stat_as_string(game_record.sb)
    stat_string += "," + get_stat_as_string(game_record.cs)
    stat_string += "," + get_stat_as_string(game_record.bb)
    stat_string += "," + get_stat_as_string(game_record.ibb)
    stat_string += "," + get_stat_as_string(game_record.strikeouts)
    stat_string += "," + get_stat_as_string(game_record.gidp)
    stat_string += "," + get_stat_as_string(game_record.hbp)
    stat_string += "," + get_stat_as_string(game_record.sh)
    stat_string += "," + get_stat_as_string(game_record.sf)
    stat_string += "," + get_stat_as_string(game_record.int)

    if output_format == "TEXT":
        text_string = build_text_output_string(batting_headers,stat_string)
        output_file.write("%s\n" % (text_string))
    else:
        output_file.write("%s\n" % (stat_string))

# Blank row between batting and pitching stats        
output_file.write("\n")
        
##########################################################
#
# Pitching stats
#    
filters = []

filters.append(PitchingStats.pid == playerid)

if s_team != "ALL":
    filters.append(PitchingStats.my_team == s_team)
    
if s_opponent != "ALL":   
    filters.append(PitchingStats.opponent == s_opponent)

if s_location == "HOME":
    filters.append(PitchingStats.home == True)
elif s_location == "ROAD":
    filters.append(PitchingStats.road == True)

if s_startdate != "NONE":
    filters.append(PitchingStats.date_as_dt >= s_startdate)

if s_enddate != "NONE":
    filters.append(PitchingStats.date_as_dt <= s_enddate)
    
header_printed = False    
for game_record in session.query(PitchingStats).filter(*filters).order_by(PitchingStats.date_as_dt,PitchingStats.game_number_that_day):
    if not header_printed:
        if output_format == "TEXT":    
            output_file.write("%s\n" % (player_name))
            text_string = build_text_output_string(pitching_headers,"Date,Tm,,Opp,W,L,GS,IP,H,R,ER,HR,BB,IBB,SO,HBP,BK,WP,BFP")
            output_file.write("%s\n" % (text_string))
        else:    
            output_file.write("Date,Tm,,Opp,W,L,GS,IP,H,R,ER,HR,BB,IBB,SO,HBP,BK,WP,BFP\n")
        header_printed = True
    
    stat_string = game_record.date + "," + game_record.my_team
    if game_record.home:
        stat_string += ",vs"
    else:
        stat_string += ",at"
    stat_string += "," + game_record.opponent
    if game_record.winning_pitcher:
        stat_string += ",1"
    else:
        stat_string += ",0"
    if game_record.losing_pitcher:
        stat_string += ",1"
    else:
        stat_string += ",0"
    if game_record.starting_pitcher:
        stat_string += ",1"
    else:
        stat_string += ",0"
    stat_string += "," + get_ip(game_record.outs)
    stat_string += "," + get_stat_as_string(game_record.hits)
    stat_string += "," + get_stat_as_string(game_record.runs)
    stat_string += "," + get_stat_as_string(game_record.earned_runs)
    stat_string += "," + get_stat_as_string(game_record.hr)
    stat_string += "," + get_stat_as_string(game_record.walks)
    stat_string += "," + get_stat_as_string(game_record.intentional_walks)
    stat_string += "," + get_stat_as_string(game_record.strikeouts)
    stat_string += "," + get_stat_as_string(game_record.hbp)
    stat_string += "," + get_stat_as_string(game_record.wp)
    stat_string += "," + get_stat_as_string(game_record.bfp)
# LIMITATION: Not available in 1938, and not listed in baseball-reference and other sites: doubles, triples, sh, sf
    
    if output_format == "TEXT":    
        text_string = build_text_output_string(pitching_headers,stat_string)
        output_file.write("%s\n" % (text_string))
    else:
        output_file.write("%s\n" % (stat_string))

output_file.close()

print("Done - saved %s" % (args.outfile))
