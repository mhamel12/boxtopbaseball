#########################################################################
#
# Loads player statistics from a Retrosheet Event file into a SQL Alchemy database.
# Proof-of-concept, tailored specifically for 1938 American Assocation and 
# 1921-1924 Eastern League box scores.
#
# CC License: Attribution-NonCommercial 4.0 International (CC BY-NC 4.0)
# https://creativecommons.org/licenses/by-nc/4.0/
#
# References:
# https://www.retrosheet.org/eventfile.htm
# https://www.retrosheet.org/boxfile.txt
# 
#
#  1.0  MH  07/08/2019  Initial version
#
import argparse, csv, datetime, glob
from collections import defaultdict
from bp_retrosheet_classes import BattingStats, PitchingStats, GameInfo, DefensiveStats, Base

DEBUG_ON = False

# Retrosheet road/home id numbers, used for "side" values in .EBx files
ROAD_ID = 0
HOME_ID = 1

defensive_positions = defaultdict(dict)
defensive_dlines = defaultdict(dict)
pinch_hitters = defaultdict(dict)
pinch_runners = defaultdict(dict)

def clear_defensive_info():
    defensive_positions["road"] = defaultdict()
    defensive_positions["home"] = defaultdict()
    pinch_hitters["road"] = defaultdict()
    pinch_hitters["home"] = defaultdict()
    pinch_runners["road"] = defaultdict()
    pinch_runners["home"] = defaultdict()
    defensive_dlines["road"] = defaultdict()
    defensive_dlines["home"] = defaultdict()

# borrowed from bp_generate_box.py    
pos_strings = ['','p','c','1b','2b','3b','ss','lf','cf','rf','dh','pr','ph']
def get_positions(tm,id):
    pos_string = ""
    
    if id in pinch_hitters[tm]:
        pos_string = "ph"
    elif id in pinch_runners[tm]:
        pos_string = "pr"
    
    if id in defensive_positions[tm]:
        for pos in defensive_positions[tm][id]:
            pos_number = int(pos)
            # sanity check position number so we don't run over the end of the list
            if pos_number >= len(pos_strings):
                pos_number = 0
                print("WARNING: Bogus position number (%s %s %s)" % (tm,id,pos))
            if pos_string == "":
                pos_string += pos_strings[pos_number]
            else:
                pos_string += "-" + pos_strings[pos_number]
                
    return pos_string
    
def add_defensive_info(game_info):

    for tm in ("road","home"):
        
        # Get all ids which appear in these three dictionaries
        id_list = list(defensive_positions[tm].keys()) + list(pinch_hitters[tm].keys()) + list(pinch_runners[tm].keys())
        # Eliminate the duplicates
        id_list = set(id_list)
        
        for id in id_list:
            m_defense = DefensiveStats()
            m_defense.date = game_info.date
            m_defense.date_as_dt = game_info.date_as_dt
            m_defense.game_number_that_day = game_info.game_number_that_day
            m_defense.pid = id
            
            m_defense.position_list = get_positions(tm,id)
            
            if tm == "road":
                m_defense.road = True
                m_defense.home = False
                m_defense.my_team = road_team
                m_defense.opponent = home_team
                
            elif tm == "home":
                m_defense.home = True
                m_defense.road = False
                m_defense.my_team = home_team
                m_defense.opponent = road_team

            # Fill in each of the following based on whether it exists in the m_defense.position_list
            # By default, they are all set to False - see the class definition.
            if m_defense.position_list.count("-") > 0:
                position_array = m_defense.position_list.split("-")
            else:
                position_array = [m_defense.position_list]
               
            if 'p' in position_array:
                m_defense.pitcher = True
            if 'c' in position_array:
                m_defense.catcher = True
            if '1b' in position_array:
                m_defense.first_base = True
            if '2b' in position_array:
                m_defense.second_base = True
            if '3b' in position_array:
                m_defense.third_base = True
            if 'ss' in position_array:
                m_defense.shortstop = True
            if 'lf' in position_array:
                m_defense.left_field = True
            if 'cf' in position_array:
                m_defense.center_field = True
            if 'rf' in position_array:
                m_defense.right_field = True
            if 'dh' in position_array:
                m_defense.designated_hitter = True
            if 'pr' in position_array:
                m_defense.pinch_runner = True
            if 'ph' in position_array:
                m_defense.pinch_hitter = True
            
            session.add(m_defense)
    
##########################################################
#
# Main program
#

parser = argparse.ArgumentParser(description='Load player stats from a Retrosheet event file into a SQL Alchemy database.') 
parser.add_argument('file', help="Event file (input)")
parser.add_argument('dbfile', help="DB file (output)")
args = parser.parse_args()

from sqlalchemy import create_engine
engine = create_engine('sqlite:///%s' % (args.dbfile), echo=False)
                       
# create all tables in database
Base.metadata.create_all(engine)
                       
from sqlalchemy.orm import sessionmaker
Session = sessionmaker(bind=engine)

session = Session() 

number_of_box_scores_scanned = 0
game_info = GameInfo()
game_info.comments = ""

clear_defensive_info()

# main loop
with open(args.file,'r') as efile:
    # We could use csv library, but I worry about reading very large files.
    for line in efile:
        line = line.rstrip()
        if line.count(",") > 0:
            line_type = line.split(",")[0]
            
            if line_type == "version":  # sentinel that always starts a new box score
                if number_of_box_scores_scanned > 0:
                    add_defensive_info(game_info)
                    session.add(game_info)
                    game_info = GameInfo()
                    game_info.comments = ""
                    clear_defensive_info()
                number_of_box_scores_scanned += 1
            
            # LIMTATION: these lines must appear in the .EBx file before any of the stats.
            elif line_type == "info":
                info_type = line.split(",")[1]
                if info_type == "visteam":
                    road_team = line.split(",")[2]
                    game_info.road_team = road_team
                elif info_type == "hometeam":
                    home_team = line.split(",")[2]
                    game_info.home_team = home_team
                elif info_type == "date":
                    s_date_of_game = line.split(",")[2]
                    game_info.date = s_date_of_game
                    game_info.date_as_dt = datetime.datetime.strptime(s_date_of_game, '%Y/%m/%d')
                elif info_type == "number":
                    s_game_number_this_date = line.split(",")[2]
                    game_info.game_number_that_day = s_game_number_this_date
                elif info_type == "wp":
                    s_winning_pitcher_pid = line.split(",")[2]
                    game_info.winning_pitcher_pid = s_winning_pitcher_pid
                elif info_type == "lp":
                    s_losing_pitcher_pid = line.split(",")[2]
                    game_info.losing_pitcher_pid = s_losing_pitcher_pid
                elif info_type == "starttime":
                    game_info.start_time = line.split(",")[2]
                elif info_type == "timeofgame":
                    game_info.time_of_game = line.split(",")[2]
                elif info_type == "attendance":
                    game_info.attendance = line.split(",")[2]
                elif info_type == "daynight":
                    dn = line.split(",")[2]
                    if dn == "day":
                        game_info.daynight_game = "D"
                    elif dn == "night":
                        game_info.daynight_game = "N"
                    else:
                        game_info.daynight_game = "U"
            
            elif line_type == "com":
                if len(game_info.comments) > 0:
                    # split only on first comma so we keep any in the comment
                    game_info.comments += ";" + line.split(",",1)[1]
                else:
                    game_info.comments = line.split(",",1)[1]
            
            elif line_type == "line":
                # linescore
                innings = line.split(",")[2:]
                total_runs = 0
                for single_inning in innings:
                    total_runs += int(single_inning)

                side = int(line.split(",")[1])
                if side == ROAD_ID:
                    game_info.road_team_runs = total_runs
                    game_info.innings = len(innings) # road team must play >= innings played by the home team
                else:
                    game_info.home_team_runs = total_runs
            
            elif line_type == "stat":
                sub_line_type = line.split(",")[1]
                if sub_line_type == "bline":
                    stats = BattingStats()
                    stats.date = s_date_of_game
                    stats.date_as_dt = datetime.datetime.strptime(s_date_of_game, '%Y/%m/%d')
                    stats.game_number_that_day = s_game_number_this_date
                    
                    # stat,bline,id,side,pos,seq,ab,r,h,2b,3b,hr,rbi,sh,sf,hbp,bb,ibb,k,sb,cs,gidp,int
                    side = int(line.split(",")[3])
                    if side == ROAD_ID:
                        stats.home = False
                        stats.road = True
                        stats.my_team = road_team
                        stats.opponent = home_team
                    else:
                        stats.home = True
                        stats.road = False
                        stats.my_team = home_team
                        stats.opponent = road_team
                    
                    stats.pid = line.split(",")[2]
                    stats.batting_order_number = line.split(",")[4]
                    stats.sequence_number = line.split(",")[5]
                    stats.ab = int(line.split(",")[6])
                    stats.runs = int(line.split(",")[7])
                    stats.hits = int(line.split(",")[8])
                    stats.doubles = int(line.split(",")[9])
                    stats.triples = int(line.split(",")[10])
                    stats.hr = int(line.split(",")[11])
                    stats.rbi = int(line.split(",")[12])
                    stats.sh = int(line.split(",")[13])
                    stats.sf = int(line.split(",")[14]) # Not used in 1938
                    stats.hbp = int(line.split(",")[15])
                    stats.bb = int(line.split(",")[16])
                    stats.ibb = int(line.split(",")[17])
                    stats.strikeouts = int(line.split(",")[18])
                    stats.sb = int(line.split(",")[19])
                    stats.cs = int(line.split(",")[20]) # Not available in 1938 boxes
                    stats.gidp = int(line.split(",")[21]) # Not available in 1938 boxes
                    stats.int = int(line.split(",")[22]) # Not available in 1938 boxes                    
                    session.add(stats)
                    
                elif sub_line_type == "pline":
                    stats = PitchingStats()
                    stats.date = s_date_of_game
                    stats.date_as_dt = datetime.datetime.strptime(s_date_of_game, '%Y/%m/%d')
                    stats.game_number_that_day = s_game_number_this_date
                    
                    # stat,pline,id,side,seq,ip*3,no-out,bfp,h,2b,3b,hr,r,er,bb,ibb,k,hbp,wp,balk,sh,sf
                    side = int(line.split(",")[3])
                    if side == ROAD_ID:
                        stats.home = False
                        stats.road = True
                        stats.my_team = road_team
                        stats.opponent = home_team
                    else:
                        stats.home = True
                        stats.road = False
                        stats.my_team = home_team
                        stats.opponent = road_team
                    
                    stats.pid = line.split(",")[2]
                    stats.sequence_number = line.split(",")[4]
                    
                    if stats.pid == s_winning_pitcher_pid:
                        stats.winning_pitcher = True
                    else:
                        stats.winning_pitcher = False
                    if stats.pid == s_losing_pitcher_pid:
                        stats.losing_pitcher = True
                    else:
                        stats.losing_pitcher = False
                        
                    seq = int(line.split(",")[4])
                    if seq == 0:
                        stats.starting_pitcher = True
                    else:
                        stats.starting_pitcher = False
                        
                    stats.outs = int(line.split(",")[5])
                    stats.bfp = int(line.split(",")[7])
                    stats.hits = int(line.split(",")[8])
                    stats.doubles = int(line.split(",")[9])
                    stats.triples = int(line.split(",")[10])
                    stats.hr = int(line.split(",")[11])
                    stats.runs = int(line.split(",")[12])
                    stats.earned_runs = int(line.split(",")[13])
                    stats.walks = int(line.split(",")[14])
                    stats.intentional_walks = int(line.split(",")[15])
                    stats.strikeouts = int(line.split(",")[16])
                    stats.hbp = int(line.split(",")[17])
                    stats.wp = int(line.split(",")[18])
                    stats.balk = int(line.split(",")[19])
                    stats.sh = int(line.split(",")[20])
                    stats.sf = int(line.split(",")[21])

                    session.add(stats)
                    
                elif sub_line_type == "phline":
                    # stat,phline,id,inning,side,ab,r,h,2b,3b,hr,rbi,sh,sf,hbp,bb,ibb,k,sb,cs,gidp,int
                    side = int(line.split(",")[4])
                    if side == ROAD_ID:
                        lookup = "road"
                    else:
                        lookup = "home"
                    id = line.split(",")[2] 
                    pinch_hitters[lookup][id] = line.split(",")[3] # save inning for now in case we want to use it
                    
                elif sub_line_type == "prline":
                    # stat,prline,id,inning,side,r,sb,cs
                    side = int(line.split(",")[4])
                    if side == ROAD_ID:
                        lookup = "road"
                    else:
                        lookup = "home"
                    id = line.split(",")[2] 
                    pinch_runners[lookup][id] = line.split(",")[3] # save inning for now in case we want to use it                
                
                elif sub_line_type == "dline":
                    # stat,dline,id,side,seq,pos,if*3,po,a,e,dp,tp,pb
                    side = int(line.split(",")[3])
                    if side == ROAD_ID:
                        lookup = "road"
                    else:
                        lookup = "home"

                    id = line.split(",")[2]
                    # LIMITATION:
                    # If player has multiple dlines, only the first one will contain valid defensive
                    # statistics because we do not have defensive stats for specific positions.
                    # So drop any other lines on the floor.
                    if id not in defensive_dlines[lookup]:
                        defensive_dlines[lookup][id] = line.split(",")[2:]
                    
                    # We use a separate dictionary to track positions.
                    # Note that we will need to check our pr and ph dicts to determine
                    # if the batter entered the game initially as a pr/ph.
                    if id in defensive_positions[lookup]:
                        defensive_positions[lookup][id].append(line.split(",")[5])
                    else:
                        defensive_positions[lookup][id] = [line.split(",")[5]]

# add last defensive info
add_defensive_info(game_info)

# add last game info
session.add(game_info)
                        
# commit the changes
session.commit() 
       
print("Done - added data from %d box scores" % (number_of_box_scores_scanned))
                
