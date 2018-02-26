import itertools
from collections import OrderedDict
from operator import itemgetter

import os
import codecs
import shutil
import re
import ConfigParser
import mylar
from mylar import logger, helpers

config = ConfigParser.SafeConfigParser()

_CONFIG_DEFINITIONS = OrderedDict({
     #keyname, type, section, default
    'CONFIG_VERSION': (int, 'General', 6),
    'MINIMAL_INI': (bool, 'General', False),
    'OLDCONFIG_VERSION': (str, 'General', None),
    'AUTO_UPDATE': (bool, 'General', False),
    'CACHE_DIR': (str, 'General', None),
    'DYNAMIC_UPDATE': (int, 'General', 0),
    'REFRESH_CACHE': (int, 'General', 7),
    'ANNUALS_ON': (bool, 'General', False),
    'SYNO_FIX': (bool, 'General', False),
    'LAUNCH_BROWSER' : (bool, 'General', False),
    'WANTED_TAB_OFF': (bool, 'General', False),
    'ENABLE_RSS': (bool, 'General', False),
    'SEARCH_DELAY' : (int, 'General', 1),
    'GRABBAG_DIR': (str, 'General', None),
    'HIGHCOUNT': (int, 'General', 0),
    'MAINTAINSERIESFOLDER': (bool, 'General', False),
    'DESTINATION_DIR': (str, 'General', None),   #if M_D_D_ is enabled, this will be the DEFAULT for writing
    'MULTIPLE_DEST_DIRS': (str, 'General', None), #Nothing will ever get written to these dirs - just for scanning, unless it's metatagging/renaming.
    'CREATE_FOLDERS': (bool, 'General', True),
    'DELETE_REMOVE_DIR': (bool, 'General', False),
    'UPCOMING_SNATCHED': (bool, 'General', True),
    'UPDATE_ENDED': (bool, 'General', False),
    'LOCMOVE': (bool, 'General', False),
    'NEWCOM_DIR': (str, 'General', None),
    'FFTONEWCOM_DIR': (bool, 'General', False),
    'FOLDER_SCAN_LOG_VERBOSE': (bool, 'General', False),
    'INTERFACE': (str, 'General', 'default'),
    'CORRECT_METADATA': (bool, 'General', False),
    'MOVE_FILES': (bool, 'General', False),
    'RENAME_FILES': (bool, 'General', False),
    'FOLDER_FORMAT': (str, 'General', '$Series ($Year)'),
    'FILE_FORMAT': (str, 'General', '$Series $Annual $Issue ($Year)'),
    'REPLACE_SPACES': (bool, 'General', False),
    'REPLACE_CHAR': (str, 'General', None),
    'ZERO_LEVEL': (bool, 'General', False),
    'ZERO_LEVEL_N': (str, 'General', None),
    'LOWERCASE_FILENAMES': (bool, 'General', False),
    'IGNORE_HAVETOTAL': (bool, 'General', False),
    'SNATCHED_HAVETOTAL': (bool, 'General', False),
    'FAILED_DOWNLOAD_HANDLING': (bool, 'General', False),
    'FAILED_AUTO': (bool, 'General',False),
    'PREFERRED_QUALITY': (int, 'General', 0),
    'USE_MINSIZE': (bool, 'General', False),
    'MINSIZE': (str, 'General', None),
    'USE_MAXSIZE': (bool, 'General', False),
    'MAXSIZE': (str, 'General', None),
    'AUTOWANT_UPCOMING': (bool, 'General', True),
    'AUTOWANT_ALL': (bool, 'General', False),
    'COMIC_COVER_LOCAL': (bool, 'General', False),
    'ADD_TO_CSV': (bool, 'General', True),
    'SKIPPED2WANTED': (bool, 'General', False),
    'READ2FILENAME': (bool, 'General', False),
    'SEND2READ': (bool, 'General', False),
    'NZB_STARTUP_SEARCH': (bool, 'General', False),
    'UNICODE_ISSUENUMBER': (bool, 'General', False),
    'CREATE_FOLDERS': (bool, 'General', True),

    'RSS_CHECKINTERVAL': (int, 'Scheduler', 20),
    'SEARCH_INTERVAL': (int, 'Scheduler', 360),
    'DOWNLOAD_SCAN_INTERVAL': (int, 'Scheduler', 5),
    'CHECK_GITHUB_INTERVAL' : (int, 'Scheduler', 360),

    'ALT_PULL' : (int, 'Weekly', 2),
    'PULL_REFRESH': (str, 'Weekly', None),
    'WEEKFOLDER': (bool, 'Weekly', False),
    'WEEKFOLDER_LOC': (str, 'Weekly', None),
    'WEEKFOLDER_FORMAT': (int, 'Weekly', 0),
    'INDIE_PUB': (int, 'Weekly', 75),
    'BIGGIE_PUB': (int, 'Weekly', 55),

    'HTTP_PORT' : (int, 'Interface', 8090),
    'HTTP_HOST' : (str, 'Interface', '0.0.0.0'),
    'HTTP_USERNAME' : (str, 'Interface', None),
    'HTTP_PASSWORD' : (str, 'Interface', None),
    'HTTP_ROOT' : (str, 'Interface', '/'),
    'ENABLE_HTTPS' : (bool, 'Interface', False),
    'HTTPS_CERT' : (str, 'Interface', None),
    'HTTPS_KEY' : (str, 'Interface', None),
    'HTTPS_CHAIN' : (str, 'Interface', None),
    'HTTPS_FORCE_ON' : (bool, 'Interface', False),
    'HOST_RETURN' : (str, 'Interface', None),
    'AUTHENTICATION' : (int, 'Interface', 0),
    'LOGIN_TIMEOUT': (int, 'Interface', 43800),

    'API_ENABLED' : (bool, 'API', False),
    'API_KEY' : (str, 'API', None),

    'CVAPI_RATE' : (int, 'CV', 2),
    'COMICVINE_API': (str, 'CV', None),
    'BLACKLISTED_PUBLISHERS' : (str, 'CV', None),
    'CV_VERIFY': (bool, 'CV', True),
    'CV_ONLY': (bool, 'CV', True),
    'CV_ONETIMER': (bool, 'CV', True),
    'CVINFO': (bool, 'CV', False),

    'LOG_DIR' : (str, 'Logs', None),
    'MAX_LOGSIZE' : (int, 'Logs', 10000000),
    'LOG_LEVEL': (int, 'Logs', 0),

    'GIT_PATH' : (str, 'Git', None),
    'GIT_USER' : (str, 'Git', 'evilhero'),
    'GIT_BRANCH' : (str, 'Git', None),
    'CHECK_GITHUB' : (bool, 'Git', False),
    'CHECK_GITHUB_ON_STARTUP' : (bool, 'Git', False),

    'ENFORCE_PERMS': (bool, 'Perms', True),
    'CHMOD_DIR': (str, 'Perms', '0777'),
    'CHMOD_FILE': (str, 'Perms', '0660'),
    'CHOWNER': (str, 'Perms', None),
    'CHGROUP': (str, 'Perms', None),

    'ADD_COMICS': (bool, 'Import', False),
    'COMIC_DIR': (str, 'Import', None),
    'IMP_MOVE': (bool, 'Import', False),
    'IMP_RENAME': (bool, 'Import', False),
    'IMP_METADATA': (bool, 'Import', False),  # should default to False - this is enabled for testing only.

    'DUPECONSTRAINT': (str, 'Duplicates', None),
    'DDUMP': (bool, 'Duplicates', False),
    'DUPLICATE_DUMP': (str, 'Duplicates', None),

    'PROWL_ENABLED': (bool, 'Prowl', False),
    'PROWL_PRIORITY': (int, 'Prowl', 0),
    'PROWL_KEYS': (str, 'Prowl', None),
    'PROWL_ONSNATCH': (bool, 'Prowl', False),

    'NMA_ENABLED': (bool, 'NMA', False),
    'NMA_APIKEY': (str, 'NMA', None),
    'NMA_PRIORITY': (int, 'NMA', 0),
    'NMA_ONSNATCH': (bool, 'NMA', False),

    'PUSHOVER_ENABLED': (bool, 'PUSHOVER', False),
    'PUSHOVER_PRIORITY': (int, 'PUSHOVER', 0),
    'PUSHOVER_APIKEY': (str, 'PUSHOVER', None),
    'PUSHOVER_USERKEY': (str, 'PUSHOVER', None),
    'PUSHOVER_ONSNATCH': (bool, 'PUSHOVER', False),

    'BOXCAR_ENABLED': (bool, 'BOXCAR', False),
    'BOXCAR_ONSNATCH': (bool, 'BOXCAR', False),
    'BOXCAR_TOKEN': (str, 'BOXCAR', None),

    'PUSHBULLET_ENABLED': (bool, 'PUSHBULLET', False),
    'PUSHBULLET_APIKEY': (str, 'PUSHBULLET', None),
    'PUSHBULLET_DEVICEID': (str, 'PUSHBULLET', None),
    'PUSHBULLET_CHANNEL_TAG': (str, 'PUSHBULLET', None),
    'PUSHBULLET_ONSNATCH': (bool, 'PUSHBULLET', False),

    'TELEGRAM_ENABLED': (bool, 'TELEGRAM', False),
    'TELEGRAM_TOKEN': (str, 'TELEGRAM', None),
    'TELEGRAM_USERID': (str, 'TELEGRAM', None),
    'TELEGRAM_ONSNATCH': (bool, 'TELEGRAM', False),

    'SLACK_ENABLED': (bool, 'SLACK', False),
    'SLACK_WEBHOOK_URL': (str, 'SLACK', None),
    'SLACK_ONSNATCH': (bool, 'SLACK', False),

    'POST_PROCESSING': (bool, 'PostProcess', False),
    'FILE_OPTS': (str, 'PostProcess', 'move'),
    'SNATCHEDTORRENT_NOTIFY': (bool, 'PostProcess', False),
    'LOCAL_TORRENT_PP': (bool, 'PostProcess', False),
    'POST_PROCESSING_SCRIPT': (str, 'PostProcess', None),
    'ENABLE_EXTRA_SCRIPTS': (bool, 'PostProcess', False),
    'EXTRA_SCRIPTS': (str, 'PostProcess', None),
    'ENABLE_SNATCH_SCRIPT': (bool, 'PostProcess', False),
    'SNATCH_SCRIPT': (str, 'PostProcess', None),
    'ENABLE_PRE_SCRIPTS': (bool, 'PostProcess', False),
    'PRE_SCRIPTS': (str, 'PostProcess', None),
    'ENABLE_CHECK_FOLDER':  (bool, 'PostProcess', False),
    'CHECK_FOLDER': (str, 'PostProcess', None),

    'PROVIDER_ORDER': (str, 'Providers', None),
    'USENET_RETENTION': (int, 'Providers', 1500),

    'NZB_DOWNLOADER': (int, 'Client', 0),  #0': sabnzbd, #1': nzbget, #2': blackhole
    'TORRENT_DOWNLOADER': (int, 'Client', 0),  #0': watchfolder, #1': uTorrent, #2': rTorrent, #3': transmission, #4': deluge, #5': qbittorrent

    'SAB_HOST': (str, 'SABnzbd', None),
    'SAB_USERNAME': (str, 'SABnzbd', None),
    'SAB_PASSWORD': (str, 'SABnzbd', None),
    'SAB_APIKEY': (str, 'SABnzbd', None),
    'SAB_CATEGORY': (str, 'SABnzbd', None),
    'SAB_PRIORITY': (str, 'SABnzbd', "Default"),
    'SAB_TO_MYLAR': (bool, 'SABnzbd', False),
    'SAB_DIRECTORY': (str, 'SABnzbd', None),
    'SAB_CLIENT_POST_PROCESSING': (bool, 'SABnzbd', False),   #0/False: ComicRN.py, #1/True: Completed Download Handling

    'NZBGET_HOST': (str, 'NZBGet', None),
    'NZBGET_PORT': (str, 'NZBGet', None),
    'NZBGET_USERNAME': (str, 'NZBGet', None),
    'NZBGET_PASSWORD': (str, 'NZBGet', None),
    'NZBGET_PRIORITY': (str, 'NZBGet', None),
    'NZBGET_CATEGORY': (str, 'NZBGet', None),
    'NZBGET_DIRECTORY': (str, 'NZBGet', None),
    'NZBGET_CLIENT_POST_PROCESSING': (bool, 'NZBGet', False),   #0/False: ComicRN.py, #1/True: Completed Download Handling

    'BLACKHOLE_DIR': (str, 'Blackhole', None),

    'ENABLE_TPSE': (bool, 'TPSE', False),
    'TPSE_PROXY': (str, 'TPSE', None),
    'TPSE_VERIFY': (bool, 'TPSE', True),

    'NZBSU': (bool, 'NZBsu', False),
    'NZBSU_UID': (str, 'NZBsu', None),
    'NZBSU_APIKEY': (str, 'NZBsu', None),
    'NZBSU_VERIFY': (bool, 'NZBsu', True),

    'DOGNZB': (bool, 'DOGnzb', False),
    'DOGNZB_APIKEY': (str, 'DOGnzb', None),
    'DOGNZB_VERIFY': (bool, 'DOGnzb', True),

    'NEWZNAB': (bool, 'Newznab', False),
    'EXTRA_NEWZNABS': (str, 'Newznab', ""),

    'ENABLE_TORZNAB': (bool, 'Torznab', False),
    'TORZNAB_NAME': (str, 'Torznab', None),
    'TORZNAB_HOST': (str, 'Torznab', None),
    'TORZNAB_APIKEY': (str, 'Torznab', None),
    'TORZNAB_CATEGORY': (str, 'Torznab', None),
    'TORZNAB_VERIFY': (bool, 'Torznab', False),

    'EXPERIMENTAL': (bool, 'Experimental', False),
    'ALTEXPERIMENTAL': (bool, 'Experimental', False),

    'TAB_ENABLE': (bool, 'Tablet', False),
    'TAB_HOST': (str, 'Tablet', None),
    'TAB_USER': (str, 'Tablet', None),
    'TAB_PASS': (str, 'Tablet', None),
    'TAB_DIRECTORY': (str, 'Tablet', None),

    'STORYARCDIR': (bool, 'StoryArc', False),
    'COPY2ARCDIR': (bool, 'StoryArc', False),
    'ARC_FOLDERFORMAT': (str, 'StoryArc', None),
    'ARC_FILEOPS': (str, 'StoryArc', 'copy'),

    'LOCMOVE': (bool, 'Update', False),
    'NEWCOM_DIR': (str, 'Update', None),
    'FFTONEWCOM_DIR': (bool, 'Update', False),

    'ENABLE_META': (bool, 'Metatagging', False),
    'CMTAGGER_PATH': (str, 'Metatagging', None),
    'CBR2CBZ_ONLY': (bool, 'Metatagging', False),
    'CT_TAG_CR': (bool, 'Metatagging', True),
    'CT_TAG_CBL': (bool, 'Metatagging', True),
    'CT_CBZ_OVERWRITE': (bool, 'Metatagging', False),
    'UNRAR_CMD': (str, 'Metatagging', None),
    'CT_SETTINGSPATH': (str, 'Metatagging', None),
    'CMTAG_VOLUME': (bool, 'Metatagging', True),
    'CMTAG_START_YEAR_AS_VOLUME': (bool, 'Metatagging', False),
    'SETDEFAULTVOLUME': (bool, 'Metatagging', False),

    'ENABLE_TORRENTS': (bool, 'Torrents', False),
    'ENABLE_TORRENT_SEARCH': (bool, 'Torrents', False),
    'MINSEEDS': (int, 'Torrents', 0),
    'ALLOW_PACKS': (bool, 'Torrents', False),

    'AUTO_SNATCH': (bool, 'AutoSnatch', False),
    'AUTO_SNATCH_SCRIPT': (str, 'AutoSnatch', None),
    'PP_SSHHOST': (str, 'AutoSnatch', None),
    'PP_SSHPORT': (str, 'AutoSnatch', 22),
    'PP_SSHUSER': (str, 'AutoSnatch', None),
    'PP_SSHPASSWD': (str, 'AutoSnatch', None),
    'PP_SSHLOCALCD': (str, 'AutoSnatch', None),
    'PP_SSHKEYFILE': (str, 'AutoSnatch', None),

    'TORRENT_LOCAL': (bool, 'Watchdir', False),
    'LOCAL_WATCHDIR': (str, 'Watchdir', None),
    'TORRENT_SEEDBOX': (bool, 'Seedbox', False),
    'SEEDBOX_HOST': (str, 'Seedbox', None),
    'SEEDBOX_PORT': (str, 'Seedbox', None),
    'SEEDBOX_USER': (str, 'Seedbox', None),
    'SEEDBOX_PASS': (str, 'Seedbox', None),
    'SEEDBOX_WATCHDIR': (str, 'Seedbox', None),

    'ENABLE_32P': (bool, '32P', False),
    'SEARCH_32P': (bool, '32P', False),   #0': use WS to grab torrent groupings, #1': use 32P to grab torrent groupings
    'DEEP_SEARCH_32P': (bool, '32P', False),  #0': do not take multiple search series results & use ref32p if available, #1=  search each search series result for valid $
    'MODE_32P': (bool, '32P', False),  #0': legacymode, #1': authmode
    'RSSFEED_32P': (str, '32P', None),
    'PASSKEY_32P': (str, '32P', None),
    'USERNAME_32P': (str, '32P', None),
    'PASSWORD_32P': (str, '32P', None),
    'VERIFY_32P': (bool, '32P', True),

    'RTORRENT_HOST': (str, 'Rtorrent', None),
    'RTORRENT_AUTHENTICATION': (str, 'Rtorrent', 'basic'),
    'RTORRENT_RPC_URL': (str, 'Rtorrent', None),
    'RTORRENT_SSL': (bool, 'Rtorrent', False),
    'RTORRENT_VERIFY': (bool, 'Rtorrent', False),
    'RTORRENT_CA_BUNDLE': (str, 'Rtorrent', None),
    'RTORRENT_USERNAME': (str, 'Rtorrent', None),
    'RTORRENT_PASSWORD': (str, 'Rtorrent', None),
    'RTORRENT_STARTONLOAD': (bool, 'Rtorrent', False),
    'RTORRENT_LABEL': (str, 'Rtorrent', None),
    'RTORRENT_DIRECTORY': (str, 'Rtorrent', None),

    'UTORRENT_HOST': (str, 'uTorrent', None),
    'UTORRENT_USERNAME': (str, 'uTorrent', None),
    'UTORRENT_PASSWORD': (str, 'uTorrent', None),
    'UTORRENT_LABEL': (str, 'uTorrent', None),

    'TRANSMISSION_HOST': (str, 'Transmission', None),
    'TRANSMISSION_USERNAME': (str, 'Transmission', None),
    'TRANSMISSION_PASSWORD': (str, 'Transmission', None),
    'TRANSMISSION_DIRECTORY': (str, 'Transmission', None),

    'DELUGE_HOST': (str, 'Deluge', None),
    'DELUGE_USERNAME': (str, 'Deluge', None),
    'DELUGE_PASSWORD': (str, 'Deluge', None),
    'DELUGE_LABEL': (str, 'Deluge', None),

    'QBITTORRENT_HOST': (str, 'qBittorrent', None),
    'QBITTORRENT_USERNAME': (str, 'qBittorrent', None),
    'QBITTORRENT_PASSWORD': (str, 'qBittorrent', None),
    'QBITTORRENT_LABEL': (str, 'qBittorrent', None),
    'QBITTORRENT_FOLDER': (str, 'qBittorrent', None),
    'QBITTORRENT_STARTONLOAD': (bool, 'qBittorrent', False),

    'OPDS_ENABLE': (bool, 'OPDS', False),
    'OPDS_AUTHENTICATION': (bool, 'OPDS', False),
    'OPDS_USERNAME': (str, 'OPDS', None),
    'OPDS_PASSWORD': (str, 'OPDS', None),
    'OPDS_METAINFO': (bool, 'OPDS', False),

})

_BAD_DEFINITIONS = OrderedDict({
     #for those items that were in wrong sections previously, or sections that are no longer present...
     #using this method, old values are able to be transfered to the new config items properly.
     #keyname, section, oldkeyname
     #ie. 'TEST_VALUE': ('TEST', 'TESTVALUE')
    'SAB_CLIENT_POST_PROCESSING': ('SABnbzd', None),
})

class Config(object):

    def __init__(self, config_file):
        # initalize the config...
        self._config_file = config_file

    def config_vals(self, update=False):
        if update is False:
            if os.path.isfile(self._config_file):
                self.config = config.readfp(codecs.open(self._config_file, 'r', 'utf8')) #read(self._config_file)
                #check for empty config / new config
                count = sum(1 for line in open(self._config_file))
            else:
                count = 0
            self.newconfig = 7
            if count == 0:
                CONFIG_VERSION = 0
                MINIMALINI = False
            else:
                # get the config version first, since we need to know.
                try:
                    CONFIG_VERSION = config.getint('General', 'config_version')
                except:
                    CONFIG_VERSION = 0
                try:
                    MINIMALINI = config.getboolean('General', 'minimal_ini')
                except:
                    MINIMALINI = False

        setattr(self, 'CONFIG_VERSION', CONFIG_VERSION)
        setattr(self, 'MINIMAL_INI', MINIMALINI)

        config_values = []
        for k,v in _CONFIG_DEFINITIONS.iteritems():
            xv = []
            xv.append(k)
            for x in v:
                if x is None:
                    x = 'None'
                xv.append(x)
            value = self.check_setting(xv)

            for b, bv in _BAD_DEFINITIONS.iteritems():
                try:
                    if config.has_section(bv[0]) and any([b == k, bv[1] is None]):
                        cvs = xv
                        if bv[1] is None:
                            ckey = k
                        else:
                            ckey = bv[1]
                        corevalues = [ckey if x == 0 else x for x in cvs]
                        corevalues = [bv[0] if x == corevalues.index(bv[0]) else x for x in cvs]
                        value = self.check_setting(corevalues)
                        if bv[1] is None:
                            config.remove_option(bv[0], ckey.lower())
                            config.remove_section(bv[0])
                        else:
                            config.remove_option(bv[0], bv[1].lower())
                        break
                except:
                    pass

            if all([k != 'CONFIG_VERSION', k != 'MINIMAL_INI']):
                try:
                    if v[0] == str and any([value == "", value is None, len(value) == 0, value == 'None']):
                        value = v[2]
                except:
                    value = v[2]

                try:
                    if v[0] == bool:
                        value = self.argToBool(value)
                except:
                    value = self.argToBool(v[2])
                try:

                    if all([v[0] == int, str(value).isdigit()]):
                        value = int(value)
                except:
                    value = v[2]

                setattr(self, k, value)

                try:
                    #make sure interpolation isn't being used, so we can just escape the % character
                    if v[0] == str:
                        value = value.replace('%', '%%')
                except Exception as e:
                    pass

                #just to ensure defaults are properly set...
                if any([value is None, value == 'None']):
                    value = v[0](v[2])

                if all([self.MINIMAL_INI is True, str(value) != str(v[2])]) or self.MINIMAL_INI is False:
                    try:
                        config.add_section(v[1])
                    except ConfigParser.DuplicateSectionError:
                        pass
                else:
                    try:
                        if config.has_section(v[1]):
                            config.remove_option(v[1], k.lower())
                    except ConfigParser.NoSectionError:
                        continue

                if all([config.has_section(v[1]), self.MINIMAL_INI is False]) or all([self.MINIMAL_INI is True, str(value) != str(v[2]), config.has_section(v[1])]):
                    config.set(v[1], k.lower(), str(value))
                else:
                    try:
                        if config.has_section(v[1]):
                            config.remove_option(v[1], k.lower())
                        if len(dict(config.items(v[1]))) == 0:
                            config.remove_section(v[1])
                    except ConfigParser.NoSectionError:
                        continue
            else:
                if k == 'CONFIG_VERSION':
                    config.remove_option('General', 'dbuser')
                    config.remove_option('General', 'dbpass')
                    config.remove_option('General', 'dbchoice')
                    config.remove_option('General', 'dbname')
                elif k == 'MINIMAL_INI':
                    config.set(v[1], k.lower(), str(self.MINIMAL_INI))

    def read(self):
        self.config_vals()
        setattr(self, 'EXTRA_NEWZNABS', self.get_extra_newznabs())
        if any([self.CONFIG_VERSION == 0, self.CONFIG_VERSION < self.newconfig]):
            try:
                shutil.move(self._config_file, os.path.join(mylar.DATA_DIR, 'config.ini.backup'))
            except:
                logger.warn('Unable to make proper backup of config file in %s' % os.path.join(mylar.DATA_DIR, 'config.ini.backup'))
            setattr(self, 'CONFIG_VERSION', str(self.newconfig))
            config.set('General', 'CONFIG_VERSION', str(self.newconfig))
            print('Updating config to newest version : %s' % self.newconfig)
            self.writeconfig()
        else:
            self.provider_sequence()
        self.configure()
        return self

    def check_section(self, section, key):
        """ Check if INI section exists, if not create it """
        if config.has_section(section):
            return True
        else:
            return False

    def argToBool(self, argument):
        _arg = argument.strip().lower() if isinstance(argument, basestring) else argument
        if _arg in (1, '1', 'on', 'true', True):
            return True
        elif _arg in (0, '0', 'off', 'false', False):
            return False
        return argument

    def check_setting(self, key):
        """ Cast any value in the config to the right type or use the default """
        keyname = key[0].upper()
        inikey = key[0].lower()
        definition_type = key[1]
        section = key[2]
        default = key[3]
        myval = self.check_config(definition_type, section, inikey, default)
        if myval['status'] is False:
            if self.CONFIG_VERSION == 6 or (config.has_section('Torrents') and any([inikey == 'auto_snatch', inikey == 'auto_snatch_script'])):
                chkstatus = False
                if config.has_section('Torrents'):
                    myval = self.check_config(definition_type, 'Torrents', inikey, default)
                    if myval['status'] is True:
                        chkstatus = True
                        try:
                            config.remove_option('Torrents', inikey)
                        except ConfigParser.NoSectionError:
                            pass
                if all([chkstatus is False, config.has_section('General')]):
                    myval = self.check_config(definition_type, 'General', inikey, default)
                    if myval['status'] is True:
                        config.remove_option('General', inikey)

                    else:
                        #print 'no key found in ini - setting to default value of %s' % definition_type(default)
                        #myval = {'value': definition_type(default)}
                        pass
            else:
                myval = {'value': definition_type(default)}
        #if all([myval['value'] is not None, myval['value'] != '', myval['value'] != 'None']):
           #if default != myval['value']:
           #    print '%s : %s' % (keyname, myval['value'])
           #else:
           #    print 'NEW CONFIGURATION SETTING %s : %s' % (keyname, myval['value'])
        return myval['value']

    def check_config(self, definition_type, section, inikey, default):
        try:
            if definition_type == str:
                myval = {'status': True, 'value': config.get(section, inikey)}
            elif definition_type == int:
                myval = {'status': True, 'value': config.getint(section, inikey)}
            elif definition_type == bool:
                myval = {'status': True, 'value': config.getboolean(section, inikey)}
        except Exception:
            if definition_type == str:
                try:
                    myval = {'status': True, 'value': config.get(section, inikey, raw=True)}
                except (ConfigParser.NoSectionError, ConfigParser.NoOptionError):
                    myval = {'status': False, 'value': None}
            else:
                myval = {'status': False, 'value': None}
        return myval

    def _define(self, name):
        key = name.upper()
        ini_key = name.lower()
        definition = _CONFIG_DEFINITIONS[key]
        if len(definition) == 3:
            definition_type, section, default = definition
        elif len(definition) == 4:
            definition_type, section, _, default = definition
        return key, definition_type, section, ini_key, default


    def process_kwargs(self, kwargs):
        """
        Given a big bunch of key value pairs, apply them to the ini.
        """
        for name, value in kwargs.items():
            if not any([(name.startswith('newznab') and name[-1].isdigit()), name.startswith('Torznab')]):
                key, definition_type, section, ini_key, default = self._define(name)
                try:
                    if any([value == "", value is None, len(value) == 0]) and definition_type == str:
                        value = default
                    else:
                        value = str(value)
                except:
                    value = default
                try:
                    if definition_type == bool:
                        value = self.argToBool(value)
                except:
                    value = self.argToBool(default)
                try:
                    if all([definition_type == int, str(value).isdigit()]):
                        value = int(value)
                except:
                    value = default

                #just to ensure defaults are properly set...
                if any([value is None, value == 'None']):
                    value = definition_type(default)

                if key != 'MINIMAL_INI':
                    if value == 'None': nv = None
                    else: nv = definition_type(value)
                    setattr(self, key, nv)

                    #print('writing config value...[%s][%s] key: %s / ini_key: %s / value: %s [%s]' % (definition_type, section, key, ini_key, value, default))
                    if all([self.MINIMAL_INI is True, definition_type(value) != definition_type(default)]) or self.MINIMAL_INI is False:
                        try:
                            config.add_section(section)
                        except ConfigParser.DuplicateSectionError:
                            pass
                    else:
                        try:
                            if config.has_section(section):
                                config.remove_option(section, ini_key)
                            if len(dict(config.items(section))) == 0:
                                config.remove_section(section) 
                        except ConfigParser.NoSectionError:
                            continue

                    if any([value is None, value == ""]):
                        value = definition_type(default)
                    if config.has_section(section) and (all([self.MINIMAL_INI is True, definition_type(value) != definition_type(default)]) or self.MINIMAL_INI is False):
                        try:
                            if definition_type == str:
                                value = value.replace('%', '%%')
                        except Exception as e:
                            pass
                        config.set(section, ini_key, str(value))
                else:
                    config.set(section, ini_key, str(self.MINIMAL_INI))

            else:
                pass

    def writeconfig(self):
        logger.fdebug("Writing configuration to file")
        self.provider_sequence()
        config.set('Newznab', 'extra_newznabs', ', '.join(self.write_extras(self.EXTRA_NEWZNABS)))
        ###this should be moved elsewhere...
        if type(self.BLACKLISTED_PUBLISHERS) != list:
            if self.BLACKLISTED_PUBLISHERS is None:
                bp = 'None'
            else:
                bp = ', '.join(self.write_extras(self.BLACKLISTED_PUBLISHERS))
            config.set('CV', 'blacklisted_publishers', bp)
        else:
            config.set('CV', 'blacklisted_publishers', ', '.join(self.BLACKLISTED_PUBLISHERS))
        ###
        config.set('General', 'dynamic_update', str(self.DYNAMIC_UPDATE))
        try:
            with codecs.open(self._config_file, encoding='utf8', mode='w+') as configfile:
                config.write(configfile)
            logger.fdebug('Configuration written to disk.')
        except IOError as e:
            logger.warn("Error writing configuration file: %s", e)

    def configure(self, update=False):
        try:
            if not any([self.SAB_HOST is None, self.SAB_HOST == '', 'http://' in self.SAB_HOST[:7], 'https://' in self.SAB_HOST[:8]]):
                self.SAB_HOST = 'http://' + self.SAB_HOST
            if self.SAB_HOST.endswith('/'):
                logger.fdebug("Auto-correcting trailing slash in SABnzbd url (not required)")
                self.SAB_HOST = self.SAB_HOST[:-1]
        except:
            pass

        if any([self.HTTP_ROOT is None, self.HTTP_ROOT == '/']):
            self.HTTP_ROOT = '/'
        else:
            if not self.HTTP_ROOT.endswith('/'):
                self.HTTP_ROOT += '/'

        if not update:
           logger.fdebug('Log dir: %s' % self.LOG_DIR)

        if self.LOG_DIR is None:
            self.LOG_DIR = os.path.join(mylar.DATA_DIR, 'logs')

        if not os.path.exists(self.LOG_DIR):
            try:
                os.makedirs(self.LOG_DIR)
            except OSError:
                if not mylar.QUIET:
                    logger.warn('Unable to create the log directory. Logging to screen only.')

        # if not update:
        #     logger.fdebug('[Cache Check] Cache directory currently set to : ' + self.CACHE_DIR)

        # Put the cache dir in the data dir for now
        if not self.CACHE_DIR:
            self.CACHE_DIR = os.path.join(str(mylar.DATA_DIR), 'cache')
            if not update:
                logger.fdebug('[Cache Check] Cache directory not found in configuration. Defaulting location to : ' + self.CACHE_DIR)

        if not os.path.exists(self.CACHE_DIR):
            try:
               os.makedirs(self.CACHE_DIR)
            except OSError:
                logger.error('[Cache Check] Could not create cache dir. Check permissions of datadir: ' + mylar.DATA_DIR)

        ## Sanity checking
        if any([self.COMICVINE_API is None, self.COMICVINE_API == 'None', self.COMICVINE_API == '']):
            logger.error('No User Comicvine API key specified. I will not work very well due to api limits - http://api.comicvine.com/ and get your own free key.')
            self.COMICVINE_API = None

        if self.SEARCH_INTERVAL < 360:
            logger.fdebug('Search interval too low. Resetting to 6 hour minimum')
            self.SEARCH_INTERVAL = 360

        if self.SEARCH_DELAY < 1:
            logger.fdebug("Minimum search delay set for 1 minute to avoid hammering.")
            self.SEARCH_DELAY = 1

        if self.RSS_CHECKINTERVAL < 20:
            logger.fdebug("Minimum RSS Interval Check delay set for 20 minutes to avoid hammering.")
            self.RSS_CHECKINTERVAL = 20

        if not helpers.is_number(self.CHMOD_DIR):
            logger.fdebug("CHMOD Directory value is not a valid numeric - please correct. Defaulting to 0777")
            self.CHMOD_DIR = '0777'

        if not helpers.is_number(self.CHMOD_FILE):
            logger.fdebug("CHMOD File value is not a valid numeric - please correct. Defaulting to 0660")
            self.CHMOD_FILE = '0660'

        if self.FILE_OPTS is None:
            self.FILE_OPTS = 'move'

        if any([self.FILE_OPTS == 'hardlink', self.FILE_OPTS == 'softlink']):
            #we can't have metatagging enabled with hard/soft linking. Forcibly disable it here just in case it's set on load.
            self.ENABLE_META = False

        if self.BLACKLISTED_PUBLISHERS is not None and type(self.BLACKLISTED_PUBLISHERS) == unicode:
            setattr(self, 'BLACKLISTED_PUBLISHERS', self.BLACKLISTED_PUBLISHERS.split(', '))

        if all([self.AUTHENTICATION == 0, self.HTTP_USERNAME is not None, self.HTTP_PASSWORD is not None]):
            #set it to the default login prompt if nothing selected.
            self.AUTHENTICATION = 1
        elif all([self.HTTP_USERNAME is None, self.HTTP_PASSWORD is None]):
            self.AUTHENTICATION = 0

        #comictagger - force to use included version if option is enabled.
        if self.ENABLE_META:
            mylar.CMTAGGER_PATH = mylar.PROG_DIR
            #we need to make sure the default folder setting for the comictagger settings exists so things don't error out
            mylar.CT_SETTINGSPATH = os.path.join(mylar.PROG_DIR, 'lib', 'comictaggerlib', 'ct_settings')
            if not update:
                logger.fdebug('Setting ComicTagger settings default path to : ' + mylar.CT_SETTINGSPATH)

            if not os.path.exists(mylar.CT_SETTINGSPATH):
                try:
                    os.mkdir(mylar.CT_SETTINGSPATH)
                except OSError,e:
                    if e.errno != errno.EEXIST:
                        logger.error('Unable to create setting directory for ComicTagger. This WILL cause problems when tagging.')
                else:
                    logger.fdebug('Successfully created ComicTagger Settings location.')

        if self.MODE_32P is False and self.RSSFEED_32P is not None:
            mylar.KEYS_32P = self.parse_32pfeed(self.RSSFEED_32P)

        if self.AUTO_SNATCH is True and self.AUTO_SNATCH_SCRIPT is None:
            setattr(self, 'AUTO_SNATCH_SCRIPT', os.path.join(mylar.PROG_DIR, 'post-processing', 'torrent-auto-snatch', 'getlftp.sh'))
            config.set('AutoSnatch', 'auto_snatch_script', self.AUTO_SNATCH_SCRIPT)
        mylar.USE_SABNZBD = False
        mylar.USE_NZBGET = False
        mylar.USE_BLACKHOLE = False

        if self.NZB_DOWNLOADER == 0:
            mylar.USE_SABNZBD = True
        elif self.NZB_DOWNLOADER == 1:
            mylar.USE_NZBGET = True
        elif self.NZB_DOWNLOADER == 2:
            mylar.USE_BLACKHOLE = True
        else:
            #default to SABnzbd
            self.NZB_DOWNLOADER = 0
            mylar.USE_SABNZBD = True

        if self.SAB_PRIORITY.isdigit():
            if self.SAB_PRIORITY == "0": self.SAB_PRIORITY = "Default"
            elif self.SAB_PRIORITY == "1": self.SAB_PRIORITY = "Low"
            elif self.SAB_PRIORITY == "2": self.SAB_PRIORITY = "Normal"
            elif self.SAB_PRIORITY == "3": self.SAB_PRIORITY = "High"
            elif self.SAB_PRIORITY == "4": self.SAB_PRIORITY = "Paused"
            else: self.SAB_PRIORITY = "Default"

        mylar.USE_WATCHDIR = False
        mylar.USE_UTORRENT = False
        mylar.USE_RTORRENT = False
        mylar.USE_TRANSMISSION = False
        mylar.USE_DELUGE = False
        mylar.USE_QBITTORRENT = False
        if self.TORRENT_DOWNLOADER == 0:
            mylar.USE_WATCHDIR = True
        elif self.TORRENT_DOWNLOADER == 1:
            mylar.USE_UTORRENT = True
        elif self.TORRENT_DOWNLOADER == 2:
            mylar.USE_RTORRENT = True
        elif self.TORRENT_DOWNLOADER == 3:
            mylar.USE_TRANSMISSION = True
        elif self.TORRENT_DOWNLOADER == 4:
            mylar.USE_DELUGE = True
        elif self.TORRENT_DOWNLOADER == 5:
            mylar.USE_QBITTORRENT = True
        else:
            self.TORRENT_DOWNLOADER = 0
            mylar.USE_WATCHDIR = True

    def parse_32pfeed(self, rssfeedline):
        KEYS_32P = {}
        if self.ENABLE_32P and len(rssfeedline) > 1:
            userid_st = rssfeedline.find('&user')
            userid_en = rssfeedline.find('&', userid_st +1)
            if userid_en == -1:
                userid_32p = rssfeedline[userid_st +6:]
            else:
                userid_32p = rssfeedline[userid_st +6:userid_en]

            auth_st = rssfeedline.find('&auth')
            auth_en = rssfeedline.find('&', auth_st +1)
            if auth_en == -1:
                auth_32p = rssfeedline[auth_st +6:]
            else:
                auth_32p = rssfeedline[auth_st +6:auth_en]

            authkey_st = rssfeedline.find('&authkey')
            authkey_en = rssfeedline.find('&', authkey_st +1)
            if authkey_en == -1:
                authkey_32p = rssfeedline[authkey_st +9:]
            else:
                authkey_32p = rssfeedline[authkey_st +9:authkey_en]

            KEYS_32P = {"user":    userid_32p,
                        "auth":    auth_32p,
                        "authkey": authkey_32p,
                        "passkey": self.PASSKEY_32P}

        return KEYS_32P

    def get_extra_newznabs(self):
        extra_newznabs = zip(*[iter(self.EXTRA_NEWZNABS.split(', '))]*6)
        return extra_newznabs

    def provider_sequence(self):
        PR = []
        PR_NUM = 0
        if self.ENABLE_TORRENT_SEARCH:
            if self.ENABLE_32P:
                PR.append('32p')
                PR_NUM +=1
            if self.ENABLE_TPSE:
                PR.append('tpse')
                PR_NUM +=1
        if self.NZBSU:
            PR.append('nzb.su')
            PR_NUM +=1
        if self.DOGNZB:
            PR.append('dognzb')
            PR_NUM +=1
        if self.EXPERIMENTAL:
            PR.append('Experimental')
            PR_NUM +=1
        if self.ENABLE_TORZNAB:
            PR.append('Torznab')
            PR_NUM +=1

        PPR = ['32p', 'tpse', 'nzb.su', 'dognzb', 'Experimental', 'Torznab']
        if self.NEWZNAB:
            for ens in self.EXTRA_NEWZNABS:
                if str(ens[5]) == '1': # if newznabs are enabled
                    if ens[0] == "":
                        en_name = ens[1]
                    else:
                        en_name = ens[0]
                    if en_name.endswith("\""):
                        en_name = re.sub("\"", "", str(en_name)).strip()
                    PR.append(en_name)
                    PPR.append(en_name)
                    PR_NUM +=1

        if self.PROVIDER_ORDER is not None:
            try:
                PRO_ORDER = zip(*[iter(self.PROVIDER_ORDER.split(', '))]*2)
            except:
                PO = []
                for k, v in self.PROVIDER_ORDER.iteritems():
                    PO.append(k)
                    PO.append(v)
                POR = ', '.join(PO)
                PRO_ORDER = zip(*[iter(POR.split(', '))]*2)

            logger.fdebug('Original provider_order sequence: %s' % self.PROVIDER_ORDER)

            #if provider order exists already, load it and then append to end any NEW entries.
            logger.fdebug('Provider sequence already pre-exists. Re-loading and adding/remove any new entries')
            TMPPR_NUM = 0
            PROV_ORDER = []
            #load original sequence
            for PRO in PRO_ORDER:
                PROV_ORDER.append({"order_seq":  PRO[0],
                                   "provider":   str(PRO[1])})
                TMPPR_NUM +=1

            #calculate original sequence to current sequence for discrepancies
            #print('TMPPR_NUM: %s --- PR_NUM: %s' % (TMPPR_NUM, PR_NUM))
            if PR_NUM != TMPPR_NUM:
                logger.fdebug('existing Order count does not match New Order count')
                if PR_NUM > TMPPR_NUM:
                    logger.fdebug('%s New entries exist, appending to end as default ordering' % (PR_NUM - TMPPR_NUM))
                    TOTALPR = (TMPPR_NUM + PR_NUM)
                else:
                    logger.fdebug('%s Disabled entries exist, removing from ordering sequence' % (TMPPR_NUM - PR_NUM))
                    TOTALPR = TMPPR_NUM
                if PR_NUM > 0:
                    logger.fdebug('%s entries are enabled.' % PR_NUM)

            NEW_PROV_ORDER = []
            i = 0
            #this should loop over ALL possible entries
            while i < len(PR):
                found = False
                for d in PPR:
                    #logger.fdebug('checking entry %s against %s' % (PR[i], d) #d['provider'])
                    if d == PR[i]:
                        x = [p['order_seq'] for p in PROV_ORDER if p['provider'] == PR[i]]
                        if x:
                            ord = x[0]
                        else:
                            ord = i
                        found = {'provider': PR[i],
                                 'order':    ord} 
                        break
                    else:
                        found = False

                if found is not False:
                    new_order_seqnum = len(NEW_PROV_ORDER)
                    if new_order_seqnum <= found['order']:
                        seqnum = found['order']
                    else:
                        seqnum = new_order_seqnum
                    NEW_PROV_ORDER.append({"order_seq":  len(NEW_PROV_ORDER),
                                           "provider":   found['provider'],
                                           "orig_seq":   int(seqnum)})
                i+=1
 

            #now we reorder based on priority of orig_seq, but use a new_order seq
            xa = 0
            NPROV = []
            for x in sorted(NEW_PROV_ORDER, key=itemgetter('orig_seq'), reverse=False):
                NPROV.append(str(xa))
                NPROV.append(x['provider'])
                xa+=1
            PROVIDER_ORDER = NPROV

        else:
            #priority provider sequence in order#, ProviderName
            logger.fdebug('creating provider sequence order now...')
            TMPPR_NUM = 0
            PROV_ORDER = []
            while TMPPR_NUM < PR_NUM:
                PROV_ORDER.append(str(TMPPR_NUM))
                PROV_ORDER.append(PR[TMPPR_NUM])
                                   #{"order_seq":  TMPPR_NUM,
                                   #"provider":   str(PR[TMPPR_NUM])})
                TMPPR_NUM +=1
            PROVIDER_ORDER = PROV_ORDER

        ll = ', '.join(PROVIDER_ORDER)
        if not config.has_section('Providers'):
            config.add_section('Providers')
        config.set('Providers', 'PROVIDER_ORDER', ll)

        PROVIDER_ORDER = dict(zip(*[PROVIDER_ORDER[i::2] for i in range(2)]))
        setattr(self, 'PROVIDER_ORDER', PROVIDER_ORDER)
        logger.fdebug('Provider Order is now set : %s ' % self.PROVIDER_ORDER)

    def write_extras(self, value):
        flattened = []
        for item in value: #self.EXTRA_NEWZNABS:
            for i in item:
                try:
                    if "\"" in i and " \"" in i:
                        ib = str(i).replace("\"", "").strip()
                    else:
                        ib = i
                except:
                    ib = i
                flattened.append(str(ib))
        return flattened
