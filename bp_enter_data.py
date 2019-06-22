#########################################################################
#
# Creates/updates a Retrosheet Event file, roughly following the "EBx" format.
#
# CC License: Attribution-NonCommercial 4.0 International (CC BY-NC 4.0)
# https://creativecommons.org/licenses/by-nc/4.0/
#
# Proof-of-concept, tailored specifically for 1938 American Assocation box 
# scores as published in the Minneapolis Star and Tribune.
# Situations where we either deviate or do not meet full requirements of
# the Retrosheet format are labeled with "LIMITATION".
#
# References:
# https://www.retrosheet.org/eventfile.htm
# https://www.retrosheet.org/boxfile.txt
# 
# Requires:
# 1. A set of .ROS files in this folder, one per team, to be used to read player ids.
#    The bp_make_team_files.py script can be used to generate Retrosheet-compatible .ROS files.
#
#  1.0  MH  06/01/2019  Initial version
#
import argparse, csv, datetime, glob, os, re, sys
from collections import defaultdict
from shutil import copyfile

# TBD - should make season and output filename command-line args for flexibility.
# This is used to find roster files, build the output filename and 
# backup filename, and to simplify date entry by concatenating this
# to the month/day info inputed by the user.
season = "1938"
# I'm calling this "EBA" since A is AL and N is NL... so using A for AA makes some sense
output_filename = season + "MINAA.EBA"

DEBUG_ON = False

ROAD_ID = 0
HOME_ID = 1

#########################################################################
#
# Misc. input functions
#
#
def get_string():
    s = sys.stdin.readline() # read in one line through the \n
    s = s.rstrip() # remove line endings
    return s  
    
def get_number():
    valid_number = False
    while not valid_number:
        s = sys.stdin.readline() # read in one line through the \n
        s = s.rstrip() # remove line endings
        s = re.sub('[^0-9]','', s)
        if len(s) > 0: # make sure they typed at least ONE numeric character, or python will exit with an error
            number = int(s)
            valid_number = "yes"    
    return number

def get_number_max_allowed(max_allowed):
    valid_number = False
    while not valid_number:
        s = sys.stdin.readline() # read in one line through the \n
        s = s.rstrip() # remove line endings
        s = re.sub('[^0-9]','', s)
        if len(s) > 0: # make sure they typed at least ONE numeric character, or python will exit with an error
            number = int(s)
            if number <= max_allowed:
                valid_number = "yes"    
    return number
    
def get_time_string():
    valid_time = False
    while not valid_time:
        print("Enter start time (00:00AM or PM or blank if unknown): ")
        the_time = get_string()
        the_time = the_time.upper() # to make am or pm into AM/PM
        if len(the_time) == 0:
            return "00:00PM"
        elif re.match("[0-9]{2}:[0-9]{2}[AP]M",the_time):
            return the_time
    
def get_date_string():
    valid_date = False
    while not valid_date:
        print("Enter date (mm/dd) for %s: " % (season))
        the_date = get_string()
        if re.match("[0-9]{2}/[0-9]{2}",the_date):
            return season + "/" + the_date
            
def get_time_of_game_in_minutes():            
    valid_time = False
    # Accept input in Hours:Minutes, then convert to minutes
    while not valid_time:
        print("Enter time of game (HH:MM): ")
        the_time = get_string()
        if re.match("[0-9]{1,2}:[0-9]{2}",the_time):
            hours = the_time.split(":")[0]
            minutes = the_time.split(":")[1]
            time_in_minutes = (int(hours) * 60) + int(minutes)
            return time_in_minutes
            
# if bottom of last inning is not played, just leave blank            
def get_linescore_string(home_road_id,team_abbrev):
    print("Enter %s linescore comma-delimited: " % (team_abbrev))
    
    s = get_string()
    s = re.sub('[^0-9,]','', s) # strip everything except for numbers and commas
    return (str(home_road_id) + "," + s)
    
#########################################################################
#
# Menu functions
#
#    
def display_menu(menu):
    for count,item in enumerate(menu):
        line = "%2d. %s " % (count+1, item)
        print("%s" % line)
    
def get_menu_selection(menu,prompt):
    number_of_items = len(menu)
    if len(prompt) > 0:
        print("%s" % (prompt))    
        
    valid = False
    while not valid:
        menu_item_string = sys.stdin.readline()
        
        # remove \n and any non-numeric characters
        menu_item_string = menu_item_string.rstrip()
        menu_item_string = re.sub('[^0-9]','', menu_item_string)
        
        if len(menu_item_string) > 0:
            menu_item = int(menu_item_string)
            if ((menu_item >= 1) and (menu_item <= number_of_items)):
                valid = True
                
    return menu[menu_item-1]
    
def display_menu_get_selection(menu,prompt):
    display_menu(menu)
    return get_menu_selection(menu,prompt)

#########################################################################
#
# Some helper functions
#
#

# Allow player selection by typing first three letters of last name.
# If a player had a two-letter last name, use a hyphen for the third digit.
# If user inputs only a "+" character, return "stop" as the id as a signal
# to the calling function to stop asking for names.
def get_player_name_and_id(team):
    valid_name = False
    while not valid_name:
        print("[%s] Name (first three characters or '+' to stop): " % (team))
        n = get_string()
        if n == "+":
            return("nobody","stop")        
        n = n.lower()
        n = re.sub('[^a-z]','',n)
        if len(n) >= 3:
            first_three = n[:3]
            possible_name_list = ["TryAgain"]
            for pid in sorted(player_info[team]):
                if re.match(first_three,pid):
                    # Yes, this is a hack. By putting both the name and id in this array,
                    # display_menu_get_selection() will return them both, which we will 
                    # then split into their separate parts before returning them back to
                    # the caller.
                    possible_name_list.append(player_info[team][pid] + ":" + pid)
            name = display_menu_get_selection(possible_name_list,"")
            if name != "TryAgain":
                return (name.split(':')[0],name.split(':')[1])
                
# Similar to the above, but works for cases where we want a menu with players
# from more than one team.
# If user inputs only a "+" character, return "stop" as the id as a signal
# to the calling function to stop asking for names.
def get_player_name_and_id_and_team(team_list):
    valid_name = False
    while not valid_name:
        print("Name (first three characters or '+' to stop): ")
        n = get_string()
        if n == "+":
            return("nobody","stop","neither")        
        n = n.lower()
        n = re.sub('[^a-z]','',n)
        if len(n) >= 3:
            first_three = n[:3]
            possible_name_list = ["TryAgain"]
            for tm in team_list:
                for pid in sorted(player_info[tm]):
                    if re.match(first_three,pid):
                        # Yes, this is a hack. By putting both the name and id in this array,
                        # display_menu_get_selection() will return them both, which we will 
                        # then split into their separate parts before returning them back to
                        # the caller.
                        possible_name_list.append(tm + ":" + player_info[tm][pid] + ":" + pid)
                    
            name = display_menu_get_selection(possible_name_list,"")
            if name != "TryAgain":
                return (name.split(':')[1],name.split(':')[2],name.split(':')[0])

            
# Obtain list of player id's who turned a double play or triple play.
def get_fielding_play_info(prompt,home_team,road_team):
    d = defaultdict() # dictionary to store count of plays by individual players
    d[home_team] = defaultdict()
    d[road_team] = defaultdict()
        
    d_event_strings = defaultdict() # dictionary to store play info (player1 to player2 on a DP for example)
    d_event_strings[home_team] = []
    d_event_strings[road_team] = []

    menu_option_1 = "Next " + prompt
    all_plays_entered = False
    
    print("%s" % (prompt))
    while not all_plays_entered:
        response = display_menu_get_selection([menu_option_1,"Done"],"")
        if response == "Done":
            all_plays_entered = True
        else:
            # get list of names that participated in this play
            list_of_pids = []
            done_with_this_play = False
            while not done_with_this_play:
                print("Enter name(s) for %s ('+' to stop): " % (prompt))
                (player,pid,tm) = get_player_name_and_id_and_team([home_team,road_team])
                if pid == "stop":
                    done_with_this_play = True
                else:
                    list_of_pids.append(pid)
                    current_team = tm # when pid == 'stop', tm will be 'neither' and not valid
            
            print("Number of %s by this combination: " % (prompt))
            number_of_plays = get_number()

            # Use this number to increment count of plays that this player participated in
            for pid in list_of_pids:
                if pid in d[current_team]:
                    d[current_team][pid] += number_of_plays
                else:
                    d[current_team][pid] = number_of_plays
                    
            # Now build a string that represents the entire play, and add it to the strings 
            # dictionary, adding it one time for each time this combination completed such a play.
            detail_line = ""
            for pid in list_of_pids:
                if len(detail_line) > 0:
                    # do not add comma if this is the first player in the list
                    detail_line = detail_line + ","
                detail_line = detail_line + pid
            count = 0
            while count < number_of_plays:
                d_event_strings[current_team].append(detail_line)
                count += 1
            
    return (d,d_event_strings)
       
# For statistics that do not appear in the box score table, we ask the user 
# to enter the names of the players who had one or more of that particular stat.
def get_stats_summary_info(prompt,home_team,road_team):
    d = defaultdict()
    d[home_team] = defaultdict()
    d[road_team] = defaultdict()
    list_of_pids = []
    
    print("\nEnter names for %s: " % (prompt))
    done = False
    while not done:
        (player,pid,team) = get_player_name_and_id_and_team([home_team,road_team])
        if pid == "stop":
            done = True
        else:
            list_of_pids.append(pid)
            print("Number of %s: " % (prompt))
            stat = get_number()
            
            # Add to dictionary
            d[team][pid]=stat
                
    return d
    
# The 1938 boxscores do not contain any pitching 'tables' at all.
# We prompt for each pitcher for each team - in order for each team - and then
# prompt for the stats in an order that makes sense given the formats used
# in 1938.    
def get_pitching_summary_info(team_list):    
    d = defaultdict()
    
    for tm in team_list:
        print("\nEnter pitchers in the order that they pitched for %s: " % (tm))
        d[tm] = []
        sequence = 0
        
        done = False
        while not done:
            (player,pid) = get_player_name_and_id(tm)
            if pid == "stop":
                done = True
            else:
                print("Walks: ")
                walks = get_number()
                print("Strikeouts: ")
                strikeouts = get_number()
                print("Hits: ")
                hits = get_number()
                print("Runs: ")
                runs = get_number()
                print("WholeInnings: ")
                innings = get_number()
                print("ThirdInnings: ")
                thirdinnings = get_number()
                print("Extra batters faced: ")
                extra_batters = get_number()
                
                ip_times_3 = (innings * 3) + thirdinnings
                
                print("HBP: ")
                hbp = get_number()
                print("Wild pitches: ")
                wp = get_number()
                print("Balks: ")
                balk = get_number()
                
                # LIMITATION: actual batters faced would include folks who reach on errors,
                # but we do not have that data for 1938?
                approx_batters_faced = -1 # ip_times_3 + hits + walks + hbp
                
                # Full line looks as follows, we only do part of it here.
                # stat,pline,id,side,seq,ip*3,no-out,bfp,h,2b,3b,hr,r,er,bb,ibb,k,hbp,wp,balk,sh,sf
                #
                # In this function, we return: pid,seq,ip*3,no-out,bfp,hits,runs,walks,strikeouts,hbp,wp,balk
                stats_line = pid + "," + str(sequence) + "," + str(ip_times_3) + "," + str(extra_batters) + "," + str(approx_batters_faced) + "," + str(hits) + "," + str(runs) + "," + str(walks) + "," + str(strikeouts) + "," + str(hbp) + "," + str(wp) + "," + str(balk)
                
                d[tm].append(stats_line)
                sequence = sequence + 1
                
    return d

    
pos_string_to_number = {
    'p' : 1,
    'c' : 2,
    '1b' : 3,
    '2b' : 4,
    '3b' : 5,
    'ss' : 6,
    'lf' : 7,
    'cf' : 8,
    'rf' : 9,
    'dh' : 10,
    'pr' : 11,
    'ph' : 12
    }    
    
def string_pos_to_number(pos_as_string):
    if pos_as_string in pos_string_to_number:
        return pos_string_to_number[pos_as_string]
    
    print("ERROR: Invalid position string (%s) entered, please try again." % (pos_as_string))
    return 99
    
# Get list of defensive positions for a specific player.    
def get_defensive_positions():
    positions_complete = False
    invalid_position_detected = False
    
    while not positions_complete:
        # Prompt for string, RF-SS-P-PH-1B, etc.
        print("Enter defensive positions (1B, LF, PH, etc.) separated by hyphens: ")
   
        # Convert each position to the 1-9 position numbers (DH=10, PH=11, PR=12) before returning.
        s = get_string()
        s = s.lower()
        # Remove everything except alphanumeric (but allow only 1-3 for first-third) and hyphens
        s = re.sub('[^a-z1-3]-','',s)

        if s.count("-") > 0:
            # Multiple position strings provided, so scan them all
            s_list = s.split("-")
            s_number_list = []
            for pos in s_list:
                number = string_pos_to_number(pos)
                if number == 99:
                    invalid_position_detected = True
                else:
                    s_number_list.append(number)
            
            # Break out of while loop if no invalid positions were detected
            if not invalid_position_detected:
                positions_complete = True
                    
        else:
            # Single position string provided, so decode and then return.
            number = string_pos_to_number(s)
            if number != 99:
                return number
            # Else, fall through and go through the loop again
        
    # Build position list
    s_number_to_return = ""
    for pos in s_number_list:
        if len(s_number_to_return) > 0:
            s_number_to_return = s_number_to_return + "-"
        s_number_to_return = s_number_to_return + str(pos)
    
    return s_number_to_return
    
# The statistics covered by this function correspond to the stats that are
# typically provided in 1938 box scores in the Minneapolis newspapers.    
def get_batting_fielding_info(team_list):    
    d = defaultdict()
    
    for tm in team_list:
        print("\nEnter batters for %s in order: " % (tm))
        d[tm] = []
        sequence = 0
        
        done = False
        while not done:
            (player,pid) = get_player_name_and_id(tm)
            if pid == "stop":
                done = True
            else:
                print("Batting order position: ")
                batting_order_pos = get_number_max_allowed(9)
                print("Starter (0) or off bench (1-n): ")
                batting_order_sequence = get_number_max_allowed(20)
                def_positions = get_defensive_positions()
                
                # The order of the following is based on 1938 box score format from the
                # Minneapolis papers. In 1938, TSN did not include a column for runs,
                # so if using TSN as your primary source, you may to disable that prompt.
                print("AB:")
                at_bats = get_number()
                print("R:")
                runs = get_number()
                print("H:")
                hits = get_number()
                print("PO:")
                putouts = get_number()
                print("A:")
                assists = get_number()
                print("E:")
                errors = get_number()
                
                # Create combination of batting and defensive stats
                # Retrosheet used:
                # stat,bline,id,side,pos,seq,ab,r,h,2b,3b,hr,rbi,sh,sf,hbp,bb,ibb,k,sb,cs,gidp,int
                # stat,dline,id,side,seq,pos,if*3,po,a,e,dp,tp,pb
                # In this function, we return: id,pos,seq,ab,r,h,pos(multiple),po,a,e
                # and then unpack those fields later.
                stats_line = pid + "," + str(batting_order_pos) + "," + str(batting_order_sequence) + "," + str(at_bats) + "," + str(runs) + "," + str(hits) + "," + str(def_positions) + "," + str(putouts) + "," + str(assists) + "," + str(errors)
                
                d[tm].append(stats_line)                    
    
    return d
    
# Similar to get_batting_fielding_info() but grabs only team totals.
def get_team_batting_fielding_info(team_list):    
    d = defaultdict()
    
    for tm in team_list:
        print("\nEnter totals for %s: " % (tm))
        d[tm] = []
        sequence = 0
        
        # The order of the following is based on 1938 box score format from the
        # Minneapolis papers. In 1938, TSN did not include a column for runs,
        # so if using TSN as your primary source, you may to disable that prompt.
        print("AB:")
        at_bats = get_number()
        print("R:")
        runs = get_number()
        print("H:")
        hits = get_number()
        print("PO:")
        putouts = get_number()
        print("A:")
        assists = get_number()
        print("E:")
        errors = get_number()
        
        # Create combination of batting and defensive stats
        # Retrosheet used:
        # stat,bline,id,side,pos,seq,ab,r,h,2b,3b,hr,rbi,sh,sf,hbp,bb,ibb,k,sb,cs,gidp,int
        # stat,dline,id,side,seq,pos,if*3,po,a,e,dp,tp,pb
        # In this function, we return: ab,r,h,po,a,e
        stats_line = str(at_bats) + "," + str(runs) + "," + str(hits) + "," + str(putouts) + "," + str(assists) + "," + str(errors)
        
        d[tm] = stats_line
    
    return d
    
# Utility function to process stats dictionaries.
# These are statistics which are not covered in the batting table,
# so we will have prompted for a list of players for each stat.
# Now, we need to unpack those dictionaries. 
def add_stat_conditionally(tm,pid,d):
    # If there is an entry for this player in this dictionary, return the value for that player.
    if pid in d[tm]:
        new_line = "," + str(d[tm][pid])
    # Otherwise, just return a zero.
    else:
        new_line = "," + str(0)
    return new_line
      
def get_inning(pid,prompt):
    print("Inning that %s %s (0 if unknown)? " % (pid,prompt))
    return str(get_number_max_allowed(99))
      
def time_to_quit():
    response = display_menu_get_selection(["Continue","Quit"],"")
    if response == "Quit":
        return True
    return False
    
#########################################################################
#
# Main program starts here
#    

# No command-line arguments are needed, but argparse will automatically print this
# help message and then exit.
parser = argparse.ArgumentParser(description='Create or add box scores to a Retrosheet event file. No command-line arguments are supported or required.') 
args = parser.parse_args()

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
            # Index by team abbrev, then player id, storing complete name in quotes like the EBx file format uses
            player_info[row[5]][row[0]] = "\"" + row[2] + " " + row[1] + "\""
            if row[5] not in list_of_teams:
                list_of_teams.append(row[5])
                
if DEBUG_ON:
    # Dump all the roster info for all teams
    for tm in sorted(player_info):
        for p in player_info[tm]:
            print("%s,%s,%s" % (tm,p,player_info[tm][p]))

current_datetime = datetime.datetime.now().strftime("%Y_%m_%d_%H%M%S")
backup_filename = output_filename.split(".")[0] + "_" + current_datetime + ".txt"

if os.path.exists(output_filename):
    # back up the output file first
    copyfile(output_filename,backup_filename)
    print("Created backup file %s" % (backup_filename))
    
quit_script = False

while not quit_script:

    # This will create the file if it does not exist already, but normally will
    # append a new box score to an existing file.
    output_file = open(output_filename,'a') 

    road_team = display_menu_get_selection(list_of_teams,"Road team:")
    print("ROAD: %s" % (road_team))
    home_team = display_menu_get_selection(list_of_teams,"Home team:")
    print("HOME: %s" % (home_team))

    date = get_date_string()
    print("DATE: %s" % (date))
    
    print("Single game (0), First of DH (1), or Second of DH (2): ")
    game_number = get_number_max_allowed(2)
    
    game_id = home_team + re.sub("/","",date) + str(game_number)
    print("GM: %s" % (game_id))
    
    output_file.write("\n")
    output_file.write("version,BOXTOP1\n")
    output_file.write("info,visteam,%s\n" % (road_team))
    output_file.write("info,hometeam,%s\n" % (home_team))
    # LIMITATION: no exceptions in 1938, so just make this "01" in all cases
    output_file.write("info,site,%s\n" % (home_team + "01")) 
    output_file.write("info,date,%s\n" % (date))
    output_file.write("info,number,%s\n" % (str(game_number)))
    
    start_time = get_time_string()
    daynight = display_menu_get_selection(["day","night","unknown"],"Day or Night:")
    
    output_file.write("info,starttime,%s\n" % (start_time))
    output_file.write("info,daynight,%s\n" % (daynight))
    
    output_file.write("info,usedh,false\n") # does not apply to our use case
    
    # "scorer" should be newspaper and/or "TSN box", so provide some abbreviation support
    # to make data entry faster.
    print("Source: ")
    scorer = get_string()
    if scorer.lower() == "tsn":
        scorer = "TSN box"
    elif scorer.lower() == "ms":
        scorer = "Minneapolis Star box"
    elif scorer.lower() == "mst":
        scorer = "Minneapolis Star-Tribune box"
    
    output_file.write("info,scorer,%s\n" % (scorer))
    output_file.write("info,howscored,unknown\n")

    # LIMITATION: Fill in defaults for some fields that 1938 box scores are unlikely to include.
    output_file.write("info,pitches,none\n")
    output_file.write("info,temp,0\n") # 0 = unknown for some numerical fields...
    output_file.write("info,winddir,unknown\n")
    output_file.write("info,windspeed,-1\n") # ... but for windspeed and many others, Retrosheet uses -1
    output_file.write("info,fieldcond,unknown\n")
    output_file.write("info,precip,unknown\n")
    output_file.write("info,sky,unknown\n")
    
    # The following is optimized for data entry purposes for 1938 box scores, storing all info in a 
    # dictionary so we can then assemble Retrosheet-compatible lines once all of the data is entered.
    #
    b_dict = get_batting_fielding_info([road_team,home_team])
    if DEBUG_ON:
        for tm in b_dict:
            for player in b_dict[tm]:
                print("%s: %s" % (tm,player))

    # We will store batting/fielding team totals in the .EBA file, even though
    # Retrosheet does not do so. That will enable us to do cross-checking.
    #
    team_bf_dict = get_team_batting_fielding_info([road_team,home_team])
    if DEBUG_ON:
        for tm in team_bf_dict:
            print("%s: %s" % (tm,b_team_bf_dict[tm]))
            
            
    # Prompt for stats that appear at the end of the box score, storing in
    # per-stat dictionaries that we can use later when we assemble full bline's and pline's
    rbi_dict = get_stats_summary_info("RBI",home_team,road_team)
    if DEBUG_ON:
        for tm in rbi_dict:
            for pid in rbi_dict[tm]:
                print("%s [%s]: %d" % (pid,tm,rbi_dict[tm][pid]))
            
    doubles_dict = get_stats_summary_info("Doubles",home_team,road_team)
    triples_dict = get_stats_summary_info("Triples",home_team,road_team)
    hr_dict = get_stats_summary_info("HRs",home_team,road_team)
    sb_dict = get_stats_summary_info("SBs",home_team,road_team)
    sh_dict = get_stats_summary_info("Sacrifice Hits",home_team,road_team)
    sf_dict = get_stats_summary_info("Sacrifice Flies",home_team,road_team)
    hbp_dict = get_stats_summary_info("HBP",home_team,road_team)
    passed_balls_dict = get_stats_summary_info("Passed Balls",home_team,road_team)
    
    # Get pitching stats
    p_dict = get_pitching_summary_info([road_team,home_team])
    if DEBUG_ON:
        for tm in p_dict:
            for player in p_dict[tm]:
                print("%s: %s" % (tm,player))
    
    # Retrosheet uses id for umpires (first four letters of last name, first letter of first name, then 9, then two-digit number.
    # But we will just input names if we have them, or treat blank entry as "unknown".
    print("Umpires")
    print("Home: ")
    ump_home = get_string()
    print("1B: ")
    ump_1b = get_string()
    print("2B: ")
    ump_2b = get_string()
    print("3B: ")
    ump_3b = get_string()

    output_file.write("info,umphome,%s\n" % (ump_home))
    output_file.write("info,ump1b,%s\n" % (ump_1b))
    output_file.write("info,ump2b,%s\n" % (ump_2b))
    output_file.write("info,ump3b,%s\n" % (ump_3b))
    
    time_of_game_in_minutes = get_time_of_game_in_minutes()
    output_file.write("info,timeofgame,%d\n" % (time_of_game_in_minutes))
    print("Attendance (0 if unknown): ")
    att = get_number()
    if att == 0:
        att = -1 # for unknown, we want to store -1
    output_file.write("info,attendance,%d\n" % (att))
    
    # Prompt for winning and losing pitcher, based on the pitchers who actually pitched
    # in the game. Note that we do not use game stats to determine which team won, so
    # it is possible to incorrectly select a pitcher from the wrong team.
    print("\n")
    list_of_all_pitchers = []
    for tm in p_dict:
        for player in p_dict[tm]:
            list_of_all_pitchers.append(player)
    if len(list_of_all_pitchers) >= 2:
        winning_pitcher = display_menu_get_selection(list_of_all_pitchers,"Winning pitcher:").split(",")[0]
        losing_pitcher = display_menu_get_selection(list_of_all_pitchers,"Losing pitcher:").split(",")[0]
    else:
        print("WARNING: Fewer than 2 pitchers listed, leaving winning and losing pitcher blank.")
        winning_pitcher = ""
        losing_pitcher = ""
    # LIMITATION: No saves in 1938
    saving_pitcher = ""
    output_file.write("info,wp,%s\n" % (winning_pitcher))
    output_file.write("info,lp,%s\n" % (losing_pitcher))
    output_file.write("info,save,%s\n" % (saving_pitcher))
    
    # LIMITATION: No game-winning RBI in 1938
    output_file.write("info,gwrbi,\n")

    # Get fielding info for double plays and triple plays
    print("\n")
    (dp_count_dict, dp_event_dict) = get_fielding_play_info("Double Play",home_team,road_team)
    print("\n")
    (tp_count_dict, tp_event_dict) = get_fielding_play_info("Triple Play",home_team,road_team)
    
    ###################################################################### 
    # At this point we have most of the information we need.
    # Start creating output lines.
    ######################################################################
    
    ######################################################################
    # "bline" lines for batters
    #
    # From Retrosheet:
    # stat,bline,id,side,pos,seq,ab,r,h,2b,3b,hr,rbi,sh,sf,hbp,bb,ibb,k,sb,cs,gidp,int
    #
    # id - the player ID
    # side - the side he appeared for (0 or 1)
    # pos - the position in the lineup (1 to 9)
    # seq - the order he appeared in that position.  For starters, this field
    #    will equal 1.  For players replacing the starter, this field will
    #    equal 2 and so on.
    # ab...int - the player's statistics for the game.  Almost all of the
    #         abbreviations should be obvious.  int - reached base on
    #         interference.    
    side = ROAD_ID
    for tm in [road_team,home_team]:
        for pinfo in b_dict[tm]:
            pid = pinfo.split(",")[0]
            #                                                                pos                      
            retrosheet_bline = "stat,bline," + pid + "," + str(side) + "," + pinfo.split(",")[1]
            #                                           seq                         ab                          runs                        hits        
            retrosheet_bline = retrosheet_bline + "," + pinfo.split(",")[2] + "," + pinfo.split(",")[3] + "," + pinfo.split(",")[4] + "," + pinfo.split(",")[5]
            
            retrosheet_bline += add_stat_conditionally(tm,pid,doubles_dict)
            retrosheet_bline += add_stat_conditionally(tm,pid,triples_dict)
            retrosheet_bline += add_stat_conditionally(tm,pid,hr_dict)
            retrosheet_bline += add_stat_conditionally(tm,pid,rbi_dict)
            retrosheet_bline += add_stat_conditionally(tm,pid,sh_dict)
            retrosheet_bline += add_stat_conditionally(tm,pid,sf_dict)
            retrosheet_bline += add_stat_conditionally(tm,pid,hbp_dict)
            
            # LIMITATION: No walk or strikeout info for individual batters, so we omit that info.
            retrosheet_bline += ",-1,-1,-1"

            retrosheet_bline += add_stat_conditionally(tm,pid,sb_dict)
            
            # LIMITATION: No caught stealing info? (TBD)
            retrosheet_bline += ",-1"

            # LIMITATION: No ground into DP or reached on interference info? (TBD)
            retrosheet_bline += ",-1,-1"
            
            output_file.write("%s\n" % (retrosheet_bline))
            
        # switch to next team
        if side == ROAD_ID:
            side = HOME_ID
        
    
    ######################################################################
    # "phline" lines for pinch-hitting 
    #
    # From Retrosheet:
    # stat,phline,id,inning,side,ab,r,h,2b,3b,hr,rbi,sh,sf,hbp,bb,ibb,k,sb,cs,gidp,int
    #
    #  id - the player ID
    #  inning - the inning he pinch-hit
    #  side - the side he appeared for (0 or 1)
    #  ab...int - same as bline
    
    ######################################################################
    # "prline" lines for pinch-running
    #
    # From Retrosheet:
    # stat,prline,id,inning,side,r,sb,cs
    #
    #  id - the player ID
    #  inning - the inning he pinch-ran
    #  side - the side he appeared for (0 or 1)
    #  r...cs - runs, stolen bases and caught stealing during appearance    
    
    ######################################################################
    # "dline" lines for defense/fielding
    #
    # From Retrosheet:
    # stat,dline,id,side,seq,pos,if*3,po,a,e,dp,tp,pb
    #
    #  id - the player ID
    #  side - the side he appeared for (0 or 1)
    #  seq - the sequence number.  This will be 1 for the first position
    #        played by the player in the game, 2 for the second position and
    #        so on.
    #  pos - the position played (1-9)
    #  if*3 - innings fielded times 3 (the number of outs he was in the field)
    #  po...pb - the traditional fielding stats    
    side = ROAD_ID
    for tm in [road_team,home_team]:
        for pinfo in b_dict[tm]:
            pid = pinfo.split(",")[0]            
            
            pos_list_string = pinfo.split(",")[6]
            if pos_list_string.count("-") > 0:
                pos_list = pos_list_string.split("-")
            else:
                pos_list = []
                pos_list.append(pos_list_string)
                
            position_seq = 0
            for pos in pos_list:
                if pos == "11":
                    # Pinch-runner
                    # Create prline, need to prompt for inning that PH happened
                    # Retrosheet: stat,prline,id,inning,side,r,sb,cs
                    # LIMITATION: We do not have R/SB/CS info for a specific PR appearance
                    retrosheet_line = "stat,prline," + pid + "," + get_inning(pid,"Pinch-run") + "," + str(side) + ",-1,-1,-1"
                elif pos == "12":
                    # Pinch-hitter
                    # Create phline, need to prompt for inning that PR happened
                    # Retrosheet: stat,phline,id,inning,side,ab,r,h,2b,3b,hr,rbi,sh,sf,hbp,bb,ibb,k,sb,cs,gidp,int
                    # LIMITATION: We do not have batting stats for a specific at-bat, except in cases where all the batter does is PH
                    retrosheet_line = "stat,phline," + pid + "," + get_inning(pid,"Pinch-hit") + "," + str(side) + ",-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1"
                else:
                    # Fielding
                    # Retrosheet: stat,dline,id,side,seq,pos,if*3,po,a,e,dp,tp,pb
                    # LIMITATION: We don't know the innings fielded.
                    retrosheet_line = "stat,dline," + pid + "," + str(side) + "," + str(position_seq) + "," + pos + ",0,"
                    # LIMITATION: For 1938, we don't know PO/A/E by position, so only include this data
                    # in the FIRST dline entry for this player.
                    if position_seq == 0:
                        #                  po                          assists                     errors
                        retrosheet_line += pinfo.split(",")[7] + "," + pinfo.split(",")[8] + "," + pinfo.split(",")[9]
                    else:
                        retrosheet_line += "0,0,0"
                    retrosheet_line += add_stat_conditionally(tm,pid,dp_count_dict)
                    retrosheet_line += add_stat_conditionally(tm,pid,tp_count_dict)
                    retrosheet_line += add_stat_conditionally(tm,pid,passed_balls_dict)
                    position_seq += 1
            
                output_file.write("%s\n" % (retrosheet_line))
            
        # switch to next team
        if side == ROAD_ID:
            side = HOME_ID     
            
    ######################################################################
    # "pline" lines for pitchers
    #
    # From Retrosheet:
    # stat,pline,id,side,seq,ip*3,no-out,bfp,h,2b,3b,hr,r,er,bb,ibb,k,hbp,wp,balk,sh,sf
    # 
    #  id - the player ID
    #  side - the side he appeared for (0 or 1)
    #  seq - the sequence number.  This will be 1 for the first pitcher in
    #        the game, 2 for the second pitcher, and so on.
    #  ip*3 - innings pitched times 3
    #  no-out - if the pitcher didn't retire a batter in an inning, the
    #           number of batters faced
    #  bfp...sf - the rest of the statistics    
    side = ROAD_ID
    for tm in [road_team,home_team]:
        for pinfo in p_dict[tm]:
            pid = pinfo.split(",")[0] 
            #                                                                seq                         ip*3
            retrosheet_pline = "stat,pline," + pid + "," + str(side) + "," + pinfo.split(",")[1] + "," + pinfo.split(",")[2] + ","
            #                   no-out                      bfp                         hits
            retrosheet_pline += pinfo.split(",")[3] + "," + pinfo.split(",")[4] + "," + pinfo.split(",")[5] + ","
            # LIMITATION: We do not know 2B/3B/HR by pitcher
            retrosheet_pline += "-1,-1,-1,"
            #                   runs      LIMITATION: no ER   walks    LIMITATION: no IBB   strikeouts    
            retrosheet_pline += pinfo.split(",")[6] + ",-1," + pinfo.split(",")[7] + ",-1," + pinfo.split(",")[8] + ","
            #                   hbp                         wp                           balk
            retrosheet_pline += pinfo.split(",")[9] + "," + pinfo.split(",")[10] + "," + pinfo.split(",")[11] + ","
            # LIMITATION: We do not know SH/SF by pitcher
            retrosheet_pline += "-1,-1"
            
            output_file.write("%s\n" % (retrosheet_pline))
            
        # switch to next team
        if side == ROAD_ID:
            side = HOME_ID 
    
    ######################################################################
    # Team statistics totals as presented in box score table.
    #
    # This is our own invention, not a standard Retrosheet format.
    # Will be used only for cross-check purposes in bp_cross_check.py
    #
    # teamstat,side,ab,r,h,po,a,e
    #
    side = ROAD_ID
    for tm in [road_team,home_team]:
        team_line = "teamstat," + str(side) + "," + team_bf_dict[tm]
        output_file.write("%s\n" % (team_line))
            
        # switch to next team
        if side == ROAD_ID:
            side = HOME_ID
            
    #######################################################################    
    # Now add linescores
    #
    road_linescore = get_linescore_string(ROAD_ID,road_team)
    home_linescore = get_linescore_string(HOME_ID,home_team)
    output_file.write("line,%s\n" % (road_linescore))
    output_file.write("line,%s\n" % (home_linescore))
    
    #######################################################################    
    # LOB
    #
    print("Left-on-base %s " % (road_team))
    r_lob = get_number()
    print("Left-on-base %s " % (home_team))
    h_lob = get_number()
    
    #######################################################################    
    # tline
    #
    # stat,tline,side,left-on-base,earned runs,number of DP turned,number of TP turned
    
    # LIMITATION: TBD - Earned runs not provided in 1938 boxes?
    r_er = -1
    h_er = -1

    output_file.write("stat,tline,%d,%d,%d,%d,%d\n" % (ROAD_ID,r_lob,r_er,len(dp_event_dict[road_team]),len(tp_event_dict[road_team])))
    output_file.write("stat,tline,%d,%d,%d,%d,%d\n" % (HOME_ID,h_lob,h_er,len(dp_event_dict[home_team]),len(tp_event_dict[home_team])))
    
    #######################################################################    
    # event
    #
    # event,dpline,side of team who turned the DP,player-id (who turned the DP)...
    # event,tpline,side of team who turned the TP,player-id (who turned the TP)...
    # TBD if we do HBP: event,hpline,side of pitcher's team,pitcher-id,batter-id
    #
    # LIMITATION: I am omitting HR, SB, CS events since the inning/outs for when these events 
    # occurred are not listed in 1938 box scores.

    for event_line in dp_event_dict[road_team]:
        output_file.write("event,dpline,%d,%s\n" % (ROAD_ID,event_line))

    for event_line in dp_event_dict[home_team]:
        output_file.write("event,dpline,%d,%s\n" % (HOME_ID,event_line))

    for event_line in tp_event_dict[road_team]:
        output_file.write("event,tpline,%d,%s\n" % (ROAD_ID,event_line))

    for event_line in tp_event_dict[home_team]:
        output_file.write("event,tpline,%d,%s\n" % (HOME_ID,event_line))

        
    print("Any comments to add? (leave blank to skip): ")
    comments = get_string()
    if len(comments) > 0:
        output_file.write("com,\"%s\"\n" % (comments))
    
    output_file.close()
    
    print("Game saved.\n")
    
    if time_to_quit():
        quit_script = True

print("Exiting script.")        

        