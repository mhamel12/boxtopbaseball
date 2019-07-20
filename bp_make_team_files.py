#########################################################################
#
# Convert "stats crew" roster files to Retrosheet roster files
#
# CC License: Attribution-NonCommercial 4.0 International (CC BY-NC 4.0)
# https://creativecommons.org/licenses/by-nc/4.0/
#
# Requires:
# 1. A set of text files containing rosters from the StatsCrew.com site (named Teamname_1938.txt)
#
#  1.0  MH  05/25/2019  Initial version
#
import argparse, csv, re, glob
from collections import defaultdict

team_name_to_abbrev = {
    'Columbus' : 'COL',
    'Indianapolis' : 'IND',
    'KansasCity' : 'KCB',
    'Louisville' : 'LOU',
    'Milwaukee' : 'MIL',
    'Minneapolis' : 'MIN',
    'StPaul' : 'SPL',
    'Toledo' : 'TOL'
    }

# LIMITATION: These are only guaranteed to be unique within a season, while real
# Retrosheet ids would need to be unique across all seasons.
used_player_ids = []
player_bio_list = defaultdict()

# From https://www.retrosheet.org/retroID.htm
# Some of the databases available incorporate Retrosheet ID codes. These are of the form "llllfnnn" where "llll" 
# are the first four letters of the last name, "f" is the first letter of the first name, and "nnn" are numbers. 
# The first number is 0 for players who appeared in 1984 or later, 1 for players whose career ended before 1984, 
# 8 for managers and coaches who never played in the majors, and 9 for umpires who never played. The next two 
# numbers are sequence numbers starting with 01. There are three fields after each name, which are that person's 
# debut dates as a player, manager, coach, and umpire. Most individuals have only one or two these fields 
# populated and the remainder are blank. However, some have entries for multiple categories, For example, check 
# Don Mattingly for his three different debut dates.
def get_player_id(first,last,bio):
    l = re.sub("'","",last) # remove any quotes
    l = re.sub("-","",l) # remove any dashes
    f = re.sub("'","",first) # remove any quotes
    f = re.sub("-","",f) # remove any dashes
    
    l = l.lower()
    f = f.lower()
    
    if len(l) >= 4:
        name_part_of_pid = l[:4] + f[:1]
    elif len(l) == 3:
        name_part_of_pid = l + "-" + f[:1]
    elif len(l) == 2:
        name_part_of_pid = l + "--" + f[:1]
    else:
        name_part_of_pid = l + "---" + f[:1]
    
    # Assumption here is that all players ended their career before 1984, so use 100
    try_another_id = True
    base_sequence_number = int(101)
    while try_another_id:
        test_pid = name_part_of_pid + str(base_sequence_number)
        if test_pid not in used_player_ids:
            used_player_ids.append(test_pid)
            player_bio_list[bio] = test_pid
            return(test_pid)
        elif bio in player_bio_list: 
            # we have already seen this player before, so we want to reuse their pid
            print("Reusing id for %s" % (bio))
            return(player_bio_list[bio])
        else:
            # increment the sequence number and go back to the top of this loop to try again
            base_sequence_number = base_sequence_number + 1
            print("Trying again for %s %s" % (first,last))
        
    # should never get here
    print("ERROR: No player id found for %s %s" % (first,last))
    return("UNEXPECTED_PID")
    
# LIMITATION: Hardcoded for 1938.    
season = "1938"
search_string = "*_" + season + ".txt"
    
list_of_files = glob.glob(search_string)
for filename in list_of_files:
    with open(filename,'r') as csvfile: # file is automatically closed when this block completes
    
        # for the output file, we are manually opening and closing the file
        abbrev = team_name_to_abbrev[filename.split("_")[0]]
        output_filename = abbrev + season + ".ROS"
        output_file = open(output_filename,'w')        
        
        items = csv.reader(csvfile, delimiter='\t') # tab-delimited input file
        for row in items:
            if len(row) > 0:
                if not re.match("Player",row[0]):
                    # LIMITATION: None of the 1938 AA players has a multi-part last name, 
                    # so just split on the last space to get first and last name
                    if row[0].count(" ") > 1:
                        print("Extra space: %s" % (row[0]))
                    first_name = row[0].rsplit(" ",1)[0]
                    last_name = row[0].rsplit(" ",1)[1]
                    bats = row[1]
                    throws = row[2]
            
                    # This is only used in cases where two players with different names 
                    # and/or bio info would otherwise be given the same player id
                    player_bio_info = "-".join(row)
                    
                    player_id = get_player_id(first_name,last_name,player_bio_info)
                    
                    output_line = player_id + "," + last_name + "," + first_name + "," + bats + "," + throws + "," + abbrev + "," + "X\n"
                    output_file.write(output_line)
        
        output_file.close()
