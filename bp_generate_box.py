#########################################################################
#
# Creates text file with box scores based on a Retrosheet-like Event file 
# that roughly follows the "EBx" format.
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
#  1.4  MH  11/23/2022  Added league_classification variable.
#  1.3  MH  04/26/2020  Correct handling of "X outs when winning run scored"
#  1.2  MH  03/07/2020  Add pinch-runner info
#  1.1  MH  01/16/2020  Use bp_load_roster_files()
#  1.0  MH  06/05/2019  Initial version
#
import argparse, csv, datetime, glob, math, os, re, sys
from collections import defaultdict
from bp_utils import bp_load_roster_files

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
    
##########################################################
#
# Main program
#


parser = argparse.ArgumentParser(description='Create box scores based on a Retrosheet event file.') 
parser.add_argument('file', help="Event file (input)")
parser.add_argument('bfile', help="Box score file (output)")
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
                        
            elif line_type == "version":  # sentinel that always starts a new box score
                if number_of_box_scores_scanned > 0:
                    print_box()
                    clear_between_games()
                    game_comment_string = ""
                number_of_box_scores_scanned += 1

# print the last box score                
print_box()                

output_file.close()

print("Done - converted %d box scores" % (number_of_box_scores_scanned))
                
