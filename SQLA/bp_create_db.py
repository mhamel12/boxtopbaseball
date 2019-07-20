#########################################################################
#
# Loads player statistics from a Retrosheet Event file into a SQL Alchemy database.
# Proof-of-concept, tailored specifically for 1938 American Assocation box 
# scores as published in the Minneapolis Star and Tribune.
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
from bp_retrosheet_classes import BattingStats, PitchingStats, GameInfo, Base

DEBUG_ON = False

# Retrosheet road/home id numbers, used for "side" values in .EBx files
ROAD_ID = 0
HOME_ID = 1

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

# main loop
with open(args.file,'r') as efile:
    # We could use csv library, but I worry about reading very large files.
    for line in efile:
        line = line.rstrip()
        if line.count(",") > 0:
            line_type = line.split(",")[0]
            
            if line_type == "version":  # sentinel that always starts a new box score
                if number_of_box_scores_scanned > 0:
                    session.add(game_info)
                    game_info = GameInfo()
                    game_info.comments = ""
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

# add last game info
session.add(game_info)
                    
# commit the changes
session.commit() 
       
print("Done - added data from %d box scores" % (number_of_box_scores_scanned))
                
