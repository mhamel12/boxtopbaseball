#
#  1.0  MH  07/08/2019  Initial version

# ORM = SQLAlchemy Object Relational Mapper

from sqlalchemy import Column, Boolean, ForeignKey, Integer, Numeric, String, DateTime
from sqlalchemy.orm import relationship
from sqlalchemy.ext.declarative import declarative_base

import datetime

# From the tutorial:
#
# Classes mapped using the Declarative system are defined in terms of a base class which maintains a 
# catalog of classes and tables relative to that base - this is known as the declarative base class. 
# Our application will usually have just one instance of this base in a commonly imported module. 
# We create the base class using the declarative_base() function, as follows:

Base = declarative_base() 

class BattingStats(Base):
    __tablename__ = 'battingstats'
    id = Column(Integer, primary_key=True)
    
    date = Column(String(15)) # YYYY/MM/DD
    date_as_dt = Column(DateTime) # Time is 00:00:00 but date part is real
    game_number_that_day = Column(Integer) # 0 if single game, 1 or 2 for doubleheader
    
    pid = Column(String(8))
    my_team = Column(String)
    opponent = Column(String)
    
     # could be a neutral site game, so store T/F flags for both home and road
    home = Column(Boolean)
    road = Column(Boolean)
    
    ab = Column(Integer)
    runs = Column(Integer)
    hits = Column(Integer)
    doubles = Column(Integer)
    triples = Column(Integer)
    hr = Column(Integer)
    rbi = Column(Integer)
    sh = Column(Integer)
    sf = Column(Integer)
    hbp = Column(Integer)
    bb = Column(Integer)
    ibb = Column(Integer)
    strikeouts = Column(Integer)
    sb = Column(Integer)
    cs = Column(Integer)
    gidp = Column(Integer)
    int = Column(Integer)
   
class PitchingStats(Base):
    __tablename__ = 'pitchingstats'
    id = Column(Integer, primary_key=True)
    
    date = Column(String(15)) # YYYY/MM/DD
    date_as_dt = Column(DateTime) # Time is 00:00:00 but date part is real
    game_number_that_day = Column(Integer) # 0 if single game, 1 or 2 for doubleheader
    
    pid = Column(String(8))
    my_team = Column(String)
    opponent = Column(String)
    
    starting_pitcher = Column(Boolean)
    winning_pitcher = Column(Boolean)
    losing_pitcher = Column(Boolean)
    
     # could be a neutral site game, so store T/F flags for both home and road
    home = Column(Boolean)
    road = Column(Boolean)

    outs = Column(Integer)
    bfp = Column(Integer)
    hits = Column(Integer)
    doubles = Column(Integer)
    triples = Column(Integer)
    hr = Column(Integer)
    runs = Column(Integer)
    earned_runs = Column(Integer)
    walks = Column(Integer)
    intentional_walks = Column(Integer)
    strikeouts = Column(Integer)
    hbp = Column(Integer)
    wp = Column(Integer)
    balk = Column(Integer)
    sh = Column(Integer)
    sf = Column(Integer)

class GameInfo(Base):
    __tablename__ = 'gameinfo'
    id = Column(Integer, primary_key=True)  

    date = Column(String(15)) # YYYY/MM/DD
    date_as_dt = Column(DateTime) # Time is 00:00:00 but date part is real
    game_number_that_day = Column(Integer) # 0 if single game, 1 or 2 for doubleheader
    
    road_team = Column(String)
    home_team = Column(String)
    
    start_time = Column(String) # 00:00AM (or PM)
    daynight_game = Column(String(1)) # D or N or U (for unknown)
    time_of_game = Column(Integer)
    attendance = Column(Integer)
    
    winning_pitcher_pid = Column(String(8))
    losing_pitcher_pid = Column(String(8))    
    
    road_team_runs = Column(Integer)
    home_team_runs = Column(Integer)
    innings = Column(Integer)
    
    comments = Column(String)