#########################################################################
#
# Creates HTML file with box scores based on a Retrosheet-like Event file 
# that roughly follows the "EBx" format. Borrows formatting from 
# https://www.waldrn.com/boxscores/ .
#
# CC License: Attribution-NonCommercial 4.0 International (CC BY-NC 4.0)
# https://creativecommons.org/licenses/by-nc/4.0/
#
# Situations where we either deviate or do not meet full requirements of
# the Retrosheet format are labeled with "LIMITATION".
#
# References:
# https://www.retrosheet.org/eventfile.htm
# https://www.retrosheet.org/boxfile.txt
# 
# Requirements:
# 1. Must have a parkcode.txt file in the same folder
# 2. Must have a set of *.ROS roster files in the same folder that include
#    rosters for every team that is included in the EBx file.
# 3. Must have a TEAM<Season_as_YYYY>.txt file, that maps team abbreviations to their full names, in the same folder.
#
# Notes:
# 1. The .EBx files are NOT suitable for use with Retrosheet's BOX.exe program.
#    BOX.exe needs EVA/EVN files that contain play-by-play data, which we do not have.
#
#  2.1  MH  07/02/2026  Read in a pair of schedule files to add detail for regular season use case.
#  2.0  MH  06/15/2026  First HTML version, building upon bp_generate_box.py (only generates the box score info itself; the preamble needs to be added manually)
#                       In the style-sheet I added indent for substitute position players, and "last-child" support for pitching-table to match the batting-table
#  1.4  MH  11/23/2022  Added league_classification variable.
#  1.3  MH  04/26/2020  Correct handling of "X outs when winning run scored"
#  1.2  MH  03/07/2020  Add pinch-runner info
#  1.1  MH  01/16/2020  Use bp_load_roster_files()
#  1.0  MH  06/05/2019  Initial version
#
import argparse, csv, datetime, glob, math, operator, os, re, sys
from collections import defaultdict
from bp_utils import bp_load_roster_files
from datetime import datetime, timedelta

DEBUG_ON = False

ROAD_ID = 0
HOME_ID = 1

league_classification = "Default"

def get_opp(tm):
    if tm == "road":
        return "home"
    return "road"
    
def get_time_in_hr_min(time_in_min):
    hours = int(time_in_min / 60)
    min = time_in_min % 60
    return str(hours) + ":" + str("%02d" % (min))
    
def get_attendance(att):
    if att == "-1":
        return "Unknown"
    return(att)
    
def get_full_innings(outs):
    ip = int(int(outs) / 3)
    return("%2d" % (ip))

def get_partial_innings(outs):
    ip = int(int(outs) % 3)
    if ip > 0:
        return(".%d" % (ip))
    return("  ")
    
def get_innings_html(outs):
    full_ip = int(int(outs) / 3)
    partial_ip = int(int(outs) % 3)

    # unlike the Retrosheet/Text format, include the .0 to make the table look nicer in HTML
    return("%d.%d" % (full_ip,partial_ip))

    
def check_stat(stat_string):
    if stat_string == "-1":
        return ""
    return(stat_string)
    
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
    
def clear_between_games():
    game_info = defaultdict() # one struct for entire game, not one per team
    
    for tm in ["road","home"]:
        linescores[tm] = []
        batting_blines[tm] = defaultdict()
        defensive_dlines[tm] = defaultdict()
        defensive_positions[tm] = defaultdict()
        dp_dict[tm] = []
        tp_dict[tm] = []
        hbp_dict[tm] = []
        pitching_plines[tm] = defaultdict()
        pinch_hitters[tm] = defaultdict()
        pinch_runners[tm] = defaultdict()
        team_totals[tm] = defaultdict()
        team_totals[tm]["ab"] = 0
        team_totals[tm]["runs"] = 0
        team_totals[tm]["hits"] = 0
        team_totals[tm]["rbi"] = 0
        team_totals[tm]["bb"] = 0
        team_totals[tm]["strikeouts"] = 0
        team_totals[tm]["po"] = 0
        team_totals[tm]["assists"] = 0
        team_totals[tm]["errors"] = 0
        team_totals[tm]["NumberOfDP"] = 0
        team_totals[tm]["NumberOfTP"] = 0
        team_totals[tm]["LOB"] = 0
        pitching_totals[tm] = defaultdict()
        pitching_totals[tm]["outs"] = 0
        pitching_totals[tm]["h"] = 0
        pitching_totals[tm]["r"] = 0
        pitching_totals[tm]["er"] = 0
        pitching_totals[tm]["bb"] = 0 
        pitching_totals[tm]["so"] = 0 
        pitching_totals[tm]["hr"] = 0
        pitching_totals[tm]["bfp"] = 0

def convert_event_play_to_name_string(tm,p):
    p_string = ""
    p_id_list = p.split(":")
    for id in p_id_list:
        name = player_info[game_info[tm]][id]
        if p_string == "":
            p_string = name
        else:
            p_string = p_string + "-" + name
    return p_string

# If stat_count > 0, add player name to stat line.
# If stat_count > 1, also add the count.    
def add_to_line_conditionally(stat_count,line,tm,id):    
    if stat_count > 0:
        string_to_add = player_info[game_info[tm]][id]
        if stat_count > 1:
            string_to_add = string_to_add + " %d" % (stat_count)
            
        if line == "":
            line = string_to_add
        else:
            line = line + ", " + string_to_add
    
    return line

    
# If stat_count > 0, add player name to stat line.
# If stat_count > 1, also add the count.    
def add_to_string_conditionally(string_to_add, original_string):
    string_to_return = ""

    if len(string_to_add) > 0:
        if original_string == "":
            string_to_return = string_to_add
        else:
            string_to_return = original_string + ", " + string_to_add
        return string_to_return

    else:
        return original_string


# If the supplied number is -1, we treat that as an unknown value,
# which by definition means that the total is unknown too.
def update_team_totals_conditionally(tm,category,number):
    if number == -1:
        team_totals[tm][category] = "" # -1
    else:
        team_totals[tm][category] += number
        
        
# If the supplied number is -1, we treat that as an unknown value,
# which by definition means that the total is unknown too.
def update_pitching_totals_conditionally(tm,category,number):
#    print("INSIDE UPDATE %s : %d" % (category,number))
    if number == -1:
        pitching_totals[tm][category] = "" # -1
    else:
        pitching_totals[tm][category] += number

def convert_to_ordinal_string(number):
    # Apply rules for 1st, 2nd, 3rd, ... 11th, 12th, 13th, ..., 21st, 22nd, ...
    if number % 10 == 1 and number != 11:
        return str(number) + "st"
    if number % 10 == 2 and number != 12: 
        return str(number) + "nd"
    if number % 10 == 3 and number != 13:
        return str(number) + "rd"

    return str(number) + "th"
        
# If a pitcher fails to record an out in an inning, we will have 'no-out'
# batters faced info in the .EBx file. Translate that inning into a text
# string based on the number of outs recorded by that pitcher and all
# previous pitchers on that team.
def get_next_inning_based_on_outs(outs):
    number_of_innings = math.floor(outs / 3) # should be an even multiple, but let's make sure
    next_inning = number_of_innings + 1
    return(convert_to_ordinal_string(next_inning))

def get_opponent(team):
    if team == "road":
        return "home"
        
    return "road"


# Increment a YYYY/MM/DD string by one day
def next_day(date_str):
    dt = datetime.strptime(date_str, "%Y/%m/%d")
    dt_next = dt + timedelta(days=1)
    return dt_next.strftime("%Y/%m/%d")

# Compare two date strings in YYYY/MM/DD format
def compare_dates(date1, date2):
    da = datetime.strptime(date1, "%Y/%m/%d")
    db = datetime.strptime(date2, "%Y/%m/%d")    
    comparison_value = (da > db) - (da < db) 
    
    if comparison_value == 0:
        return("Match")
    elif comparison_value == 1:
        return("Later") # date1 is a later date than date2
    elif comparison_value == -1:
        return("Earlier") # date1 is an earlier date than date2
    
    # should never get here
    return("NoMatch")

# convert YYYY/MM/DD to DayOfWeek Month Day (no leading zero), Year
def convert_slashdate_to_fulldate(slash_date):
    dt = datetime.strptime(slash_date, "%Y/%m/%d")
    return(dt.strftime("%A %B %d, %Y").replace(" 0", " "))


def print_linescore_html(road_or_home, max_inning_count, max_runs, max_hits, max_errors):
    output_file.write('          <div class="team-line">\n')
    output_file.write('            <div class="team-name">%s</div>\n' % (team_abbrev_to_full_name[game_info[road_or_home]]))
    
    inning_count = 0
    linescore_string = '            <div class="team-score">'
    for inn in linescores[road_or_home]:
        if inning_count > 0 and (inning_count % 3 == 0):
            linescore_string = linescore_string + " "
        if int(inn) >= 10:
            runs_to_print = "(%s)" % (inn) # As of 6/9/2026 waldrn has a bug where 10 gets printed as 0. This is my attempt to fix this but it will need work for better alignment.
        else:
            runs_to_print = inn
        linescore_string = linescore_string + runs_to_print
        inning_count += 1
    
    if inning_count < max_inning_count:
        if inning_count % 3 == 0:
            linescore_string = linescore_string + "&numsp;"
        linescore_string = linescore_string + "x"
    
#    linescore_string = linescore_string + " &mdash; %s &numsp; %s &numsp; %s &numsp;</div>\n" % (team_totals[road_or_home]["runs"],team_totals[road_or_home]["hits"],team_totals[road_or_home]["errors"])

    runs_string = "%s " % (team_totals[road_or_home]["runs"])
    if max_runs >= 10 and team_totals[road_or_home]["runs"] < 10:
        runs_string = "&numsp;" + runs_string

    hits_string = "&numsp; %s " % (team_totals[road_or_home]["hits"])
    if max_hits >= 10 and team_totals[road_or_home]["hits"] < 10:
        hits_string = "&numsp;" + hits_string

    errors_string = "&numsp; %s " % (team_totals[road_or_home]["errors"])
    if max_errors >= 10 and team_totals[road_or_home]["errors"] < 10:
        errors_string = "&numsp;" + errors_string
        
    linescore_string = linescore_string + " &mdash; " + runs_string + hits_string + errors_string + "</div>\n"
    
    output_file.write(linescore_string)
    output_file.write('          </div>\n')
    

def print_batting_table_html(road_or_home):
    tm = road_or_home
    
    ##############################################################
    #
    # Batting table portion of box score
    #
    
    output_file.write('          <table class="batting-table">\n')
    output_file.write('          <thead>\n')
    output_file.write('            <tr>\n')
    output_file.write('              <th class="player-col">%s</th>\n' % (team_abbrev_to_full_name[game_info[tm]]))
    output_file.write('              <th class="stat-col">AB</th>\n')
    output_file.write('              <th class="stat-col">R</th>\n')
    output_file.write('              <th class="stat-col">H</th>\n')
    output_file.write('              <th class="stat-col">BI</th>\n')
#    output_file.write('              <th class="stat-col">BB</th>\n') # Missing from Eastern League data
#    output_file.write('              <th class="stat-col">SO</th>\n') # Missing from Eastern League data
    output_file.write('              <th class="stat-col">PO</th>\n')
    output_file.write('              <th class="stat-col">A</th>\n')
#    output_file.write('              <th class="avg-col">Avg</th>\n') # Missing from Eastern League data
    output_file.write('            </tr>\n')
    output_file.write('          </thead>\n')
    output_file.write('          <tbody>\n')
    
    batters_by_slot = defaultdict()
    for p in batting_blines[tm]:
        # id,side,pos,seq,ab,r,h,2b,3b,hr,rbi,sh,sf,hbp,bb,ibb,k,sb,cs,gidp,int
        # Store in dictionary by batting order slot and sequence number inside that slot.
        the_key = "batter_%02d_%02d" % (int(batting_blines[tm][p][2]),int(batting_blines[tm][p][3]))
        batters_by_slot[the_key] = batting_blines[tm][p]
    
    for p in sorted(batters_by_slot.keys()):
        id = check_stat(batters_by_slot[p][0])
        ab = check_stat(batters_by_slot[p][4])
        runs = check_stat(batters_by_slot[p][5])
        hits = check_stat(batters_by_slot[p][6])
        rbi = check_stat(batters_by_slot[p][10])
        bb = check_stat(batters_by_slot[p][14])
        strikeouts = check_stat(batters_by_slot[p][16])
        
        # dline format
        # id,side,seq,pos,if*3,po,a,e,dp,tp,pb
        if id in defensive_dlines[tm]:
            po = defensive_dlines[tm][id][5]
            assists = defensive_dlines[tm][id][6]
        else:
            # Will not have dline if only a PR or PH
            po = 0
            assists = 0
            
        name = ""
        if batters_by_slot[p][3] != "0": # came off bench, so indent the batter's name
            substitute = True
        else:
            substitute = False
        name += player_info[game_info[tm]][id]
        
        name += " " + get_positions(tm,id)

        output_file.write('            <tr>\n')
        if substitute:
            # I added this class type to provide indentation
            output_file.write('              <td class="player-col-substitute">%s</td>\n' % (name))
        else:
            output_file.write('              <td class="player-col">%s</td>\n' % (name))
        output_file.write('              <td class="stat-col">%s</td>\n' % (ab))
        output_file.write('              <td class="stat-col">%s</td>\n' % (runs))
        output_file.write('              <td class="stat-col">%s</td>\n' % (hits))
        output_file.write('              <td class="stat-col">%s</td>\n' % (rbi))
        output_file.write('              <td class="stat-col">%s</td>\n' % (po))
        output_file.write('              <td class="stat-col">%s</td>\n' % (assists))
        output_file.write('            </tr>\n')
        
        # end of batter loop

    # batting totals
    output_file.write('            <tr>\n')
    output_file.write('              <td class="player-col">Totals</td>\n')
    output_file.write('              <td class="stat-col">%s</td>\n' % (team_totals[tm]["ab"]))
    output_file.write('              <td class="stat-col">%s</td>\n' % (team_totals[tm]["runs"]))
    output_file.write('              <td class="stat-col">%s</td>\n' % (team_totals[tm]["hits"]))
    output_file.write('              <td class="stat-col">%s</td>\n' % (team_totals[tm]["rbi"]))
    output_file.write('              <td class="stat-col">%s</td>\n' % (team_totals[tm]["po"]))
    output_file.write('              <td class="stat-col">%s</td>\n' % (team_totals[tm]["assists"]))
    output_file.write('            </tr>\n')

    output_file.write('          </tbody>\n')
    output_file.write('          </table>\n')



def print_pitching_table_html(road_or_home):
    tm = road_or_home
    
    output_file.write('          <table class="pitching-table">\n')
    output_file.write('          <thead>\n')
    output_file.write('            <tr>\n')
    output_file.write('              <th class="player-col">%s</th>\n' % (team_abbrev_to_full_name[game_info[tm]]))
    output_file.write('              <th class="ip-col">IP</th>\n')
    output_file.write('              <th class="stat-col">H</th>\n')
    output_file.write('              <th class="stat-col">R</th>\n')
    output_file.write('              <th class="stat-col">ER</th>\n')
    output_file.write('              <th class="stat-col">BB</th>\n')
    output_file.write('              <th class="stat-col">SO</th>\n')
    output_file.write('            </tr>\n')
    output_file.write('          </thead>\n')
    output_file.write('          <tbody>\n')
    

    pitchers_by_slot = defaultdict()
    for p in pitching_plines[tm]:
        # plines should be in seq order already, but we will re-sort them just in case.
        # id,side,seq,ip*3,no-out,bfp,h,2b,3b,hr,r,er,bb,ibb,k,hbp,wp,balk,sh,sf
        the_key = "pitcher_%02d" % int(pitching_plines[tm][p][2])
        pitchers_by_slot[the_key] = pitching_plines[tm][p]

    wild_pitches_string = ""
    balks_string = ""        
    for p in sorted(pitchers_by_slot.keys()):
    
        id = pitchers_by_slot[p][0]
        outs = int(pitchers_by_slot[p][3])
        update_pitching_totals_conditionally(tm,"outs",outs)
        hits = int(pitchers_by_slot[p][6])
        update_pitching_totals_conditionally(tm,"h",hits)
        runs = int(pitchers_by_slot[p][10])
        update_pitching_totals_conditionally(tm,"r",runs)
        er = int(pitchers_by_slot[p][11])
        update_pitching_totals_conditionally(tm,"er",er)
        bb = int(pitchers_by_slot[p][12])
        update_pitching_totals_conditionally(tm,"bb",bb)
        so = int(pitchers_by_slot[p][14])
        update_pitching_totals_conditionally(tm,"so",so)
        hr = int(pitchers_by_slot[p][9])
        update_pitching_totals_conditionally(tm,"hr",hr)
        bfp = int(pitchers_by_slot[p][5])
        update_pitching_totals_conditionally(tm,"bfp",bfp)
        
        wildpitches = int(pitchers_by_slot[p][16])
        wild_pitches_string = add_to_line_conditionally(wildpitches,wild_pitches_string,tm,id)            
        balks = int(pitchers_by_slot[p][17])
        balks_string = add_to_line_conditionally(balks,balks_string,tm,id)            
        
        hits = check_stat(pitchers_by_slot[p][6])
        runs = check_stat(pitchers_by_slot[p][10])
        er = check_stat(pitchers_by_slot[p][11])
        bb = check_stat(pitchers_by_slot[p][12])
        so = check_stat(pitchers_by_slot[p][14])
        hr = check_stat(pitchers_by_slot[p][9])
        bfp = check_stat(pitchers_by_slot[p][5])
        
        pitcher_name = player_info[game_info[tm]][id]
        if id == winning_pitcher_id:
            pitcher_name = pitcher_name + " (W)"
        elif id == losing_pitcher_id:
            pitcher_name = pitcher_name + " (L)"
            
    
        output_file.write('            <tr>\n')   
        output_file.write('              <td class="player-col">%s</td>\n' % (pitcher_name))
        output_file.write('              <td class="ip-col">%s</td>\n' % (get_innings_html(outs)))
        output_file.write('              <td class="stat-col">%s</td>\n' % (hits))
        output_file.write('              <td class="stat-col">%s</td>\n' % (runs))
        output_file.write('              <td class="stat-col">%s</td>\n' % (er))
        output_file.write('              <td class="stat-col">%s</td>\n' % (bb))
        output_file.write('              <td class="stat-col">%s</td>\n' % (so))
        output_file.write('            </tr>\n')
                
#        output_file.write("\n%-30s%s%s  %2s  %2s  %2s  %2s  %2s  %2s %3s" % (pitcher_name,get_full_innings(outs),get_partial_innings(outs),hits,runs,er,bb,so,hr,bfp))
#            print ("%s:%s" % (p,pitchers_by_slot[p]))
        
    # Convert stats to string, honoring the rule that a negative number means 
    # that we do not have a valid value for this stat.
    for stat in pitching_totals[tm]:
#            print("%s = %s" % (stat,str(pitching_totals[tm][stat])))
        pitching_totals[stat] = check_stat(str(pitching_totals[tm][stat]))
            
    # batting totals
    output_file.write('            <tr>\n')
    output_file.write('              <td class="player-col">Totals</td>\n')
    output_file.write('              <td class="stat-col">%s</td>\n' % (get_innings_html(pitching_totals[tm]["outs"])))
    output_file.write('              <td class="stat-col">%s</td>\n' % (pitching_totals[tm]["h"]))
    output_file.write('              <td class="stat-col">%s</td>\n' % (pitching_totals[tm]["r"]))
    output_file.write('              <td class="stat-col">%s</td>\n' % (pitching_totals[tm]["er"]))
    output_file.write('              <td class="stat-col">%s</td>\n' % (pitching_totals[tm]["bb"]))
    output_file.write('              <td class="stat-col">%s</td>\n' % (pitching_totals[tm]["so"]))
    output_file.write('            </tr>\n')

    output_file.write('          </tbody>\n')
    output_file.write('          </table>\n')            


    batters_faced_strings = []
    # XYZ faced X batters in the Xth inning
    outs_so_far_in_game = 0
    for p in sorted(pitchers_by_slot.keys()):
        id = pitchers_by_slot[p][0]
        outs_so_far_in_game = outs_so_far_in_game + int(pitchers_by_slot[p][3])
        batters_faced_in_Xth_inning = int(pitchers_by_slot[p][4])
        if batters_faced_in_Xth_inning > 0:
            pitcher_name = player_info[game_info[tm]][id]
            the_Xth_inning = get_next_inning_based_on_outs(outs_so_far_in_game)
            if batters_faced_in_Xth_inning == 1:
                batter_text_string = "batter"
            else:
                batter_text_string = "batters"
            extra_info_string = "%s faced %d %s in the %s inning.\n" % (pitcher_name,batters_faced_in_Xth_inning,batter_text_string,the_Xth_inning)
            batters_faced_strings.append(extra_info_string)

    return (outs_so_far_in_game, batters_faced_strings, wild_pitches_string, balks_string)



def print_box_html():
    if team_totals["home"]["runs"] >= team_totals["road"]["runs"]:
        winning_team = "home"
        losing_team = "road"
    else:
        losing_team = "home"
        winning_team = "road"
        
    output_file.write('       <div class="game-container" data-team-away="%s" data-team-home="%s">\n' % (game_info["road"],game_info["home"])) # Example: BAL, BOS
    output_file.write('         <div class="game-header">%s %s<br>%s %s</div>\n' % (team_abbrev_to_full_name[game_info[winning_team]],team_totals[winning_team]["runs"],team_abbrev_to_full_name[game_info[losing_team]],team_totals[losing_team]["runs"]))

    game_day = datetime.strptime(game_info["date"], '%Y/%m/%d').strftime('%A, %B %e, %Y') # Note that %e is like %d but omits leading zero for the day.
    if game_info["daynight"] == "day":
        game_daynight = " (Day) "
    elif game_info["daynight"] == "night":
        game_daynight = " (Night) "
    else:
        game_daynight = " "
    location = park_info[game_info["site"]]["name"] + " (" + park_info[game_info["site"]]["city"] + ", " + park_info[game_info["site"]]["state"] + ")"
    output_file.write('         <div class="game-location">%s</div>\n' % (game_day + game_daynight + "<br>at %s" % (location)))
    
    max_inning_count = max(len(linescores["road"]),len(linescores["home"]))
    max_runs = max(team_totals["road"]["runs"],team_totals["home"]["runs"])
    max_hits = max(team_totals["road"]["hits"],team_totals["home"]["hits"])
    max_errors = max(team_totals["road"]["errors"],team_totals["home"]["errors"])
    
    print_linescore_html("road", max_inning_count, max_runs, max_hits, max_errors)
    print_linescore_html("home", max_inning_count, max_runs, max_hits, max_errors)
    
    print_batting_table_html("road")
    print_batting_table_html("home")
    
    #
    # START OF NOTES SECTION
    #
    
    output_file.write('          <div class="notes">')

    ##############################################################
    #
    # Pinch-hitters and pinch-runners
    #
    pinch_count = 0
    pinch_string = ""

    for tm in ["road","home"]:
        for ph in pinch_hitters[tm]:
            pinch_string = pinch_string + "%s pinch-hit in the %s. " % (player_info[game_info[tm]][ph],convert_to_ordinal_string(int(pinch_hitters[tm][ph])))
            pinch_count += 1
            
        for pr in pinch_runners[tm]:
            pinch_string = pinch_string + "%s pinch-ran in the %s." % (player_info[game_info[tm]][pr],convert_to_ordinal_string(int(pinch_runners[tm][pr])))
            pinch_count += 1
            
    if pinch_count > 0:
        output_file.write(pinch_string + "<br>\n")


    # Errors
    error_string = ""
    for tm in ["road","home"]:
        if team_totals[tm]["errors"] > 0:
            error_string = ""
            # We store the following in the defensive_dlines dictionary:
            # id,side,seq,pos,if*3,po,a,e,dp,tp,pb
            for id in defensive_dlines[tm]:
                error_count = int(defensive_dlines[tm][id][7])
                error_string = add_to_line_conditionally(error_count,error_string,tm,id)
    
    if len(error_string) > 0:
        output_file.write(" <b>E:</b> %s. " % (error_string))   

    # Left on base
    lob_string = ""
    for tm in ["road","home"]:
        if int (team_totals[tm]["LOB"]) >= 0:  # -1 means no data available
            if len(lob_string) > 0:
                lob_string = lob_string + ", %s %s" % (team_abbrev_to_full_name[game_info[tm]], team_totals[tm]["LOB"])
            else:
                lob_string = lob_string + "%s %s" % (team_abbrev_to_full_name[game_info[tm]], team_totals[tm]["LOB"])
    if len(lob_string) > 0:
        output_file.write(" <b>LOB:</b> %s. " % (lob_string))

    doubles_string = ""
    triples_string = ""
    homeruns_string = ""
    sb_string = ""
    cs_string = ""
    sh_string = ""
    sf_string = ""
#        hbp_string = ""
    ibb_string = ""
    gidp_string = ""
    reached_on_int_string = ""
    
    for tm in ["road","home"]:
        
        # The batting_blines dict contains lines of the form:
        # id,side,pos,seq,ab,r,h,2b,3b,hr,rbi,sh,sf,hbp,bb,ibb,k,sb,cs,gidp,int
        for id in batting_blines[tm]:
            count_2b = int(batting_blines[tm][id][7])
            count_3b = int(batting_blines[tm][id][8])
            count_hr = int(batting_blines[tm][id][9])
            count_sb = int(batting_blines[tm][id][17])
            count_cs = int(batting_blines[tm][id][18])
            
            count_sh = int(batting_blines[tm][id][11])
            count_sf = int(batting_blines[tm][id][12])
#            count_hbp = int(batting_blines[tm][id][13])
            count_ibb = int(batting_blines[tm][id][15])
            count_gidp = int(batting_blines[tm][id][19])
            count_int = int(batting_blines[tm][id][20])
            
            doubles_string = add_to_line_conditionally(count_2b,doubles_string,tm,id)
            triples_string = add_to_line_conditionally(count_3b,triples_string,tm,id)
            homeruns_string = add_to_line_conditionally(count_hr,homeruns_string,tm,id)
            sb_string = add_to_line_conditionally(count_sb,sb_string,tm,id)
            cs_string = add_to_line_conditionally(count_cs,cs_string,tm,id)
                            
            sh_string = add_to_line_conditionally(count_sh,sh_string,tm,id)
            sf_string = add_to_line_conditionally(count_sf,sf_string,tm,id)
#            hbp_string = add_to_line_conditionally(count_hbp,hbp_string,tm,id)
            ibb_string = add_to_line_conditionally(count_ibb,ibb_string,tm,id)
            gidp_string = add_to_line_conditionally(count_gidp,gidp_string,tm,id)
            reached_on_int_string = add_to_line_conditionally(count_int,reached_on_int_string,tm,id)

    if len(doubles_string) > 0:
        output_file.write("<b>2B:</b> %s. " % (doubles_string))
    if len(triples_string) > 0:
        output_file.write("<b>3B:</b> %s. " % (triples_string))
    if len(homeruns_string) > 0:
        output_file.write("<b>HR:</b> %s. " % (homeruns_string))
    
    if len(sh_string) > 0:
        output_file.write("<b>SH:</b> %s. " % (sh_string))
    if len(sf_string) > 0:
        output_file.write("<b>SF:</b> %s. " % (sf_string))
    if len(hbp_dict[tm]) > 0:
        output_file.write("<b>HBP:</b> ")
        count_of_hbp = 0
        for hit_batter in hbp_dict[tm]:
            if count_of_hbp > 0:
                output_file.write(", ")
            h_hitter = hit_batter.split(":")[0]
            h_pitcher = hit_batter.split(":")[1]
            output_file.write("%s (by %s)" % (player_info[game_info[tm]][h_hitter],player_info[game_info[get_opponent(tm)]][h_pitcher]))
            count_of_hbp += 1
        output_file.write(".")
        
    if len(ibb_string) > 0:
        output_file.write("<b>IBB:</b> %s. " % (ibb_string))
    if len(gidp_string) > 0:
        output_file.write("<b>GIDP:</b> %s. " % (gidp_string))
    if len(reached_on_int_string) > 0:
        output_file.write("<b>Reached on interference:</b> %s. " % (reached_on_int_string))

    if len(sb_string) > 0 or len(cs_string) > 0:
        if len(sb_string) > 0:
            output_file.write("<b>SB:</b> %s. " % (sb_string))
        if len(cs_string) > 0:
            output_file.write("<b>CS:</b> %s. " % (cs_string))

    # Double plays - grouped by team
    dp_count = 0
    dp_string = ""
    for tm in ["road","home"]:
        dp_team_string = ""
        if int(team_totals[tm]["NumberOfDP"]) > 0:
            for play in dp_dict[tm]:
                play_names = "(" + convert_event_play_to_name_string(tm,play) + ")"
                if dp_team_string == "":
                    dp_team_string = "%s" % (team_abbrev_to_full_name[game_info[tm]]) + " " + play_names
                else:
                    dp_team_string = dp_team_string + ", " + play_names
                dp_count += 1
        if len(dp_team_string) > 0:
            dp_string = dp_string + dp_team_string + ". "
                
    if len(dp_string) > 0:
        output_file.write(" <b>DP:</b> %s" % (dp_string))

    # Triple plays - grouped by team
    tp_count = 0
    tp_string = ""
    for tm in ["road","home"]:
        tp_team_string = ""
        if int(team_totals[tm]["NumberOfTP"]) > 0:
            for play in tp_dict[tm]:
                play_names = "(" + convert_event_play_to_name_string(tm,play) + ")"
                if tp_team_string == "":
                    tp_team_string = "%s" % (team_abbrev_to_full_name[game_info[tm]]) + " " + play_names
                else:
                    tp_team_string = tp_team_string + ", " + play_names
                tp_count += 1
        if len(tp_team_string) > 0:
            tp_string = tp_string + tp_team_string + ". "
                
    if len(tp_string) > 0:
        output_file.write(" <b>TP:</b> %s" % (tp_string))

    # 
    # END OF NOTES SECTION
    #
    output_file.write('\n          </div>\n')

    ##############################################################
    #
    # Pitching summary
    #
    (road_outs_so_far_in_game, road_batters_faced_array, road_wild_pitches_string, road_balks_string) = print_pitching_table_html("road")
    (home_outs_so_far_in_game, home_batters_faced_array, home_wild_pitches_string, home_balks_string) = print_pitching_table_html("home")

    output_file.write('          <div class="notes">')

    # Only one of these can NOT be a multiple of 3 but we need to check both of them.
    outs_so_far_in_game_dict = defaultdict()
    outs_so_far_in_game_dict["road"] = road_outs_so_far_in_game
    outs_so_far_in_game_dict["home"] = home_outs_so_far_in_game
    
    game_ended_in_middle_of_inning = ""

    for tm in ["road","home"]:
        outs_at_end_of_game = outs_so_far_in_game_dict[tm] % 3
        if outs_at_end_of_game == 1 or outs_at_end_of_game == 2 or (outs_so_far_in_game_dict[tm] / 3) != len(linescores[get_opp(tm)]):
    #        if ((outs_so_far_in_game / 3) != len(linescores[get_opp(tm)])):
            # Game may have ended with 0,1,2 outs when winning run scored, or
            # the game could have been called due to rain or other reasons.
            # Determine if winning run scored in the final inning.
            if team_totals["home"]["runs"] > team_totals["road"]["runs"]:
                # Check runs scored by home team in their final inning. Were those the 'winning' runs?
                if (team_totals["home"]["runs"] - int(linescores["home"][len(linescores["home"])-1])) <= team_totals["road"]["runs"]:
                    if outs_at_end_of_game == 1:
                        game_ended_in_middle_of_inning = "One out when winning run scored\.n"
                    elif outs_at_end_of_game == 2:
                        game_ended_in_middle_of_inning = "Two outs when winning run scored.\n"
                    else:
                        if (outs_so_far_in_game_dict[tm] / 3) != len(linescores[get_opp(tm)]):
                            game_ended_in_middle_of_inning = "No outs when winning run scored.\n"
    if len(game_ended_in_middle_of_inning) > 0:
        output_file.write("%s<br>" % (game_ended_in_middle_of_inning))

    for bf in road_batters_faced_array:
        output_file.write("%s<br>" % (bf))

    if len(road_wild_pitches_string) > 0 or len(home_wild_pitches_string) > 0:
        output_file.write("<b>WP:</b>%s %s " % (road_wild_pitches_string, home_wild_pitches_string))
        
    if len(road_balks_string) > 0 or len(home_balks_string) > 0:
        output_file.write("<b>BALK:</b>%s %s " % (road_balks_string, home_balks_string))

    # LIMITATION: In our format, we store umpire full names in the EBx file, 
    #             instead of ids that we would look up in an umpire list file.
    #             Also, in 1946 specific umpire positions were not listed, so we omit them.
#    output_file.write("\nUmpires: HP - %s, 1B - %s, 2B - %s, 3B - %s\n" % (game_info["umphome"],game_info["ump1b"],game_info["ump2b"],game_info["ump3b"]))
    
    if len(game_info["umphome"]) > 0 or len(game_info["ump1b"]) > 0 or len(game_info["ump2b"]) > 0 or len(game_info["ump3b"]) > 0:
        umpire_string = ""
        umpire_string = add_to_string_conditionally(game_info["umphome"], umpire_string)
        umpire_string = add_to_string_conditionally(game_info["ump1b"], umpire_string)
        umpire_string = add_to_string_conditionally(game_info["ump2b"], umpire_string)
        umpire_string = add_to_string_conditionally(game_info["ump3b"], umpire_string)
        output_file.write("<b>Umpires:</b> " + umpire_string + ". ")
    
#    output_file.write("\nTime of Game: %s   Attendance: %s\n" % (get_time_in_hr_min(int(game_info["timeofgame"])),get_attendance(game_info["attendance"])))
    output_file.write("<b>T:</b> %s. <b>A:</b> %s. " % (get_time_in_hr_min(int(game_info["timeofgame"])), get_attendance(game_info["attendance"])))
    
    if len(game_comment_string) > 0:
        output_file.write("<b>Notes:</b> %s" % (game_comment_string))

    # Close the notes section
    output_file.write('\n          </div>')
    
    # Close the game-container
    output_file.write('\n       </div> <!-- end of game-container -->\n\n')


# This is the old text-based function used in bp_generate_box.py    
def print_box():
    if team_totals["home"]["runs"] >= team_totals["road"]["runs"]:
        winning_team = "home"
        losing_team = "road"
    else:
        losing_team = "home"
        winning_team = "road"
    output_line = "\n%s %s, %s %s" % (team_abbrev_to_full_name[game_info[winning_team]],team_totals[winning_team]["runs"],team_abbrev_to_full_name[game_info[losing_team]],team_totals[losing_team]["runs"])
    if game_number_this_day != "0":
        output_line = output_line + " (%s)" % game_number_this_day
    output_file.write("%s\n" % (output_line))
    
    output_line = "\nGame Played on "
    game_day = datetime.datetime.strptime(game_info["date"], '%Y/%m/%d').strftime('%A, %B %d, %Y')
    if game_info["daynight"] == "day":
        game_daynight = " (D) "
    elif game_info["daynight"] == "night":
        game_daynight = " (N) "
    else:
        game_daynight = " "
#    print(game_info["site"])
    location = park_info[game_info["site"]]["name"] + " (" + park_info[game_info["site"]]["city"] + ", " + park_info[game_info["site"]]["state"] + ")"
    output_line += game_day + game_daynight + "at %s" % (location)
    
    output_file.write("%s\n\n" % (output_line))
        
    max_inning_count = max(len(linescores["road"]),len(linescores["home"]))
    for tm in ["road","home"]:
        output_file.write("%3s %s" % (game_info[tm],league_classification))
        inning_count = 0
        for inn in linescores[tm]:
            if inning_count % 3 == 0:
                output_file.write("  ")
            output_file.write("%3d" % (int(inn)))
            inning_count += 1
        
        if inning_count < max_inning_count:
            if inning_count % 3 == 0:
                output_file.write("  ")
            output_file.write("  X")
        
        output_file.write("  -  %2s %2s %2s" % (team_totals[tm]["runs"],team_totals[tm]["hits"],team_totals[tm]["errors"]))
#        output_file.write("  -  %2d %2d %2d" % (team_totals[tm]["runs"],team_totals[tm]["hits"],team_totals[tm]["errors"]))
        
        output_file.write("\n");

    for tm in ["road","home"]:

        ##############################################################
        #
        # Batting table portion of box score
        #
        output_file.write("\n%-30sAB   R   H RBI      BB  SO      PO   A\n" % team_abbrev_to_full_name[game_info[tm]])
        batters_by_slot = defaultdict()
        for p in batting_blines[tm]:
            # id,side,pos,seq,ab,r,h,2b,3b,hr,rbi,sh,sf,hbp,bb,ibb,k,sb,cs,gidp,int
            # Store in dictionary by batting order slot and sequence number inside that slot.
            the_key = "batter_%02d_%02d" % (int(batting_blines[tm][p][2]),int(batting_blines[tm][p][3]))
            batters_by_slot[the_key] = batting_blines[tm][p]
        
        for p in sorted(batters_by_slot.keys()):
            id = check_stat(batters_by_slot[p][0])
            ab = check_stat(batters_by_slot[p][4])
            runs = check_stat(batters_by_slot[p][5])
            hits = check_stat(batters_by_slot[p][6])
            rbi = check_stat(batters_by_slot[p][10])
            bb = check_stat(batters_by_slot[p][14])
            strikeouts = check_stat(batters_by_slot[p][16])
            
            # dline format
            # id,side,seq,pos,if*3,po,a,e,dp,tp,pb
            if id in defensive_dlines[tm]:
                po = defensive_dlines[tm][id][5]
                assists = defensive_dlines[tm][id][6]
            else:
                # Will not have dline if only a PR or PH
                po = 0
                assists = 0
                
            if batters_by_slot[p][3] != "0": # came off bench, so indent the batter's name
                name = " "
            else:
                name = ""
            name += player_info[game_info[tm]][id]
            
            name += " " + get_positions(tm,id)

            output_file.write("%-30s%2s  %2s  %2s  %2s      %2s  %2s      %2s  %2s\n" % (name,ab,runs,hits,rbi,bb,strikeouts,po,assists))
                
        output_file.write("%-30s%2s  %2s  %2s  %2s      %2s  %2s      %2s  %2s\n" % ("TOTALS",team_totals[tm]["ab"],team_totals[tm]["runs"],team_totals[tm]["hits"],team_totals[tm]["rbi"],team_totals[tm]["bb"],team_totals[tm]["strikeouts"],team_totals[tm]["po"],team_totals[tm]["assists"]))
        
        ##############################################################
        #
        # Pinch-hitters and pinch-runners
        #
        pinch_count = 0

        for ph in pinch_hitters[tm]:
            output_file.write("\n%s pinch-hit in the %s inning" % (player_info[game_info[tm]][ph],convert_to_ordinal_string(int(pinch_hitters[tm][ph]))))
            pinch_count += 1
            
        for pr in pinch_runners[tm]:
            output_file.write("\n%s pinch-runner in the %s inning" % (player_info[game_info[tm]][pr],convert_to_ordinal_string(int(pinch_runners[tm][pr]))))
            pinch_count += 1
            
        if pinch_count > 0:
            output_file.write("\n")
            
        ##############################################################
        #
        # Fielding summary
        #
        output_file.write("\nFIELDING -")
        if int(team_totals[tm]["NumberOfDP"]) > 0:
            play_string = ""
            for play in dp_dict[tm]:
                play_names = convert_event_play_to_name_string(tm,play)
                if play_string == "":
                    play_string = play_names
                else:
                    play_string = play_string + ", " + play_names
            output_file.write("\nDP: %s. %s." % (team_totals[tm]["NumberOfDP"],play_string))
        if int(team_totals[tm]["NumberOfTP"]) > 0:
            play_string = ""
            for play in tp_dict[tm]:
                play_names = convert_event_play_to_name_string(tm,play)
                if play_string == "":
                    play_string = play_names
                else:
                    play_string = play_string + ", " + play_names
            output_file.write("\nTP: %s. %s." % (team_totals[tm]["NumberOfTP"],play_string))
        
        # Errors
        if team_totals[tm]["errors"] > 0:
            error_string = ""
            # We store the following in the defensive_dlines dictionary:
            # id,side,seq,pos,if*3,po,a,e,dp,tp,pb
            for id in defensive_dlines[tm]:
                error_count = int(defensive_dlines[tm][id][7])
                error_string = add_to_line_conditionally(error_count,error_string,tm,id)
            
            output_file.write("\nE: %s" % (error_string))
        
        ##############################################################
        #
        # Batting summary (2B, 3B, HR)
        #
        output_file.write("\n\nBATTING -")
        
        doubles_string = ""
        triples_string = ""
        homeruns_string = ""
        sb_string = ""
        cs_string = ""
        sh_string = ""
        sf_string = ""
#        hbp_string = ""
        ibb_string = ""
        gidp_string = ""
        reached_on_int_string = ""
        
        # The batting_blines dict contains lines of the form:
        # id,side,pos,seq,ab,r,h,2b,3b,hr,rbi,sh,sf,hbp,bb,ibb,k,sb,cs,gidp,int
        for id in batting_blines[tm]:
            count_2b = int(batting_blines[tm][id][7])
            count_3b = int(batting_blines[tm][id][8])
            count_hr = int(batting_blines[tm][id][9])
            count_sb = int(batting_blines[tm][id][17])
            count_cs = int(batting_blines[tm][id][18])
            
            count_sh = int(batting_blines[tm][id][11])
            count_sf = int(batting_blines[tm][id][12])
#            count_hbp = int(batting_blines[tm][id][13])
            count_ibb = int(batting_blines[tm][id][15])
            count_gidp = int(batting_blines[tm][id][19])
            count_int = int(batting_blines[tm][id][20])
            
            doubles_string = add_to_line_conditionally(count_2b,doubles_string,tm,id)
            triples_string = add_to_line_conditionally(count_3b,triples_string,tm,id)
            homeruns_string = add_to_line_conditionally(count_hr,homeruns_string,tm,id)
            sb_string = add_to_line_conditionally(count_sb,sb_string,tm,id)
            cs_string = add_to_line_conditionally(count_cs,cs_string,tm,id)
                            
            sh_string = add_to_line_conditionally(count_sh,sh_string,tm,id)
            sf_string = add_to_line_conditionally(count_sf,sf_string,tm,id)
#            hbp_string = add_to_line_conditionally(count_hbp,hbp_string,tm,id)
            ibb_string = add_to_line_conditionally(count_ibb,ibb_string,tm,id)
            gidp_string = add_to_line_conditionally(count_gidp,gidp_string,tm,id)
            reached_on_int_string = add_to_line_conditionally(count_int,reached_on_int_string,tm,id)

        if len(doubles_string) > 0:
            output_file.write("\n2B: %s" % (doubles_string))
        if len(triples_string) > 0:
            output_file.write("\n3B: %s" % (triples_string))
        if len(homeruns_string) > 0:
            output_file.write("\nHR: %s" % (homeruns_string))
        
        if len(sh_string) > 0:
            output_file.write("\nSH: %s" % (sh_string))
        if len(sf_string) > 0:
            output_file.write("\nSF: %s" % (sf_string))
        if len(hbp_dict[tm]) > 0:
            output_file.write("\nHBP: ")
            count_of_hbp = 0
            for hit_batter in hbp_dict[tm]:
                if count_of_hbp > 0:
                    output_file.write(", ")
                h_hitter = hit_batter.split(":")[0]
                h_pitcher = hit_batter.split(":")[1]
                output_file.write("%s (by %s)" % (player_info[game_info[tm]][h_hitter],player_info[game_info[get_opponent(tm)]][h_pitcher]))
                count_of_hbp += 1
            
        if len(ibb_string) > 0:
            output_file.write("\nIBB: %s" % (ibb_string))
        if len(gidp_string) > 0:
            output_file.write("\nGIDP: %s" % (gidp_string))
        if len(reached_on_int_string) > 0:
            output_file.write("\nReached on interference: %s" % (reached_on_int_string))
        if int(team_totals[tm]["LOB"]) >= 0:    
            output_file.write("\nTeam LOB: %s" % (team_totals[tm]["LOB"]))
        
        ##############################################################
        #
        # Baserunning summary (SB, CS)
        #
        if len(sb_string) > 0 or len(cs_string) > 0:
            output_file.write("\n\nBASERUNNING -")
            if len(sb_string) > 0:
                output_file.write("\nSB: %s" % (sb_string))
            if len(cs_string) > 0:
                output_file.write("\nCS: %s" % (cs_string))
            
        ##############################################################
        #
        # Pitching summary
        #
        output_file.write("\n\n%-30sIP     H   R  ER  BB  SO  HR BFP" % team_abbrev_to_full_name[game_info[tm]])
        pitchers_by_slot = defaultdict()
        for p in pitching_plines[tm]:
            # plines should be in seq order already, but we will re-sort them just in case.
            # id,side,seq,ip*3,no-out,bfp,h,2b,3b,hr,r,er,bb,ibb,k,hbp,wp,balk,sh,sf
            the_key = "pitcher_%02d" % int(pitching_plines[tm][p][2])
            pitchers_by_slot[the_key] = pitching_plines[tm][p]

        wild_pitches_string = ""
        balks_string = ""        
        for p in sorted(pitchers_by_slot.keys()):
        
            id = pitchers_by_slot[p][0]
            outs = int(pitchers_by_slot[p][3])
            update_pitching_totals_conditionally(tm,"outs",outs)
            hits = int(pitchers_by_slot[p][6])
            update_pitching_totals_conditionally(tm,"h",hits)
            runs = int(pitchers_by_slot[p][10])
            update_pitching_totals_conditionally(tm,"r",runs)
            er = int(pitchers_by_slot[p][11])
            update_pitching_totals_conditionally(tm,"er",er)
            bb = int(pitchers_by_slot[p][12])
            update_pitching_totals_conditionally(tm,"bb",bb)
            so = int(pitchers_by_slot[p][14])
            update_pitching_totals_conditionally(tm,"so",so)
            hr = int(pitchers_by_slot[p][9])
            update_pitching_totals_conditionally(tm,"hr",hr)
            bfp = int(pitchers_by_slot[p][5])
            update_pitching_totals_conditionally(tm,"bfp",bfp)
            
            wildpitches = int(pitchers_by_slot[p][16])
            wild_pitches_string = add_to_line_conditionally(wildpitches,wild_pitches_string,tm,id)            
            balks = int(pitchers_by_slot[p][17])
            balks_string = add_to_line_conditionally(balks,balks_string,tm,id)            
            
            hits = check_stat(pitchers_by_slot[p][6])
            runs = check_stat(pitchers_by_slot[p][10])
            er = check_stat(pitchers_by_slot[p][11])
            bb = check_stat(pitchers_by_slot[p][12])
            so = check_stat(pitchers_by_slot[p][14])
            hr = check_stat(pitchers_by_slot[p][9])
            bfp = check_stat(pitchers_by_slot[p][5])
            
            pitcher_name = player_info[game_info[tm]][id]
            if id == winning_pitcher_id:
                pitcher_name = pitcher_name + " W"
            elif id == losing_pitcher_id:
                pitcher_name = pitcher_name + " L"
            output_file.write("\n%-30s%s%s  %2s  %2s  %2s  %2s  %2s  %2s %3s" % (pitcher_name,get_full_innings(outs),get_partial_innings(outs),hits,runs,er,bb,so,hr,bfp))
#            print ("%s:%s" % (p,pitchers_by_slot[p]))
            
        # Convert stats to string, honoring the rule that a negative number means 
        # that we do not have a valid value for this stat.
        for stat in pitching_totals[tm]:
#            print("%s = %s" % (stat,str(pitching_totals[tm][stat])))
            pitching_totals[stat] = check_stat(str(pitching_totals[tm][stat]))
                
        output_file.write("\n%-30s%s%s  %2s  %2s  %2s  %2s  %2s  %2s %3s" % ("TOTALS",get_full_innings(pitching_totals[tm]["outs"]),get_partial_innings(pitching_totals[tm]["outs"]),pitching_totals[tm]["h"],pitching_totals[tm]["r"],pitching_totals[tm]["er"],pitching_totals[tm]["bb"],pitching_totals[tm]["so"],pitching_totals[tm]["hr"],pitching_totals[tm]["bfp"]))
        
        additional_pitching_info_string = ""
        if len(wild_pitches_string) > 0:
            additional_pitching_info_string = additional_pitching_info_string + "\nWP: %s" % (wild_pitches_string)
        if len(balks_string) > 0:
            additional_pitching_info_string = additional_pitching_info_string + "\nBALK: %s" % (balks_string)
        if len(additional_pitching_info_string) > 0:
            output_file.write("\n%s" % (additional_pitching_info_string))
        
        output_file.write("\n")
        
        extra_info_string = ""
        # XYZ faced X batters in the Xth inning
        outs_so_far_in_game = 0
        for p in sorted(pitchers_by_slot.keys()):
            id = pitchers_by_slot[p][0]
            outs_so_far_in_game = outs_so_far_in_game + int(pitchers_by_slot[p][3])
            batters_faced_in_Xth_inning = int(pitchers_by_slot[p][4])
            if batters_faced_in_Xth_inning > 0:
                pitcher_name = player_info[game_info[tm]][id]
                the_Xth_inning = get_next_inning_based_on_outs(outs_so_far_in_game)
                if batters_faced_in_Xth_inning == 1:
                    batter_text_string = "batter"
                else:
                    batter_text_string = "batters"
                extra_info_string = extra_info_string + "%s faced %d %s in the %s inning\n" % (pitcher_name,batters_faced_in_Xth_inning,batter_text_string,the_Xth_inning)
        
        outs_at_end_of_game = outs_so_far_in_game % 3
        if outs_at_end_of_game == 1 or outs_at_end_of_game == 2 or (outs_so_far_in_game / 3) != len(linescores[get_opp(tm)]):
#        if ((outs_so_far_in_game / 3) != len(linescores[get_opp(tm)])):
            # Game may have ended with 0,1,2 outs when winning run scored, or
            # the game could have been called due to rain or other reasons.
            # Determine if winning run scored in the final inning.
            if team_totals["home"]["runs"] > team_totals["road"]["runs"]:
                # Check runs scored by home team in their final inning. Were those the 'winning' runs?
                if (team_totals["home"]["runs"] - int(linescores["home"][len(linescores["home"])-1])) <= team_totals["road"]["runs"]:
                    if outs_at_end_of_game == 1:
                        extra_info_string = extra_info_string + "One out when winning run scored\n"
                    elif outs_at_end_of_game == 2:
                        extra_info_string = extra_info_string + "Two outs when winning run scored\n"
                    else:
                        if (outs_so_far_in_game / 3) != len(linescores[get_opp(tm)]):
                            extra_info_string = extra_info_string + "No outs when winning run scored\n"
         
        if len(extra_info_string) > 0:
            output_file.write("\n%s" % (extra_info_string))
        
        output_file.write("\n")
            
    # LIMITATION: In our format, we store umpire full names in the EBx file, 
    #             instead of ids that we would look up in an umpire list file.
    #             Also, in 1938 specific umpire positions were not listed, so we omit them.
#    output_file.write("\nUmpires: HP - %s, 1B - %s, 2B - %s, 3B - %s\n" % (game_info["umphome"],game_info["ump1b"],game_info["ump2b"],game_info["ump3b"]))
    output_file.write("\nUmpires: %s, %s" % (game_info["umphome"],game_info["ump1b"]))
    if len(game_info["ump2b"]) > 0:
        output_file.write(", %s" % (game_info["ump2b"]))
    if len(game_info["ump3b"]) > 0:
        output_file.write(", %s" % (game_info["ump3b"]))
    output_file.write("\n")
    
    output_file.write("\nTime of Game: %s   Attendance: %s\n" % (get_time_in_hr_min(int(game_info["timeofgame"])),get_attendance(game_info["attendance"])))
    
    if len(game_comment_string) > 0:
        output_file.write("\nNOTES: %s\n\n" % (game_comment_string))
    else:
        output_file.write("\n")
        
    output_file.write("=====================================================================\n")


def update_standings_streak(the_streak,result):
    # the_streak is either W#, L#, T# or None (at start of season)
    # result is WIN, LOSS, TIE

    if the_streak[0:1] == result[0:1]:
        # Streak continues! Increment win/loss/tie total
        count = int(the_streak[1:2]) + 1
        return(the_streak[0:1] + str(count))

    # Otherwise, it is the start of a new streak
    return(result[0:1] + "1")


def print_todays_standings(todays_date):
    output_file.write("           <div class='column-25'>\n")
    output_file.write("             <div class='games-section-title'>STANDINGS</div>\n")    

    if todays_date in day_by_day_dict:
        for game_today in day_by_day_dict[todays_date]:
#            print(game_today)
            road_team_abbrev = game_today.split("_")[1]
            road_team_runs = game_today.split("_")[2]
            home_team_abbrev = game_today.split("_")[3]
            home_team_runs = game_today.split("_")[4]
            rescheduled = game_today.split("_")[7]

            # Skip postponed games and games that were later overturned on protest
            if rescheduled != "PROTESTEDSUCCESSFULLY" and road_team_runs != "PPD" and home_team_runs != "PPD":

                neutral_site_info = game_today.split("_")[10]
                if len(neutral_site_info) > 1:
                    played_at_neutral_site = True
                else:
                    played_at_neutral_site = False
        
                if int(road_team_runs) > int(home_team_runs):
                    winner = road_team_abbrev
                    loser = home_team_abbrev
                    if not played_at_neutral_site:
                        standings_dict[road_team_abbrev]["road_wins"] += 1
                        standings_dict[home_team_abbrev]["home_losses"] += 1
                elif int(road_team_runs) < int(home_team_runs):
                    loser = road_team_abbrev
                    winner = home_team_abbrev
                    if not played_at_neutral_site:
                        standings_dict[road_team_abbrev]["road_losses"] += 1
                        standings_dict[home_team_abbrev]["home_wins"] += 1
                
                if int(road_team_runs) == int(home_team_runs):
                    standings_dict[road_team_abbrev]["ties"] += 1
                    standings_dict[home_team_abbrev]["ties"] += 1
                    standings_dict[road_team_abbrev]["streak"] = update_standings_streak(standings_dict[road_team_abbrev]["streak"],"TIE")
                    standings_dict[home_team_abbrev]["streak"] = update_standings_streak(standings_dict[home_team_abbrev]["streak"],"TIE")
                    if not played_at_neutral_site:
                        standings_dict[road_team_abbrev]["road_ties"] += 1
                        standings_dict[home_team_abbrev]["home_ties"] += 1
                    
                else:
                    standings_dict[winner]["wins"] += 1
                    standings_dict[loser]["losses"] += 1
                    standings_dict[winner]["streak"] = update_standings_streak(standings_dict[winner]["streak"],"WIN")
                    standings_dict[loser]["streak"] = update_standings_streak(standings_dict[loser]["streak"],"LOSS")
    
    # TBD Would like to add Games Back GB (would need to increase 'newspaper' max width again: was 1200px, I made it 1300px)
    output_file.write("              <table class='standings-table'>\n")
    output_file.write("               <thead>\n")
    output_file.write("                <tr>\n")
    output_file.write("                 <th class='team-col'>Team</th>\n")
    output_file.write("                 <th class='num-col'>W</th>\n") # TBD use pct-col for GB
    output_file.write("                 <th class='num-col'>L</th>\n")
    output_file.write("                 <th class='num-col'>T</th>\n")
    output_file.write("                 <th class='pct-col'>Pct</th>\n")
    output_file.write("                 <th class='pct-col'>Str</th>\n")
    output_file.write("                 <th class='pct-col'>Home</th>\n")
    output_file.write("                 <th class='pct-col'>Road</th>\n")
    output_file.write("                </tr>\n")
    output_file.write("               </thead>\n")

    output_file.write("               <tbody>\n")

    for team in standings_dict:
        if int(standings_dict[team]["wins"]) + int(standings_dict[team]["losses"]) == 0:
            standings_dict[team]["pct"] = ".000"
        else:
            tm_pct = int(standings_dict[team]["wins"]) / (int(standings_dict[team]["wins"]) + int(standings_dict[team]["losses"]))
            tm_pct_string = f"{tm_pct:.3f}"
            if tm_pct_string.startswith("0."):
                tm_pct_string = tm_pct_string[1:]
#            standings_dict[team]["pct"] = float(f"{tm_pct:.3f}")
            standings_dict[team]["pct"] = tm_pct_string

    # need to sort by Pct
    standings_dict_pct = defaultdict()
    for team in standings_dict:
        standings_dict_pct[team] = standings_dict[team]["pct"]
    
    for team in dict(sorted(standings_dict_pct.items(), key=operator.itemgetter(1), reverse=True)):
        output_file.write("                <tr data-team=''>\n") # omitting data-team for now because I deactivated highlighting by team
        output_file.write("                 <td class='team-col'>%s</th>\n" % (team_abbrev_to_city[team]))
        output_file.write("                 <td class='num-col'>%s</th>\n" % (standings_dict[team]["wins"]))
        output_file.write("                 <td class='num-col'>%s</th>\n" % (standings_dict[team]["losses"]))
        output_file.write("                 <td class='num-col'>%s</th>\n" % (standings_dict[team]["ties"]))
        output_file.write("                 <td class='pct-col'>%s</th>\n" % (standings_dict[team]["pct"]))
        output_file.write("                 <td class='pct-col'>%s</th>\n" % (standings_dict[team]["streak"]))
        # omit ties for now in these columns to save space
        output_file.write("                 <td class='pct-col'>%s-%s</th>\n" % (standings_dict[team]["home_wins"] , standings_dict[team]["home_losses"]))
        output_file.write("                 <td class='pct-col'>%s-%s</th>\n" % (standings_dict[team]["road_wins"] , standings_dict[team]["road_losses"]))
        output_file.write("                </tr>\n")
        
    output_file.write("               </tbody>\n")

    output_file.write("              </table>\n")
    
    output_file.write("             </div>\n")    

def print_todays_scores(todays_date):  
    output_file.write("           <div class='column-25'>\n")
    output_file.write("             <div class='games-section-title'>TODAY'S SCORES</div>\n")    
    if todays_date in day_by_day_dict:
        for game_today in day_by_day_dict[todays_date]:
#            print(game_today)
            road_team_abbrev = game_today.split("_")[1]
            road_team_runs = game_today.split("_")[2]
            home_team_abbrev = game_today.split("_")[3]
            home_team_runs = game_today.split("_")[4]
            innings = game_today.split("_")[5]
            
            rescheduled = game_today.split("_")[7]
            shortened_reason = game_today.split("_")[9]
            neutral_site_info = game_today.split("_")[10]
            
            output_file.write("             <div class='game-score-line' data-team-away='%s' data-team-home='%s'>\n" % (road_team_abbrev,home_team_abbrev))
            
            # TECHDEBT: We are not correctly handling cases where a scheduled 7-inning game 
            #            takes exactly 9 innings to play due to extra innings. In theory,
            #            we should print (9). But this never happened in 1946 Eastern League
            #            and as along as the box scores include a note about this, that
            #            is good enough.
            if innings == "" or innings == "9":
                innings_to_print = "" # print nothing
            else:
                if len(shortened_reason) > 1:
                    innings_to_print = " (%s, %s) " % (innings, shortened_reason)
                else:
                    innings_to_print = " (%s) " % (innings)

            # In theory, either both will be PPD or neither will be.
            # But check them both.
            if rescheduled == "PROTESTEDSUCCESSFULLY":
                postponed_reason = game_today.split("_")[8] # This is actually a note about the protest.
                if len(postponed_reason) > 1:
                    postponed_string = postponed_reason
                else:
                    postponed_string = "Overtuned on protest"
                output_file.write("        %s at %s (%s)\n" % (team_abbrev_to_full_name[road_team_abbrev], team_abbrev_to_full_name[home_team_abbrev], postponed_string))

            elif road_team_runs == "PPD" or home_team_runs == "PPD":
                postponed_reason = game_today.split("_")[8]
                if len(postponed_reason) > 1:
                    postponed_string = "PPD " + postponed_reason
                else:
                    postponed_string = "PPD"
                output_file.write("        %s at %s (%s)\n" % (team_abbrev_to_full_name[road_team_abbrev], team_abbrev_to_full_name[home_team_abbrev], postponed_string))
            
            else:
                if len(neutral_site_info) > 1:
                    innings_to_print = innings_to_print + " at %s" % (neutral_site_info)
                    
                if int(road_team_runs) > int(home_team_runs):
                    output_file.write('                <span class="winner">%s %s</span>, <span class="">%s %s</span>%s\n' % (team_abbrev_to_full_name[road_team_abbrev], road_team_runs, team_abbrev_to_full_name[home_team_abbrev], home_team_runs, innings_to_print))
                elif int(road_team_runs) < int(home_team_runs):
                    output_file.write('                <span class="">%s %s</span>, <span class="winner">%s %s</span>%s\n' % (team_abbrev_to_full_name[road_team_abbrev], road_team_runs, team_abbrev_to_full_name[home_team_abbrev], home_team_runs, innings_to_print))
                else:
                    output_file.write('                <span class="">%s %s</span>, <span class="">%s %s</span>%s\n' % (team_abbrev_to_full_name[road_team_abbrev], road_team_runs, team_abbrev_to_full_name[home_team_abbrev], home_team_runs, innings_to_print))                                    
            
            
            output_file.write("             </div>\n")
    else:
            output_file.write("             <div class='game-score-line' data-team-away='NONE' data-team-home='NONE'>\n")
            output_file.write("             No Games Scheduled\n")
            output_file.write("             </div>\n")
    output_file.write("           </div>\n")


def print_original_schedule_for_today(todays_date):                        
    output_file.write("           <div class='column-25'>\n")
    output_file.write("             <div class='games-section-title'>TODAY'S ORIGINAL SCHEDULE</div>\n")
    if todays_date in original_schedule_dict:
        for game_today in original_schedule_dict[todays_date]:
            road_team_abbrev = game_today.split("_")[1]
            home_team_abbrev = game_today.split("_")[3]
            output_file.write("             <div class='original-schedule-game' data-team-away='%s' data-team-home='%s'>\n" % (road_team_abbrev,home_team_abbrev))
            # TECHDEBT: this does not handle neutral games because the original_schedule_dict file doesn't have a column for that yet.
            output_file.write("             %s at %s\n" % (team_abbrev_to_full_name[road_team_abbrev], team_abbrev_to_full_name[home_team_abbrev]))
            output_file.write("             </div>\n")
    else:
            output_file.write("             <div class='original-schedule-game' data-team-away='NONE' data-team-home='NONE'>\n")
            output_file.write("             No Games Scheduled\n")
            output_file.write("             </div>\n")
    output_file.write("           </div>\n")


def print_tomorrows_games(tomorrows_date):                            
    output_file.write("           <div class='column-25'>\n")
    output_file.write("             <div class='games-section-title'>TOMORROW'S GAMES</div>\n")
    if tomorrows_date in day_by_day_dict:
        for game_tomorrow in day_by_day_dict[tomorrows_date]:
            road_team_abbrev = game_tomorrow.split("_")[1]
            home_team_abbrev = game_tomorrow.split("_")[3]
            game_time = game_tomorrow.split("_")[6]
            neutral_site_info = game_tomorrow.split("_")[10]
            
            output_file.write("             <div class='tomorrow-game' data-team-away='%s' data-team-home='%s'>\n" % (road_team_abbrev,home_team_abbrev))
            
            if len(neutral_site_info) > 1:
                output_file.write("             %s vs. %s at %s" % (team_abbrev_to_full_name[road_team_abbrev], team_abbrev_to_full_name[home_team_abbrev], neutral_site_info))
            else:
                output_file.write("             %s at %s" % (team_abbrev_to_full_name[road_team_abbrev], team_abbrev_to_full_name[home_team_abbrev]))
                
            if len(game_time) > 0:
                output_file.write(", %s\n" % (game_time))
            else:
                output_file.write("\n")
                
            output_file.write("             </div>\n")
    else:
            output_file.write("             <div class='tomorrow-game' data-team-away='NONE' data-team-home='NONE'>\n")
            output_file.write("             No Games Scheduled\n")
            output_file.write("             </div>\n")
    output_file.write("           </div>\n")
    
##########################################################
#
# Main program
#

parser = argparse.ArgumentParser(description='Create box scores based on a Retrosheet event file.') 
parser.add_argument('file', help="Event file (input)")
parser.add_argument('bfile', help="Box score file in html format (output)")
parser.add_argument('-playoffs', '-p', help="Playoff info file")
parser.add_argument('-actual_schedule', '-a', help="List of games as actually played")
parser.add_argument('-original_schedule', '-o', help="List of games as originally scheduled")

args = parser.parse_args()

# Read in all of the .ROS files up front so we can build dictionary of player ids and names, by team.
(player_info,list_of_teams) = bp_load_roster_files()

if len(list_of_teams) == 0:
    print("ERROR: Could not find any roster files. Exiting.")
    sys.exit(0)

# Read in parkcode.txt file    
park_info = defaultdict(dict)
filename = "parkcode.txt"
with open(filename,'r') as csvfile: # file is automatically closed when this block completes
    items = csv.reader(csvfile)
    for row in items:    
        # PARKID,NAME,AKA,CITY,STATE,START,END,LEAGUE,NOTES
        # COL01,Red Bird Stadium,,Columbus,OH,01/01/1932,12/31/1954,AA
        if len(row) > 0:
            if row[0] != "PARKID":
                park_info[row[0]] = defaultdict()
                park_info[row[0]]["name"] = row[1]
                park_info[row[0]]["city"] = row[3]
                park_info[row[0]]["state"] = row[4]
    
if len(park_info) == 0:
    print("ERROR: Could not find any ballpark infomation. Exiting.")
    sys.exit(0)

# Read in team full name file
team_abbrev_to_full_name = defaultdict()
team_abbrev_to_city = defaultdict()

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
            team_abbrev_to_city[row[0]] = row[2]
            league_classification = row[1]
        
# Initialize the rest of the structures we need.
game_info = defaultdict()
linescores = defaultdict()
batting_blines = defaultdict()
pinch_hitters = defaultdict()
pinch_runners = defaultdict()
defensive_dlines = defaultdict()
defensive_positions = defaultdict()
dp_dict = defaultdict()
tp_dict = defaultdict()
hbp_dict = defaultdict()
pitching_plines = defaultdict()
team_totals = defaultdict()
pitching_totals = defaultdict()
clear_between_games()    

game_comment_string = ""

number_of_box_scores_scanned = 0

# This will create the file if it does not exist already, and will overwrite file if it already exists.
output_file = open(args.bfile,'w') 

# #################################################
#
# Open .eba file to create day-by-day list of games

day_by_day_dict = defaultdict(lambda: defaultdict(list))
game_count = 0
with open(args.file,'r') as efile:
    for line in efile:
        line = line.rstrip()
        if line.count(",") > 0:
            line_type = line.split(",")[0]

            if line_type == "id":
                if game_count > 0:
                    # For now, postponed_reason, shortened_reason, and neutral_site_info is empty. Merge it in later.
                    this_game = game_id + "_" + road_team + "_" + road_runs + "_" + home_team + "_" + home_runs + "_" + number_of_innings + "_" + game_time + "__P_S_N"
                    if game_date in day_by_day_dict:
                        day_by_day_dict[game_date].append(this_game)
                    else:
                        day_by_day_dict[game_date] = [this_game]

                game_id = line.split(",")[1]
                game_count += 1
                
            elif line_type == "info":
                if line.count(",") == 2:
                    info_type = line.split(",")[1]
                    if info_type == "visteam":
                        road_team = line.split(",")[2]
                    elif info_type == "hometeam":
                        home_team = line.split(",")[2]
                    elif info_type == "date":
                        game_date = line.split(",")[2]
                    elif info_type == "starttime":
                        game_time = line.split(",")[2].lower()
                        if game_time == "00:00pm": # this is the default and means we do not have the data
                            game_time = ""
                        game_time = re.sub("^0","",game_time) # get rid of leading zero
            
            elif line_type == "line":
                if line.split(",")[1] == "0": # road team because home team might not bat in the bottom of the last inning
                    number_of_innings = str(line.count(",") - 1)
                
            elif line_type == "teamstat":
                team_id = line.split(",")[1]
                team_runs = line.split(",")[3]
                if team_id == "0":
                    road_runs = str(team_runs)
                elif team_id == "1":
                    home_runs = str(team_runs)

# finish last game   
if game_count > 0:                 
    this_game = game_id + "_" + road_team + "_" + road_runs + "_" + home_team + "_" + home_runs + "_" + number_of_innings + "_" + game_time + "__P_S_N"
    if game_date in day_by_day_dict:
        day_by_day_dict[game_date].append(this_game)
    else:
        day_by_day_dict[game_date] = [this_game]                    


###########################################################
#
# Read in original schedule information if provided
#
# PRV194605080,FRV,2,PRV,6,
original_schedule_dict = defaultdict(lambda: defaultdict(list))
if args.original_schedule:
    with open(args.original_schedule,'r') as csvfile:
        items = csv.reader(csvfile)
        for row in items:    
            if len(row) > 0:
                game_id = row[0]
                road_team = row[1]
                home_team = row[3]
                
                # Put X's in the runs fields for now
                this_game = game_id + "_" + road_team + "_" + "X" + "_" + home_team + "_" + "X" + "_"
                date_from_game_id = game_id[3:7] + "/" + game_id[7:9] + "/" + game_id[9:11]
                
                if date_from_game_id in original_schedule_dict:
                    original_schedule_dict[date_from_game_id].append(this_game)
                else:
                    original_schedule_dict[date_from_game_id] = [this_game]

# print(original_schedule_dict)

###########################################################
#
# Read in actual schedule/results if provided, but do not overwrite games that already exist in the dict.
#
# PAW194608230,MAN,PPD,PAW,PPD,,8:30pm,RAINEDOUT,Rain,,
if args.actual_schedule:
    with open(args.actual_schedule,'r') as csvfile:
        items = csv.reader(csvfile)
        for row in items:    
            if len(row) > 0:
                game_id = row[0]
                road_team = row[1]
                road_runs = row[2]
                home_team = row[3]
                home_runs = row[4]
                innings = row[5]
                game_time = row[6]
                rescheduled = row[7]
                postponed_reason = row[8]
                shortened_reason = row[9]
                neutral_site_info = row[10]
                
                this_game = game_id + "_" + road_team + "_" + road_runs + "_" + home_team + "_" + home_runs + "_" + innings + "_" + game_time + "_" + rescheduled + "_" + postponed_reason + "_" + shortened_reason + "_" + neutral_site_info
                date_from_game_id = game_id[3:7] + "/" + game_id[7:9] + "/" + game_id[9:11]
                
                if date_from_game_id in day_by_day_dict:
                    found_game = False
#                    for gm in day_by_day_dict[date_from_game_id]:
                    for gm_index,gm in enumerate(day_by_day_dict[date_from_game_id]):
                        gameid_already_in_dict = gm.split("_")[0]
                        if game_id == gameid_already_in_dict:
                            found_game = True
                            # Determine if there is any postponed_reason, shortened_reason, or neutral_site_info 
                            # that needs to be merged into this string.
                            if len(postponed_reason) > 0 or len(shortened_reason) > 0 or len(neutral_site_info) > 0:
                                data_to_merge = postponed_reason + "_" + shortened_reason + "_" + neutral_site_info
                                re.sub("P_S_N", data_to_merge, day_by_day_dict[date_from_game_id][gm_index])
                                # TBD debug print
                                print("Merging %s into game %s\n" % (data_to_merge, game_id))
                            
                    if not found_game:
                        day_by_day_dict[date_from_game_id].append(this_game)
                else:
                    day_by_day_dict[date_from_game_id] = [this_game]

# print(original_schedule_dict)




boxscore_header = """
<html><head><meta http-equiv="Content-Type" content="text/html; charset=UTF-8">
  
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="format-detection" content="telephone=no">
  <title>1946 Eastern League Baseball Box Scores</title>
  <style>
    @import url('https://fonts.googleapis.com/css2?family=Source+Sans+3:ital,wght@0,200..900;1,200..900&display=swap');
    :root {
      --bg-page: #f9f7f1;
      --bg-paper: #fff;
      --text-primary: #000;
      --text-secondary: #333;
      --text-muted: #666;
      --border-strong: #000;
      --border-light: #ddd;
      --shadow: rgba(0,0,0,0.1);
      --hover-bg: #f0f0f0;
      --highlight-bg: #fff3cd;
      --highlight-box-bg: #fff9e6;
      --highlight-border: #ffc107;
    }
    body.dark-mode {
      --bg-page: #121212;
      --bg-paper: #1e1e1e;
      --text-primary: #e0e0e0;
      --text-secondary: #ccc;
      --text-muted: #999;
      --border-strong: #555;
      --border-light: #333;
      --shadow: rgba(0,0,0,0.4);
      --hover-bg: #2a2a2a;
      --highlight-bg: #3a3520;
      --highlight-box-bg: #2e2b1a;
      --highlight-border: #ffc107;
    }
    body { font-family: 'Source Sans 3', 'Segoe UI'; margin: 0; padding: 0; background-color: var(--bg-page); color: var(--text-primary); }
    a { color: var(--text-primary); }
    .newspaper { max-width: 1300px; margin: 0 auto; padding: 20px; background-color: var(--bg-paper); box-shadow: 0 0 10px var(--shadow); } /* increased from 1200px to 1300px to provide room for 4-column table */
    .header { text-align: center; border-bottom: 2px solid var(--border-strong); padding-bottom: 10px; margin-bottom: 20px; }
    .date { font-style: italic; margin-bottom: 10px; }
    .credit-line { font-style: italic; text-align: center; margin-bottom: 10px; border-top: 1px solid var(--border-strong); } /* added for credit line */
    .main-title { font-size: 42px; font-weight: bold; margin: 0; }
    .subtitle { font-size: 24px; margin: 5px 0 15px 0; }
    .page { break-after: page; }
    .nav-container { display: flex; justify-content: space-between; align-items: center; padding: 10px 0; margin: 10px 0; border-top: 1px solid var(--border-light); border-bottom: 1px solid var(--border-light); }
    .leaders div { font-size: 14px; margin: 4px 0px; }
    .leaders table { font-size: 14px; margin: 5px 0px; }
    .boxscores-title { text-align: center; font-size: 24px; font-weight: bold; margin: 10px 0; border-bottom: 2px solid var(--border-strong); }
    .boxscores-subtitle { text-align: center; font-size: 18px; font-weight: bold; margin: 10px 0; border-bottom: 1px solid var(--border-strong); }
    .boxscores-container { column-count: 4; column-gap: 20px; margin-top: 20px; }
    .game-container { break-inside: avoid; page-break-inside: avoid; margin-bottom: 20px; }
    .game-header { font-weight: bold; font-size: 20px; solid var(--border-strong); } /* removed border-bottom: 1px because I added game-location underneath it */
    .game-location { border-bottom: 1px solid var(--border-strong); } /* Added for game date and location */
    .team-line { display: flex; justify-content: space-between; font-size: 14px; font-weight: 700; line-height: 1.2; margin-top: 2px; }
    /* Improved table styling */
    table { width: 100%; border-collapse: collapse; font-size: 14px; table-layout: fixed; }
    .batting tr:last-child { font-weight:700 }
    th, td { text-align: left; overflow: hidden; line-height: 1.1; }
    th { border-top: 1px solid var(--border-strong); font-weight: bold; }
    /* Specific column widths for standings tables */
    .standings-table th { border: none; }
    .standings-table .team-col { width: 16%; text-align: left; } /* shrunk from 20% to 16% to save space */
    .standings-table .num-col { width: 5%; text-align: right; }
    .standings-table .pct-col { width: 8%; text-align: right; }
    /* General column alignment */
    th:not(.team-col), td:not(.team-col) { text-align: right; }
    td { white-space: nowrap; }
    .notes { font-size: 14px; line-height: 1.2; padding: 4px 0; border-top: 1px solid var(--border-strong); }
    .section { margin-bottom: 20px; }
    .column-container { display: flex; gap: 15px; }
    .column { flex: 1; }
    .column-25 { width: 25%; }
    .column-40 { width: 40%; }
    .column-60 { width: 60%; }
    .stats-header { font-size: 16px; font-weight: bold; margin: 8px 0; border-bottom: 1px solid var(--border-strong); }
    .stats-subheader { font-size: 14px; font-weight: bold; margin: 4px 0; border-bottom: 1px solid var(--border-strong); }
    /* Batting and pitching table styles */
    .batting-table .player-col { width: 30%; text-align: left; }
    .batting-table .player-col-substitute { width: 30%; text-align: left; padding-left: 10px;} /* added for substitute case */
    .batting-table .stat-col { width: 5%; text-align: right; }
    .batting-table .avg-col { width: 8%; text-align: right; }
    .batting-table tr:last-child { font-weight:700 }
    .pitching-table .player-col { width: 37%; text-align: left; }
    .pitching-table .ip-col { width: 5%; text-align: right; }
    .pitching-table .stat-col { width: 5%; text-align: right; }
    .pitching-table .era-col { width: 10%; text-align: right; }
    .pitching-table tr:last-child { font-weight:700 } /* added to match the batting-table so the Totals line is in bold */
    
    /* Leaders table styles */
    .leaders-table th { border: none; }
    .leaders-table .player-col { width: 30%; text-align: left; }
    .leaders-table .stat-col { width: 5%; text-align: right; }
    .leaders-table .avg-col { width: 8%; text-align: right; }
    .leaders-section { margin-bottom: 20px; }
    .leaders-note { font-size: 13px; margin: 5px 0; }
    /* Games Schedule Section */
    .games-section { margin-bottom: 20px; padding: 10px 0; border-top: 2px solid var(--border-strong); }
    .games-section .column-container { display: flex; gap: 20px; }
    .games-left { width: 65%; }
    .games-left-inner { display: grid; grid-template-columns: 1fr 1fr; gap: 4px 20px; }
    .games-right { width: 35%; display: flex; flex-direction: column; gap: 15px; }
    .games-section-title { font-size: 16px; font-weight: bold; margin-bottom: 8px; border-bottom: 1px solid var(--border-strong); padding-bottom: 4px; }
    .game-score-line { font-size: 13px; line-height: 1.5; margin: 2px 0; }
    .game-score-line .winner { font-weight: bold; }
    .scheduled-game { padding-bottom: 4px; border-bottom: 1px dotted var(--border-strong); }
    .scheduled-game:last-child { border-bottom: none; }
    .center-links { display: flex; align-items: center; gap: 0; }
    .nav-divider { display: inline-block; width: 1px; height: 14px; background-color: var(--border-strong); margin: 0 10px; }
    .dark-toggle { cursor: pointer; }
    .game-time { font-size: 12px; color: var(--text-muted); }
    .matchup { font-size: 14px; font-weight: bold; }
    .pitchers { font-size: 12px; color: var(--text-secondary); }
    .tomorrow-game { font-size: 13px; line-height: 1.6; }
    .original-schedule-game { font-size: 13px; line-height: 1.6; }
    .leaders-note span.team-highlight { padding: 0 2px; }
  @media (min-width: 700px) and (max-width: 1000px) {
    .main-title { font-size:32px; }
    .subtitle { font-size:20px; }
    .stats-subheader { font-size:16px; }
    .game-header { font-size:26px; }
    .game-location { font-size:20px; }
    .boxscores-container { column-count: 1; column-gap: 10px; margin-top: 10px; }
    .column-container { display: block }
    table { font-size: 16px; }
    .team-line { font-size: 20px; }
    .leaders div { font-size: 16px; }
    .leaders table { font-size: 16px; }
    .leaders-note { font-size:16px; }
    .notes { font-size: 16px; }
    .column-25, .column-40, .column-60 { width: 100%; }
    .games-section .column-container { flex-direction: column; }
    .games-left, .games-right { width: 100%; }
    .games-left-inner { grid-template-columns: 1fr; }
  }
  @media (max-width: 700px) {
    .main-title { font-size:28px; }
    .subtitle { font-size:18px; }
    .stats-subheader { font-size:14px; }
    .game-header { font-size:22px; }
    .game-location { font-size:16px; }
    .boxscores-container { column-count: 1; column-gap: 10px; margin-top: 10px; }
    .column-container { display: block }
    table { font-size: 14px; }
    .team-line { font-size: 18px; }
    .leaders div { font-size: 14px; }
    .leaders table { font-size: 14px; }
    .leaders-note { font-size:14px; }
    .notes { font-size: 14px; }
    .column-25, .column-40, .column-60 { width: 100%; }
    .games-section .column-container { flex-direction: column; }
    .games-left, .games-right { width: 100%; }
    .games-left-inner { grid-template-columns: 1fr; }
  }
  @media print {
      body { 
        background-color: #fff;
        color: #000;
          width:1650px;
        --bg-page: #fff; --bg-paper: #fff; --text-primary: #000; --border-strong: #000; --border-light: #ddd;
      }
      .newspaper { box-shadow: none; max-width: none; padding: 0; margin: 0; }
      .nav-container { display: none; }
      .dark-toggle { display: none; }
      .column-container { display: flex; }
      .boxscores-container { column-count: 5; }
    }
  </style>

</head>
<body>
<script>if(localStorage.getItem('darkMode')==='on')document.body.classList.add('dark-mode');</script>
  <div class="newspaper">
    <div class="header">
      <h1 class="main-title">1946 Eastern League Baseball Box Scores</h1>
      <div class="subtitle">As Researched by Michael Hamel / DistantReplay</div>
"""
output_file.write(boxscore_header)

output_file.write('          <div class="date">Updated %s</div>' % (datetime.today().strftime('%B %d, %Y')))

list_of_regular_season_game_days = []

if args.playoffs:

    boxscore_header_playoffs = """      
        </div>

        <div class='page'>
          <div class='section'>
            <div class='column-container'>
              <div class='column-40'>
                <div class='boxscores-title'>Playoff Series Results</div>
"""

    output_file.write(boxscore_header_playoffs)

    playoff_series_dict = defaultdict(lambda: defaultdict(list))
    with open(args.playoffs,'r') as pfile:
        for line in pfile:
            line = line.rstrip()
            if line.count(",") > 0:            
                line_type = line.split(",")[0]
                if line_type == "Series":
                    series_name = line.split(",")[1]
                    output_file.write('                  <div class="stats-subheader">%s</div>\n' % (series_name))
                    outcome_string = line.split(",")[2]
                    list_of_game_ids = line.split(",",3)[3] # split 3 times and take the rest
                    # print(list_of_game_ids)
                    
                    output_file.write('                   <div class="leaders-note">\n')
                    
                    # look up game information for this game of the series
                    game_info_to_print = ""
                    for game in list_of_game_ids.split(","):
                        date_from_game_id = game[3:7] + "/" + game[7:9] + "/" + game[9:11]
                        for game_id in day_by_day_dict[date_from_game_id]:
                            if game_id.split("_")[0] == game:
                                
                                road_team = game_id.split("_")[1]
                                road_runs = game_id.split("_")[2]
                                home_team = game_id.split("_")[3]
                                home_runs = game_id.split("_")[4]
                                innings = game_id.split("_")[5]
                                
                                month_day = datetime.strptime(game_id[3:11], "%Y%m%d").strftime("%b %e")
                                
                                if innings == "9":
                                    innings_to_print = "" # print nothing
                                else:
                                    innings_to_print = " (%s) " % (innings)
                                
                                output_file.write('                    <div class="game-score-line" data-team-away="%s" data-team-home="%s">\n' % (road_team, home_team))
                                output_file.write('                      <span class="">%s:</span>\n' % (month_day))
                                
                                if int(road_runs) > int(home_runs):
                                    output_file.write('                      <span class="winner">%s %s</span>, <span class="">%s %s</span>%s\n' % (team_abbrev_to_full_name[road_team], road_runs, team_abbrev_to_full_name[home_team], home_runs, innings_to_print))
                                elif int(road_runs) < int(home_runs):
                                    output_file.write('                      <span class="">%s %s</span>, <span class="winner">%s %s</span>%s\n' % (team_abbrev_to_full_name[road_team], road_runs, team_abbrev_to_full_name[home_team], home_runs, innings_to_print))
                                else:
                                    output_file.write('                      <span class="">%s %s</span>, <span class="">%s %s</span>%s\n' % (team_abbrev_to_full_name[road_team], road_runs, team_abbrev_to_full_name[home_team], home_runs, innings_to_print))
                                
                                output_file.write('                    </div>\n')                                

                        
                    output_file.write('                      <span class=""><i>%s</i><br><br></span>\n' % (outcome_string))
                    output_file.write('                   </div>\n')

    output_file.write('             </div>\n') # close column-40
    


    output_file.write('          <div class="column-60">\n')
    output_file.write('            <div class="boxscores-title">Day-by-Day</div>\n')
    output_file.write('              <table><tr valign=top><td width=45%>\n')
    number_of_days = len(day_by_day_dict)
    count_of_days = 0
    for day in day_by_day_dict:
        count_of_days += 1

        # extract full month name and day without leading zero
        month_day = datetime.strptime(day, "%Y/%m/%d").strftime("%B %e")
        
        output_file.write('              <div class="games-section-title">%s</div>\n' % (month_day))
        for game in day_by_day_dict[day]:
            road_team = game.split("_")[1]
            road_runs = game.split("_")[2]
            home_team = game.split("_")[3]
            home_runs = game.split("_")[4]
            innings = game.split("_")[5]
            
            if innings == "9":
                innings_to_print = "" # print nothing
            else:
                innings_to_print = " (%s) " % (innings)
            
            output_file.write('              <div class="game-score-line" data-team-away="%s" data-team-home="%s">\n' % (road_team, home_team))
            
            if int(road_runs) > int(home_runs):
                output_file.write('                <span class="winner">%s %s</span>, <span class="">%s %s%s</span>\n' % (team_abbrev_to_full_name[road_team], road_runs, team_abbrev_to_full_name[home_team], home_runs, innings_to_print))
            elif int(road_runs) < int(home_runs):
                output_file.write('                <span class="">%s %s</span>, <span class="winner">%s %s%s</span>\n' % (team_abbrev_to_full_name[road_team], road_runs, team_abbrev_to_full_name[home_team], home_runs, innings_to_print))
            else:
                output_file.write('                <span class="">%s %s</span>, <span class="">%s %s%s</span>\n' % (team_abbrev_to_full_name[road_team], road_runs, team_abbrev_to_full_name[home_team], home_runs, innings_to_print))
            
            output_file.write('              </div>\n')
        output_file.write('              <br>\n') # break between days
        
        if count_of_days == math.ceil(number_of_days / 2):
            # start second column
            output_file.write('              </td>\n')
            output_file.write('              <td width=10%></td><td width=45%>\n')
            
    output_file.write('              </td></tr></table>\n')
    output_file.write('            </div>\n')
    output_file.write('          </div>\n')
    output_file.write('        </div>\n')

    output_file.write("    <div class='page'>\n")
    output_file.write("      <div class='boxscores-title'>PLAYOFF BOX SCORES</div>\n")
    output_file.write("      <div class='boxscores-container'>\n")

else: # For regular season we need standings and schedule info prior to each day's box scores

    boxscore_header2 = """      
    </div>

    <div class="page">
    """

    output_file.write(boxscore_header2)
              
#    output_file.write("    <div class='page'>\n")

    # Display standings, results, and original schedule for each day first and then the box 
    # scores that day. Assume that the .EBA file is in chronological order and use the date portion
    # of the game id to figure out when to switch days - but handle case where ZERO games were
    # due to rainouts, etc.
    #
    # IMPORTANT: My original 1946NEL.EBA for the playoffs is NOT in perfect chronological order
    #            because I wanted to display the boxes grouped by series, not dates.

    # TBD I'm not sure all of the "div's" in the .htm are balanced, but it seems to work.
    
    # TBD this is fake data for testing
#    original_schedule_dict["1946/08/01"] = ["DummyData"] # no games on this date, first game is AFTER this date
#    original_schedule_dict["1946/09/05"] = ["DummyData"]
#    original_schedule_dict["1946/09/07"] = ["DummyData"] # no games on this date
#    original_schedule_dict["1946/09/22"] = ["DummyData"] # no games on this date, last game is BEFORE this date
    
    all_date_keys = set(day_by_day_dict) | set(original_schedule_dict)

    # 2. Convert to datetime and sort
    sorted_dates = sorted(all_date_keys, key=lambda d: datetime.strptime(d, "%Y/%m/%d"))

# print(sorted_dates)    
next_game_date_index = 0

################################################
#
# Create the standings dictionary
#

standings_dict = defaultdict(lambda: defaultdict(dict))

for team in team_abbrev_to_full_name:
    standings_dict[team]["wins"] = 0
    standings_dict[team]["losses"] = 0
    standings_dict[team]["ties"] = 0
    standings_dict[team]["streak"] = "None"
    standings_dict[team]["pct"] = ".000"
    standings_dict[team]["home_wins"] = 0
    standings_dict[team]["home_losses"] = 0
    standings_dict[team]["home_ties"] = 0
    standings_dict[team]["road_wins"] = 0
    standings_dict[team]["road_losses"] = 0
    standings_dict[team]["road_ties"] = 0

################################################
#
# Now open the .eba file again to process the box scores
#

with open(args.file,'r') as efile:
    # We could use csv library, but I worry about reading very large files.
    for line in efile:
        line = line.rstrip()
        if line.count(",") > 0:
            line_type = line.split(",")[0]
            
            if line_type == "id":
                # The id field is always the first field in a box score, 
                # so print the preceding box score before doing anything else
                if number_of_box_scores_scanned > 0:
                    # print_box()
                    print_box_html()
                    clear_between_games()
                    game_comment_string = ""
                number_of_box_scores_scanned += 1
                
                if not args.playoffs:
                    
                    # For regular season, we want to display standings/results/original schedule info in between 
                    # each day of box scores. Use the id as a sentinel. If the date info inside the id changes,
                    # that tells us that it is time to display the standings/results/original schedule info.
                    
                    game_id = line.split(",")[1]            
                    date_from_game_id = game_id[3:7] + "/" + game_id[7:9] + "/" + game_id[9:11]
                    check_dates = compare_dates(date_from_game_id,sorted_dates[next_game_date_index])
                    if check_dates == "Match" or check_dates == "Later":
                        while check_dates != "Match":
                            # This means that there were no games actually played on the sorted_dates[next_game_date_index] date.
                            # Need to display standings/schedule (no results) for sorted_dates[next_game_date_index] and continue
                            # to increment the next_game_date_index (and display standings/schedule) until we reach a date that
                            # matches the date of the current game (date_from_game_id).                            
                            
                            if next_game_date_index != 0:
                                output_file.write("      </div>\n")
                            
                            # Today's date as header
                            output_file.write("\n      <div class='boxscores-title'>%s</div>\n" % (convert_slashdate_to_fulldate(sorted_dates[next_game_date_index])))
                            
                            todays_date = sorted_dates[next_game_date_index]
                            
                            output_file.write("           <div class='column-container'>\n")                         
                            print_todays_standings(todays_date)
                            print_todays_scores(todays_date)
                            print_original_schedule_for_today(todays_date)

                            tomorrows_date = next_day(sorted_dates[next_game_date_index])
                            print_tomorrows_games(tomorrows_date)
                            output_file.write("      </div>\n")

                            output_file.write("      <div class='boxscores-container'>\n")

                            next_game_date_index += 1
                            check_dates = compare_dates(date_from_game_id,sorted_dates[next_game_date_index])

                        if next_game_date_index != 0:
                            output_file.write("           </div>\n")
                            
                        output_file.write("\n      <div class='boxscores-title'>%s</div>\n" % (convert_slashdate_to_fulldate(date_from_game_id)))

                        todays_date = date_from_game_id

                        output_file.write("           <div class='column-container'>\n")                         
                        print_todays_standings(todays_date)
                        print_todays_scores(todays_date)
                        print_original_schedule_for_today(todays_date)

                        tomorrows_date = next_day(date_from_game_id)
                        print_tomorrows_games(tomorrows_date)
                        output_file.write("           </div>\n")

                        # Uses a special subtitle style with a smaller font size and a thinner underline border
                        output_file.write("      <div class='boxscores-subtitle'>BOX SCORES</div>\n")
                        output_file.write("      <div class='boxscores-container'>\n")                            
                        
                        next_game_date_index += 1

                    # elif check_dates == "Earlier": # do nothing, simply process and print the next box score
            
            elif line_type == "stat":
                sub_line_type = line.split(",")[1]
                if sub_line_type == "bline":
                    # stat,bline,id,side,pos,seq,ab,r,h,2b,3b,hr,rbi,sh,sf,hbp,bb,ibb,k,sb,cs,gidp,int
                    side = int(line.split(",")[3])
                    if side == ROAD_ID:
                        lookup = "road"
                    else:
                        lookup = "home"
                    
                    id = line.split(",")[2]
                    batting_blines[lookup][id] = line.split(",")[2:]
                    
                    # increment team totals
                    update_team_totals_conditionally(lookup,"ab",int(line.split(",")[6]))
                    update_team_totals_conditionally(lookup,"runs",int(line.split(",")[7]))
                    update_team_totals_conditionally(lookup,"hits",int(line.split(",")[8]))
                    update_team_totals_conditionally(lookup,"rbi",int(line.split(",")[12]))
                    update_team_totals_conditionally(lookup,"bb",int(line.split(",")[16]))
                    update_team_totals_conditionally(lookup,"strikeouts",int(line.split(",")[18]))
                
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
                    
                    # increment team totals
                    update_team_totals_conditionally(lookup,"po",int(line.split(",")[7]))
                    update_team_totals_conditionally(lookup,"assists",int(line.split(",")[8]))
                    update_team_totals_conditionally(lookup,"errors",int(line.split(",")[9]))

                elif sub_line_type == "pline":
                    # stat,pline,id,side,seq,ip*3,no-out,bfp,h,2b,3b,hr,r,er,bb,ibb,k,hbp,wp,balk,sh,sf
                    side = int(line.split(",")[3])
                    if side == ROAD_ID:
                        lookup = "road"
                    else:
                        lookup = "home"

                    id = line.split(",")[2]
                    pitching_plines[lookup][id] = line.split(",")[2:]
                    
                elif sub_line_type == "tline":
                    # stat,tline,side,left-on-base,earned runs,number of DP turned,number of TP turned
                    side = int(line.split(",")[2])
                    if side == ROAD_ID:
                        lookup = "road"
                    else:
                        lookup = "home"
                    team_totals[lookup]["LOB"] = line.split(",")[3]
                    team_totals[lookup]["EarnedRuns"] = line.split(",")[4]
                    team_totals[lookup]["NumberOfDP"] = line.split(",")[5]
                    team_totals[lookup]["NumberOfTP"] = line.split(",")[6]
                 
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
                        
            elif line_type == "event":
                # event,dpline,side of team who turned the DP,player-id (who turned the DP)...
                # event,tpline,side of team who turned the TP,player-id (who turned the TP)...                
                # event,hpline,side of pitcher's team,pitcher-id,batter-id
                sub_line_type = line.split(",")[1]
                side = int(line.split(",")[2])
                if side == ROAD_ID:
                    lookup = "road"
                    opponent = "home"
                else:
                    lookup = "home"
                    opponent = "road"
                if sub_line_type == "dpline":
                    dp_dict[lookup].append(":".join(line.split(",")[3:]))
                elif sub_line_type == "tpline":
                    tp_dict[lookup].append(":".join(line.split(",")[3:]))
                elif sub_line_type == "hpline":
                    # put the hitter first, and index by the BATTER's team
                    hbp_dict[opponent].append("%s:%s" % (line.split(",")[4],line.split(",")[3]))
                
            elif line_type == "line":
                # linescore
                side = int(line.split(",")[1])
                if side == ROAD_ID:
                    lookup = "road"
                else:
                    lookup = "home"

                innings = line.split(",")[2:]
                for single_inning in innings:
                    linescores[lookup].append(single_inning)
                
            elif line_type == "info":
                if line.count(",") == 2:
                    info_type = line.split(",")[1]
                    game_info[info_type] = line.split(",")[2]
                 
                    # We use "road" and "home" in our dictionaries, so store that info
                    # indexed by those names too.
                    if info_type == "visteam":
                        game_info["road"] = line.split(",")[2]
                    elif info_type == "hometeam":
                        game_info["home"] = line.split(",")[2]
                    elif info_type == "wp":
                        winning_pitcher_id = line.split(",")[2]
                    elif info_type == "lp":
                        losing_pitcher_id = line.split(",")[2]
                    elif info_type == "number":
                        game_number_this_day = line.split(",")[2]

            elif line_type == "com":
                # split only on first comma so we keep any in the comment
                game_comment_string = line.split(",",1)[1].strip()
                
                # now strip leading and trailing quotes if included in the comment
                if game_comment_string.startswith("\""):
                    game_comment_string = game_comment_string[1:]
                if game_comment_string.endswith("\""):
                    game_comment_string = game_comment_string[:-1]
                        
# print the last box score                
# print_box() old text-based function
if number_of_box_scores_scanned > 0:
    print_box_html()

# For regular season case, print any extra days at the end of the original schedule where no games were found.

if not args.playoffs:
    while next_game_date_index < len(sorted_dates):
        print("Cleaning up additional off days (%s)" % (sorted_dates[next_game_date_index]))
        
        if next_game_date_index != 0:
            output_file.write("      </div>\n")        
#        output_file.write("      <div class='boxscores-title'>CLEANUP NO GAMES %s</div>\n" % (sorted_dates[next_game_date_index]))
        output_file.write("\n      <div class='boxscores-title'>%s</div>\n" % (convert_slashdate_to_fulldate(sorted_dates[next_game_date_index])))
#        output_file.write("      <div class='boxscores-container'>\n")        
        
        todays_date = sorted_dates[next_game_date_index]
        
        output_file.write("           <div class='column-container'>\n")
        
        print_todays_standings(todays_date)
        print_todays_scores(todays_date)
        print_original_schedule_for_today(todays_date)

        tomorrows_date = next_day(sorted_dates[next_game_date_index])
        print_tomorrows_games(tomorrows_date)        
        output_file.write("      </div>\n")

        output_file.write("      <div class='boxscores-container'>\n")
                            
        next_game_date_index += 1

boxscore_footer = """
       </div>
    </div>      
    <div class="credit-line">HTML CSS styles adapted from <a href='https://www.waldrn.com/boxscores/'>David Waldron's daily box scores</a></div>
  </div>
</body>
"""
output_file.write(boxscore_footer)

output_file.close()

print("Done - converted %d box scores" % (number_of_box_scores_scanned))
                
