#########################################################################
#
# Obtain player statistics from SQL Alchemy database.
#
# CC License: Attribution-NonCommercial 4.0 International (CC BY-NC 4.0)
# https://creativecommons.org/licenses/by-nc/4.0/
#
# References:
# https://www.retrosheet.org/eventfile.htm
# https://www.retrosheet.org/boxfile.txt
# 
#
#  1.0  MH  07/11/2019  Initial version
#
import argparse, csv, datetime, glob, re, sys
from collections import defaultdict
from bp_retrosheet_classes import BattingStats, PitchingStats, Base

DEBUG_ON = False

#########################################################################
#
# Stats dictionaries
#  
m_batting_stats = defaultdict()
m_pitching_stats = defaultdict()
m_batting_stats_counters = defaultdict()
m_pitching_stats_counters = defaultdict()

#########################################################################
#
# Functions to clear the stats dictionaries in between players.
#    

# Ordered in the same order that we will write them to the output files.
# Items in CAPS are calculated just prior to writing out the data.
list_of_batting_stats = ["games","ab","runs","hits","doubles","triples","hr","rbi","sb","cs","bb","strikeouts","BA","OBP","SLG","OPS","TB","gidp","hbp","sh","sf","ibb","int"]

def clear_batting_stats():
    for stat in list_of_batting_stats:
        m_batting_stats[stat] = 0
    
def clear_batting_stats_counters():
    for stat in list_of_batting_stats:
        m_batting_stats_counters[stat] = 0

# Ordered in the same order that we will write them to the output files.
# Items in CAPS are calculated just prior to writing out the data.
# "outs" is translated into IP.
list_of_pitching_stats = ["games_won","games_lost","WLPCT","ERA","games","games_started","outs","hits","runs","earned_runs","hr","walks","intentional_walks","strikeouts","hbp","balk","wp","bfp","WHIP","H9","HR9","BB9","SO9","SO/W"]        

def clear_pitching_stats():
    for stat in list_of_pitching_stats:
        m_pitching_stats[stat] = 0
    
def clear_pitching_stats_counters():
    for stat in list_of_pitching_stats:
        m_pitching_stats_counters[stat] = 0

#########################################################################
#
# Functions to update the stats dictionaries
#          

# stat_name is a string such as "ab" - must be present in list_of_batting_stats
# stat as integer is an integer value for that stat. If -1, the stat is missing for this game.
def update_batting_stat(stat_name,stat_as_integer):
    if stat_as_integer >= 0:
        m_batting_stats_counters[stat_name] += 1
        m_batting_stats[stat_name] += stat_as_integer
        
    # drop any -1 stats on the floor and do not adjust the season statistics.
    # The rationale for this is that we might be missing a stat for a game or
    # two and it useful to have the remaining total.
    
# stat_name is a string such as "strikeouts" - must be present in list_of_pitching_stats
# stat as integer is an integer value for that stat. If -1, the stat is missing for this game.
def update_pitching_stat(stat_name,stat_as_integer):
    if stat_as_integer >= 0:
        m_pitching_stats_counters[stat_name] += 1
        m_pitching_stats[stat_name] += stat_as_integer
        
    # drop any -1 stats on the floor and do not adjust the season statistics.
    # The rationale for this is that we might be missing a stat for a game or
    # two and it useful to have the remaining total.    
    
##########################################################
#
# Text output functions
#    
# Default is left-justified, use > for right-justified or ^ for centered.
# An extra space is added between all columns.
# Width should be typical max width of a statistic, plus an extra character for an asterisk for partial stats.
# Percentage stats, like batting average, could be 5 characters (1.000) though will typically be 4.
# Note that calculated stats will not have an asterisk.
batting_headers = ['30','16','>4','>4','>4','>4','>4','>4','>4','>4','>4','>4','>4','>4','>5','>5','>5','>5','>4','>4','>4','>4','>4','>4','>4','>4']
pitching_headers = ['30','16','>2','>2','>5','>6','>3','>3','>5','>3','>3','>3','>3','>3','>3','>3','>3','>3','>3','>3','>6','>5','>4','>4','>4','>4','>4']

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
    
# Determine if one or more stats are available for every game that this player played.
# If this returns False, at least one statistic is incomplete, and the caller may wish
# to omit this statistic from the output or mark it with an asterisk or a similar
# distiguishing mark.
def check_stat_completeness(the_stats_counter_dictionary,stats_array):
    for stat in stats_array:
        if the_stats_counter_dictionary[stat] != the_stats_counter_dictionary["games"]:
            return False
    return True
    
##########################################################
#
# Main program
#

parser = argparse.ArgumentParser(description='Obtain player stats from a SQL Alchemy database. Generates one file with statistics, and a second file with counts of the number of games where each statistic is available.') 
parser.add_argument('dbfile', help="DB file (input)")
parser.add_argument('outfile', help="Stats file (output)")
parser.add_argument('countersfile', help="Stats counters file (output)")
parser.add_argument('-format', '-f', help="Output format as CSV (default) or TEXT") 
parser.add_argument('-team', '-t', help="Team abbreviation or ALL for all teams (default)")
parser.add_argument('-opponent', '-o', help="Team abbreviation or ALL for all teams (default)")
parser.add_argument('-location', '-l', help="HOME, ROAD, or ALL (default)")
parser.add_argument('-startdate', '-s', help="Report stats starting on YYYY/MM/DD (optional)")
parser.add_argument('-enddate', '-e', help="Report stats up through YYYY/MM/DD inclusive (optional)")
args = parser.parse_args()

output_file = open(args.outfile,'w')
counters_file = open(args.countersfile,'w')

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

if output_format == "TEXT":    
    text_string = build_text_output_string(batting_headers,"Name,Team,G,AB,R,H,2B,3B,HR,RBI,SB,CS,BB,SO,BA,OBP,SLG,OPS,TB,GDP,HBP,SH,SF,IBB,INT")
    output_file.write("%s\n" % (text_string))
    counters_file.write("%s\n" % (text_string))
else:
    output_file.write("Name,Team,G,AB,R,H,2B,3B,HR,RBI,SB,CS,BB,SO,BA,OBP,SLG,OPS,TB,GDP,HBP,SH,SF,IBB,INT\n")
    counters_file.write("Name,Team,G,AB,R,H,2B,3B,HR,RBI,SB,CS,BB,SO,BA,OBP,SLG,OPS,TB,GDP,HBP,SH,SF,IBB,INT\n")
    
for player in session.query(BattingStats.pid).filter(*filters).distinct().order_by(BattingStats.pid).all():
    player_filters = []
    # "player" is actually a tuple of some sort, so the pid we want is at the first index
    player_filters.append(BattingStats.pid == player[0]) 
    if s_team != "ALL":
        player_filters.append(BattingStats.my_team == s_team)    
        
    if s_opponent != "ALL":   
        player_filters.append(BattingStats.opponent == s_opponent)
        
    if s_location == "HOME":
        player_filters.append(BattingStats.home == True)
    elif s_location == "ROAD":
        player_filters.append(BattingStats.road == True)
        
    if s_startdate != "NONE":
        player_filters.append(BattingStats.date_as_dt >= s_startdate)
        
    if s_enddate != "NONE":
        player_filters.append(BattingStats.date_as_dt <= s_enddate)
        
    count += 1
        
    clear_batting_stats()
    clear_batting_stats_counters()
    team_name_list = []
    for game_record in session.query(BattingStats).filter(*player_filters).order_by(BattingStats.date_as_dt,BattingStats.game_number_that_day):

        update_batting_stat("games",1)
        update_batting_stat("ab",game_record.ab)
        update_batting_stat("runs",game_record.runs)
        update_batting_stat("hits",game_record.hits)
        update_batting_stat("doubles",game_record.doubles)
        update_batting_stat("triples",game_record.triples)
        update_batting_stat("hr",game_record.hr)
        update_batting_stat("rbi",game_record.rbi)
        update_batting_stat("sh",game_record.sh)
        update_batting_stat("sf",game_record.sf)
        update_batting_stat("hbp",game_record.hbp)
        update_batting_stat("bb",game_record.bb)
        update_batting_stat("ibb",game_record.ibb)
        update_batting_stat("strikeouts",game_record.strikeouts)
        update_batting_stat("sb",game_record.sb)
        update_batting_stat("cs",game_record.cs)
        update_batting_stat("gidp",game_record.gidp)
        update_batting_stat("int",game_record.int)
        
        # For cases where we are not filtering on a single team, a player
        # could have played for multiple teams. So store the team(s) in an
        # array.
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
        
        
    slg_as_float = -1.0
    obp_as_float = -1.0
    
    # Build start of stat/counters output line.
    stat_string = "%s,%s," % (player_info[team_name_list[0]][game_record.pid],team_name_string)
    counters_string = stat_string
    for stat in list_of_batting_stats:
        if stat.isupper():
            # We need to do a calculation for this stat
            calculated = ""
            if stat == "BA":
                if check_stat_completeness(m_batting_stats_counters,["hits","ab"]):
                    calculated = get_pct_as_string(m_batting_stats["hits"],m_batting_stats["ab"],3,True)
            elif stat == "TB":
                if check_stat_completeness(m_batting_stats_counters,["hits","doubles","triples","hr"]):
                    calculated = str(m_batting_stats["hits"] + m_batting_stats["doubles"] + (m_batting_stats["triples"] * 2) + (m_batting_stats["hr"] * 3))
            elif stat == "SLG":
                if check_stat_completeness(m_batting_stats_counters,["ab","hits","doubles","triples","hr"]):
                    total_bases = m_batting_stats["hits"] + m_batting_stats["doubles"] + (m_batting_stats["triples"] * 2) + (m_batting_stats["hr"] * 3)
                    calculated = get_pct_as_string(total_bases,m_batting_stats["ab"],3,True)
                    slg_as_float = float(calculated)
            elif stat == "OBP": # (H + BB + HBP)/(At Bats + BB + HBP + SF)
                if check_stat_completeness(m_batting_stats_counters,["ab","hits","bb","hbp"]):
                    if m_batting_stats_counters["sf"] != m_batting_stats_counters["games"]:
                        sf_adjusted = 0 # allow missing SF since this was not always tracked
                    else:
                        sf_adjusted = m_batting_stats["sf"]
                    calculated = get_pct_as_string((m_batting_stats["hits"] + m_batting_stats["bb"] + m_batting_stats["hbp"]),(m_batting_stats["ab"] + m_batting_stats["hits"] + m_batting_stats["bb"] + m_batting_stats["hbp"] + sf_adjusted),3,True)
                    obp_as_float = float(calculated)
            elif stat == "OPS":
                if slg_as_float != -1.0 and obp_as_float != -1.0:
                    calculated = str(slg_as_float + obp_as_float).lstrip('0')
            
            stat_string = stat_string + calculated + ","
            # no counters for calculated stats
            counters_string = counters_string + ","
        else:
            if m_batting_stats_counters[stat] > 0:
                if check_stat_completeness(m_batting_stats_counters,[stat]):
                    stat_string = stat_string + str(m_batting_stats[stat]) + ","
                else:
                    # stat is incomplete, so mark with an asterisk
                    stat_string = stat_string + str(m_batting_stats[stat]) + "*,"
                counters_string = counters_string + str(m_batting_stats_counters[stat]) + ","
            else:
                stat_string = stat_string + ","
    
    if output_format == "TEXT":
        text_string = build_text_output_string(batting_headers,stat_string)
        output_file.write("%s\n" % (text_string))
        text_string = build_text_output_string(batting_headers,counters_string)
        counters_file.write("%s\n" % (text_string))
    else:
        output_file.write("%s\n" % (stat_string))
        counters_file.write("%s\n" % (counters_string))

# Blank row between batting and pitching stats        
output_file.write("\n")
counters_file.write("\n")
        
##########################################################
#
# Pitching stats
#    
count = 0

filters = []
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

##########################################################
#
# NTOE: There is some duplicate code in the pitching stats
# code that follows. Could modularize this in the future
# so we share code with the batting stats code above.
#
##########################################################

if output_format == "TEXT":    
    text_string = build_text_output_string(pitching_headers,"Name,Team,W,L,W-L%,ERA,G,GS,IP,H,R,ER,HR,BB,IBB,SO,HBP,BK,WP,BFP,WHIP,H9,HR9,BB9,SO9,SO/W")
    output_file.write("%s\n" % (text_string))
    counters_file.write("%s\n" % (text_string))
else:    
    output_file.write("Name,Team,W,L,W-L%,ERA,G,GS,IP,H,R,ER,HR,BB,IBB,SO,HBP,BK,WP,BFP,WHIP,H9,HR9,BB9,SO9,SO/W\n")
    counters_file.write("Name,Team,W,L,W-L%,ERA,G,GS,IP,H,R,ER,HR,BB,IBB,SO,HBP,BK,WP,BFP,WHIP,H9,HR9,BB9,SO9,SO/W\n")
    
for player in session.query(PitchingStats.pid).filter(*filters).distinct().order_by(PitchingStats.pid).all():
    player_filters = []
    # "player" is actually a tuple of some sort, so the pid we want is at the first index
    player_filters.append(PitchingStats.pid == player[0]) 
    if s_team != "ALL":
        player_filters.append(PitchingStats.my_team == s_team)    
        
    if s_opponent != "ALL":   
        player_filters.append(PitchingStats.opponent == s_opponent)
        
    if s_location == "HOME":
        player_filters.append(PitchingStats.home == True)
    elif s_location == "ROAD":
        player_filters.append(PitchingStats.road == True)
        
    if s_startdate != "NONE":
        player_filters.append(PitchingStats.date_as_dt >= s_startdate)
    elif s_enddate != "NONE":
        player_filters.append(PitchingStats.date_as_dt <= s_enddate)
        
    count += 1
        
    clear_pitching_stats()    
    clear_pitching_stats_counters()
    team_name_list = []
    for game_record in session.query(PitchingStats).filter(*player_filters).order_by(PitchingStats.date_as_dt,PitchingStats.game_number_that_day):
        update_pitching_stat("games",1)
        if game_record.starting_pitcher:
            update_pitching_stat("games_started",1)
        if game_record.winning_pitcher:
            update_pitching_stat("games_won",1)
        if game_record.losing_pitcher:
            update_pitching_stat("games_lost",1)
        update_pitching_stat("outs",game_record.outs) # will convert this to IP when we print
        update_pitching_stat("bfp",game_record.bfp)
        update_pitching_stat("hits",game_record.hits)
        update_pitching_stat("hr",game_record.hr)
        update_pitching_stat("runs",game_record.runs)
        update_pitching_stat("earned_runs",game_record.earned_runs)
        update_pitching_stat("walks",game_record.walks)
        update_pitching_stat("intentional_walks",game_record.intentional_walks)
        update_pitching_stat("strikeouts",game_record.strikeouts)
        update_pitching_stat("hbp",game_record.hbp)
        update_pitching_stat("wp",game_record.wp)
        update_pitching_stat("balk",game_record.balk)
# LIMITATION: Not available in 1938, and not listed in baseball-reference and other sites        
#        update_pitching_stat("doubles",game_record.doubles)
#        update_pitching_stat("triples",game_record.triples)
#        update_pitching_stat("sh",game_record.sh)
#        update_pitching_stat("sf",game_record.sf)
    
        # For cases where we are not filtering on a single team, a player
        # could have played for multiple teams. So store the team(s) in an
        # array.
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

                    
    # Build start of stat/counters output line.
    stat_string = "%s,%s," % (player_info[team_name_list[0]][game_record.pid],team_name_string)
    
    counter_string = stat_string
    for stat in list_of_pitching_stats:
        if stat.isupper():
            # We need to do a calculation for this stat
            calculated = ""
            if stat == "WLPCT":
                calculated = get_pct_as_string(m_pitching_stats["games_won"],(m_pitching_stats["games_won"] + m_pitching_stats["games_lost"]),3,True)
            elif stat == "ERA":
                if check_stat_completeness(m_pitching_stats_counters,["outs","earned_runs"]):
                    calculated = get_pct_as_string((9*m_pitching_stats["earned_runs"]),get_ip_as_float(m_pitching_stats["outs"]),3,False)
            elif stat == "WHIP":
                if check_stat_completeness(m_pitching_stats_counters,["outs","walks","hits"]):
                    calculated = get_pct_as_string((m_pitching_stats["walks"] + m_pitching_stats["hits"]),get_ip_as_float(m_pitching_stats["outs"]),3,False)
            elif stat == "H9":
                if check_stat_completeness(m_pitching_stats_counters,["hits"]):
                    calculated = get_pct_as_string((9*m_pitching_stats["hits"]),get_ip_as_float(m_pitching_stats["outs"]),1,False)
            elif stat == "HR9":
                if check_stat_completeness(m_pitching_stats_counters,["hr"]):
                    calculated = get_pct_as_string((9*m_pitching_stats["hr"]),get_ip_as_float(m_pitching_stats["outs"]),1,False)
            elif stat == "BB9":
                if check_stat_completeness(m_pitching_stats_counters,["walks"]):
                    calculated = get_pct_as_string((9*m_pitching_stats["walks"]),get_ip_as_float(m_pitching_stats["outs"]),1,False)
            elif stat == "SO9":
                if check_stat_completeness(m_pitching_stats_counters,["strikeouts"]):
                    calculated = get_pct_as_string((9*m_pitching_stats["strikeouts"]),get_ip_as_float(m_pitching_stats["outs"]),1,False)
            elif stat == "SO/W":
                if check_stat_completeness(m_pitching_stats_counters,["strikeouts","walks"]):
                    calculated = get_pct_as_string(m_pitching_stats["strikeouts"],m_pitching_stats["walks"],1,False)
            
            stat_string = stat_string + calculated + ","
            
            # No counters for calculated stats
            counter_string = counter_string + ","
        elif stat == "outs":
            # Convert to IP
            stat_string = stat_string + get_ip(m_pitching_stats[stat]) + ","
            counter_string = counter_string + str(m_pitching_stats_counters[stat]) + ","
        elif stat == "games_started" or stat == "games_won" or stat == "games_lost":
            stat_string = stat_string + str(m_pitching_stats[stat]) + ","
            # counters do not apply to these stats either
            counter_string = counter_string + ","
        else:
            # Include in output if we have that stat for at least one game
            if m_pitching_stats_counters[stat] > 0:
                if check_stat_completeness(m_pitching_stats_counters,[stat]):
                    stat_string = stat_string + str(m_pitching_stats[stat]) + ","
                else:
                    # stat is incomplete, so mark with an asterisk
                    stat_string = stat_string + str(m_pitching_stats[stat]) + "*,"
            else:
                stat_string = stat_string + ","
            counter_string = counter_string + str(m_pitching_stats_counters[stat]) + ","

    if output_format == "TEXT":    
        text_string = build_text_output_string(pitching_headers,stat_string)
        output_file.write("%s\n" % (text_string))
        text_string = build_text_output_string(pitching_headers,counter_string)
        counters_file.write("%s\n" % (text_string))
    else:
        output_file.write("%s\n" % (stat_string))
        counters_file.write("%s\n" % (counter_string))

counters_file.close()
output_file.close()

print("Done - saved %s and %s" % (args.outfile,args.countersfile))
