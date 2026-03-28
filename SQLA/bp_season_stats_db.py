#########################################################################
#
# Obtain season stats for a team from the SQL Alchemy database.
# Team stats are the sum of the individual player stats.
#
# CC License: Attribution-NonCommercial 4.0 International (CC BY-NC 4.0)
# https://creativecommons.org/licenses/by-nc/4.0/
#
# References:
# https://www.retrosheet.org/eventfile.htm
# https://www.retrosheet.org/boxfile.txt
# 
#
#  1.0  MH  03/26/2026  Initial version
#
import argparse, csv, datetime, glob, re, sys
from collections import defaultdict
from bp_retrosheet_classes import BattingStats, DefensiveStats, PitchingStats, GameInfo, Base
from sqlalchemy import or_, and_
from bp_utils import bp_load_roster_files

DEBUG_ON = False

def get_stat_as_string(stat_as_integer):
    if stat_as_integer >= 0:
        return str(stat_as_integer)
    # drop any -1 stat values on the floor
    return ("")

def get_stat_as_int(stat_as_integer):
    if stat_as_integer >= 0:
        return stat_as_integer
    # drop any -1 stat values on the floor
    return (0)
    
##########################################################
#
# Text output functions
#    
# Default is left-justified, use > for right-justified or ^ for centered.
# An extra space is added between all columns.

# LIMITATION: For 1930's & 1940's minor league boxscores, batter walks are missing, so OBP calcuations are incorrect.

#                  Name,G,   AB,  R,   H,   2B,  3B,  HR,  RBI, SB,  CS,  BB,  IBB, SO,  TB,  BA,  SLG, OBP, GDP, HBP, SH,  SF,  INT
batting_headers = ['20','>3','>3','>3','>3','>3','>3','>3','>3','>3','>3','>3','>3','>3','>3','>5','>5','>5','>3','>3','>3','>3','>3']

#                  Name, W,   L,   G,  GS,  IP,  H,   R,   ER,  HR,  BB,  IBB, SO,  HBP, WP,  BFP"
pitching_headers = ['20','>3','>3','>3','>2','>5','>3','>3','>3','>3','>3','>3','>3','>3','>3','>3']

#                  Name,  P,   C,   1B, 2B,  3B,  SS,  LF,  CF,  RF,  DH,  PH,  PR"    
defensive_headers = ['20','>3','>3','>3','>3','>3','>3','>3','>3','>3','>3','>3','>3']

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

parser = argparse.ArgumentParser(description='Obtain season stats for a team from a SQL Alchemy database.') 
parser.add_argument('dbfile', help="DB file (input)")
parser.add_argument('outfile', help="Stats file (output)")
parser.add_argument('team', help="Team abbreviation")
parser.add_argument('-format', '-f', help="Output format as CSV (default) or TEXT") 
parser.add_argument('-opponent', '-o', help="Team abbreviation or ALL for all teams (default)")
parser.add_argument('-location', '-l', help="HOME, ROAD, or ALL (default)")
parser.add_argument('-startdate', '-s', help="Report stats starting on YYYY/MM/DD (optional)")
parser.add_argument('-enddate', '-e', help="Report stats up through YYYY/MM/DD inclusive (optional)")
args = parser.parse_args()

s_team = args.team

output_file = open(args.outfile,'w')

output_format = "CSV"
if args.format:
    if args.format == "TEXT":
        output_format = "TEXT"
        
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

# Read in all of the .ROS files up front
(player_info,list_of_teams) = bp_load_roster_files()

from sqlalchemy import create_engine
engine = create_engine('sqlite:///%s' % (args.dbfile), echo=False)
                       
from sqlalchemy.orm import sessionmaker
Session = sessionmaker(bind=engine)

session = Session() 

team_batting_stats = defaultdict(dict)
team_defensive_stats = defaultdict(dict)
team_pitching_stats = defaultdict(dict)

team_total_batting_stats = defaultdict()
team_total_pitching_stats = defaultdict()

team_total_batting_stats["games_played"]=0
team_total_batting_stats["ab"]=0
team_total_batting_stats["runs"] = 0
team_total_batting_stats["hits"] = 0
team_total_batting_stats["doubles"] = 0
team_total_batting_stats["triples"] = 0
team_total_batting_stats["hr"] = 0
team_total_batting_stats["rbi"] = 0
team_total_batting_stats["sb"] = 0
team_total_batting_stats["cs"] = 0
team_total_batting_stats["bb"] = 0
team_total_batting_stats["ibb"] = 0
team_total_batting_stats["strikeouts"] = 0
team_total_batting_stats["gidp"] = 0
team_total_batting_stats["hbp"] = 0
team_total_batting_stats["sh"] = 0
team_total_batting_stats["sf"] = 0
team_total_batting_stats["int"] = 0

team_total_pitching_stats["games_played"] = 0
team_total_pitching_stats["wins"] = 0
team_total_pitching_stats["losses"] = 0
team_total_pitching_stats["games_started"] = 0
team_total_pitching_stats["outs"] = 0
team_total_pitching_stats["hits"] = 0
team_total_pitching_stats["runs"] = 0
team_total_pitching_stats["earned_runs"] = 0
team_total_pitching_stats["hr"] = 0
team_total_pitching_stats["walks"] = 0
team_total_pitching_stats["intentional_walks"] = 0
team_total_pitching_stats["strikeouts"] = 0
team_total_pitching_stats["hbp"] = 0
team_total_pitching_stats["wp"] = 0
team_total_pitching_stats["bfp"] = 0


##########################################################
#
# Get total number of games for this team
#
# There is definitely a better way to do this... but this should work.
#
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

game_count = 0
for game_record in session.query(GameInfo).filter(*filters).order_by(GameInfo.date_as_dt,GameInfo.game_number_that_day):
    game_count += 1

team_total_batting_stats["games_played"] = game_count
team_total_pitching_stats["games_played"] = game_count


##########################################
#
# Main player loop
#
#

for playerid in player_info[s_team]:
    player_name = player_info[s_team][playerid]
    
    team_batting_stats[playerid]["games_played"]=0
    team_batting_stats[playerid]["ab"]=0
    team_batting_stats[playerid]["runs"] = 0
    team_batting_stats[playerid]["hits"] = 0
    team_batting_stats[playerid]["doubles"] = 0
    team_batting_stats[playerid]["triples"] = 0
    team_batting_stats[playerid]["hr"] = 0
    team_batting_stats[playerid]["rbi"] = 0
    team_batting_stats[playerid]["sb"] = 0
    team_batting_stats[playerid]["cs"] = 0
    team_batting_stats[playerid]["bb"] = 0
    team_batting_stats[playerid]["ibb"] = 0
    team_batting_stats[playerid]["strikeouts"] = 0
    team_batting_stats[playerid]["gidp"] = 0
    team_batting_stats[playerid]["hbp"] = 0
    team_batting_stats[playerid]["sh"] = 0
    team_batting_stats[playerid]["sf"] = 0
    team_batting_stats[playerid]["int"] = 0
    
    # omitting DH for now
    team_defensive_stats[playerid]["games_at_p"] = 0
    team_defensive_stats[playerid]["games_at_1b"] = 0
    team_defensive_stats[playerid]["games_at_2b"] = 0
    team_defensive_stats[playerid]["games_at_ss"] = 0
    team_defensive_stats[playerid]["games_at_3b"] = 0
    team_defensive_stats[playerid]["games_at_c"] = 0
    team_defensive_stats[playerid]["games_at_lf"] = 0
    team_defensive_stats[playerid]["games_at_cf"] = 0
    team_defensive_stats[playerid]["games_at_rf"] = 0
    team_defensive_stats[playerid]["games_at_ph"] = 0
    team_defensive_stats[playerid]["games_at_pr"] = 0


    # yes, this is overkill for non-pitchers, but it keeps the code simpler
    team_pitching_stats[playerid]["games_played"] = 0
    team_pitching_stats[playerid]["wins"] = 0
    team_pitching_stats[playerid]["losses"] = 0
    team_pitching_stats[playerid]["games_started"] = 0
    team_pitching_stats[playerid]["outs"] = 0
    team_pitching_stats[playerid]["hits"] = 0
    team_pitching_stats[playerid]["runs"] = 0
    team_pitching_stats[playerid]["earned_runs"] = 0
    team_pitching_stats[playerid]["hr"] = 0
    team_pitching_stats[playerid]["walks"] = 0
    team_pitching_stats[playerid]["intentional_walks"] = 0
    team_pitching_stats[playerid]["strikeouts"] = 0
    team_pitching_stats[playerid]["hbp"] = 0
    team_pitching_stats[playerid]["wp"] = 0
    team_pitching_stats[playerid]["bfp"] = 0

    ##########################################################
    #
    # Batting stats
    #
    filters = []

    filters.append(BattingStats.pid == playerid)

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
    
    for game_record in session.query(BattingStats).filter(*filters).order_by(BattingStats.date_as_dt,BattingStats.game_number_that_day):

        team_batting_stats[playerid]["games_played"] += 1
        team_batting_stats[playerid]["ab"] += get_stat_as_int(game_record.ab)
        team_batting_stats[playerid]["runs"] += get_stat_as_int(game_record.runs)
        team_batting_stats[playerid]["hits"] += get_stat_as_int(game_record.hits)
        team_batting_stats[playerid]["doubles"] += get_stat_as_int(game_record.doubles)
        team_batting_stats[playerid]["triples"] += get_stat_as_int(game_record.triples)
        team_batting_stats[playerid]["hr"] += get_stat_as_int(game_record.hr)
        team_batting_stats[playerid]["rbi"] += get_stat_as_int(game_record.rbi)
        team_batting_stats[playerid]["sb"] += get_stat_as_int(game_record.sb)
        team_batting_stats[playerid]["cs"] += get_stat_as_int(game_record.cs)
        team_batting_stats[playerid]["bb"] += get_stat_as_int(game_record.bb)
        team_batting_stats[playerid]["ibb"] += get_stat_as_int(game_record.ibb)
        team_batting_stats[playerid]["strikeouts"] += get_stat_as_int(game_record.strikeouts)
        team_batting_stats[playerid]["gidp"] += get_stat_as_int(game_record.gidp)
        team_batting_stats[playerid]["hbp"] += get_stat_as_int(game_record.hbp)
        team_batting_stats[playerid]["sh"] += get_stat_as_int(game_record.sh)
        team_batting_stats[playerid]["sf"] += get_stat_as_int(game_record.sf)
        team_batting_stats[playerid]["int"] += get_stat_as_int(game_record.int)

        team_total_batting_stats["ab"] += get_stat_as_int(game_record.ab)
        team_total_batting_stats["runs"] += get_stat_as_int(game_record.runs)
        team_total_batting_stats["hits"] += get_stat_as_int(game_record.hits)
        team_total_batting_stats["doubles"] += get_stat_as_int(game_record.doubles)
        team_total_batting_stats["triples"] += get_stat_as_int(game_record.triples)
        team_total_batting_stats["hr"] += get_stat_as_int(game_record.hr)
        team_total_batting_stats["rbi"] += get_stat_as_int(game_record.rbi)
        team_total_batting_stats["sb"] += get_stat_as_int(game_record.sb)
        team_total_batting_stats["cs"] += get_stat_as_int(game_record.cs)
        team_total_batting_stats["bb"] += get_stat_as_int(game_record.bb)
        team_total_batting_stats["ibb"] += get_stat_as_int(game_record.ibb)
        team_total_batting_stats["strikeouts"] += get_stat_as_int(game_record.strikeouts)
        team_total_batting_stats["gidp"] += get_stat_as_int(game_record.gidp)
        team_total_batting_stats["hbp"] += get_stat_as_int(game_record.hbp)
        team_total_batting_stats["sh"] += get_stat_as_int(game_record.sh)
        team_total_batting_stats["sf"] += get_stat_as_int(game_record.sf)
        team_total_batting_stats["int"] += get_stat_as_int(game_record.int)


    ##########################################################
    #
    # Defensive stats
    #
    filters = []

    filters.append(DefensiveStats.pid == playerid)

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
    
    for game_record in session.query(DefensiveStats).filter(*filters).order_by(DefensiveStats.date_as_dt,DefensiveStats.game_number_that_day):

        if game_record.pitcher:
            team_defensive_stats[playerid]["games_at_p"] += 1
        if game_record.first_base:
            team_defensive_stats[playerid]["games_at_1b"] += 1
        if game_record.second_base:
            team_defensive_stats[playerid]["games_at_2b"] += 1
        if game_record.shortstop:
            team_defensive_stats[playerid]["games_at_ss"] += 1
        if game_record.third_base:
            team_defensive_stats[playerid]["games_at_3b"] += 1
        if game_record.catcher:
            team_defensive_stats[playerid]["games_at_c"] += 1
        if game_record.left_field:
            team_defensive_stats[playerid]["games_at_lf"] += 1
        if game_record.center_field:
            team_defensive_stats[playerid]["games_at_cf"] += 1
        if game_record.right_field:
            team_defensive_stats[playerid]["games_at_rf"] += 1
        if game_record.pinch_hitter:
            team_defensive_stats[playerid]["games_at_ph"] += 1
        if game_record.pinch_runner:
            team_defensive_stats[playerid]["games_at_pr"] += 1
        
        
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

        if game_record.winning_pitcher:
            team_pitching_stats[playerid]["wins"] += 1
            team_total_pitching_stats["wins"] += 1

        if game_record.losing_pitcher:
            team_pitching_stats[playerid]["losses"] += 1
            team_total_pitching_stats["losses"] += 1

        if game_record.starting_pitcher:
            team_pitching_stats[playerid]["games_started"] += 1
            team_total_pitching_stats["games_started"] += 1
            
        team_pitching_stats[playerid]["games_played"] += 1
        team_pitching_stats[playerid]["outs"] += get_stat_as_int(game_record.outs)
        team_pitching_stats[playerid]["hits"] += get_stat_as_int(game_record.hits)
        team_pitching_stats[playerid]["runs"] += get_stat_as_int(game_record.runs)
        team_pitching_stats[playerid]["earned_runs"] += get_stat_as_int(game_record.earned_runs)
        team_pitching_stats[playerid]["hr"] += get_stat_as_int(game_record.hr)
        team_pitching_stats[playerid]["walks"] += get_stat_as_int(game_record.walks)
        team_pitching_stats[playerid]["intentional_walks"] += get_stat_as_int(game_record.intentional_walks)
        team_pitching_stats[playerid]["strikeouts"] += get_stat_as_int(game_record.strikeouts)
        team_pitching_stats[playerid]["hbp"] += get_stat_as_int(game_record.hbp)
        team_pitching_stats[playerid]["wp"] += get_stat_as_int(game_record.wp)
        team_pitching_stats[playerid]["bfp"] += get_stat_as_int(game_record.bfp)

        team_total_pitching_stats["outs"] += get_stat_as_int(game_record.outs)
        team_total_pitching_stats["hits"] += get_stat_as_int(game_record.hits)
        team_total_pitching_stats["runs"] += get_stat_as_int(game_record.runs)
        team_total_pitching_stats["earned_runs"] += get_stat_as_int(game_record.earned_runs)
        team_total_pitching_stats["hr"] += get_stat_as_int(game_record.hr)
        team_total_pitching_stats["walks"] += get_stat_as_int(game_record.walks)
        team_total_pitching_stats["intentional_walks"] += get_stat_as_int(game_record.intentional_walks)
        team_total_pitching_stats["strikeouts"] += get_stat_as_int(game_record.strikeouts)
        team_total_pitching_stats["hbp"] += get_stat_as_int(game_record.hbp)
        team_total_pitching_stats["wp"] += get_stat_as_int(game_record.wp)
        team_total_pitching_stats["bfp"] += get_stat_as_int(game_record.bfp)
                
        # LIMITATION: Not available in 1938, and not listed in baseball-reference and other sites: doubles, triples, sh, sf

###############################################
#
# Printing batting stats
# 
if output_format == "TEXT":    
    text_string = build_text_output_string(batting_headers,"NAME,G,AB,R,H,2B,3B,HR,RBI,SB,CS,BB,IBB,SO,TB,BA,OBP,SLG,GDP,HBP,SH,SF,INT")
    output_file.write("%s\n" % (text_string))
else:
    output_file.write("NAME,G,AB,R,H,2B,3B,HR,RBI,SB,CS,BB,IBB,SO,TB,BA,OBP,SLG,GDP,HBP,SH,SF,INT\n")

for playerid in team_batting_stats:
    if team_batting_stats[playerid]["games_played"] > 0:
        stat_string = "%s" % (player_info[s_team][playerid])
        stat_string += "," + get_stat_as_string(team_batting_stats[playerid]["games_played"])          
        stat_string += "," + get_stat_as_string(team_batting_stats[playerid]["ab"])
        stat_string += "," + get_stat_as_string(team_batting_stats[playerid]["runs"])
        stat_string += "," + get_stat_as_string(team_batting_stats[playerid]["hits"])
        stat_string += "," + get_stat_as_string(team_batting_stats[playerid]["doubles"])
        stat_string += "," + get_stat_as_string(team_batting_stats[playerid]["triples"])
        stat_string += "," + get_stat_as_string(team_batting_stats[playerid]["hr"])
        stat_string += "," + get_stat_as_string(team_batting_stats[playerid]["rbi"])
        stat_string += "," + get_stat_as_string(team_batting_stats[playerid]["sb"])
        stat_string += "," + get_stat_as_string(team_batting_stats[playerid]["cs"])
        stat_string += "," + get_stat_as_string(team_batting_stats[playerid]["bb"])
        stat_string += "," + get_stat_as_string(team_batting_stats[playerid]["ibb"])
        stat_string += "," + get_stat_as_string(team_batting_stats[playerid]["strikeouts"])

        total_bases = team_batting_stats[playerid]["hits"] + team_batting_stats[playerid]["doubles"] + (2 * team_batting_stats[playerid]["triples"]) + (3 * team_batting_stats[playerid]["hr"])
        stat_string += "," + get_stat_as_string(total_bases)
        
        batting_avg = get_pct_as_string(team_batting_stats[playerid]["hits"],team_batting_stats[playerid]["ab"],3,True)
        stat_string += "," + batting_avg
        
        batting_slg = get_pct_as_string(total_bases, team_batting_stats[playerid]["ab"],3,True)
        stat_string += "," + batting_slg

        batting_obp = get_pct_as_string((team_batting_stats[playerid]["hits"] + team_batting_stats[playerid]["bb"] + team_batting_stats[playerid]["hbp"]), (team_batting_stats[playerid]["ab"] + team_batting_stats[playerid]["bb"] + team_batting_stats[playerid]["hbp"] + team_batting_stats[playerid]["sf"]),3,True)
        stat_string += "," + batting_obp
        
        stat_string += "," + get_stat_as_string(team_batting_stats[playerid]["gidp"])
        stat_string += "," + get_stat_as_string(team_batting_stats[playerid]["hbp"])
        stat_string += "," + get_stat_as_string(team_batting_stats[playerid]["sh"])
        stat_string += "," + get_stat_as_string(team_batting_stats[playerid]["sf"])
        stat_string += "," + get_stat_as_string(team_batting_stats[playerid]["int"])            

        
        if output_format == "TEXT":
            text_string = build_text_output_string(batting_headers,stat_string)
            output_file.write("%s\n" % (text_string))
        else:
            output_file.write("%s\n" % (stat_string))

stat_string = "TEAM"
stat_string += "," + get_stat_as_string(team_total_batting_stats["games_played"])
stat_string += "," + get_stat_as_string(team_total_batting_stats["ab"])
stat_string += "," + get_stat_as_string(team_total_batting_stats["runs"])
stat_string += "," + get_stat_as_string(team_total_batting_stats["hits"])
stat_string += "," + get_stat_as_string(team_total_batting_stats["doubles"])
stat_string += "," + get_stat_as_string(team_total_batting_stats["triples"])
stat_string += "," + get_stat_as_string(team_total_batting_stats["hr"])
stat_string += "," + get_stat_as_string(team_total_batting_stats["rbi"])
stat_string += "," + get_stat_as_string(team_total_batting_stats["sb"])
stat_string += "," + get_stat_as_string(team_total_batting_stats["cs"])
stat_string += "," + get_stat_as_string(team_total_batting_stats["bb"])
stat_string += "," + get_stat_as_string(team_total_batting_stats["ibb"])
stat_string += "," + get_stat_as_string(team_total_batting_stats["strikeouts"])

total_bases = team_total_batting_stats["hits"] + team_total_batting_stats["doubles"] + (2 * team_total_batting_stats["triples"]) + (3 * team_total_batting_stats["hr"])
stat_string += "," + get_stat_as_string(total_bases)

batting_avg = get_pct_as_string(team_total_batting_stats["hits"],team_total_batting_stats["ab"],3,True)
stat_string += "," + batting_avg

batting_slg = get_pct_as_string(total_bases, team_total_batting_stats["ab"],3,True)
stat_string += "," + batting_slg

batting_obp = get_pct_as_string((team_total_batting_stats["hits"] + team_total_batting_stats["bb"] + team_total_batting_stats["hbp"]), (team_total_batting_stats["ab"] + team_total_batting_stats["bb"] + team_total_batting_stats["hbp"] + team_total_batting_stats["sf"]),3,True)
stat_string += "," + batting_obp

stat_string += "," + get_stat_as_string(team_total_batting_stats["gidp"])
stat_string += "," + get_stat_as_string(team_total_batting_stats["hbp"])
stat_string += "," + get_stat_as_string(team_total_batting_stats["sh"])
stat_string += "," + get_stat_as_string(team_total_batting_stats["sf"])
stat_string += "," + get_stat_as_string(team_total_batting_stats["int"])            

if output_format == "TEXT":
    text_string = build_text_output_string(batting_headers,stat_string)
    output_file.write("%s\n" % (text_string))
else:
    output_file.write("%s\n" % (stat_string))

output_file.write("\n\n")

###############################################
#
# Printing pitching stats
# 

if output_format == "TEXT":    
    text_string = build_text_output_string(pitching_headers,"NAME,W,L,G,GS,IP,H,R,ER,HR,BB,IBB,SO,HBP,WP,BFP")
    output_file.write("%s\n" % (text_string))
else:
    output_file.write("NAME,W,L,G,GS,IP,H,R,ER,HR,BB,IBB,SO,HBP,WP,BFP\n")
    
for playerid in team_pitching_stats:
    if team_pitching_stats[playerid]["games_played"] > 0:
        stat_string = "%s" % (player_info[s_team][playerid])
        stat_string += "," + get_stat_as_string(team_pitching_stats[playerid]["wins"])
        stat_string += "," + get_stat_as_string(team_pitching_stats[playerid]["losses"])
        stat_string += "," + get_stat_as_string(team_pitching_stats[playerid]["games_played"])
        stat_string += "," + get_stat_as_string(team_pitching_stats[playerid]["games_started"])
        
        stat_string += "," + get_ip(team_pitching_stats[playerid]["outs"])

        stat_string += "," + get_stat_as_string(team_pitching_stats[playerid]["hits"])
        stat_string += "," + get_stat_as_string(team_pitching_stats[playerid]["runs"])
        stat_string += "," + get_stat_as_string(team_pitching_stats[playerid]["earned_runs"])
        stat_string += "," + get_stat_as_string(team_pitching_stats[playerid]["hr"])
        stat_string += "," + get_stat_as_string(team_pitching_stats[playerid]["walks"])
        stat_string += "," + get_stat_as_string(team_pitching_stats[playerid]["intentional_walks"])
        stat_string += "," + get_stat_as_string(team_pitching_stats[playerid]["strikeouts"])
        stat_string += "," + get_stat_as_string(team_pitching_stats[playerid]["hbp"])
        stat_string += "," + get_stat_as_string(team_pitching_stats[playerid]["wp"])
        stat_string += "," + get_stat_as_string(team_pitching_stats[playerid]["bfp"])
        # TBD - add WHIP, ERA when we have earned run data
        
        
        if output_format == "TEXT":
            text_string = build_text_output_string(pitching_headers,stat_string)
            output_file.write("%s\n" % (text_string))
        else:
            output_file.write("%s\n" % (stat_string))


stat_string = "TEAM"
stat_string += "," + get_stat_as_string(team_total_pitching_stats["wins"])
stat_string += "," + get_stat_as_string(team_total_pitching_stats["losses"])
stat_string += "," + get_stat_as_string(team_total_pitching_stats["games_played"])
stat_string += "," + get_stat_as_string(team_total_pitching_stats["games_started"])

stat_string += "," + get_ip(team_total_pitching_stats["outs"])

stat_string += "," + get_stat_as_string(team_total_pitching_stats["hits"])
stat_string += "," + get_stat_as_string(team_total_pitching_stats["runs"])
stat_string += "," + get_stat_as_string(team_total_pitching_stats["earned_runs"])
stat_string += "," + get_stat_as_string(team_total_pitching_stats["hr"])
stat_string += "," + get_stat_as_string(team_total_pitching_stats["walks"])
stat_string += "," + get_stat_as_string(team_total_pitching_stats["intentional_walks"])
stat_string += "," + get_stat_as_string(team_total_pitching_stats["strikeouts"])
stat_string += "," + get_stat_as_string(team_total_pitching_stats["hbp"])
stat_string += "," + get_stat_as_string(team_total_pitching_stats["wp"])
stat_string += "," + get_stat_as_string(team_total_pitching_stats["bfp"])
# TBD - add WHIP, ERA


if output_format == "TEXT":
    text_string = build_text_output_string(pitching_headers,stat_string)
    output_file.write("%s\n" % (text_string))
else:
    output_file.write("%s\n" % (stat_string))
            
output_file.write("\n\n")


###############################################
#
# Printing defensive stats
# 
if output_format == "TEXT":    
    text_string = build_text_output_string(defensive_headers,"NAME,P,C,1B,2B,3B,SS,LF,CF,RF,DH,PH,PR")
    output_file.write("%s\n" % (text_string))
else:
    output_file.write("NAME,P,C,1B,2B,3B,SS,LF,CF,RF,DH,PH,PR\n")
    
for playerid in team_defensive_stats:
    stat_string = "%s" % (player_info[s_team][playerid])
    stat_string += "," + get_stat_as_string(team_defensive_stats[playerid]["games_at_p"])
    stat_string += "," + get_stat_as_string(team_defensive_stats[playerid]["games_at_c"])
    stat_string += "," + get_stat_as_string(team_defensive_stats[playerid]["games_at_1b"])
    stat_string += "," + get_stat_as_string(team_defensive_stats[playerid]["games_at_2b"])
    stat_string += "," + get_stat_as_string(team_defensive_stats[playerid]["games_at_3b"])
    stat_string += "," + get_stat_as_string(team_defensive_stats[playerid]["games_at_ss"])
    stat_string += "," + get_stat_as_string(team_defensive_stats[playerid]["games_at_lf"])
    stat_string += "," + get_stat_as_string(team_defensive_stats[playerid]["games_at_cf"])
    stat_string += "," + get_stat_as_string(team_defensive_stats[playerid]["games_at_rf"])
    stat_string += "," + get_stat_as_string(0) # DH
    stat_string += "," + get_stat_as_string(team_defensive_stats[playerid]["games_at_ph"])
    stat_string += "," + get_stat_as_string(team_defensive_stats[playerid]["games_at_pr"])

    if output_format == "TEXT":    
        text_string = build_text_output_string(defensive_headers,stat_string)
        output_file.write("%s\n" % (text_string))
    else:
        output_file.write("%s\n" % (stat_string))
            

output_file.close()

print("Done - saved %s" % (args.outfile))

