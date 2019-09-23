#########################################################################
#
# Obtain player games by position from SQL Alchemy database.
#
# CC License: Attribution-NonCommercial 4.0 International (CC BY-NC 4.0)
# https://creativecommons.org/licenses/by-nc/4.0/
#
# References:
# https://www.retrosheet.org/eventfile.htm
# https://www.retrosheet.org/boxfile.txt
# 
#
#  1.0  MH  08/18/2019  Initial version
#
import argparse, csv, datetime, glob, re, sys
from collections import defaultdict
from bp_retrosheet_classes import DefensiveStats, Base

DEBUG_ON = False

#########################################################################
#
# Stats dictionaries
#  
m_defensive_stats = defaultdict()

#########################################################################
#
# Functions to clear the stats dictionaries in between players.
#    

pos_strings = ['p','c','1b','2b','3b','ss','lf','cf','rf','dh','pr','ph']

def clear_m_defensive_stats():
    m_defensive_stats["TotalGames"] = 0
    for stat in pos_strings:
        m_defensive_stats[stat] = 0
    
##########################################################
#
# Text output functions
#    
# Default is left-justified, use > for right-justified or ^ for centered.
# An extra space is added between all columns.
defensive_position_headers = ['30','16','>4','>4','>4','>4','>4','>4','>4','>4','>4','>4','>4','>4','>4']

def build_text_output_string(format_widths_list,stats_strings_list):
    s = ""
    for count,stat in enumerate(stats_strings_list.split(",")):
        s = s + '{:{w}s}'.format(stat, w=format_widths_list[count]) + " "
    return s
    
##########################################################
#
# Main program
#

parser = argparse.ArgumentParser(description='Obtain player games by position from a SQL Alchemy database.') 
parser.add_argument('dbfile', help="DB file (input)")
parser.add_argument('outfile', help="Stats file (output)")
parser.add_argument('-format', '-f', help="Output format as CSV (default) or TEXT") 
parser.add_argument('-team', '-t', help="Team abbreviation or ALL for all teams (default)")
parser.add_argument('-opponent', '-o', help="Team abbreviation or ALL for all teams (default)")
parser.add_argument('-location', '-l', help="HOME, ROAD, or ALL (default)")
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

# read in all .ROS files so we can lookup pid and get full name
season = "1938"
list_of_teams = []    
    
# Read in all of the .ROS files up front so we can build dictionary of player ids and names, by team.
player_info = defaultdict(dict)
search_string = "*" + season + ".ROS"
    
list_of_roster_files = glob.glob(search_string)
for filename in list_of_roster_files:
    with open(filename,'r') as csvfile: # file is automatically closed when this block completes
        items = csv.reader(csvfile)
        for row in items:    
            # beanb101,Bean,Belve,R,R,MIN,X
            # Index by team abbrev, then player id, storing complete name WITHOUT quotes for easier printing
            player_info[row[5]][row[0]] = row[2] + " " + row[1]
            if row[5] not in list_of_teams:
                list_of_teams.append(row[5])

from sqlalchemy import create_engine
engine = create_engine('sqlite:///%s' % (args.dbfile), echo=False)
                       
from sqlalchemy.orm import sessionmaker
Session = sessionmaker(bind=engine)

session = Session() 

count = 0

filters = []
if s_team != "ALL":
    filters.append(DefensiveStats.my_team == s_team)
    
if s_opponent != "ALL":   
    filters.append(DefensiveStats.opponent == s_opponent)
    
if s_location == "HOME":
    filters.append(DefensiveStats.home == True)
elif s_location == "ROAD":
    filters.append(DefensiveStats.road == True)
    
if s_startdate != "NONE":
    filters.append(DefensiveStats.date_as_dt >= s_startdate)
    print("Stats beginning on %s" % (args.startdate))
    
if s_enddate != "NONE":
    filters.append(DefensiveStats.date_as_dt <= s_enddate)
    print("Stats through %s" % (args.enddate))
    
if output_format == "TEXT":    
    text_string = build_text_output_string(defensive_position_headers,"Name,Team,TOT,P,C,1B,2B,3B,SS,LF,CF,RF,DH,PR,PH")
    output_file.write("%s\n" % (text_string))
else:
    output_file.write("Name,Team,TOT,P,C,1B,2B,3B,SS,LF,CF,RF,DH,PR,PH\n")
    
for player in session.query(DefensiveStats.pid).filter(*filters).distinct().order_by(DefensiveStats.pid).all():
    player_filters = []
    # "player" is actually a tuple of some sort, so the pid we want is at the first index
    player_filters.append(DefensiveStats.pid == player[0]) 
    if s_team != "ALL":
        player_filters.append(DefensiveStats.my_team == s_team)    
        
    if s_opponent != "ALL":   
        player_filters.append(DefensiveStats.opponent == s_opponent)
        
    if s_location == "HOME":
        player_filters.append(DefensiveStats.home == True)
    elif s_location == "ROAD":
        player_filters.append(DefensiveStats.road == True)
        
    if s_startdate != "NONE":
        player_filters.append(DefensiveStats.date_as_dt >= s_startdate)
        
    if s_enddate != "NONE":
        player_filters.append(DefensiveStats.date_as_dt <= s_enddate)
        
    count += 1
        
    clear_m_defensive_stats()
    team_name_list = []
    for game_record in session.query(DefensiveStats).filter(*player_filters).order_by(DefensiveStats.date_as_dt,DefensiveStats.game_number_that_day):

        m_defensive_stats["TotalGames"] += 1

        if game_record.pitcher:
            m_defensive_stats['p'] += 1
        if game_record.catcher:
            m_defensive_stats['c'] += 1
        if game_record.first_base:
            m_defensive_stats['1b'] += 1
        if game_record.second_base:
            m_defensive_stats['2b'] += 1
        if game_record.third_base:
            m_defensive_stats['3b'] += 1
        if game_record.shortstop:
            m_defensive_stats['ss'] += 1
        if game_record.left_field:
            m_defensive_stats['lf'] += 1
        if game_record.center_field:
            m_defensive_stats['cf'] += 1
        if game_record.right_field:
            m_defensive_stats['rf'] += 1
        if game_record.designated_hitter:
            m_defensive_stats['dh'] += 1
        if game_record.pinch_runner:
            m_defensive_stats['pr'] += 1
        if game_record.pinch_hitter:
            m_defensive_stats['ph'] += 1
        
        # update list of teams this player played for
        if game_record.my_team not in team_name_list:
            team_name_list.append(game_record.my_team)
    
    # Now unpack the team_name_list array and build a "-" delimited string with each team name.
    if len(team_name_list) == 1:
        team_name_string = team_name_list[0]
    else:
        team_name_string = ""
        for team_count,team in enumerate(team_name_list):
            if team_count == 0:
                team_name_string = team
            else:
                team_name_string = team_name_string + "-" + team
        

    # Build start of stat output line.
    stat_string = "%s,%s,%s" % (player_info[team_name_list[0]][game_record.pid],team_name_string,str(m_defensive_stats["TotalGames"]))
    for p in pos_strings:
        stat_string += ",%s" % (str(m_defensive_stats[p]))
    
    if output_format == "TEXT":
        text_string = build_text_output_string(defensive_position_headers,stat_string)
        output_file.write("%s\n" % (text_string))
    else:
        output_file.write("%s\n" % (stat_string))

output_file.close()

print("Done - saved %s" % (args.outfile))
