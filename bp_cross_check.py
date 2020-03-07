#########################################################################
#
# Validates a Retrosheet Event file that roughly follows the "EBx" format.
#
# CC License: Attribution-NonCommercial 4.0 International (CC BY-NC 4.0)
# https://creativecommons.org/licenses/by-nc/4.0/
#
# References:
# https://www.retrosheet.org/eventfile.htm
# https://www.retrosheet.org/boxfile.txt
# 
# Requirements:
#
# 1. Must have a set of *.ROS roster files in the same folder that include
#    rosters for every team that is included in the EBx file.
#
#  1.1  MH  01/10/2020  Remove "season" and use bp_load_roster_files()
#  1.0  MH  06/20/2019  Initial version
#
import argparse, csv, glob
from collections import defaultdict
from bp_utils import bp_load_roster_files

DEBUG_ON = False

# Retrosheet road/home id numbers, used for "side" values in .EBx files
ROAD_ID = 0
HOME_ID = 1

# List of players at each position in the batting order
batting_order_list = defaultdict()

# List of "batting order numbers" which are equal to (spot in batting order * 100) + sequence number,
# such that the first player to bat in the third spot is 300 while the second player would be 301.
batting_order_numbers = defaultdict()

# Lists of players in batting order, designed to catch duplicate batter ids
players_in_batting_order = defaultdict()
players_in_batting_order["road"] = defaultdict()
players_in_batting_order["home"] = defaultdict()

# Lists of pitchers, designed to catch duplicate pitcher ids
list_of_pitchers = defaultdict()
list_of_pitchers["road"] = defaultdict()
list_of_pitchers["home"] = defaultdict()

# Lists of pitch hitters, designed to catch duplicate pinch hitter entries, 
# or cases where a PH is also listed as a PR
list_of_pinch_hitters = defaultdict()
list_of_pinch_hitters["road"] = defaultdict()
list_of_pinch_hitters["home"] = defaultdict()

# Lists of pitch runners, designed to catch duplicate pinch runner entries, 
# or cases where a PR is also listed as a PH
list_of_pinch_runners = defaultdict()
list_of_pinch_runners["road"] = defaultdict()
list_of_pinch_runners["home"] = defaultdict()

# Position lists, listing the player(s) who played at each position.
pos_list = defaultdict()

# Batting/fielding stats
stats_list = defaultdict()
stats_list["road"] = defaultdict()
stats_list["home"] = defaultdict()

# Pitching stats
pitching_stats_list = defaultdict()
pitching_stats_list["road"] = defaultdict()
pitching_stats_list["home"] = defaultdict()

# Teamstat lines for comparison purposes
team_stats_list = defaultdict()
team_stats_list["road"] = defaultdict()
team_stats_list["home"] = defaultdict()

# For the line score, we want to store both the total runs and the
# inning-by-inning runs.
linescore_total = defaultdict()
linescore_total["road"] = 0
linescore_total["home"] = 0

linescore_innings = defaultdict()
linescore_innings["road"] = 0
linescore_innings["home"] = 0

s_team_names = defaultdict()
s_date_of_game = ""
s_game_number_this_date = ""
s_usedh = "false"

# Clear all stats in between each game.
def clear_stats():

    s_team_names["road"] = ""
    s_team_names["home"] = ""
    s_date_of_game = ""
    s_game_number_this_date = ""
    s_usedh = "false"
    
    batting_order_list["road"] = [None] * 10 # need 1-9 all to be filled
    batting_order_list["home"] = [None] * 10

    batting_order_numbers["road"] = []
    batting_order_numbers["home"] = []
    
    players_in_batting_order["road"] = defaultdict()
    players_in_batting_order["home"] = defaultdict()

    list_of_pitchers["road"] = defaultdict()
    list_of_pitchers["home"] = defaultdict()
    
    list_of_pinch_hitters["road"] = defaultdict()
    list_of_pinch_hitters["home"] = defaultdict()
    
    list_of_pinch_runners["road"] = defaultdict()
    list_of_pinch_runners["home"] = defaultdict()
    
    pos_list["road"] = [None] * 15 # must have 1-9, plus 10 (DH) optionally
    pos_list["home"] = [None] * 15

    for tm in ["road","home"]:
        stats_list[tm]["AB"] = 0
        stats_list[tm]["Runs"] = 0
        stats_list[tm]["Hits"] = 0
        stats_list[tm]["RBI"] = 0
        stats_list[tm]["Putouts"] = 0
        stats_list[tm]["Assists"] = 0
        stats_list[tm]["Errors"] = 0
        stats_list[tm]["Walks"] = 0
        stats_list[tm]["Strikeouts"] = 0

    for tm in ["road","home"]:
        pitching_stats_list[tm]["Outs"] = 0
        pitching_stats_list[tm]["Runs"] = 0
        pitching_stats_list[tm]["Hits"] = 0
        pitching_stats_list[tm]["Walks"] = 0
        pitching_stats_list[tm]["Strikeouts"] = 0

    for tm in ["road","home"]:
        team_stats_list[tm]["AB"] = 0
        team_stats_list[tm]["Runs"] = 0
        team_stats_list[tm]["Hits"] = 0
        team_stats_list[tm]["Putouts"] = 0
        team_stats_list[tm]["Assists"] = 0
        team_stats_list[tm]["Errors"] = 0

    linescore_total["road"] = 0
    linescore_total["home"] = 0
    
    linescore_innings["road"] = 0
    linescore_innings["road"] = 0

# If the supplied number is -1, we treat that as an unknown value,
# which by definition means that the total is unknown too.
def update_stats_list_conditionally(tm,category,number):
    if number == -1:
        stats_list[tm][category] = -1
    else:
        stats_list[tm][category] += number
        
# If the supplied number is -1, we treat that as an unknown value,
# which by definition means that the total is unknown too.
def update_pitching_stats_list_conditionally(tm,category,number):
    if number == -1:
        pitching_stats_list[tm][category] = -1
    else:
        pitching_stats_list[tm][category] += number
        
# If the supplied number is -1, we treat that as an unknown value,
# which by definition means that the total is unknown too.
def update_team_stats_list_conditionally(tm,category,number):
    if number == -1:
        team_stats_list[tm][category] = -1
    else:
        team_stats_list[tm][category] += number
        
# The majority of stats checking is done here, once we are sure that we have read in
# all data for this game.        
def check_stats():
    # Check for any pid's on the wrong team.
    for tm in ["road","home"]:
        for p in list_of_pitchers[tm]:
            if p not in player_info[s_team_names[tm]]:
                print("ERROR: Pitcher %s not found in %s roster file." % (p,s_team_names[tm]))
        for p in players_in_batting_order[tm]:
            if p not in player_info[s_team_names[tm]]:
                print("ERROR: Batter %s not found in %s roster file." % (p,s_team_names[tm]))
        for p in list_of_pinch_hitters[tm]:
            if p not in player_info[s_team_names[tm]]:
                print("ERROR: Pinch-hitter %s not found in %s roster file." % (p,s_team_names[tm]))
        for p in list_of_pinch_runners[tm]:
            if p not in player_info[s_team_names[tm]]:
                print("ERROR: Pinch-runner %s not found in %s roster file." % (p,s_team_names[tm]))
    
    # Compare player totals with the team stats totals
    for tm in ["road","home"]:
        for stat in team_stats_list[tm]:
            if team_stats_list[tm][stat] != stats_list[tm][stat]:
                if stats_list[tm][stat] != -1: # skip cases where a stat is not available for the players
                    print("MISMATCH: %s %s (sum of players=%d, team total=%d)" % (s_team_names[tm],stat,stats_list[tm][stat],team_stats_list[tm][stat]))
    
    # Check that winning and losing pitcher are from the correct teams
    if team_stats_list["road"]["Runs"] > team_stats_list["home"]["Runs"]:
        if s_wp_id not in list_of_pitchers["road"]:
            print("ERROR: Winning pitcher %s not found in %s roster file." % (s_wp_id,s_team_names["road"]))
        if s_lp_id not in list_of_pitchers["home"]:
            print("ERROR: Losing pitcher %s not found in %s roster file." % (s_lp_id,s_team_names["home"]))
    elif team_stats_list["home"]["Runs"] > team_stats_list["road"]["Runs"]:
        if s_wp_id not in list_of_pitchers["home"]:
            print("ERROR: Winning pitcher %s not found in %s roster file." % (s_wp_id,s_team_names["home"]))
        if s_lp_id not in list_of_pitchers["road"]:
            print("ERROR: Losing pitcher %s not found in %s roster file." % (s_lp_id,s_team_names["road"]))
    
    # Compare batters against opposing pitchers
    for tm in ["road","home"]:
        if tm == "road":
            pitching_tm = "home"
        else:
            pitching_tm = "road"
        for stat in ["Runs","Hits"]:
            if pitching_stats_list[pitching_tm][stat] != stats_list[tm][stat]:
                if stats_list[tm][stat] != -1: # skip cases where a stat is not available for the players
                    print("MISMATCH: %s %s (sum of players=%d, opposing pitcher totals=%d %s)" % (s_team_names[tm],stat,stats_list[tm][stat],pitching_stats_list[pitching_tm][stat],s_team_names[pitching_tm]))
                
    # Compare line scores
    # Length of home linescore can be one less than road, but only if the home team won
    # TBD: Suspended games might break this?
    linescore_length_ok = False
    if linescore_innings["road"] == linescore_innings["home"]:
        linescore_length_ok = True
    elif (linescore_innings["road"] == (linescore_innings["home"] + 1)) and (team_stats_list["home"]["Runs"] > team_stats_list["road"]["Runs"]):
        linescore_length_ok = True
    if not linescore_length_ok:
        print("MISMATCH: Linescore length %s=%d, %s=%d" % (s_team_names["road"],linescore_innings["road"],s_team_names["home"],linescore_innings["home"]))

    for tm in ["road","home"]:
        if linescore_total[tm] != team_stats_list[tm]["Runs"]:
            print("MISMATCH: %s Linescore runs %d, team total %d" % (s_team_names[tm],linescore_total[tm],team_stats_list[tm]["Runs"]))
            
        # Note that if a run scores on an error, there will be no RBI on the play.
        # So we check for RBI > than Runs, but allow RBI < Runs
        if stats_list[tm]["Runs"] != -1 and stats_list[tm]["RBI"] > stats_list[tm]["Runs"]:
            print("MISMATCH: %s More RBI %d than Runs %d" % (s_team_names[tm],stats_list[tm]["RBI"],stats_list[tm]["Runs"]))

        if tm == "road":
            pitching_tm = "home"
        else:
            pitching_tm = "road"        
            
        if pitching_stats_list[pitching_tm]["Outs"] % 3 == 0:
            # Game ended with three outs, or no outs.
            # Normally, the number of innings will equal outs/3...
            if linescore_innings[tm] != int(pitching_stats_list[pitching_tm]["Outs"] / 3):
                # ... unless the game ended with no outs. To cover this case, we check the defensive putouts too.
                if team_stats_list[pitching_tm]["Putouts"] != pitching_stats_list[pitching_tm]["Outs"]:
                    print("MISMATCH: %s Linescore innings %d, opposing pitcher outs %d, opposing putouts %s" % (s_team_names[tm],linescore_innings[tm],pitching_stats_list[pitching_tm]["Outs"],team_stats_list[pitching_tm]["Putouts"]))
        else:
            # If game ended with 1 or 2 outs, our integer division will result in one fewer inning.
            if linescore_innings[tm] != int((pitching_stats_list[pitching_tm]["Outs"] / 3) + 1):
                print("MISMATCH: %s Linescore innings %d, opposing pitcher outs %d (game ended with 1 or 2 outs)" % (s_team_names[tm],linescore_innings[tm],pitching_stats_list[pitching_tm]["Outs"]))
        
    # Check batting order and defensive positions
    for tm in ["road","home"]:
        pos = 1
        while pos <= 9:
            if batting_order_list[tm][pos] == None:
                print("MISSING BATTING ORDER: %s %d" % (s_team_names[tm],pos))
            pos += 1
            
        def_pos = 1
        # require positions 1-9, and 10 (DH) if DH used in game
        if s_usedh == "false":
            require_pos_max = 9
        else:
            require_pos_max = 10
        while def_pos <= require_pos_max:
            if pos_list[tm][def_pos] == None:
                print("MISSING DEFENSIVE POSITION: %s %d" % (s_team_names[tm],def_pos))
            def_pos += 1

        # Check for duplicate batting order number/seq combinations.
        # Example of valid combination list: 100, 200, 300, 400, 401, 402, 500, ... 900, 901
        # Example of INVALID combination list: 100, 103, 200, 400, 500, etc.
        previous_number = 0
        batting_order_numbers[tm].sort()
        # print("BON: %s: %s" % (tm,batting_order_numbers))
        for current_number in batting_order_numbers[tm]:
            if current_number < 100 or current_number >= 1000:
                # Hundreds digit must be 1-9
                print("INVALID BATTING ORDER POSITION: %s %d" % (s_team_names[tm],current_number))
            # Two valid cases:
            # 1. We found a substitute player, so the seq number is +1 the previous number.
            # 2. We found a starter in the next batting order slot, which is equivalent to rounding
            #    up the previous_number to the next even multiple of 100.
            elif (current_number != previous_number + 1) and (current_number != (int(previous_number/100) * 100) + 100):
                print("UNEXPECTED BATTING ORDER SEQUENCE: %s %d followed by %d" % (s_team_names[tm],previous_number,current_number))
            previous_number = current_number
        
        # Check for duplicates in batting, pitching, pinch hitters, or pinch runners.
        for pid in players_in_batting_order[tm]:
            if players_in_batting_order[tm][pid] > 1:
                print("PLAYER IN BATTING ORDER MORE THAN ONCE: %s %s (%d)" % (s_team_names[tm],pid,players_in_batting_order[tm][pid]))
                
        for pid in list_of_pitchers[tm]:
            if list_of_pitchers[tm][pid] > 1:
                print("PITCHER LISTED MORE THAN ONCE: %s %s (%d)" % (s_team_names[tm],pid,list_of_pitchers[tm][pid]))
                
        for pid in list_of_pinch_hitters[tm]:
            if list_of_pinch_hitters[tm][pid] > 1:
                print("PH LISTED MORE THAN ONCE: %s %s (%d)" % (s_team_names[tm],pid,list_of_pinch_hitters[tm][pid]))
            # A player cannot be both a PR and a PH in the same game
            if pid in list_of_pinch_runners[tm]:
                print("PH ALSO LISTED AS A PR: %s %s (%d)" % (s_team_names[tm],pid,list_of_pinch_hitters[tm][pid]))
                
        for pid in list_of_pinch_runners[tm]:
            if list_of_pinch_runners[tm][pid] > 1:
                print("PR LISTED MORE THAN ONCE: %s %s (%d)" % (s_team_names[tm],pid,list_of_pitchers[tm][pid]))
    
##########################################################
#
# Main program
#

parser = argparse.ArgumentParser(description='Validate a Retrosheet event file.') 
parser.add_argument('file', help="File to validate")
args = parser.parse_args()
    
# Read in all of the .ROS files up front so we can build dictionary of player ids and names, by team.
(player_info,list_of_teams) = bp_load_roster_files()

clear_stats()
number_of_box_scores_scanned = 0

# main loop
with open(args.file,'r') as efile:
    # We could use csv library, but I worry about reading very large files.
    for line in efile:
        line = line.rstrip()
        if line.count(",") > 0:
            line_type = line.split(",")[0]
            
            if line_type == "stat":
                sub_line_type = line.split(",")[1]
                if sub_line_type == "bline":
                    # stat,bline,id,side,pos,seq,ab,r,h,2b,3b,hr,rbi,sh,sf,hbp,bb,ibb,k,sb,cs,gidp,int
                    side = int(line.split(",")[3])
                    if side == ROAD_ID:
                        lookup = "road"
                    else:
                        lookup = "home"
                    
                    pos = int(line.split(",")[4])
                    batting_order_list[lookup][pos] = 1
                    seq = int(line.split(",")[5])
                    batting_order_numbers[lookup].append(int((pos * 100) + seq))
                    
                    id = line.split(",")[2]
#                    print("%s" % (id))
                    if id not in players_in_batting_order[lookup]:
                        players_in_batting_order[lookup][id] = 1
                    else:
                        players_in_batting_order[lookup][id] += 1
                    
                    ab = int(line.split(",")[6])
                    update_stats_list_conditionally(lookup,"AB",ab)
                    r = int(line.split(",")[7])
                    update_stats_list_conditionally(lookup,"Runs",r)
                    h = int(line.split(",")[8])
                    update_stats_list_conditionally(lookup,"Hits",h)
                    rbi = int(line.split(",")[12])
                    update_stats_list_conditionally(lookup,"RBI",rbi)
                    bb = int(line.split(",")[16])
                    update_stats_list_conditionally(lookup,"Walks",bb)
                    strikeouts = int(line.split(",")[18])
                    update_stats_list_conditionally(lookup,"Strikeouts",strikeouts)
                    
                    # Check a few statistics for this specific player
                    doubles = int(line.split(",")[9])
                    if doubles == -1:
                        doubles = 0
                    triples = int(line.split(",")[10])
                    if triples == -1:
                        triples = 0
                    homeruns = int(line.split(",")[11])
                    if homeruns == -1:
                        homeruns = 0
                    if doubles + triples + homeruns > h:
                        print("ERROR: %s: %s more 2B (%d) 3B (%d) and HR (%d) than Hits (%d)" % ([s_team_names[lookup]],player_info[s_team_names[lookup]][id],doubles,triples,homeruns,h))
                    if h > ab:
                        print("ERROR: %s: %s more Hits (%d) than AB (%d)" % ([s_team_names[lookup]],player_info[s_team_names[lookup]][id],h,ab))
                
                elif sub_line_type == "dline":
                    # stat,dline,id,side,seq,pos,if*3,po,a,e,dp,tp,pb
                    side = int(line.split(",")[3])
                    if side == ROAD_ID:
                        lookup = "road"
                    else:
                        lookup = "home"

                    pos = int(line.split(",")[5])
                    pos_list[lookup][pos] = 1
                    
                    putouts = int(line.split(",")[7])
                    update_stats_list_conditionally(lookup,"Putouts",putouts)
                    assists = int(line.split(",")[8])
                    update_stats_list_conditionally(lookup,"Assists",assists)
                    errors = int(line.split(",")[9])
                    update_stats_list_conditionally(lookup,"Errors",errors)

                elif sub_line_type == "pline":
                    # stat,pline,id,side,seq,ip*3,no-out,bfp,h,2b,3b,hr,r,er,bb,ibb,k,hbp,wp,balk,sh,sf
                    side = int(line.split(",")[3])
                    if side == ROAD_ID:
                        lookup = "road"
                    else:
                        lookup = "home"

                    outs = int(line.split(",")[5])
                    update_pitching_stats_list_conditionally(lookup,"Outs",outs)
                    hits = int(line.split(",")[8])
                    update_pitching_stats_list_conditionally(lookup,"Hits",hits)
                    runs = int(line.split(",")[12])
                    update_pitching_stats_list_conditionally(lookup,"Runs",runs)
                    walks = int(line.split(",")[14])
                    update_pitching_stats_list_conditionally(lookup,"Walks",walks)
                    strikeouts = int(line.split(",")[16])
                    update_pitching_stats_list_conditionally(lookup,"Strikeouts",strikeouts)

                    id = line.split(",")[2]
                    if id not in list_of_pitchers[lookup]:
                        list_of_pitchers[lookup][id] = 1
                    else:
                        list_of_pitchers[lookup][id] += 1
                 
                    # Check a few statistics for this specific player
                    if strikeouts > outs:
                        print("ERROR: %s: %s more Strikeouts (%d) than Outs (%d)" % ([s_team_names[lookup]],player_info[s_team_names[lookup]][id],strikeouts,outs))
                    
                elif sub_line_type == "prline":
                    # stat,prline,id,inning,side,r,sb,cs
                    side = int(line.split(",")[4])
                    if side == ROAD_ID:
                        lookup = "road"
                    else:
                        lookup = "home" 
                        
                    id = line.split(",")[2]
                    if id not in list_of_pinch_runners[lookup]:
                        list_of_pinch_runners[lookup][id] = 1
                    else:
                        list_of_pinch_runners[lookup][id] += 1                    
                        
                elif sub_line_type == "phline":
                    # stat,phline,id,inning,side,ab,r,h,2b,3b,hr,rbi,sh,sf,hbp,bb,ibb,k,sb,cs,gidp,int
                    side = int(line.split(",")[4])
                    if side == ROAD_ID:
                        lookup = "road"
                    else:
                        lookup = "home" 
                    
                    id = line.split(",")[2]
                    if id not in list_of_pinch_hitters[lookup]:
                        list_of_pinch_hitters[lookup][id] = 1
                    else:
                        list_of_pinch_hitters[lookup][id] += 1                    
                        
            elif line_type == "line":
                # linescore
                side = int(line.split(",")[1])
                if side == ROAD_ID:
                    lookup = "road"
                else:
                    lookup = "home"
                
                innings = line.split(",")[2:]
                total_runs = 0
                for single_inning in innings:
                    total_runs += int(single_inning)
                linescore_total[lookup] = total_runs
                linescore_innings[lookup] = len(innings)
                
            elif line_type == "event":
                # event,dpline,side of team who turned the DP,player-id (who turned the DP)...
                # event,tpline,side of team who turned the TP,player-id (who turned the TP)...                
                # event,hpline,side of pitcher's team,pitcher-id,batter-id
                event_type = line.split(",")[1]
                side = int(line.split(",")[2])
                if side == ROAD_ID:
                    lookup = "road"
                    opponent = "home"
                else:
                    lookup = "home"
                    opponent = "road"

                pid_list = line.split(",")[3:]
                if event_type == "dpline" or event_type == "tpline":
                    # This checks that all of the players who turned the DP or TP play on the
                    # appropriate team, and that they have an entry in the batting order.
                    # LIMITATION: The batting order check makes the assumption that the
                    # batting order info preceeds the event info in the .EBx file.                    
                    for pid in pid_list:
                        if pid not in player_info[s_team_names[lookup]]:
                            print("ERROR for %s event: %s not found in %s roster file." % (event_type,pid,s_team_names[lookup]))
                        if pid not in players_in_batting_order[lookup]:
                            print("ERROR for %s event: %s not found in %s batting order." % (event_type,pid,s_team_names[lookup]))
                elif event_type == "hpline":
                    # For HBP, the pitcher and batter need to be on different teams.
                    if pid_list[0] not in player_info[s_team_names[lookup]]:
                        print("ERROR for HBP: Pitcher %s not found in %s roster file." % (pid_list[0],s_team_names[opponent]))
                    if pid_list[1] not in player_info[s_team_names[opponent]]:
                        print("ERROR for HBP: Batter %s not found in %s roster file." % (pid_list[1],s_team_names[lookup]))
                    
            # LIMITATION: The "teamstat" lines are our own invention. 
            # If these lines are not present in the EBx file, these checks will be skipped.
            elif line_type == "teamstat":
                # teamstat,side,ab,r,h,po,a,e
                side = int(line.split(",")[1])
                if side == ROAD_ID:
                    lookup = "road"
                else:
                    lookup = "home"
                
                ab = int(line.split(",")[2])
                update_team_stats_list_conditionally(lookup,"AB",ab)
                r = int(line.split(",")[3])
                update_team_stats_list_conditionally(lookup,"Runs",r)
                h = int(line.split(",")[4])
                update_team_stats_list_conditionally(lookup,"Hits",h)
                po = int(line.split(",")[5])
                update_team_stats_list_conditionally(lookup,"Putouts",po)
                a = int(line.split(",")[6])
                update_team_stats_list_conditionally(lookup,"Assists",a)
                e = int(line.split(",")[7])
                update_team_stats_list_conditionally(lookup,"Errors",e)
                    
            elif line_type == "info":
                info_type = line.split(",")[1]
                if info_type == "visteam":
                    s_team_names["road"] = line.split(",")[2]
                elif info_type == "hometeam":
                    s_team_names["home"] = line.split(",")[2]
                elif info_type == "date":
                    s_date_of_game = line.split(",")[2]
                elif info_type == "number":
                    s_game_number_this_date = line.split(",")[2]
                    # Doing this here makes the assumption that team, date, and game number info are at the start
                    # of the data for each game. We print this here so that it precedes our DP checks above.
                    print("\nChecking %s at %s, %s (%s)" % (s_team_names["road"],s_team_names["home"],s_date_of_game,s_game_number_this_date))                    
                elif info_type == "usedh":
                    s_usedh = line.split(",")[2]
                elif info_type == "wp":
                    s_wp_id = line.split(",")[2]
                elif info_type == "lp":
                    s_lp_id = line.split(",")[2]
                    
            elif line_type == "version":  # sentinel that always starts a new box score
                if number_of_box_scores_scanned > 0:
                    check_stats()
                    clear_stats()
                number_of_box_scores_scanned += 1
                
# check the last box score
check_stats()

print("Done - verified %d box scores" % (number_of_box_scores_scanned))
                
