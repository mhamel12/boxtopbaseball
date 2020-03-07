#########################################################################
#
# Boxtop-related utilities.
#
# CC License: Attribution-NonCommercial 4.0 International (CC BY-NC 4.0)
# https://creativecommons.org/licenses/by-nc/4.0/
#
# References:
# https://www.retrosheet.org/eventfile.htm
# https://www.retrosheet.org/boxfile.txt
# 
#
#  1.0  MH  01/15/2020  Initial version
#
import csv, glob
from collections import defaultdict

##########################################################
#
# Read in a set of roster files, returning:
# 1. Dictionary with list of player id's and names
# 2. List of teams
#
def bp_load_roster_files():
    player_dict = defaultdict(dict)
    list_of_teams = []
    search_string = "*.ROS"
        
    list_of_roster_files = glob.glob(search_string)
    for filename in list_of_roster_files:
        with open(filename,'r') as csvfile: # file is automatically closed when this block completes
            items = csv.reader(csvfile)
            for row in items:    
                if len(row) > 0:        
                    # beanb101,Bean,Belve,R,R,MIN,X
                    # Index by team abbrev, then player id, storing complete name
                    player_id = row[0]
                    last_name = row[1]
                    first_name = row[2]
                    team_abbrev = row[5]
                    
                    # If first name not known, drop it and the space before the last_name
                    if first_name == "Unknown":
                        player_dict[team_abbrev][player_id] = last_name
                    else:
                        player_dict[team_abbrev][player_id] = first_name + " " + last_name
                        
                    if team_abbrev not in list_of_teams:
                        list_of_teams.append(team_abbrev)

    return(player_dict,list_of_teams)
    
##########################################################
#
# Read in (usually one at most) "ignore_stats.txt" file containing one statistical abbreviation per line.
# Return list of those abbreviations.
#
# Goal is to automatically ignore, at data entry time, statistics that are not available. The stats
# will be stored as "-1" in the .EBA file, which will cause them to be ignored by the other scripts.
# 
# The following is the list of stats that can be specified in this file.
#
# BATTING STATS
# 2b,3b,hr,rbi,gwrbi,bb,ibb,so,sb,cs,sh,sf,gidp,int
#
# PITCHING STATS
# save,2b_by_pitcher,3b_by_pitcher,hr_by_pitcher,er_by_pitcher,ibb_by_pitcher,sh_by_pitcher,sf_by_pitcher
#    
def bp_load_ignore_stats():
    list_of_stats_to_ignore = []
    search_string = "ignore*.txt"
    
    list_of_files = glob.glob(search_string)
    for filename in list_of_files:
        with open(filename,'r') as csvfile:
            items = csv.reader(csvfile)
            for row in items:
                if len(row) > 0:
                    if row[0] not in list_of_stats_to_ignore:
                        abbrev = row[0].lower() # convert to all lower-case to make comparisons in code easier
                        list_of_stats_to_ignore.append(abbrev)
     
    return(list_of_stats_to_ignore)
            