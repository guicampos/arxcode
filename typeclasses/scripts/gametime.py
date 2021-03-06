"""
The gametime module handles the global passage of time in the mud.

It also supplies some useful methods to convert between
in-mud time and real-world time as well allows to get the
total runtime of the server and the current uptime.
"""

from time import time
from django.conf import settings
from .scripts import Script
from evennia.utils.create import create_script

GAMETIME_SCRIPT_NAME = "sys_game_time"

# Speed-up factor of the in-game time compared
# to real time.

TIMEFACTOR = settings.TIME_FACTOR

# Common real-life time measure, in seconds.
# You should not change this.

REAL_MIN = 60.0  # seconds per minute in real world

# Game-time units, in real-life seconds. These are supplied as
# a convenient measure for determining the current in-game time,
# e.g. when defining in-game events. The words month, week and year can
# be used to mean whatever units of time are used in the game.

MIN = 60
HOUR = MIN * 60
DAY = HOUR * 24
WEEK = DAY * 7
MONTH = WEEK * 4
YEAR = MONTH * 12

# Cached time stamps
# SERVER_STARTTIME = time()
#added it as a constant in case the module is ever reloaded
SERVER_STARTTIME = time()
SERVER_RUNTIME = 0.0
LOGPATH = settings.LOG_DIR
BACKUP_FILE = LOGPATH + "/gametime_backup_log.txt"


class GameTime(Script):
    """
    This script repeatedly saves server times so
    it can be retrieved after server downtime.
    """
    def at_script_creation(self):
        """
        Setup the script
        """
        self.key = GAMETIME_SCRIPT_NAME
        self.desc = "Keeps track of the game time"
        self.interval = 60
        self.persistent = True
        self.start_delay = True
        self.attributes.add("run_time", 0.0)  # OOC time
        self.attributes.add("up_time", 0.0)  # OOC time
        try:
            logfile = open(BACKUP_FILE)
            lines = [line.strip() for line in logfile if line[0].isdigit()]
            #get the last recorded time in file
            last_time = float(lines[-1])
            if last_time:
                self.attributes.add("run_time", last_time)
        except Exception:
            from evennia.utils import logger
            logger.log_trace()

    def at_repeat(self):
        """
        Called every minute to update the timers.
        """
        self.attributes.add("run_time", runtime())
        self.attributes.add("up_time", uptime())
        # Despite having checks elsewhere, apparently sometimes
        # the script can restart without ever calling at_start
        # or at_script_creation. So a final check here, just
        # to make absolutely sure it loads the correct values if
        # it reset.
        try:
            if SERVER_RUNTIME < 1000:
                self.at_start()
        except Exception:
            from evennia.utils import logger
            logger.log_trace()
        

    def at_start(self):
        """
        This is called once every server restart.
        We reset the up time and load the relevant
        times.
        """
        global SERVER_RUNTIME
        SERVER_RUNTIME = self.attributes.get("run_time")
        #In case of an error loading script from database, we'll check time
        #versus the last saved gametime in the logfile
        try:
            logfile = open(BACKUP_FILE)
            lines = [line.strip() for line in logfile if line[0].isdigit()]
            #get the last recorded time in file
            last_time = float(lines[-1])
            if SERVER_RUNTIME < last_time:
                SERVER_RUNTIME = last_time
        except Exception:
            from evennia.utils import logger
            logger.log_trace()

def save():
    "Force save of time. This is called by server when shutting down/reloading."
    from evennia.scripts.models import ScriptDB
    try:
        script = ScriptDB.objects.get(db_key=GAMETIME_SCRIPT_NAME)
        script.at_repeat()
    except Exception:
        from evennia.utils import logger
        logger.log_trace()
    try:
        with open(BACKUP_FILE, 'r+') as logfile:
            data = logfile.readline()
            if not data or float(data) < runtime():
                logfile.seek(0)
                logfile.write(str(runtime()))
                logfile.close()
    except Exception:
        from evennia.utils import logger
        logger.log_trace()

def _format(seconds, *divisors) :
    """
    Helper function. Creates a tuple of even dividends given
    a range of divisors.

    Inputs
      seconds - number of seconds to format
      *divisors - a number of integer dividends. The number of seconds will be
                  integer-divided by the first number in this sequence, the remainder
                  will be divided with the second and so on.
    Output:
        A tuple of length len(*args)+1, with the last element being the last remaining
        seconds not evenly divided by the supplied dividends.

    """
    results = []
    seconds = int(seconds)
    for divisor in divisors:
        results.append(seconds / divisor)
        seconds %= divisor
    results.append(seconds)
    return tuple(results)


# Access functions

def runtime(format=False):
    "Get the total runtime of the server since first start (minus downtimes)"
    runtime = SERVER_RUNTIME + (time() - SERVER_STARTTIME)
    if format:
        return _format(runtime, 31536000, 2628000, 604800, 86400, 3600, 60)
    return runtime

def uptime(format=False):
    "Get the current uptime of the server since last reload"
    uptime = time() - SERVER_STARTTIME
    if format:
        return _format(uptime, 31536000, 2628000, 604800, 86400, 3600, 60)
    return uptime

def gametime(format=False):
    "Get the total gametime of the server since first start (minus downtimes)"
    gametime = runtime() * TIMEFACTOR
    if format:
        return _format(gametime, YEAR, MONTH, WEEK, DAY, HOUR, MIN)
    return gametime


def gametime_to_realtime(secs=0, mins=0, hrs=0, days=0,
                         weeks=0, months=0, yrs=0, format=False):
    """
    This method helps to figure out the real-world time it will take until an
    in-game time has passed. E.g. if an event should take place a month later
    in-game, you will be able to find the number of real-world seconds this
    corresponds to (hint: Interval events deal with real life seconds).

    Example:
     gametime_to_realtime(days=2) -> number of seconds in real life from
                                now after which 2 in-game days will have passed.
    """
    realtime = (secs + mins * MIN + hrs * HOUR + days * DAY + weeks * WEEK + \
                months * MONTH + yrs * YEAR) / TIMEFACTOR
    if format:
        return _format(realtime, 31536000, 2628000, 604800, 86400, 3600, 60)
    return realtime


def realtime_to_gametime(secs=0, mins=0, hrs=0, days=0,
                         weeks=0, months=0, yrs=0, format=False):
    """
    This method calculates how much in-game time a real-world time
    interval would correspond to. This is usually a lot less interesting
    than the other way around.

     Example:
      realtime_to_gametime(days=2) -> number of game-world seconds
                                      corresponding to 2 real days.
    """
    gametime = TIMEFACTOR * (secs + mins * 60 + hrs * 3600 + days * 86400 +
                             weeks * 604800 + months * 2628000 + yrs * 31536000)
    if format:
        return _format(gametime, YEAR, MONTH, WEEK, DAY, HOUR, MIN)
    return gametime


# Time administration routines

def init_gametime():
    """
    This is called once, when the server starts for the very first time.
    """
    # create the GameTime script and start it
    game_time = create_script(GameTime)
    game_time.start()
