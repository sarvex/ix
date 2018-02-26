#!/usr/bin/env python
# -*- coding: utf-8 -*-

#  This file is part of Mylar.
#
#  Mylar is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
#
#  Mylar is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with Mylar.  If not, see <http://www.gnu.org/licenses/>.

from __future__ import with_statement

import os, sys, subprocess

import threading
import datetime
import webbrowser
import sqlite3
import itertools
import csv
import shutil
import Queue
import platform
import locale
import re
from threading import Lock, Thread

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

import cherrypy

from mylar import logger, versioncheckit, rsscheckit, searchit, weeklypullit, PostProcessor, updater, helpers

from mylar import versioncheck, logger
import mylar.config

#these are the globals that are runtime-based (ie. not config-valued at all)
#they are referenced in other modules just as mylar.VARIABLE (instead of mylar.CONFIG.VARIABLE)
PROG_DIR = None
DATA_DIR = None
FULL_PATH = None
LOG_DIR = None
LOGTYPE = 'log'
ARGS = None
SIGNAL = None
SYS_ENCODING = None
OS_DETECT = platform.system()
USER_AGENT = None
VERBOSE = False
DAEMON = False
PIDFILE= None
CREATEPID = False
QUIET=False
LOG_LEVEL = 0
MAX_LOGSIZE = 5000000
SAFESTART = False
NOWEEKLY = False
INIT_LOCK = threading.Lock()
IMPORTLOCK = False
IMPORTBUTTON = False
DONATEBUTTON = False
IMPORT_STATUS = None
IMPORT_FILES = 0
IMPORT_TOTALFILES = 0
IMPORT_CID_COUNT = 0
IMPORT_PARSED_COUNT = 0
IMPORT_FAILURE_COUNT = 0
CHECKENABLED = False
_INITIALIZED = False
started = False
MONITOR_STATUS = 'Waiting'
SEARCH_STATUS = 'Waiting'
RSS_STATUS = 'Waiting'
WEEKLY_STATUS = 'Waiting'
VERSION_STATUS = 'Waiting'
UPDATER_STATUS = 'Waiting'
SCHED_RSS_LAST = None
SCHED_WEEKLY_LAST = None
SCHED_MONITOR_LAST = None
SCHED_SEARCH_LAST = None
SCHED_VERSION_LAST = None
SCHED_DBUPDATE_LAST = None
DBUPDATE_INTERVAL = 5
DBLOCK = False
DB_FILE = None
UMASK = None
WANTED_TAB_OFF = False
PULLNEW = None
CONFIG = None
CONFIG_FILE = None
CV_HEADERS = None
CVURL = None
DEMURL = None
WWTURL = None
TPSEURL = None
KEYS_32P = None
AUTHKEY_32P = None
FEED_32P = None
FEEDINFO_32P = None
INKDROPS_32P = None
USE_SABNZBD = False
USE_NZBGET = False
USE_BLACKHOLE = False
USE_RTORRENT = False
USE_DELUGE = False
USE_TRANSMISSION = False
USE_QBITTORENT = False
USE_UTORRENT = False
USE_WATCHDIR = False
SNPOOL = None
NZBPOOL = None
SNATCHED_QUEUE = Queue.Queue()
NZB_QUEUE = Queue.Queue()
COMICSORT = None
PULLBYFILE = None
CFG = None
LOG_LIST = []
CURRENT_WEEKNUMBER = None
CURRENT_YEAR = None
INSTALL_TYPE = None
CURRENT_BRANCH = None
CURRENT_VERSION = None
LATEST_VERSION = None
COMMITS_BEHIND = None
LOCAL_IP = None
DOWNLOAD_APIKEY = None
CMTAGGER_PATH = None
STATIC_COMICRN_VERSION = "1.01"
STATIC_APC_VERSION = "1.0"
SAB_PARAMS = None
SCHED = BackgroundScheduler({
                             'apscheduler.executors.default': {
                                 'class':  'apscheduler.executors.pool:ThreadPoolExecutor',
                                 'max_workers': '20'
                             },
                             'apscheduler.job_defaults.coalesce': 'false',
                             'apscheduler.job_defaults.max_instances': '3',
                             'apscheduler.timezone': 'UTC'})



def initialize(config_file):
    with INIT_LOCK:

        global CONFIG, _INITIALIZED, QUIET, CONFIG_FILE, CURRENT_VERSION, LATEST_VERSION, COMMITS_BEHIND, INSTALL_TYPE, IMPORTLOCK, PULLBYFILE, INKDROPS_32P, \
               DONATEBUTTON, CURRENT_WEEKNUMBER, CURRENT_YEAR, UMASK, USER_AGENT, SNATCHED_QUEUE, NZB_QUEUE, PULLNEW, COMICSORT, WANTED_TAB_OFF, CV_HEADERS, \
               IMPORTBUTTON, IMPORT_FILES, IMPORT_TOTALFILES, IMPORT_CID_COUNT, IMPORT_PARSED_COUNT, IMPORT_FAILURE_COUNT, CHECKENABLED, CVURL, DEMURL, WWTURL, TPSEURL, \
               USE_SABNZBD, USE_NZBGET, USE_BLACKHOLE, USE_RTORRENT, USE_UTORRENT, USE_QBITTORRENT, USE_DELUGE, USE_TRANSMISSION, USE_WATCHDIR, SAB_PARAMS, \
               PROG_DIR, DATA_DIR, CMTAGGER_PATH, DOWNLOAD_APIKEY, LOCAL_IP, STATIC_COMICRN_VERSION, STATIC_APC_VERSION, KEYS_32P, AUTHKEY_32P, FEED_32P, FEEDINFO_32P, \
               MONITOR_STATUS, SEARCH_STATUS, RSS_STATUS, WEEKLY_STATUS, VERSION_STATUS, UPDATER_STATUS, DBUPDATE_INTERVAL, \
               SCHED_RSS_LAST, SCHED_WEEKLY_LAST, SCHED_MONITOR_LAST, SCHED_SEARCH_LAST, SCHED_VERSION_LAST, SCHED_DBUPDATE_LAST

        cc = mylar.config.Config(config_file)
        CONFIG = cc.read()

        assert CONFIG is not None

        if _INITIALIZED:
            return False

        #set up the default values here if they're wrong.
        #cc.configure()

        # Start the logger, silence console logging if we need to
        logger.initLogger(console=not QUIET, log_dir=CONFIG.LOG_DIR, verbose=VERBOSE) #logger.mylar_log.initLogger(verbose=VERBOSE)

        #try to get the local IP using socket. Get this on every startup so it's at least current for existing session.
        import socket
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(('8.8.8.8', 80))
            LOCAL_IP = s.getsockname()[0]
            s.close()
            logger.info('Successfully discovered local IP and locking it in as : ' + str(LOCAL_IP))
        except:
            logger.warn('Unable to determine local IP - this might cause problems when downloading (maybe use host_return in the config.ini)')
            LOCAL_IP = CONFIG.HTTP_HOST


        # verbatim back the logger being used since it's now started.
        if LOGTYPE == 'clog':
            logprog = 'Concurrent Rotational Log Handler'
        else:
            logprog = 'Rotational Log Handler (default)'

        logger.fdebug('Logger set to use : ' + logprog)
        if LOGTYPE == 'log' and OS_DETECT == 'Windows':
            logger.fdebug('ConcurrentLogHandler package not installed. Using builtin log handler for Rotational logs (default)')
            logger.fdebug('[Windows Users] If you are experiencing log file locking and want this auto-enabled, you need to install Python Extensions for Windows ( http://sourceforge.net/projects/pywin32/ )')

        logger.info('Config GIT Branch: %s' % CONFIG.GIT_BRANCH)

        # Get the currently installed version - returns None, 'win32' or the git hash
        # Also sets INSTALL_TYPE variable to 'win', 'git' or 'source'
        CURRENT_VERSION, CONFIG.GIT_BRANCH = versioncheck.getVersion()
        #versioncheck.getVersion()
        #config_write()

        if CURRENT_VERSION is not None:
            hash = CURRENT_VERSION[:7]
        else:
            hash = "unknown"

        if CONFIG.GIT_BRANCH == 'master':
            vers = 'M'
        elif CONFIG.GIT_BRANCH == 'development':
           vers = 'D'
        else:
           vers = 'NONE'

        USER_AGENT = 'Mylar/' +str(hash) +'(' +vers +') +http://www.github.com/evilhero/mylar/'

        CV_HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 6.1; WOW64; rv:40.0) Gecko/20100101 Firefox/40.1'}

        # set the current week for the pull-list
        todaydate = datetime.datetime.today()
        CURRENT_WEEKNUMBER = todaydate.strftime("%U")
        CURRENT_YEAR = todaydate.strftime("%Y")

        # Initialize the database
        logger.info('Checking to see if the database has all tables....')
        try:
            dbcheck()
        except Exception, e:
            logger.error('Cannot connect to the database: %s' % e)

        # Check for new versions (autoupdate)
        if CONFIG.CHECK_GITHUB_ON_STARTUP:
            try:
                LATEST_VERSION = versioncheck.checkGithub()
            except:
                LATEST_VERSION = CURRENT_VERSION
        else:
            LATEST_VERSION = CURRENT_VERSION
#
        if CONFIG.AUTO_UPDATE:
            if CURRENT_VERSION != LATEST_VERSION and INSTALL_TYPE != 'win' and COMMITS_BEHIND > 0:
                logger.info('Auto-updating has been enabled. Attempting to auto-update.')
#                SIGNAL = 'update'

        #check for syno_fix here
        if CONFIG.SYNO_FIX:
            parsepath = os.path.join(DATA_DIR, 'bs4', 'builder', '_lxml.py')
            if os.path.isfile(parsepath):
                print ("found bs4...renaming appropriate file.")
                src = os.path.join(parsepath)
                dst = os.path.join(DATA_DIR, 'bs4', 'builder', 'lxml.py')
                try:
                    shutil.move(src, dst)
                except (OSError, IOError):
                    logger.error('Unable to rename file...shutdown Mylar and go to ' + src.encode('utf-8') + ' and rename the _lxml.py file to lxml.py')
                    logger.error('NOT doing this will result in errors when adding / refreshing a series')
            else:
                logger.info('Synology Parsing Fix already implemented. No changes required at this time.')

        #set the default URL for ComicVine API here.
        CVURL = 'https://comicvine.gamespot.com/api/'

        #set default URL for Public trackers (just in case it changes more frequently)
        WWTURL = 'https://worldwidetorrents.me/'
        DEMURL = 'https://www.demonoid.pw/'
        TPSEURL = 'https://torrentproject.se/'

        if CONFIG.LOCMOVE:
            helpers.updateComicLocation()


        #Ordering comics here
        logger.info('Remapping the sorting to allow for new additions.')
        COMICSORT = helpers.ComicSort(sequence='startup')

        # Store the original umask
        UMASK = os.umask(0)
        os.umask(UMASK)

        _INITIALIZED = True
        return True

def daemonize():

    if threading.activeCount() != 1:
        logger.warn('There are %r active threads. Daemonizing may cause \
                        strange behavior.' % threading.enumerate())

    sys.stdout.flush()
    sys.stderr.flush()

    # Do first fork
    try:
        pid = os.fork()
        if pid == 0:
            pass
        else:
            # Exit the parent process
            logger.debug('Forking once...')
            os._exit(0)
    except OSError, e:
        sys.exit("1st fork failed: %s [%d]" % (e.strerror, e.errno))

    os.setsid()

    # Make sure I can read my own files and shut out others
    prev = os.umask(0)  # @UndefinedVariable - only available in UNIX
    os.umask(prev and int('077', 8))

    # Do second fork
    try:
        pid = os.fork()
        if pid > 0:
            logger.debug('Forking twice...')
            os._exit(0) # Exit second parent process
    except OSError, e:
        sys.exit("2nd fork failed: %s [%d]" % (e.strerror, e.errno))

    dev_null = file('/dev/null', 'r')
    os.dup2(dev_null.fileno(), sys.stdin.fileno())

    si = open('/dev/null', "r")
    so = open('/dev/null', "a+")
    se = open('/dev/null', "a+")

    os.dup2(si.fileno(), sys.stdin.fileno())
    os.dup2(so.fileno(), sys.stdout.fileno())
    os.dup2(se.fileno(), sys.stderr.fileno())

    pid = os.getpid()
    logger.info('Daemonized to PID: %s' % pid)
    if CREATEPID:
        logger.info("Writing PID %d to %s", pid, PIDFILE)
        with file(PIDFILE, 'w') as fp:
            fp.write("%s\n" % pid)

def launch_browser(host, port, root):

    if host == '0.0.0.0':
        host = 'localhost'

    try:
        webbrowser.open('http://%s:%i%s' % (host, port, root))
    except Exception, e:
        logger.error('Could not launch browser: %s' % e)

def start():

    global _INITIALIZED, started

    with INIT_LOCK:

        if _INITIALIZED:

            #load up the previous runs from the job sql table so we know stuff...
            monitors = helpers.job_management()
            SCHED_WEEKLY_LAST = monitors['weekly']
            SCHED_SEARCH_LAST = monitors['search']
            SCHED_UPDATER_LAST = monitors['dbupdater']
            SCHED_MONITOR_LAST = monitors['monitor']
            SCHED_VERSION_LAST = monitors['version']
            SCHED_RSS_LAST = monitors['rss']

            # Start our scheduled background tasks
            SCHED.add_job(func=updater.dbUpdate, id='dbupdater', name='DB Updater', args=[None,None,True], trigger=IntervalTrigger(hours=0, minutes=5, timezone='UTC'))

            #let's do a run at the Wanted issues here (on startup) if enabled.
            ss = searchit.CurrentSearcher()
            if CONFIG.NZB_STARTUP_SEARCH:
                SCHED.add_job(func=ss.run, id='search', next_run_time=datetime.datetime.utcnow(), name='Auto-Search', trigger=IntervalTrigger(hours=0, minutes=CONFIG.SEARCH_INTERVAL, timezone='UTC'))
            else:
                if SCHED_SEARCH_LAST is not None:
                    search_timestamp = float(SCHED_SEARCH_LAST)
                    logger.fdebug('[AUTO-SEARCH] Search last run @ %s' % datetime.datetime.utcfromtimestamp(search_timestamp))
                else:
                    search_timestamp = helpers.utctimestamp() + (int(CONFIG.SEARCH_INTERVAL) *60)

                duration_diff = (helpers.utctimestamp() - search_timestamp)/60
                if duration_diff >= int(CONFIG.SEARCH_INTERVAL):
                    logger.fdebug('[AUTO-SEARCH]Auto-Search set to a delay of one minute before initialization as it has been %s minutes since the last run' % duration_diff)
                    SCHED.add_job(func=ss.run, id='search', name='Auto-Search', trigger=IntervalTrigger(hours=0, minutes=CONFIG.SEARCH_INTERVAL, timezone='UTC'))
                else:
                    search_diff = datetime.datetime.utcfromtimestamp(helpers.utctimestamp() + ((int(CONFIG.SEARCH_INTERVAL) * 60)  - (duration_diff*60)))
                    logger.fdebug('[AUTO-SEARCH] Scheduling next run @ %s every %s minutes' % (search_diff, CONFIG.SEARCH_INTERVAL))
                    SCHED.add_job(func=ss.run, id='search', name='Auto-Search', next_run_time=search_diff, trigger=IntervalTrigger(hours=0, minutes=CONFIG.SEARCH_INTERVAL, timezone='UTC'))

            if all([CONFIG.ENABLE_TORRENTS, CONFIG.AUTO_SNATCH, OS_DETECT != 'Windows']) and any([CONFIG.TORRENT_DOWNLOADER == 2, CONFIG.TORRENT_DOWNLOADER == 4]):
                logger.info('[AUTO-SNATCHER] Auto-Snatch of completed torrents enabled & attempting to background load....')
                SNPOOL = threading.Thread(target=helpers.worker_main, args=(SNATCHED_QUEUE,), name="AUTO-SNATCHER")
                SNPOOL.start()
                logger.info('[AUTO-SNATCHER] Succesfully started Auto-Snatch add-on - will now monitor for completed torrents on client....')

            if CONFIG.POST_PROCESSING is True and ( all([CONFIG.NZB_DOWNLOADER == 0, CONFIG.SAB_CLIENT_POST_PROCESSING is True]) or all([CONFIG.NZB_DOWNLOADER == 1, CONFIG.NZBGET_CLIENT_POST_PROCESSING is True]) ):
                if CONFIG.NZB_DOWNLOADER == 0:
                    logger.info('[SAB-MONITOR] Completed post-processing handling enabled for SABnzbd. Attempting to background load....')
                elif CONFIG.NZB_DOWNLOADER == 1:
                    logger.info('[NZBGET-MONITOR] Completed post-processing handling enabled for NZBGet. Attempting to background load....')
                NZBPOOL = threading.Thread(target=helpers.nzb_monitor, args=(NZB_QUEUE,), name="AUTO-COMPLETE-NZB")
                NZBPOOL.start()
                if CONFIG.NZB_DOWNLOADER == 0:
                    logger.info('[AUTO-COMPLETE-NZB] Succesfully started Completed post-processing handling for SABnzbd - will now monitor for completed nzbs within sabnzbd and post-process automatically....')
                elif CONFIG.NZB_DOWNLOADER == 1:
                    logger.info('[AUTO-COMPLETE-NZB] Succesfully started Completed post-processing handling for NZBGet - will now monitor for completed nzbs within nzbget and post-process automatically....')


            helpers.latestdate_fix()

            if CONFIG.ALT_PULL == 2:
                weektimer = 4
            else:
                weektimer = 24

            #weekly pull list gets messed up if it's not populated first, so let's populate it then set the scheduler.
            logger.info('[WEEKLY] Checking for existance of Weekly Comic listing...')

            #now the scheduler (check every 24 hours)
            weekly_interval = weektimer * 60 * 60
            try:
                if SCHED_WEEKLY_LAST:
                    pass
            except:
                SCHED_WEEKLY_LAST = None

            weektimestamp = helpers.utctimestamp()
            if SCHED_WEEKLY_LAST is not None:
                weekly_timestamp = float(SCHED_WEEKLY_LAST)
            else:
                weekly_timestamp = weektimestamp + weekly_interval

            ws = weeklypullit.Weekly()
            duration_diff = (weektimestamp - weekly_timestamp)/60

            if abs(duration_diff) >= weekly_interval/60:
                logger.info('[WEEKLY] Weekly Pull-Update initializing immediately as it has been %s hours since the last run' % abs(duration_diff/60))
                SCHED.add_job(func=ws.run, id='weekly', name='Weekly Pullist', next_run_time=datetime.datetime.utcnow(), trigger=IntervalTrigger(hours=weektimer, minutes=0, timezone='UTC'))
            else:
                weekly_diff = datetime.datetime.utcfromtimestamp(weektimestamp + (weekly_interval - (duration_diff * 60)))
                logger.fdebug('[WEEKLY] Scheduling next run for @ %s every %s hours' % (weekly_diff, weektimer))
                SCHED.add_job(func=ws.run, id='weekly', name='Weekly Pullist', next_run_time=weekly_diff, trigger=IntervalTrigger(hours=weektimer, minutes=0, timezone='UTC'))

            #initiate startup rss feeds for torrents/nzbs here...
            if CONFIG.ENABLE_RSS:
                logger.info('[RSS-FEEDS] Initiating startup-RSS feed checks.')
                if SCHED_RSS_LAST is not None:
                    rss_timestamp = float(SCHED_RSS_LAST)
                    logger.info('[RSS-FEEDS] RSS last run @ %s' % datetime.datetime.utcfromtimestamp(rss_timestamp))
                else:
                    rss_timestamp = helpers.utctimestamp() + (int(CONFIG.RSS_CHECKINTERVAL) *60)
                rs = rsscheckit.tehMain()
                duration_diff = (helpers.utctimestamp() - rss_timestamp)/60
                if duration_diff >= int(CONFIG.RSS_CHECKINTERVAL):
                    SCHED.add_job(func=rs.run, id='rss', name='RSS Feeds', args=[True], next_run_time=datetime.datetime.utcnow(), trigger=IntervalTrigger(hours=0, minutes=int(CONFIG.RSS_CHECKINTERVAL), timezone='UTC'))
                else:
                    rss_diff = datetime.datetime.utcfromtimestamp(helpers.utctimestamp() + (int(CONFIG.RSS_CHECKINTERVAL) * 60) - (duration_diff * 60))
                    logger.fdebug('[RSS-FEEDS] Scheduling next run for @ %s every %s minutes' % (rss_diff, CONFIG.RSS_CHECKINTERVAL))
                    SCHED.add_job(func=rs.run, id='rss', name='RSS Feeds', args=[True], next_run_time=rss_diff, trigger=IntervalTrigger(hours=0, minutes=int(CONFIG.RSS_CHECKINTERVAL), timezone='UTC'))

            if CONFIG.CHECK_GITHUB:
                vs = versioncheckit.CheckVersion()
                SCHED.add_job(func=vs.run, id='version', name='Check Version', trigger=IntervalTrigger(hours=0, minutes=CONFIG.CHECK_GITHUB_INTERVAL, timezone='UTC'))

            ##run checkFolder every X minutes (basically Manual Run Post-Processing)
            if CONFIG.ENABLE_CHECK_FOLDER:
                if CONFIG.DOWNLOAD_SCAN_INTERVAL >0:
                    logger.info('[FOLDER MONITOR] Enabling folder monitor for : ' + str(CONFIG.CHECK_FOLDER) + ' every ' + str(CONFIG.DOWNLOAD_SCAN_INTERVAL) + ' minutes.')
                    fm = PostProcessor.FolderCheck()
                    SCHED.add_job(func=fm.run, id='monitor', name='Folder Monitor', trigger=IntervalTrigger(hours=0, minutes=int(CONFIG.DOWNLOAD_SCAN_INTERVAL), timezone='UTC'))
                else:
                    logger.error('[FOLDER MONITOR] You need to specify a monitoring time for the check folder option to work')

            logger.info('Firing up the Background Schedulers now....')
            try:
                SCHED.start()
                #update the job db here
                logger.info('Background Schedulers successfully started...')
                helpers.job_management(write=True)
            except Exception as e:
                logger.info(e)
                SCHED.print_jobs()

        started = True

def dbcheck():
    conn = sqlite3.connect(DB_FILE)
    c_error = 'sqlite3.OperationalError'
    c=conn.cursor()

    c.execute('CREATE TABLE IF NOT EXISTS comics (ComicID TEXT UNIQUE, ComicName TEXT, ComicSortName TEXT, ComicYear TEXT, DateAdded TEXT, Status TEXT, IncludeExtras INTEGER, Have INTEGER, Total INTEGER, ComicImage TEXT, ComicPublisher TEXT, ComicLocation TEXT, ComicPublished TEXT, NewPublish TEXT, LatestIssue TEXT, LatestDate TEXT, Description TEXT, QUALalt_vers TEXT, QUALtype TEXT, QUALscanner TEXT, QUALquality TEXT, LastUpdated TEXT, AlternateSearch TEXT, UseFuzzy TEXT, ComicVersion TEXT, SortOrder INTEGER, DetailURL TEXT, ForceContinuing INTEGER, ComicName_Filesafe TEXT, AlternateFileName TEXT, ComicImageURL TEXT, ComicImageALTURL TEXT, DynamicComicName TEXT, AllowPacks TEXT, Type TEXT, Corrected_SeriesYear TEXT)')
    c.execute('CREATE TABLE IF NOT EXISTS issues (IssueID TEXT, ComicName TEXT, IssueName TEXT, Issue_Number TEXT, DateAdded TEXT, Status TEXT, Type TEXT, ComicID TEXT, ArtworkURL Text, ReleaseDate TEXT, Location TEXT, IssueDate TEXT, Int_IssueNumber INT, ComicSize TEXT, AltIssueNumber TEXT, IssueDate_Edit TEXT, ImageURL TEXT, ImageURL_ALT TEXT)')
    c.execute('CREATE TABLE IF NOT EXISTS snatched (IssueID TEXT, ComicName TEXT, Issue_Number TEXT, Size INTEGER, DateAdded TEXT, Status TEXT, FolderName TEXT, ComicID TEXT, Provider TEXT, Hash TEXT, crc TEXT)')
    c.execute('CREATE TABLE IF NOT EXISTS upcoming (ComicName TEXT, IssueNumber TEXT, ComicID TEXT, IssueID TEXT, IssueDate TEXT, Status TEXT, DisplayComicName TEXT)')
    c.execute('CREATE TABLE IF NOT EXISTS nzblog (IssueID TEXT, NZBName TEXT, SARC TEXT, PROVIDER TEXT, ID TEXT, AltNZBName TEXT, OneOff TEXT)')
    c.execute('CREATE TABLE IF NOT EXISTS weekly (SHIPDATE TEXT, PUBLISHER TEXT, ISSUE TEXT, COMIC VARCHAR(150), EXTRA TEXT, STATUS TEXT, ComicID TEXT, IssueID TEXT, CV_Last_Update TEXT, DynamicName TEXT, weeknumber TEXT, year TEXT, volume TEXT, seriesyear TEXT, rowid INTEGER PRIMARY KEY)')
    c.execute('CREATE TABLE IF NOT EXISTS importresults (impID TEXT, ComicName TEXT, ComicYear TEXT, Status TEXT, ImportDate TEXT, ComicFilename TEXT, ComicLocation TEXT, WatchMatch TEXT, DisplayName TEXT, SRID TEXT, ComicID TEXT, IssueID TEXT, Volume TEXT, IssueNumber TEXT, DynamicName TEXT)')
    c.execute('CREATE TABLE IF NOT EXISTS readlist (IssueID TEXT, ComicName TEXT, Issue_Number TEXT, Status TEXT, DateAdded TEXT, Location TEXT, inCacheDir TEXT, SeriesYear TEXT, ComicID TEXT, StatusChange TEXT)')
    c.execute('CREATE TABLE IF NOT EXISTS readinglist(StoryArcID TEXT, ComicName TEXT, IssueNumber TEXT, SeriesYear TEXT, IssueYEAR TEXT, StoryArc TEXT, TotalIssues TEXT, Status TEXT, inCacheDir TEXT, Location TEXT, IssueArcID TEXT, ReadingOrder INT, IssueID TEXT, ComicID TEXT, StoreDate TEXT, IssueDate TEXT, Publisher TEXT, IssuePublisher TEXT, IssueName TEXT, CV_ArcID TEXT, Int_IssueNumber INT, DynamicComicName TEXT, Volume TEXT, Manual TEXT)')
    c.execute('CREATE TABLE IF NOT EXISTS annuals (IssueID TEXT, Issue_Number TEXT, IssueName TEXT, IssueDate TEXT, Status TEXT, ComicID TEXT, GCDComicID TEXT, Location TEXT, ComicSize TEXT, Int_IssueNumber INT, ComicName TEXT, ReleaseDate TEXT, ReleaseComicID TEXT, ReleaseComicName TEXT, IssueDate_Edit TEXT)')
    c.execute('CREATE TABLE IF NOT EXISTS rssdb (Title TEXT UNIQUE, Link TEXT, Pubdate TEXT, Site TEXT, Size TEXT)')
    c.execute('CREATE TABLE IF NOT EXISTS futureupcoming (ComicName TEXT, IssueNumber TEXT, ComicID TEXT, IssueID TEXT, IssueDate TEXT, Publisher TEXT, Status TEXT, DisplayComicName TEXT, weeknumber TEXT, year TEXT)')
    c.execute('CREATE TABLE IF NOT EXISTS failed (ID TEXT, Status TEXT, ComicID TEXT, IssueID TEXT, Provider TEXT, ComicName TEXT, Issue_Number TEXT, NZBName TEXT, DateFailed TEXT)')
    c.execute('CREATE TABLE IF NOT EXISTS searchresults (SRID TEXT, results Numeric, Series TEXT, publisher TEXT, haveit TEXT, name TEXT, deck TEXT, url TEXT, description TEXT, comicid TEXT, comicimage TEXT, issues TEXT, comicyear TEXT, ogcname TEXT)')
    c.execute('CREATE TABLE IF NOT EXISTS ref32p (ComicID TEXT UNIQUE, ID TEXT, Series TEXT, Updated TEXT)')
    c.execute('CREATE TABLE IF NOT EXISTS oneoffhistory (ComicName TEXT, IssueNumber TEXT, ComicID TEXT, IssueID TEXT, Status TEXT, weeknumber TEXT, year TEXT)')
    c.execute('CREATE TABLE IF NOT EXISTS jobhistory (JobName TEXT, prev_run_datetime timestamp, prev_run_timestamp REAL, next_run_datetime timestamp, next_run_timestamp REAL, last_run_completed TEXT, successful_completions TEXT, failed_completions TEXT, status TEXT)')
    conn.commit
    c.close

    csv_load()


    #add in the late players to the game....
    # -- Comics Table --

    try:
        c.execute('SELECT LastUpdated from comics')
    except sqlite3.OperationalError:
        c.execute('ALTER TABLE comics ADD COLUMN LastUpdated TEXT')

    try:
        c.execute('SELECT QUALalt_vers from comics')
    except sqlite3.OperationalError:
        c.execute('ALTER TABLE comics ADD COLUMN QUALalt_vers TEXT')

    try:
        c.execute('SELECT QUALtype from comics')
    except sqlite3.OperationalError:
        c.execute('ALTER TABLE comics ADD COLUMN QUALtype TEXT')

    try:
        c.execute('SELECT QUALscanner from comics')
    except sqlite3.OperationalError:
        c.execute('ALTER TABLE comics ADD COLUMN QUALscanner TEXT')

    try:
        c.execute('SELECT QUALquality from comics')
    except sqlite3.OperationalError:
        c.execute('ALTER TABLE comics ADD COLUMN QUALquality TEXT')

    try:
        c.execute('SELECT AlternateSearch from comics')
    except sqlite3.OperationalError:
        c.execute('ALTER TABLE comics ADD COLUMN AlternateSearch TEXT')

    try:
        c.execute('SELECT ComicVersion from comics')
    except sqlite3.OperationalError:
        c.execute('ALTER TABLE comics ADD COLUMN ComicVersion TEXT')

    try:
        c.execute('SELECT SortOrder from comics')
    except sqlite3.OperationalError:
        c.execute('ALTER TABLE comics ADD COLUMN SortOrder INTEGER')

    try:
        c.execute('SELECT UseFuzzy from comics')
    except sqlite3.OperationalError:
        c.execute('ALTER TABLE comics ADD COLUMN UseFuzzy TEXT')

    try:
        c.execute('SELECT DetailURL from comics')
    except sqlite3.OperationalError:
        c.execute('ALTER TABLE comics ADD COLUMN DetailURL TEXT')

    try:
        c.execute('SELECT ForceContinuing from comics')
    except sqlite3.OperationalError:
        c.execute('ALTER TABLE comics ADD COLUMN ForceContinuing INTEGER')

    try:
        c.execute('SELECT ComicName_Filesafe from comics')
    except sqlite3.OperationalError:
        c.execute('ALTER TABLE comics ADD COLUMN ComicName_Filesafe TEXT')

    try:
        c.execute('SELECT AlternateFileName from comics')
    except sqlite3.OperationalError:
        c.execute('ALTER TABLE comics ADD COLUMN AlternateFileName TEXT')

    try:
        c.execute('SELECT ComicImageURL from comics')
    except sqlite3.OperationalError:
        c.execute('ALTER TABLE comics ADD COLUMN ComicImageURL TEXT')

    try:
        c.execute('SELECT ComicImageALTURL from comics')
    except sqlite3.OperationalError:
        c.execute('ALTER TABLE comics ADD COLUMN ComicImageALTURL TEXT')

    try:
        c.execute('SELECT NewPublish from comics')
    except sqlite3.OperationalError:
        c.execute('ALTER TABLE comics ADD COLUMN NewPublish TEXT')

    try:
        c.execute('SELECT AllowPacks from comics')
    except sqlite3.OperationalError:
        c.execute('ALTER TABLE comics ADD COLUMN AllowPacks TEXT')

    try:
        c.execute('SELECT Type from comics')
    except sqlite3.OperationalError:
        c.execute('ALTER TABLE comics ADD COLUMN Type TEXT')

    try:
        c.execute('SELECT Corrected_SeriesYear from comics')
    except sqlite3.OperationalError:
        c.execute('ALTER TABLE comics ADD COLUMN Corrected_SeriesYear TEXT')

    try:
        c.execute('SELECT DynamicComicName from comics')
        if CONFIG.DYNAMIC_UPDATE < 3:
            dynamic_upgrade = True
        else:
            dynamic_upgrade = False
    except sqlite3.OperationalError:
        c.execute('ALTER TABLE comics ADD COLUMN DynamicComicName TEXT')
        dynamic_upgrade = True

    # -- Issues Table --

    try:
        c.execute('SELECT ComicSize from issues')
    except sqlite3.OperationalError:
        c.execute('ALTER TABLE issues ADD COLUMN ComicSize TEXT')

    try:
        c.execute('SELECT inCacheDir from issues')
    except sqlite3.OperationalError:
        c.execute('ALTER TABLE issues ADD COLUMN inCacheDIR TEXT')

    try:
        c.execute('SELECT AltIssueNumber from issues')
    except sqlite3.OperationalError:
        c.execute('ALTER TABLE issues ADD COLUMN AltIssueNumber TEXT')

    try:
        c.execute('SELECT IssueDate_Edit from issues')
    except sqlite3.OperationalError:
        c.execute('ALTER TABLE issues ADD COLUMN IssueDate_Edit TEXT')

    try:
        c.execute('SELECT ImageURL from issues')
    except sqlite3.OperationalError:
        c.execute('ALTER TABLE issues ADD COLUMN ImageURL TEXT')

    try:
        c.execute('SELECT ImageURL_ALT from issues')
    except sqlite3.OperationalError:
        c.execute('ALTER TABLE issues ADD COLUMN ImageURL_ALT TEXT')


    ## -- ImportResults Table --

    try:
        c.execute('SELECT WatchMatch from importresults')
    except sqlite3.OperationalError:
        c.execute('ALTER TABLE importresults ADD COLUMN WatchMatch TEXT')

    try:
        c.execute('SELECT IssueCount from importresults')
    except sqlite3.OperationalError:
        c.execute('ALTER TABLE importresults ADD COLUMN IssueCount TEXT')

    try:
        c.execute('SELECT ComicLocation from importresults')
    except sqlite3.OperationalError:
        c.execute('ALTER TABLE importresults ADD COLUMN ComicLocation TEXT')

    try:
        c.execute('SELECT ComicFilename from importresults')
    except sqlite3.OperationalError:
        c.execute('ALTER TABLE importresults ADD COLUMN ComicFilename TEXT')

    try:
        c.execute('SELECT impID from importresults')
    except sqlite3.OperationalError:
        c.execute('ALTER TABLE importresults ADD COLUMN impID TEXT')

    try:
        c.execute('SELECT implog from importresults')
    except sqlite3.OperationalError:
        c.execute('ALTER TABLE importresults ADD COLUMN implog TEXT')

    try:
        c.execute('SELECT DisplayName from importresults')
    except sqlite3.OperationalError:
        c.execute('ALTER TABLE importresults ADD COLUMN DisplayName TEXT')

    try:
        c.execute('SELECT SRID from importresults')
    except sqlite3.OperationalError:
        c.execute('ALTER TABLE importresults ADD COLUMN SRID TEXT')

    try:
        c.execute('SELECT ComicID from importresults')
    except sqlite3.OperationalError:
        c.execute('ALTER TABLE importresults ADD COLUMN ComicID TEXT')

    try:
        c.execute('SELECT IssueID from importresults')
    except sqlite3.OperationalError:
        c.execute('ALTER TABLE importresults ADD COLUMN IssueID TEXT')

    try:
        c.execute('SELECT Volume from importresults')
    except sqlite3.OperationalError:
        c.execute('ALTER TABLE importresults ADD COLUMN Volume TEXT')

    try:
        c.execute('SELECT IssueNumber from importresults')
    except sqlite3.OperationalError:
        c.execute('ALTER TABLE importresults ADD COLUMN IssueNumber TEXT')

    try:
        c.execute('SELECT DynamicName from importresults')
    except sqlite3.OperationalError:
        c.execute('ALTER TABLE importresults ADD COLUMN DynamicName TEXT')

    ## -- Readlist Table --

    try:
        c.execute('SELECT inCacheDIR from readlist')
    except sqlite3.OperationalError:
        c.execute('ALTER TABLE readlist ADD COLUMN inCacheDIR TEXT')

    try:
        c.execute('SELECT Location from readlist')
    except sqlite3.OperationalError:
        c.execute('ALTER TABLE readlist ADD COLUMN Location TEXT')

    try:
        c.execute('SELECT IssueDate from readlist')
    except sqlite3.OperationalError:
        c.execute('ALTER TABLE readlist ADD COLUMN IssueDate TEXT')

    try:
        c.execute('SELECT SeriesYear from readlist')
    except sqlite3.OperationalError:
        c.execute('ALTER TABLE readlist ADD COLUMN SeriesYear TEXT')

    try:
        c.execute('SELECT ComicID from readlist')
    except sqlite3.OperationalError:
        c.execute('ALTER TABLE readlist ADD COLUMN ComicID TEXT')

    try:
        c.execute('SELECT StatusChange from readlist')
    except sqlite3.OperationalError:
        c.execute('ALTER TABLE readlist ADD COLUMN StatusChange TEXT')

    ## -- Weekly Table --

    try:
        c.execute('SELECT ComicID from weekly')
    except sqlite3.OperationalError:
        c.execute('ALTER TABLE weekly ADD COLUMN ComicID TEXT')

    try:
        c.execute('SELECT IssueID from weekly')
    except sqlite3.OperationalError:
        c.execute('ALTER TABLE weekly ADD COLUMN IssueID TEXT')

    try:
        c.execute('SELECT DynamicName from weekly')
    except sqlite3.OperationalError:
        c.execute('ALTER TABLE weekly ADD COLUMN DynamicName TEXT')

    try:
        c.execute('SELECT CV_Last_Update from weekly')
    except sqlite3.OperationalError:
        c.execute('ALTER TABLE weekly ADD COLUMN CV_Last_Update TEXT')

    try:
        c.execute('SELECT weeknumber from weekly')
    except sqlite3.OperationalError:
        c.execute('ALTER TABLE weekly ADD COLUMN weeknumber TEXT')

    try:
        c.execute('SELECT year from weekly')
    except sqlite3.OperationalError:
        c.execute('ALTER TABLE weekly ADD COLUMN year TEXT')

    try:
        c.execute('SELECT rowid from weekly')
    except sqlite3.OperationalError:
        c.execute('ALTER TABLE weekly ADD COLUMN rowid INTEGER PRIMARY KEY')

    try:
        c.execute('SELECT volume from weekly')
    except sqlite3.OperationalError:
        c.execute('ALTER TABLE weekly ADD COLUMN volume TEXT')

    try:
        c.execute('SELECT seriesyear from weekly')
    except sqlite3.OperationalError:
        c.execute('ALTER TABLE weekly ADD COLUMN seriesyear TEXT')

    ## -- Nzblog Table --

    try:
        c.execute('SELECT SARC from nzblog')
    except sqlite3.OperationalError:
        c.execute('ALTER TABLE nzblog ADD COLUMN SARC TEXT')

    try:
        c.execute('SELECT PROVIDER from nzblog')
    except sqlite3.OperationalError:
        c.execute('ALTER TABLE nzblog ADD COLUMN PROVIDER TEXT')

    try:
        c.execute('SELECT ID from nzblog')
    except sqlite3.OperationalError:
        c.execute('ALTER TABLE nzblog ADD COLUMN ID TEXT')

    try:
        c.execute('SELECT AltNZBName from nzblog')
    except sqlite3.OperationalError:
        c.execute('ALTER TABLE nzblog ADD COLUMN AltNZBName TEXT')

    try:
        c.execute('SELECT OneOff from nzblog')
    except sqlite3.OperationalError:
        c.execute('ALTER TABLE nzblog ADD COLUMN OneOff TEXT')
    ## -- Annuals Table --

    try:
        c.execute('SELECT Location from annuals')
    except sqlite3.OperationalError:
        c.execute('ALTER TABLE annuals ADD COLUMN Location TEXT')

    try:
        c.execute('SELECT ComicSize from annuals')
    except sqlite3.OperationalError:
        c.execute('ALTER TABLE annuals ADD COLUMN ComicSize TEXT')

    try:
        c.execute('SELECT Int_IssueNumber from annuals')
    except sqlite3.OperationalError:
        c.execute('ALTER TABLE annuals ADD COLUMN Int_IssueNumber INT')

    try:
        c.execute('SELECT ComicName from annuals')
        annual_update = "no"
    except sqlite3.OperationalError:
        c.execute('ALTER TABLE annuals ADD COLUMN ComicName TEXT')
        annual_update = "yes"

    if annual_update == "yes":
        logger.info("Updating Annuals table for new fields - one-time update.")
        helpers.annual_update()

    try:
        c.execute('SELECT ReleaseDate from annuals')
    except sqlite3.OperationalError:
        c.execute('ALTER TABLE annuals ADD COLUMN ReleaseDate TEXT')

    try:
        c.execute('SELECT ReleaseComicID from annuals')
    except sqlite3.OperationalError:
        c.execute('ALTER TABLE annuals ADD COLUMN ReleaseComicID TEXT')

    try:
        c.execute('SELECT ReleaseComicName from annuals')
    except sqlite3.OperationalError:
        c.execute('ALTER TABLE annuals ADD COLUMN ReleaseComicName TEXT')

    try:
        c.execute('SELECT IssueDate_Edit from annuals')
    except sqlite3.OperationalError:
        c.execute('ALTER TABLE annuals ADD COLUMN IssueDate_Edit TEXT')


    ## -- Snatched Table --

    try:
        c.execute('SELECT Provider from snatched')
    except sqlite3.OperationalError:
        c.execute('ALTER TABLE snatched ADD COLUMN Provider TEXT')

    try:
        c.execute('SELECT Hash from snatched')
    except sqlite3.OperationalError:
        c.execute('ALTER TABLE snatched ADD COLUMN Hash TEXT')

    try:
        c.execute('SELECT crc from snatched')
    except sqlite3.OperationalError:
        c.execute('ALTER TABLE snatched ADD COLUMN crc TEXT')

    ## -- Upcoming Table --

    try:
        c.execute('SELECT DisplayComicName from upcoming')
    except sqlite3.OperationalError:
        c.execute('ALTER TABLE upcoming ADD COLUMN DisplayComicName TEXT')


    ## -- Readinglist Table --

    try:
        c.execute('SELECT ComicID from readinglist')
    except sqlite3.OperationalError:
        c.execute('ALTER TABLE readinglist ADD COLUMN ComicID TEXT')

    try:
        c.execute('SELECT StoreDate from readinglist')
    except sqlite3.OperationalError:
        c.execute('ALTER TABLE readinglist ADD COLUMN StoreDate TEXT')

    try:
        c.execute('SELECT IssueDate from readinglist')
    except sqlite3.OperationalError:
        c.execute('ALTER TABLE readinglist ADD COLUMN IssueDate TEXT')

    try:
        c.execute('SELECT Publisher from readinglist')
    except sqlite3.OperationalError:
        c.execute('ALTER TABLE readinglist ADD COLUMN Publisher TEXT')

    try:
        c.execute('SELECT IssuePublisher from readinglist')
    except sqlite3.OperationalError:
        c.execute('ALTER TABLE readinglist ADD COLUMN IssuePublisher TEXT')

    try:
        c.execute('SELECT IssueName from readinglist')
    except sqlite3.OperationalError:
        c.execute('ALTER TABLE readinglist ADD COLUMN IssueName TEXT')

    try:
        c.execute('SELECT CV_ArcID from readinglist')
    except sqlite3.OperationalError:
        c.execute('ALTER TABLE readinglist ADD COLUMN CV_ArcID TEXT')

    try:
        c.execute('SELECT Int_IssueNumber from readinglist')
    except sqlite3.OperationalError:
        c.execute('ALTER TABLE readinglist ADD COLUMN Int_IssueNumber INT')

    try:
        c.execute('SELECT DynamicComicName from readinglist')
        if CONFIG.DYNAMIC_UPDATE < 4:
            dynamic_upgrade = True
        else:
            dynamic_upgrade = False
    except sqlite3.OperationalError:
        c.execute('ALTER TABLE readinglist ADD COLUMN DynamicComicName TEXT')
        dynamic_upgrade = True

    try:
        c.execute('SELECT Volume from readinglist')
    except sqlite3.OperationalError:
        c.execute('ALTER TABLE readinglist ADD COLUMN Volume TEXT')

    try:
        c.execute('SELECT Manual from readinglist')
    except sqlite3.OperationalError:
        c.execute('ALTER TABLE readinglist ADD COLUMN Manual TEXT')

    ## -- searchresults Table --
    try:
        c.execute('SELECT SRID from searchresults')
    except sqlite3.OperationalError:
        c.execute('ALTER TABLE searchresults ADD COLUMN SRID TEXT')

    try:
        c.execute('SELECT Series from searchresults')
    except sqlite3.OperationalError:
        c.execute('ALTER TABLE searchresults ADD COLUMN Series TEXT')

    try:
        c.execute('SELECT sresults from searchresults')
    except sqlite3.OperationalError:
        c.execute('ALTER TABLE searchresults ADD COLUMN sresults TEXT')

    try:
        c.execute('SELECT ogcname from searchresults')
    except sqlite3.OperationalError:
        c.execute('ALTER TABLE searchresults ADD COLUMN ogcname TEXT')

    ## -- futureupcoming Table --
    try:
        c.execute('SELECT weeknumber from futureupcoming')
    except sqlite3.OperationalError:
        c.execute('ALTER TABLE futureupcoming ADD COLUMN weeknumber TEXT')

    try:
        c.execute('SELECT year from futureupcoming')
    except sqlite3.OperationalError:
        c.execute('ALTER TABLE futureupcoming ADD COLUMN year TEXT')

    ## -- Failed Table --
    try:
        c.execute('SELECT DateFailed from Failed')
    except sqlite3.OperationalError:
        c.execute('ALTER TABLE Failed ADD COLUMN DateFailed TEXT')

    ## -- Ref32p Table --
    try:
        c.execute('SELECT Updated from ref32p')
    except sqlite3.OperationalError:
        c.execute('ALTER TABLE ref32p ADD COLUMN Updated TEXT')


    ## -- Jobhistory Table --
    try:
        c.execute('SELECT status from jobhistory')
    except sqlite3.OperationalError:
        c.execute('ALTER TABLE jobhistory ADD COLUMN status TEXT')

    #if it's prior to Wednesday, the issue counts will be inflated by one as the online db's everywhere
    #prepare for the next 'new' release of a series. It's caught in updater.py, so let's just store the
    #value in the sql so we can display it in the details screen for everyone to wonder at.
    try:
        c.execute('SELECT not_updated_db from comics')
    except sqlite3.OperationalError:
        c.execute('ALTER TABLE comics ADD COLUMN not_updated_db TEXT')

# -- not implemented just yet ;)

    # for metadata...
    # MetaData_Present will be true/false if metadata is present
    # MetaData will hold the MetaData itself in tuple format
#    try:
#        c.execute('SELECT MetaData_Present from comics')
#    except sqlite3.OperationalError:
#        c.execute('ALTER TABLE importresults ADD COLUMN MetaData_Present TEXT')

#    try:
#        c.execute('SELECT MetaData from importresults')
#    except sqlite3.OperationalError:
#        c.execute('ALTER TABLE importresults ADD COLUMN MetaData TEXT')

    #let's delete errant comics that are stranded (ie. Comicname = Comic ID: )
    c.execute("DELETE from comics WHERE ComicName='None' OR ComicName LIKE 'Comic ID%' OR ComicName is NULL")
    c.execute("DELETE from issues WHERE ComicName='None' OR ComicName LIKE 'Comic ID%' OR ComicName is NULL")
    c.execute("DELETE from issues WHERE ComicID is NULL")
    c.execute("DELETE from annuals WHERE ComicName='None' OR ComicName is NULL or Issue_Number is NULL")
    c.execute("DELETE from upcoming WHERE ComicName='None' OR ComicName is NULL or IssueNumber is NULL")
    c.execute("DELETE from importresults WHERE ComicName='None' OR ComicName is NULL")
    c.execute("DELETE from Failed WHERE ComicName='None' OR ComicName is NULL OR ID is NULL")
    logger.info('Ensuring DB integrity - Removing all Erroneous Comics (ie. named None)')

    logger.info('Correcting Null entries that make the main page break on startup.')
    c.execute("UPDATE Comics SET LatestDate='Unknown' WHERE LatestDate='None' or LatestDate is NULL")

    job_listing = c.execute('SELECT * FROM jobhistory')
    job_history = []
    for jh in job_listing:
        job_history.append(jh)

    #logger.fdebug('job_history loaded: %s' % job_history)
    conn.commit()
    c.close()

    if dynamic_upgrade is True:
        logger.info('Updating db to include some important changes.')
        helpers.upgrade_dynamic()

def csv_load():
    # for redudant module calls..include this.
    conn = sqlite3.connect(DB_FILE)
    c=conn.cursor()

    c.execute('DROP TABLE IF EXISTS exceptions')

    c.execute('CREATE TABLE IF NOT EXISTS exceptions (variloop TEXT, ComicID TEXT, NewComicID TEXT, GComicID TEXT)')

    # for Mylar-based Exception Updates....
    i = 0
    EXCEPTIONS = []
    EXCEPTIONS.append('exceptions.csv')
    EXCEPTIONS.append('custom_exceptions.csv')

    while (i <= 1):
    #EXCEPTIONS_FILE = os.path.join(DATA_DIR, 'exceptions.csv')
        EXCEPTIONS_FILE = os.path.join(DATA_DIR, EXCEPTIONS[i])

        if not os.path.exists(EXCEPTIONS_FILE):
            try:
                csvfile = open(str(EXCEPTIONS_FILE), "rb")
            except (OSError, IOError):
                if i == 1:
                    logger.info('No Custom Exceptions found - Using base exceptions only. Creating blank custom_exceptions for your personal use.')
                    try:
                        shutil.copy(os.path.join(DATA_DIR, "custom_exceptions_sample.csv"), EXCEPTIONS_FILE)
                    except (OSError, IOError):
                        logger.error('Cannot create custom_exceptions.csv in ' + str(DATA_DIR) + '. Make sure _sample.csv is present and/or check permissions.')
                        return
                else:
                    logger.error('Could not locate ' + str(EXCEPTIONS[i]) + ' file. Make sure it is in datadir: ' + DATA_DIR)
                break
        else:
            csvfile = open(str(EXCEPTIONS_FILE), "rb")
        if i == 0:
            logger.info('Populating Base Exception listings into Mylar....')
        elif i == 1:
            logger.info('Populating Custom Exception listings into Mylar....')

        creader = csv.reader(csvfile, delimiter=',')

        for row in creader:
            try:
                #print row.split(',')
                c.execute("INSERT INTO exceptions VALUES (?,?,?,?)", row)
            except Exception, e:
                #print ("Error - invald arguments...-skipping")
                pass
        csvfile.close()
        i+=1

    conn.commit()
    c.close()

def halt():
    global _INITIALIZED, started

    with INIT_LOCK:

        if _INITIALIZED:

            logger.info('Shutting down the background schedulers...')
            SCHED.shutdown(wait=False)

            if NZBPOOL is not None:
                logger.info('Terminating the nzb auto-complete thread.')
                try:
                    NZBPOOL.join(10)
                    logger.info('Joined pool for termination -  successful')
                except KeyboardInterrupt:
                    NZB_QUEUE.put('exit')
                    NZBPOOL.join(5)
                except AssertionError:
                    os._exit(0)

            if SNPOOL is not None:
                logger.info('Terminating the auto-snatch thread.')
                try:
                    SNPOOL.join(10)
                    logger.info('Joined pool for termination -  successful')
                except KeyboardInterrupt:
                    SNATCHED_QUEUE.put('exit')
                    SNPOOL.join(5)
                except AssertionError:
                    os._exit(0)
            _INITIALIZED = False

def shutdown(restart=False, update=False):

    cherrypy.engine.exit()
    halt()

    if not restart and not update:
        logger.info('Mylar is shutting down...')
    if update:
        logger.info('Mylar is updating...')
        try:
            versioncheck.update()
        except Exception as e:
            logger.warn('Mylar failed to update: %s. Restarting.' % e)

    if CREATEPID:
        logger.info('Removing pidfile %s' % PIDFILE)
        os.remove(PIDFILE)

    if restart:
        logger.info('Mylar is restarting...')
        popen_list = [sys.executable, FULL_PATH]
        popen_list += ARGS
#        if '--nolaunch' not in popen_list:
#            popen_list += ['--nolaunch']
        logger.info('Restarting Mylar with ' + str(popen_list))
        subprocess.Popen(popen_list, cwd=os.getcwd())

    os._exit(0)
