#########################################################################
#
# Dump player statistics from SQL Alchemy database.
# Nothing fancy, just a basic data dump script.
#
# CC License: Attribution-NonCommercial 4.0 International (CC BY-NC 4.0)
# https://creativecommons.org/licenses/by-nc/4.0/
#
# References:
# https://www.retrosheet.org/eventfile.htm
# https://www.retrosheet.org/boxfile.txt
# 
#
#  1.0  MH  07/09/2019  Initial version
#
import argparse, csv, sys
from collections import defaultdict
from bp_retrosheet_classes import BattingStats, PitchingStats, GameInfo, Base

DEBUG_ON = False

##########################################################
#
# Main program
#

parser = argparse.ArgumentParser(description='Dump player stats from a SQL Alchemy database.') 
parser.add_argument('dbfile', help="DB file (input)")
args = parser.parse_args()

from sqlalchemy import create_engine
engine = create_engine('sqlite:///%s' % (args.dbfile), echo=False)
                       
from sqlalchemy.orm import sessionmaker
Session = sessionmaker(bind=engine)

session = Session() 

count = 0

csv_to_stdout_obj = csv.writer(sys.stdout)

for instance in session.query(BattingStats).order_by(BattingStats.id):

    count += 1
    
    array_to_print = []
    
    # Print all columns, in a consistent order, with name:value in output for now.
    # Might want to use a header row eventually, and omit the name portion of this output.
    for col in BattingStats.__table__.columns:
        array_to_print.append('{}:{}'.format(col.name, getattr(instance,col.name)))

    csv_to_stdout_obj.writerow(array_to_print)

print("Batting row count = %s\n\n\n" % (count))

count = 0

for instance in session.query(PitchingStats).order_by(PitchingStats.id):

    count += 1
    
    array_to_print = []
    
    # Print all columns, in a consistent order, with name:value in output for now.
    # Might want to use a header row eventually, and omit the name portion of this output.
    for col in PitchingStats.__table__.columns:
        array_to_print.append('{}:{}'.format(col.name, getattr(instance,col.name)))

    csv_to_stdout_obj.writerow(array_to_print)

print("Pitching row count = %s\n\n\n" % (count))


count = 0

for instance in session.query(GameInfo).order_by(GameInfo.id):

    count += 1
    
    array_to_print = []
    
    # Print all columns, in a consistent order, with name:value in output for now.
    # Might want to use a header row eventually, and omit the name portion of this output.
    for col in GameInfo.__table__.columns:
        array_to_print.append('{}:{}'.format(col.name, getattr(instance,col.name)))

    csv_to_stdout_obj.writerow(array_to_print)

print("GameInfo row count = %s\n\n\n" % (count))