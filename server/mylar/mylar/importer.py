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

import time
import os, errno
import sys
import shlex
import datetime
import re
import urllib
import urllib2
import shutil
import imghdr
import sqlite3
import cherrypy
import requests
import gzip
from StringIO import StringIO

import mylar
from mylar import logger, helpers, db, mb, cv, parseit, filechecker, search, updater, moveit, comicbookdb


def is_exists(comicid):

    myDB = db.DBConnection()

    # See if the artist is already in the database
    comiclist = myDB.select('SELECT ComicID, ComicName from comics WHERE ComicID=?', [comicid])

    if any(comicid in x for x in comiclist):
        logger.info(comiclist[0][1] + ' is already in the database.')
        return False
    else:
        return False


def addComictoDB(comicid, mismatch=None, pullupd=None, imported=None, ogcname=None, calledfrom=None, annload=None, chkwant=None, issuechk=None, issuetype=None, latestissueinfo=None, csyear=None):
    myDB = db.DBConnection()

    controlValueDict = {"ComicID":     comicid}

    dbcomic = myDB.selectone('SELECT * FROM comics WHERE ComicID=?', [comicid]).fetchone()
    if dbcomic is None:
        newValueDict = {"ComicName":   "Comic ID: %s" % (comicid),
                "Status":   "Loading"}
        comlocation = None
        oldcomversion = None
        series_status = 'Loading'
    else:
        if chkwant is not None:
            logger.fdebug('ComicID: ' + str(comicid) + ' already exists. Not adding from the future pull list at this time.')
            return 'Exists'
        if dbcomic['Status'] == 'Active':
            series_status = 'Active'
        elif dbcomic['Status'] == 'Paused':
            series_status = 'Paused'
        else:
            series_status = 'Loading'

        newValueDict = {"Status":   "Loading"}
        comlocation = dbcomic['ComicLocation']
        if not latestissueinfo:
            latestissueinfo = []
            latestissueinfo.append({"latestiss": dbcomic['LatestIssue'],
                                    "latestdate":  dbcomic['LatestDate']})

        if mylar.CONFIG.CREATE_FOLDERS is True:
            checkdirectory = filechecker.validateAndCreateDirectory(comlocation, True)
            if not checkdirectory:
               logger.warn('Error trying to validate/create directory. Aborting this process at this time.')
               return
        oldcomversion = dbcomic['ComicVersion'] #store the comicversion and chk if it exists before hammering.
    myDB.upsert("comics", newValueDict, controlValueDict)

    #run the re-sortorder here in order to properly display the page
    if pullupd is None:
        helpers.ComicSort(comicorder=mylar.COMICSORT, imported=comicid)

    # we need to lookup the info for the requested ComicID in full now
    comic = cv.getComic(comicid, 'comic')

    if not comic:
        logger.warn('Error fetching comic. ID for : ' + comicid)
        if dbcomic is None:
            newValueDict = {"ComicName":   "Fetch failed, try refreshing. (%s)" % (comicid),
                    "Status":   "Active"}
        else:
            if series_status == 'Active' or series_status == 'Loading':
                newValueDict = {"Status":   "Active"}
        myDB.upsert("comics", newValueDict, controlValueDict)
        return

    if comic['ComicName'].startswith('The '):
        sortname = comic['ComicName'][4:]
    else:
        sortname = comic['ComicName']


    logger.info('Now adding/updating: ' + comic['ComicName'])
    #--Now that we know ComicName, let's try some scraping
    #--Start
    # gcd will return issue details (most importantly publishing date)
    if not mylar.CONFIG.CV_ONLY:
        if mismatch == "no" or mismatch is None:
            gcdinfo=parseit.GCDScraper(comic['ComicName'], comic['ComicYear'], comic['ComicIssues'], comicid)
            #print ("gcdinfo: " + str(gcdinfo))
            mismatch_com = "no"
            if gcdinfo == "No Match":
                updater.no_searchresults(comicid)
                nomatch = "true"
                logger.info('There was an error when trying to add ' + comic['ComicName'] + ' (' + comic['ComicYear'] + ')')
                return nomatch
            else:
                mismatch_com = "yes"
                #print ("gcdinfo:" + str(gcdinfo))

        elif mismatch == "yes":
            CV_EXcomicid = myDB.selectone("SELECT * from exceptions WHERE ComicID=?", [comicid])
            if CV_EXcomicid['variloop'] is None: pass
            else:
                vari_loop = CV_EXcomicid['variloop']
                NewComicID = CV_EXcomicid['NewComicID']
                gcomicid = CV_EXcomicid['GComicID']
                resultURL = "/series/" + str(NewComicID) + "/"
                #print ("variloop" + str(CV_EXcomicid['variloop']))
                #if vari_loop == '99':
                gcdinfo = parseit.GCDdetails(comseries=None, resultURL=resultURL, vari_loop=0, ComicID=comicid, TotalIssues=0, issvariation="no", resultPublished=None)

    # print ("Series Published" + parseit.resultPublished)

    CV_NoYearGiven = "no"
    #if the SeriesYear returned by CV is blank or none (0000), let's use the gcd one.
    if any([comic['ComicYear'] is None, comic['ComicYear'] == '0000', comic['ComicYear'][-1:] == '-']):
        if mylar.CONFIG.CV_ONLY:
            #we'll defer this until later when we grab all the issues and then figure it out
            logger.info('Uh-oh. I cannot find a Series Year for this series. I am going to try analyzing deeper.')
            SeriesYear = cv.getComic(comicid, 'firstissue', comic['FirstIssueID'])
            if SeriesYear == '0000':
                logger.info('Ok - I could not find a Series Year at all. Loading in the issue data now and will figure out the Series Year.')
                CV_NoYearGiven = "yes"
                issued = cv.getComic(comicid, 'issue')
                SeriesYear = issued['firstdate'][:4]
        else:
            SeriesYear = gcdinfo['SeriesYear']
    else:
        SeriesYear = comic['ComicYear']

    if any([int(SeriesYear) > int(datetime.datetime.now().year) + 1, int(SeriesYear) == 2099]) and csyear is not None:
        logger.info('Corrected year of ' + str(SeriesYear) + ' to corrected year for series that was manually entered previously of ' + str(csyear))
        SeriesYear = csyear

    logger.info('Sucessfully retrieved details for ' + comic['ComicName'])

    #since the weekly issue check could return either annuals or issues, let's initialize it here so it carries through properly.
    weeklyissue_check = []

    if any([oldcomversion is None, oldcomversion == "None"]):
        logger.info('Previous version detected as None - seeing if update required')
        if comic['ComicVersion'].isdigit():
            comicVol = 'v' + comic['ComicVersion']
            logger.info('Updated version to :' + str(comicVol))
            if all([mylar.CONFIG.SETDEFAULTVOLUME is False, comicVol == 'v1']):
                comicVol = None
        else:
            if mylar.CONFIG.SETDEFAULTVOLUME is True:
                comicVol = 'v1'
            else:
                comicVol = None
    else:
        comicVol = oldcomversion
        if all([mylar.CONFIG.SETDEFAULTVOLUME is True, comicVol is None]):
            comicVol = 'v1'



    # setup default location here
    u_comicnm = comic['ComicName']
    # let's remove the non-standard characters here that will break filenaming / searching.
    comicname_filesafe = helpers.filesafe(u_comicnm)

    if comlocation is None:
        comicdir = comicname_filesafe
        series = comicdir
        if series[-1:] == '.':
            series[:-1]

        publisher = re.sub('!', '', comic['ComicPublisher']) # thanks Boom!
        publisher = helpers.filesafe(publisher)
        year = SeriesYear
        if comicVol is None:
            comicVol = 'None'
        #if comversion is None, remove it so it doesn't populate with 'None'
        if comicVol == 'None':
            chunk_f_f = re.sub('\$VolumeN', '', mylar.CONFIG.FOLDER_FORMAT)
            chunk_f = re.compile(r'\s+')
            chunk_folder_format = chunk_f.sub(' ', chunk_f_f)
            logger.fdebug('No version # found for series, removing from folder format')
            logger.fdebug("new folder format: " + str(chunk_folder_format))
        else:
            chunk_folder_format = mylar.CONFIG.FOLDER_FORMAT

        #do work to generate folder path

        values = {'$Series':        series,
                  '$Publisher':     publisher,
                  '$Year':          year,
                  '$series':        series.lower(),
                  '$publisher':     publisher.lower(),
                  '$VolumeY':       'V' + str(year),
                  '$VolumeN':       comicVol.upper(),
                  '$Annual':        'Annual'
                  }

        if mylar.CONFIG.FOLDER_FORMAT == '':
            comlocation = os.path.join(mylar.CONFIG.DESTINATION_DIR, comicdir, " (" + SeriesYear + ")")
        else:
            comlocation = os.path.join(mylar.CONFIG.DESTINATION_DIR, helpers.replace_all(chunk_folder_format, values))


        #comlocation = mylar.CONFIG.DESTINATION_DIR + "/" + comicdir + " (" + comic['ComicYear'] + ")"
        if mylar.CONFIG.DESTINATION_DIR == "":
            logger.error('There is no Comic Location Path specified - please specify one in Config/Web Interface.')
            return
        if mylar.CONFIG.REPLACE_SPACES:
            #mylar.CONFIG.REPLACE_CHAR ...determines what to replace spaces with underscore or dot
            comlocation = comlocation.replace(' ', mylar.CONFIG.REPLACE_CHAR)

    #moved this out of the above loop so it will chk for existance of comlocation in case moved
    #if it doesn't exist - create it (otherwise will bugger up later on)
    if os.path.isdir(comlocation):
        logger.info('Directory (' + comlocation + ') already exists! Continuing...')
    else:
        if mylar.CONFIG.CREATE_FOLDERS is True:
            checkdirectory = filechecker.validateAndCreateDirectory(comlocation, True)
            if not checkdirectory:
                logger.warn('Error trying to validate/create directory. Aborting this process at this time.')
                return

    #try to account for CV not updating new issues as fast as GCD
    #seems CV doesn't update total counts
    #comicIssues = gcdinfo['totalissues']
    comicIssues = comic['ComicIssues']

    if not mylar.CONFIG.CV_ONLY:
        if gcdinfo['gcdvariation'] == "cv":
            comicIssues = str(int(comic['ComicIssues']) + 1)

    #let's download the image...
    if os.path.exists(mylar.CONFIG.CACHE_DIR): pass
    else:
        #let's make the dir.
        try:
            os.makedirs(str(mylar.CONFIG.CACHE_DIR))
            logger.info('Cache Directory successfully created at: ' + str(mylar.CONFIG.CACHE_DIR))

        except OSError:
            logger.error('Could not create cache dir. Check permissions of cache dir: ' + str(mylar.CONFIG.CACHE_DIR))

    coverfile = os.path.join(mylar.CONFIG.CACHE_DIR,  str(comicid) + ".jpg")

    #if cover has '+' in url it's malformed, we need to replace '+' with '%20' to retreive properly.

    #new CV API restriction - one api request / second.(probably unecessary here, but it doesn't hurt)
    if mylar.CONFIG.CVAPI_RATE is None or mylar.CONFIG.CVAPI_RATE < 2:
        time.sleep(2)
    else:
        time.sleep(mylar.CONFIG.CVAPI_RATE)

    logger.info('Attempting to retrieve the comic image for series')
    try:
        r = requests.get(comic['ComicImage'], params=None, stream=True, verify=mylar.CONFIG.CV_VERIFY, headers=mylar.CV_HEADERS)
    except Exception, e:
        logger.warn('Unable to download image from CV URL link: ' + comic['ComicImage'] + ' [Status Code returned: ' + str(r.status_code) + ']')

    logger.fdebug('comic image retrieval status code: ' + str(r.status_code))

    if str(r.status_code) != '200':
        logger.warn('Unable to download image from CV URL link: ' + comic['ComicImage'] + ' [Status Code returned: ' + str(r.status_code) + ']')
        coversize = 0
    else:
        if r.headers.get('Content-Encoding') == 'gzip':
            buf = StringIO(r.content)
            f = gzip.GzipFile(fileobj=buf)

        with open(coverfile, 'wb') as f:
            for chunk in r.iter_content(chunk_size=1024):
                if chunk: # filter out keep-alive new chunks
                    f.write(chunk)
                    f.flush()


        statinfo = os.stat(coverfile)
        coversize = statinfo.st_size

    if int(coversize) < 30000 or str(r.status_code) != '200':
        if str(r.status_code) != '200':
            logger.info('Trying to grab an alternate cover due to problems trying to retrieve the main cover image.')
        else:
            logger.info('Image size invalid [' + str(coversize) + ' bytes] - trying to get alternate cover image.')
        logger.fdebug('invalid image link is here: ' + comic['ComicImage'])

        if os.path.exists(coverfile):
            os.remove(coverfile)

        logger.info('Attempting to retrieve alternate comic image for the series.')
        try:
            r = requests.get(comic['ComicImageALT'], params=None, stream=True, verify=mylar.CONFIG.CV_VERIFY, headers=mylar.CV_HEADERS)
        except Exception, e:
            logger.warn('Unable to download image from CV URL link: ' + comic['ComicImageALT'] + ' [Status Code returned: ' + str(r.status_code) + ']')

        logger.fdebug('comic image retrieval status code: ' + str(r.status_code))

        if str(r.status_code) != '200':
            logger.warn('Unable to download image from CV URL link: ' + comic['ComicImageALT'] + ' [Status Code returned: ' + str(r.status_code) + ']')

        else:
            if r.headers.get('Content-Encoding') == 'gzip':
                buf = StringIO(r.content)
                f = gzip.GzipFile(fileobj=buf)

            with open(coverfile, 'wb') as f:
                for chunk in r.iter_content(chunk_size=1024):
                    if chunk: # filter out keep-alive new chunks
                        f.write(chunk)
                        f.flush()

    PRComicImage = os.path.join('cache', str(comicid) + ".jpg")
    ComicImage = helpers.replacetheslash(PRComicImage)

            #this is for Firefox when outside the LAN...it works, but I don't know how to implement it
            #without breaking the normal flow for inside the LAN (above)
            #ComicImage = "http://" + str(mylar.CONFIG.HTTP_HOST) + ":" + str(mylar.CONFIG.HTTP_PORT) + "/cache/" + str(comicid) + ".jpg"

    #if the comic cover local is checked, save a cover.jpg to the series folder.
    if mylar.CONFIG.COMIC_COVER_LOCAL and os.path.isdir(comlocation):
        try:
            comiclocal = os.path.join(comlocation, 'cover.jpg')
            shutil.copyfile(coverfile, comiclocal)
            if mylar.CONFIG.ENFORCE_PERMS:
                filechecker.setperms(comiclocal)
        except IOError as e:
            logger.error('Unable to save cover (' + str(coverfile) + ') into series directory (' + str(comiclocal) + ') at this time.')

    #for description ...
    #Cdesc = helpers.cleanhtml(comic['ComicDescription'])
    #cdes_find = Cdesc.find("Collected")
    #cdes_removed = Cdesc[:cdes_find]
    #logger.fdebug('description: ' + cdes_removed)

    #dynamic-name generation here.
    as_d = filechecker.FileChecker(watchcomic=comic['ComicName'])
    as_dinfo = as_d.dynamic_replace(comic['ComicName'])
    tmpseriesname = as_dinfo['mod_seriesname']
    dynamic_seriesname = re.sub('[\|\s]','', tmpseriesname.lower()).strip()

    controlValueDict = {"ComicID":        comicid}
    newValueDict = {"ComicName":          comic['ComicName'],
                    "ComicSortName":      sortname,
                    "ComicName_Filesafe": comicname_filesafe,
                    "DynamicComicName":   dynamic_seriesname,
                    "ComicYear":          SeriesYear,
                    "ComicImage":         ComicImage,
                    "ComicImageURL":      comic.get("ComicImage", ""),
                    "ComicImageALTURL":   comic.get("ComicImageALT", ""),
                    "Total":              comicIssues,
                    "ComicVersion":       comicVol,
                    "ComicLocation":      comlocation,
                    "ComicPublisher":     comic['ComicPublisher'],
#                    "Description":       Cdesc, #.dencode('utf-8', 'replace'),
                    "DetailURL":          comic['ComicURL'],
#                    "AlternateSearch":    comic['Aliases'],
#                    "ComicPublished":    gcdinfo['resultPublished'],
                    "ComicPublished":     "Unknown",
                    "Type":               comic['Type'],
                    "DateAdded":          helpers.today(),
                    "Status":             "Loading"}

    myDB.upsert("comics", newValueDict, controlValueDict)

    #comicsort here...
    #run the re-sortorder here in order to properly display the page
    if pullupd is None:
        helpers.ComicSort(sequence='update')

    if CV_NoYearGiven == 'no':
        #if set to 'no' then we haven't pulled down the issues, otherwise we did it already
        issued = cv.getComic(comicid, 'issue')
        if issued is None:
            logger.warn('Unable to retrieve data from ComicVine. Get your own API key already!')
            return
    logger.info('Sucessfully retrieved issue details for ' + comic['ComicName'])

    #move to own function so can call independently to only refresh issue data
    #issued is from cv.getComic, comic['ComicName'] & comicid would both be already known to do independent call.
    updateddata = updateissuedata(comicid, comic['ComicName'], issued, comicIssues, calledfrom, SeriesYear=SeriesYear, latestissueinfo=latestissueinfo)
    issuedata = updateddata['issuedata']
    anndata = updateddata['annualchk']
    nostatus = updateddata['nostatus']
    importantdates = updateddata['importantdates']
    if issuedata is None:
        logger.warn('Unable to complete Refreshing / Adding issue data - this WILL create future problems if not addressed.')
        return {'status': 'incomplete'}

    if calledfrom is None:
        issue_collection(issuedata, nostatus='False')
        #need to update annuals at this point too....
        if anndata:
            manualAnnual(annchk=anndata)

    if (mylar.CONFIG.CVINFO or (mylar.CONFIG.CV_ONLY and mylar.CONFIG.CVINFO)) and os.path.isdir(comlocation):
        if not os.path.exists(os.path.join(comlocation, "cvinfo")) or mylar.CONFIG.CV_ONETIMER:
            with open(os.path.join(comlocation, "cvinfo"), "w") as text_file:
                text_file.write(str(comic['ComicURL']))


    if calledfrom == 'weekly':
        logger.info('Successfully refreshed ' + comic['ComicName'] + ' (' + str(SeriesYear) + '). Returning to Weekly issue comparison.')
        logger.info('Update issuedata for ' + str(issuechk) + ' of : ' + str(weeklyissue_check))
        return {'status': 'complete',
                'issuedata': issuedata} # this should be the weeklyissue_check data from updateissuedata function

    elif calledfrom == 'dbupdate':
        logger.info('returning to dbupdate module')
        return {'status': 'complete',
                'issuedata': issuedata,
                'anndata': anndata } # this should be the issuedata data from updateissuedata function

    elif calledfrom == 'weeklycheck':
        logger.info('Successfully refreshed ' + comic['ComicName'] + ' (' + str(SeriesYear) + '). Returning to Weekly issue update.')
        return  #no need to return any data here.


    logger.info('Updating complete for: ' + comic['ComicName'])

    #if it made it here, then the issuedata contains dates, let's pull the data now.
    latestiss = importantdates['LatestIssue']
    latestdate = importantdates['LatestDate']
    lastpubdate = importantdates['LastPubDate']
    series_status = importantdates['SeriesStatus']
    #move the files...if imported is not empty & not futurecheck (meaning it's not from the mass importer.)
    #logger.info('imported is : ' + str(imported))
    if imported is None or imported == 'None' or imported == 'futurecheck':
        pass
    else:
        if mylar.CONFIG.IMP_MOVE:
            logger.info('Mass import - Move files')
            moveit.movefiles(comicid, comlocation, imported)
        else:
            logger.info('Mass import - Moving not Enabled. Setting Archived Status for import.')
            moveit.archivefiles(comicid, comlocation, imported)

    #check for existing files...
    statbefore = myDB.selectone("SELECT * FROM issues WHERE ComicID=? AND Int_IssueNumber=?", [comicid, helpers.issuedigits(latestiss)]).fetchone()
    logger.fdebug('issue: ' + latestiss + ' status before chk :' + str(statbefore['Status']))
    updater.forceRescan(comicid)
    statafter = myDB.selectone("SELECT * FROM issues WHERE ComicID=? AND Int_IssueNumber=?", [comicid, helpers.issuedigits(latestiss)]).fetchone()
    logger.fdebug('issue: ' + latestiss + ' status after chk :' + str(statafter['Status']))

    logger.fdebug('pullupd: ' + str(pullupd))
    logger.fdebug('lastpubdate: ' + str(lastpubdate))
    logger.fdebug('series_status: ' + str(series_status))
    if pullupd is None:
    # lets' check the pullist for anything at this time as well since we're here.
    # do this for only Present comics....
        if mylar.CONFIG.AUTOWANT_UPCOMING and lastpubdate == 'Present' and series_status == 'Active': #and 'Present' in gcdinfo['resultPublished']:
            logger.fdebug('latestissue: #' + str(latestiss))
            chkstats = myDB.selectone("SELECT * FROM issues WHERE ComicID=? AND Int_IssueNumber=?", [comicid, helpers.issuedigits(latestiss)]).fetchone()
            if chkstats is None:
                if mylar.CONFIG.ANNUALS_ON:
                    chkstats = myDB.selectone("SELECT * FROM annuals WHERE ComicID=? AND Int_IssueNumber=?", [comicid, helpers.issuedigits(latestiss)]).fetchone()

            if chkstats:
                logger.fdebug('latestissue status: ' + chkstats['Status'])
                if chkstats['Status'] == 'Skipped' or chkstats['Status'] == 'Wanted' or chkstats['Status'] == 'Snatched':
                    logger.info('Checking this week pullist for new issues of ' + comic['ComicName'])
                    if comic['ComicName'] != comicname_filesafe:
                        cn_pull = comicname_filesafe
                    else:
                        cn_pull = comic['ComicName']
                    updater.newpullcheck(ComicName=cn_pull, ComicID=comicid, issue=latestiss)

            #here we grab issues that have been marked as wanted above...
                    results = []
                    issresults = myDB.select("SELECT * FROM issues where ComicID=? AND Status='Wanted'", [comicid])
                    if issresults:
                        for issr in issresults:
                            results.append({'IssueID':       issr['IssueID'],
                                            'Issue_Number':  issr['Issue_Number'],
                                            'Status':        issr['Status']
                                           })
                    if mylar.CONFIG.ANNUALS_ON:
                        an_results = myDB.select("SELECT * FROM annuals WHERE ComicID=? AND Status='Wanted'", [comicid])
                        if an_results:
                            for ar in an_results:
                                results.append({'IssueID':       ar['IssueID'],
                                                'Issue_Number':  ar['Issue_Number'],
                                                'Status':        ar['Status']
                                               })


                    if results:
                        logger.info('Attempting to grab wanted issues for : '  + comic['ComicName'])

                        for result in results:
                            logger.fdebug('Searching for : ' + str(result['Issue_Number']))
                            logger.fdebug('Status of : ' + str(result['Status']))
                            search.searchforissue(result['IssueID'])
                    else: logger.info('No issues marked as wanted for ' + comic['ComicName'])

                    logger.info('Finished grabbing what I could.')
                else:
                    logger.info('Already have the latest issue : #' + str(latestiss))

    if chkwant is not None:
        #if this isn't None, this is being called from the futureupcoming list
        #a new series was added automagically, but it has more than 1 issue (probably because it was a back-dated issue)
        #the chkwant is a tuple containing all the data for the given series' issues that were marked as Wanted for futureupcoming dates.
        chkresults = myDB.select("SELECT * FROM issues WHERE ComicID=? AND Status='Skipped'", [comicid])
        if chkresults:
            logger.info('[FROM THE FUTURE CHECKLIST] Attempting to grab wanted issues for : ' + comic['ComicName'])
            for result in chkresults:
                for chkit in chkwant:
                    logger.fdebug('checking ' + chkit['IssueNumber'] + ' against ' + result['Issue_Number'])
                    if chkit['IssueNumber'] == result['Issue_Number']:
                        logger.fdebug('Searching for : ' + result['Issue_Number'])
                        logger.fdebug('Status of : ' + str(result['Status']))
                        search.searchforissue(result['IssueID'])
        else: logger.info('No issues marked as wanted for ' + comic['ComicName'])

        logger.info('Finished grabbing what I could.')

    if imported == 'futurecheck':
        logger.info('Returning to Future-Check module to complete the add & remove entry.')
        return
    elif all([imported is not None, imported != 'None']):
        logger.info('Successfully imported : ' + comic['ComicName'])
        return

    if calledfrom == 'addbyid':
        logger.info('Sucessfully added %s (%s) to the watchlist by directly using the ComicVine ID' % (comic['ComicName'], SeriesYear))
        return {'status': 'complete'}
    else:
        logger.info('Sucessfully added %s (%s) to the watchlist' % (comic['ComicName'], SeriesYear))
        return {'status': 'complete'}

#        if imported['Volume'] is None or imported['Volume'] == 'None':
#            results = myDB.select("SELECT * FROM importresults WHERE (WatchMatch is Null OR WatchMatch LIKE 'C%') AND DynamicName=? AND Volume IS NULL",[imported['DynamicName']])
#        else:
#            if not imported['Volume'].lower().startswith('v'):
#                volume = 'v' + str(imported['Volume'])
#            results = myDB.select("SELECT * FROM importresults WHERE (WatchMatch is Null OR WatchMatch LIKE 'C%') AND DynamicName=? AND Volume=?",[imported['DynamicName'],imported['Volume']])
#
#        if results is not None:
#            for result in results:
#                controlValue = {"DynamicName":  imported['DynamicName'],
#                                "Volume":       imported['Volume']}
#                newValue = {"Status":           "Imported",
#                            "SRID":             result['SRID'],
#                            "ComicID":          comicid}
#                myDB.upsert("importresults", newValue, controlValue)


def GCDimport(gcomicid, pullupd=None, imported=None, ogcname=None):
    # this is for importing via GCD only and not using CV.
    # used when volume spanning is discovered for a Comic (and can't be added using CV).
    # Issue Counts are wrong (and can't be added).

    # because Comicvine ComicID and GCD ComicID could be identical at some random point, let's distinguish.
    # CV = comicid, GCD = gcomicid :) (ie. CV=2740, GCD=G3719)

    gcdcomicid = gcomicid
    myDB = db.DBConnection()

    # We need the current minimal info in the database instantly
    # so we don't throw a 500 error when we redirect to the artistPage

    controlValueDict = {"ComicID":     gcdcomicid}

    comic = myDB.selectone('SELECT ComicName, ComicYear, Total, ComicPublished, ComicImage, ComicLocation, ComicPublisher FROM comics WHERE ComicID=?', [gcomicid]).fetchone()
    ComicName = comic[0]
    ComicYear = comic[1]
    ComicIssues = comic[2]
    ComicPublished = comic[3]
    comlocation = comic[5]
    ComicPublisher = comic[6]
    #ComicImage = comic[4]
    #print ("Comic:" + str(ComicName))

    newValueDict = {"Status":   "Loading"}
    myDB.upsert("comics", newValueDict, controlValueDict)

    # we need to lookup the info for the requested ComicID in full now
    #comic = cv.getComic(comicid,'comic')

    if not comic:
        logger.warn('Error fetching comic. ID for : ' + gcdcomicid)
        if dbcomic is None:
            newValueDict = {"ComicName":   "Fetch failed, try refreshing. (%s)" % (gcdcomicid),
                    "Status":   "Active"}
        else:
            newValueDict = {"Status":   "Active"}
        myDB.upsert("comics", newValueDict, controlValueDict)
        return

    #run the re-sortorder here in order to properly display the page
    if pullupd is None:
        helpers.ComicSort(comicorder=mylar.COMICSORT, imported=gcomicid)

    if ComicName.startswith('The '):
        sortname = ComicName[4:]
    else:
        sortname = ComicName


    logger.info(u"Now adding/updating: " + ComicName)
    #--Now that we know ComicName, let's try some scraping
    #--Start
    # gcd will return issue details (most importantly publishing date)
    comicid = gcomicid[1:]
    resultURL = "/series/" + str(comicid) + "/"
    gcdinfo=parseit.GCDdetails(comseries=None, resultURL=resultURL, vari_loop=0, ComicID=gcdcomicid, TotalIssues=ComicIssues, issvariation=None, resultPublished=None)
    if gcdinfo == "No Match":
        logger.warn("No matching result found for " + ComicName + " (" + ComicYear + ")")
        updater.no_searchresults(gcomicid)
        nomatch = "true"
        return nomatch
    logger.info(u"Sucessfully retrieved details for " + ComicName)
    # print ("Series Published" + parseit.resultPublished)
    #--End

    ComicImage = gcdinfo['ComicImage']

    #comic book location on machine
    # setup default location here
    if comlocation is None:
        # let's remove the non-standard characters here.
        u_comicnm = ComicName
        u_comicname = u_comicnm.encode('ascii', 'ignore').strip()
        if ':' in u_comicname or '/' in u_comicname or ',' in u_comicname:
            comicdir = u_comicname
            if ':' in comicdir:
                comicdir = comicdir.replace(':', '')
            if '/' in comicdir:
                comicdir = comicdir.replace('/', '-')
            if ',' in comicdir:
                comicdir = comicdir.replace(',', '')
        else: comicdir = u_comicname

        series = comicdir
        publisher = ComicPublisher
        year = ComicYear

        #do work to generate folder path
        values = {'$Series':        series,
                  '$Publisher':     publisher,
                  '$Year':          year,
                  '$series':        series.lower(),
                  '$publisher':     publisher.lower(),
                  '$Volume':        year
                  }

        if mylar.CONFIG.FOLDER_FORMAT == '':
            comlocation = mylar.CONFIG.DESTINATION_DIR + "/" + comicdir + " (" + comic['ComicYear'] + ")"
        else:
            comlocation = mylar.CONFIG.DESTINATION_DIR + "/" + helpers.replace_all(mylar.CONFIG.FOLDER_FORMAT, values)

        #comlocation = mylar.CONFIG.DESTINATION_DIR + "/" + comicdir + " (" + ComicYear + ")"
        if mylar.CONFIG.DESTINATION_DIR == "":
            logger.error(u"There is no general directory specified - please specify in Config/Post-Processing.")
            return
        if mylar.CONFIG.REPLACE_SPACES:
            #mylar.CONFIG.REPLACE_CHAR ...determines what to replace spaces with underscore or dot
            comlocation = comlocation.replace(' ', mylar.CONFIG.REPLACE_CHAR)

    #if it doesn't exist - create it (otherwise will bugger up later on)
    if os.path.isdir(comlocation):
        logger.info(u"Directory (" + comlocation + ") already exists! Continuing...")
    else:
        if mylar.CONFIG.CREATE_FOLDERS is True:
            checkdirectory = filechecker.validateAndCreateDirectory(comlocation, True)
            if not checkdirectory:
                logger.warn('Error trying to validate/create directory. Aborting this process at this time.')
                return

    comicIssues = gcdinfo['totalissues']

    #let's download the image...
    if os.path.exists(mylar.CONFIG.CACHE_DIR): pass
    else:
        #let's make the dir.
        try:
            os.makedirs(str(mylar.CONFIG.CACHE_DIR))
            logger.info(u"Cache Directory successfully created at: " + str(mylar.CONFIG.CACHE_DIR))

        except OSError:
            logger.error(u"Could not create cache dir : " + str(mylar.CONFIG.CACHE_DIR))

    coverfile = os.path.join(mylar.CONFIG.CACHE_DIR, str(gcomicid) + ".jpg")

    #new CV API restriction - one api request / second.
    if mylar.CONFIG.CVAPI_RATE is None or mylar.CONFIG.CVAPI_RATE < 2:
        time.sleep(2)
    else:
        time.sleep(mylar.CONFIG.CVAPI_RATE)

    urllib.urlretrieve(str(ComicImage), str(coverfile))
    try:
        with open(str(coverfile)) as f:
            ComicImage = os.path.join('cache', str(gcomicid) + ".jpg")

            #this is for Firefox when outside the LAN...it works, but I don't know how to implement it
            #without breaking the normal flow for inside the LAN (above)
            #ComicImage = "http://" + str(mylar.CONFIG.HTTP_HOST) + ":" + str(mylar.CONFIG.HTTP_PORT) + "/cache/" + str(comi$

            logger.info(u"Sucessfully retrieved cover for " + ComicName)
            #if the comic cover local is checked, save a cover.jpg to the series folder.
            if mylar.CONFIG.COMIC_COVER_LOCAL and os.path.isdir(comlocation):
                comiclocal = os.path.join(comlocation + "/cover.jpg")
                shutil.copy(ComicImage, comiclocal)
    except IOError as e:
        logger.error(u"Unable to save cover locally at this time.")

    #if comic['ComicVersion'].isdigit():
    #    comicVol = "v" + comic['ComicVersion']
    #else:
    #    comicVol = None


    controlValueDict = {"ComicID":      gcomicid}
    newValueDict = {"ComicName":        ComicName,
                    "ComicSortName":    sortname,
                    "ComicYear":        ComicYear,
                    "Total":            comicIssues,
                    "ComicLocation":    comlocation,
                    #"ComicVersion":     comicVol,
                    "ComicImage":       ComicImage,
                    "ComicImageURL":    comic.get('ComicImage', ''),
                    "ComicImageALTURL": comic.get('ComicImageALT', ''),
                    #"ComicPublisher":   comic['ComicPublisher'],
                    #"ComicPublished":   comicPublished,
                    "DateAdded":        helpers.today(),
                    "Status":           "Loading"}

    myDB.upsert("comics", newValueDict, controlValueDict)

    #comicsort here...
    #run the re-sortorder here in order to properly display the page
    if pullupd is None:
        helpers.ComicSort(sequence='update')

    logger.info(u"Sucessfully retrieved issue details for " + ComicName)
    n = 0
    iscnt = int(comicIssues)
    issnum = []
    issname = []
    issdate = []
    int_issnum = []
    #let's start issue #'s at 0 -- thanks to DC for the new 52 reboot! :)
    latestiss = "0"
    latestdate = "0000-00-00"
    #print ("total issues:" + str(iscnt))
    #---removed NEW code here---
    logger.info(u"Now adding/updating issues for " + ComicName)
    bb = 0
    while (bb <= iscnt):
        #---NEW.code
        try:
            gcdval = gcdinfo['gcdchoice'][bb]
            #print ("gcdval: " + str(gcdval))
        except IndexError:
            #account for gcd variation here
            if gcdinfo['gcdvariation'] == 'gcd':
                #print ("gcd-variation accounted for.")
                issdate = '0000-00-00'
                int_issnum =  int (issis / 1000)
            break
        if 'nn' in str(gcdval['GCDIssue']):
            #no number detected - GN, TP or the like
            logger.warn(u"Non Series detected (Graphic Novel, etc) - cannot proceed at this time.")
            updater.no_searchresults(comicid)
            return
        elif '.' in str(gcdval['GCDIssue']):
            issst = str(gcdval['GCDIssue']).find('.')
            issb4dec = str(gcdval['GCDIssue'])[:issst]
            #if the length of decimal is only 1 digit, assume it's a tenth
            decis = str(gcdval['GCDIssue'])[issst +1:]
            if len(decis) == 1:
                decisval = int(decis) * 10
                issaftdec = str(decisval)
            if len(decis) == 2:
                decisval = int(decis)
                issaftdec = str(decisval)
            if int(issaftdec) == 0: issaftdec = "00"
            gcd_issue = issb4dec + "." + issaftdec
            gcdis = (int(issb4dec) * 1000) + decisval
        else:
            gcdis = int(str(gcdval['GCDIssue'])) * 1000
            gcd_issue = str(gcdval['GCDIssue'])
        #get the latest issue / date using the date.
        int_issnum = int(gcdis / 1000)
        issdate = str(gcdval['GCDDate'])
        issid = "G" + str(gcdval['IssueID'])
        if gcdval['GCDDate'] > latestdate:
            latestiss = str(gcd_issue)
            latestdate = str(gcdval['GCDDate'])
        #print("(" + str(bb) + ") IssueID: " + str(issid) + " IssueNo: " + str(gcd_issue) + " Date" + str(issdate) )
        #---END.NEW.

        # check if the issue already exists
        iss_exists = myDB.selectone('SELECT * from issues WHERE IssueID=?', [issid]).fetchone()


        # Only change the status & add DateAdded if the issue is not already in the database
        if iss_exists is None:
            newValueDict['DateAdded'] = helpers.today()

        #adjust for inconsistencies in GCD date format - some dates have ? which borks up things.
        if "?" in str(issdate):
            issdate = "0000-00-00"

        controlValueDict = {"IssueID":  issid}
        newValueDict = {"ComicID":            gcomicid,
                        "ComicName":          ComicName,
                        "Issue_Number":       gcd_issue,
                        "IssueDate":          issdate,
                        "Int_IssueNumber":    int_issnum
                        }

        #print ("issueid:" + str(controlValueDict))
        #print ("values:" + str(newValueDict))

        if mylar.CONFIG.AUTOWANT_ALL:
            newValueDict['Status'] = "Wanted"
        elif issdate > helpers.today() and mylar.CONFIG.AUTOWANT_UPCOMING:
            newValueDict['Status'] = "Wanted"
        else:
            newValueDict['Status'] = "Skipped"

        if iss_exists:
            #print ("Existing status : " + str(iss_exists['Status']))
            newValueDict['Status'] = iss_exists['Status']


        myDB.upsert("issues", newValueDict, controlValueDict)
        bb+=1

#        logger.debug(u"Updating comic cache for " + ComicName)
#        cache.getThumb(ComicID=issue['issueid'])

#        logger.debug(u"Updating cache for: " + ComicName)
#        cache.getThumb(ComicIDcomicid)


    controlValueStat = {"ComicID":     gcomicid}
    newValueStat = {"Status":          "Active",
                    "LatestIssue":     latestiss,
                    "LatestDate":      latestdate,
                    "LastUpdated":     helpers.now()
                   }

    myDB.upsert("comics", newValueStat, controlValueStat)

    if mylar.CONFIG.CVINFO and os.path.isdir(comlocation):
        if not os.path.exists(comlocation + "/cvinfo"):
            with open(comlocation + "/cvinfo", "w") as text_file:
                text_file.write("http://comicvine.gamespot.com/volume/49-" + str(comicid))

    logger.info(u"Updating complete for: " + ComicName)

    #move the files...if imported is not empty (meaning it's not from the mass importer.)
    if imported is None or imported == 'None':
        pass
    else:
        if mylar.CONFIG.IMP_MOVE:
            logger.info("Mass import - Move files")
            moveit.movefiles(gcomicid, comlocation, ogcname)
        else:
            logger.info("Mass import - Moving not Enabled. Setting Archived Status for import.")
            moveit.archivefiles(gcomicid, ogcname)

    #check for existing files...
    updater.forceRescan(gcomicid)


    if pullupd is None:
        # lets' check the pullist for anyting at this time as well since we're here.
        if mylar.CONFIG.AUTOWANT_UPCOMING and 'Present' in ComicPublished:
            logger.info(u"Checking this week's pullist for new issues of " + ComicName)
            updater.newpullcheck(comic['ComicName'], gcomicid)

        #here we grab issues that have been marked as wanted above...

        results = myDB.select("SELECT * FROM issues where ComicID=? AND Status='Wanted'", [gcomicid])
        if results:
            logger.info(u"Attempting to grab wanted issues for : "  + ComicName)

            for result in results:
                foundNZB = "none"
                if (mylar.CONFIG.NZBSU or mylar.CONFIG.DOGNZB or mylar.CONFIG.EXPERIMENTAL or mylar.CONFIG.NEWZNAB) and (mylar.CONFIG.SAB_HOST):
                    foundNZB = search.searchforissue(result['IssueID'])
                    if foundNZB == "yes":
                        updater.foundsearch(result['ComicID'], result['IssueID'])
        else: logger.info(u"No issues marked as wanted for " + ComicName)

        logger.info(u"Finished grabbing what I could.")


def issue_collection(issuedata, nostatus):
    myDB = db.DBConnection()
    nowdate = datetime.datetime.now()
    now_week = datetime.datetime.strftime(nowdate, "%Y%U")

    if issuedata:
        for issue in issuedata:


            controlValueDict = {"IssueID":  issue['IssueID']}
            newValueDict = {"ComicID":            issue['ComicID'],
                            "ComicName":          issue['ComicName'],
                            "IssueName":          issue['IssueName'],
                            "Issue_Number":       issue['Issue_Number'],
                            "IssueDate":          issue['IssueDate'],
                            "ReleaseDate":        issue['ReleaseDate'],
                            "Int_IssueNumber":    issue['Int_IssueNumber'],
                            "ImageURL":           issue['ImageURL'],
                            "ImageURL_ALT":       issue['ImageURL_ALT']
                            #"Status":             "Skipped"  #set this to Skipped by default to avoid NULL entries.
                            }

            # check if the issue already exists
            iss_exists = myDB.selectone('SELECT * from issues WHERE IssueID=?', [issue['IssueID']]).fetchone()
            dbwrite = "issues"

            #if iss_exists is None:
            #    iss_exists = myDB.selectone('SELECT * from annuals WHERE IssueID=?', [issue['IssueID']]).fetchone()
            #    if iss_exists:
            #        dbwrite = "annuals"

            if nostatus == 'False':

                # Only change the status & add DateAdded if the issue is already in the database
                if iss_exists is None:
                    newValueDict['DateAdded'] = helpers.today()
                    if issue['ReleaseDate'] == '0000-00-00':
                        dk = re.sub('-', '', issue['IssueDate']).strip()
                    else:
                        dk = re.sub('-', '', issue['ReleaseDate']).strip() # converts date to 20140718 format
                    if dk == '00000000':
                        logger.warn('Issue Data is invalid for Issue Number %s. Marking this issue as Skipped' % issue['Issue_Number'])
                        newValueDict['Status'] = "Skipped"
                    else:
                        datechk = datetime.datetime.strptime(dk, "%Y%m%d")
                        issue_week = datetime.datetime.strftime(datechk, "%Y%U")
                        if mylar.CONFIG.AUTOWANT_ALL:
                            newValueDict['Status'] = "Wanted"
                            #logger.fdebug('autowant all')
                        elif issue_week >= now_week and mylar.CONFIG.AUTOWANT_UPCOMING:
                            #logger.fdebug(str(datechk) + ' >= ' + str(nowtime))
                            newValueDict['Status'] = "Wanted"
                        else:
                            newValueDict['Status'] = "Skipped"
                        #logger.fdebug('status is : ' + str(newValueDict))
                else:
                    #logger.fdebug('Existing status for issue #%s : %s' % (issue['Issue_Number'], iss_exists['Status']))
                    if any([iss_exists['Status'] is None, iss_exists['Status'] == 'None']):
                        is_status = 'Skipped'
                    else:
                        is_status = iss_exists['Status']
                    newValueDict['Status'] = is_status

            else:
                #logger.fdebug("Not changing the status at this time - reverting to previous module after to re-append existing status")
                pass #newValueDict['Status'] = "Skipped"

            try:
                myDB.upsert(dbwrite, newValueDict, controlValueDict)
            except sqlite3.InterfaceError, e:
                #raise sqlite3.InterfaceError(e)
                logger.error('Something went wrong - I cannot add the issue information into my DB.')
                myDB.action("DELETE FROM comics WHERE ComicID=?", [issue['ComicID']])
                return


def manualAnnual(manual_comicid=None, comicname=None, comicyear=None, comicid=None, annchk=None, manualupd=False):
        #called when importing/refreshing an annual that was manually added.
        myDB = db.DBConnection()

        if annchk is None:
            nowdate = datetime.datetime.now()
            now_week = datetime.datetime.strftime(nowdate, "%Y%U")
            annchk = []
            issueid = manual_comicid
            logger.fdebug(str(issueid) + ' added to series list as an Annual')
            sr = cv.getComic(manual_comicid, 'comic')
            logger.fdebug('Attempting to integrate ' + sr['ComicName'] + ' (' + str(issueid) + ') to the existing series of ' + comicname + '(' + str(comicyear) + ')')
            if len(sr) is None or len(sr) == 0:
                logger.fdebug('Could not find any information on the series indicated : ' + str(manual_comicid))
                return
            else:
                n = 0
                issued = cv.getComic(re.sub('4050-', '', manual_comicid).strip(), 'issue')
                if int(sr['ComicIssues']) == 0 and len(issued['issuechoice']) == 1:
                    noissues = 1
                else:
                    noissues = sr['ComicIssues']
                logger.fdebug('there are ' + str(noissues) + ' annuals within this series.')
                while (n < int(noissues)):
                    try:
                        firstval = issued['issuechoice'][n]
                    except IndexError:
                        break
                    try:
                        cleanname = helpers.cleanName(firstval['Issue_Name'])
                    except:
                        cleanname = 'None'

                    if firstval['Store_Date'] == '0000-00-00':
                        dk = re.sub('-', '', firstval['Issue_Date']).strip()
                    else:
                        dk = re.sub('-', '', firstval['Store_Date']).strip() # converts date to 20140718 format
                    if dk == '00000000':
                        logger.warn('Issue Data is invalid for Issue Number %s. Marking this issue as Skipped' % firstval['Issue_Number'])
                        astatus = "Skipped"
                    else:
                        datechk = datetime.datetime.strptime(dk, "%Y%m%d")
                        issue_week = datetime.datetime.strftime(datechk, "%Y%U")
                        if mylar.CONFIG.AUTOWANT_ALL:
                            astatus = "Wanted"
                        elif issue_week >= now_week and mylar.CONFIG.AUTOWANT_UPCOMING is True:
                            astatus = "Wanted"
                        else:
                            astatus = "Skipped"

                    annchk.append({'IssueID':          str(firstval['Issue_ID']),
                                   'ComicID':          comicid,
                                   'ReleaseComicID':   re.sub('4050-', '', manual_comicid).strip(),
                                   'ComicName':        comicname,
                                   'Issue_Number':     str(firstval['Issue_Number']),
                                   'IssueName':        cleanname,
                                   'IssueDate':        str(firstval['Issue_Date']),
                                   'ReleaseDate':      str(firstval['Store_Date']),
                                   'Status':           astatus,
                                   'ReleaseComicName': sr['ComicName']})
                    n+=1

            if manualupd is True:
                return annchk

        for ann in annchk:
            newCtrl = {"IssueID": ann['IssueID']}
            newVals = {"Issue_Number":     ann['Issue_Number'],
                       "Int_IssueNumber":  helpers.issuedigits(ann['Issue_Number']),
                       "IssueDate":        ann['IssueDate'],
                       "ReleaseDate":      ann['ReleaseDate'],
                       "IssueName":        ann['IssueName'],
                       "ComicID":          ann['ComicID'],   #this is the series ID
                       "ReleaseComicID":   ann['ReleaseComicID'],  #this is the series ID for the annual(s)
                       "ComicName":        ann['ComicName'], #series ComicName
                       "ReleaseComicName": ann['ReleaseComicName'], #series ComicName for the manual_comicid
                       "Status":           ann['Status']}
                       #need to add in the values for the new series to be added.
                       #"M_ComicName":    sr['ComicName'],
                       #"M_ComicID":      manual_comicid}
            myDB.upsert("annuals", newVals, newCtrl)
        if len(annchk) > 0:
            logger.info('Successfully integrated ' + str(len(annchk)) + ' annuals into the series: ' + annchk[0]['ComicName'])
        return


def updateissuedata(comicid, comicname=None, issued=None, comicIssues=None, calledfrom=None, issuechk=None, issuetype=None, SeriesYear=None, latestissueinfo=None):
    annualchk = []
    weeklyissue_check = []
    logger.fdebug('issuedata call references...')
    logger.fdebug('comicid:' + str(comicid))
    logger.fdebug('comicname:' + comicname)
    logger.fdebug('comicissues:' + str(comicIssues))
    logger.fdebug('calledfrom: ' + str(calledfrom))
    logger.fdebug('issuechk: ' + str(issuechk))
    logger.fdebug('latestissueinfo: ' + str(latestissueinfo))
    logger.fdebug('issuetype: ' + str(issuetype))
    #to facilitate independent calls to updateissuedata ONLY, account for data not available and get it.
    #chkType comes from the weeklypulllist - either 'annual' or not to distinguish annuals vs. issues
    if comicIssues is None:
        comic = cv.getComic(comicid, 'comic')
        if comic is None:
            logger.warn('Error retrieving from ComicVine - either the site is down or you are not using your own CV API key')
            return
        if comicIssues is None:
            comicIssues = comic['ComicIssues']
        if SeriesYear is None:
            SeriesYear = comic['ComicYear']
        if comicname is None:
            comicname = comic['ComicName']
    if issued is None:
        issued = cv.getComic(comicid, 'issue')
        if issued is None:
            logger.warn('Error retrieving from ComicVine - either the site is down or you are not using your own CV API key')
            return

    # poll against annuals here - to make sure annuals are uptodate.
    annualchk = annual_check(comicname, SeriesYear, comicid, issuetype, issuechk, annualchk)
    if annualchk is None:
        annualchk = []
    logger.fdebug('Finished Annual checking.')

    n = 0
    iscnt = int(comicIssues)
    issid = []
    issnum = []
    issname = []
    issdate = []
    issuedata = []
    int_issnum = []
    #let's start issue #'s at 0 -- thanks to DC for the new 52 reboot! :)
    latestiss = "0"
    latestdate = "0000-00-00"
    firstiss = "10000000"
    firstdate = "2099-00-00"
    #print ("total issues:" + str(iscnt))
    logger.info('Now adding/updating issues for ' + comicname)

    if iscnt > 0: #if a series is brand new, it wont have any issues/details yet so skip this part
        while (n <= iscnt):
            try:
                firstval = issued['issuechoice'][n]
                #print firstval
            except IndexError:
                break
            try:
                cleanname = helpers.cleanName(firstval['Issue_Name'])
            except:
                cleanname = 'None'
            issid = str(firstval['Issue_ID'])
            issnum = firstval['Issue_Number']
            #logger.info("issnum: " + str(issnum))
            issname = cleanname
            issdate = str(firstval['Issue_Date'])
            storedate = str(firstval['Store_Date'])
            if issnum.isdigit():
                int_issnum = int(issnum) * 1000
            else:
                if 'a.i.' in issnum.lower() or 'ai' in issnum.lower():
                    issnum = re.sub('\.', '', issnum)
                    #int_issnum = (int(issnum[:-2]) * 1000) + ord('a') + ord('i')
                if 'au' in issnum.lower():
                    int_issnum = (int(issnum[:-2]) * 1000) + ord('a') + ord('u')
                elif 'inh' in issnum.lower():
                    int_issnum = (int(issnum[:-4]) * 1000) + ord('i') + ord('n') + ord('h')
                elif 'now' in issnum.lower():
                    int_issnum = (int(issnum[:-4]) * 1000) + ord('n') + ord('o') + ord('w')
                elif 'mu' in issnum.lower():
                    int_issnum = (int(issnum[:-3]) * 1000) + ord('m') + ord('u')
                elif u'\xbd' in issnum:
                    int_issnum = .5 * 1000
                    logger.info('1/2 issue detected :' + issnum + ' === ' + str(int_issnum))
                elif u'\xbc' in issnum:
                    int_issnum = .25 * 1000
                elif u'\xbe' in issnum:
                    int_issnum = .75 * 1000
                elif u'\u221e' in issnum:
                    #issnum = utf-8 will encode the infinity symbol without any help
                    int_issnum = 9999999999 * 1000  # set 9999999999 for integer value of issue
                elif '.' in issnum or ',' in issnum:
                    if ',' in issnum: issnum = re.sub(',', '.', issnum)
                    issst = str(issnum).find('.')
                    #logger.fdebug("issst:" + str(issst))
                    if issst == 0:
                        issb4dec = 0
                    else:
                        issb4dec = str(issnum)[:issst]
                    #logger.fdebug("issb4dec:" + str(issb4dec))
                    #if the length of decimal is only 1 digit, assume it's a tenth
                    decis = str(issnum)[issst +1:]
                    #logger.fdebug("decis:" + str(decis))
                    if len(decis) == 1:
                        decisval = int(decis) * 10
                        issaftdec = str(decisval)
                    elif len(decis) == 2:
                        decisval = int(decis)
                        issaftdec = str(decisval)
                    else:
                        decisval = decis
                        issaftdec = str(decisval)
                    #if there's a trailing decimal (ie. 1.50.) and it's either intentional or not, blow it away.
                    if issaftdec[-1:] == '.':
                        logger.fdebug('Trailing decimal located within issue number. Irrelevant to numbering. Obliterating.')
                        issaftdec = issaftdec[:-1]
                    try:
#                        int_issnum = str(issnum)
                        int_issnum = (int(issb4dec) * 1000) + (int(issaftdec) * 10)
                    except ValueError:
                        logger.error('This has no issue # for me to get - Either a Graphic Novel or one-shot.')
                        updater.no_searchresults(comicid)
                        return
                else:
                    try:
                        x = float(issnum)
                        #validity check
                        if x < 0:
                            logger.info('I have encountered a negative issue #: ' + str(issnum) + '. Trying to accomodate.')
                            logger.fdebug('value of x is : ' + str(x))
                            int_issnum = (int(x) *1000) - 1
                        else: raise ValueError
                    except ValueError, e:
                        x = 0
                        tstord = None
                        issno = None
                        invchk = "false"
                        while (x < len(issnum)):
                            if issnum[x].isalpha():
                                #take first occurance of alpha in string and carry it through
                                tstord = issnum[x:].rstrip()
                                tstord = re.sub('[\-\,\.\+]', '', tstord).rstrip()
                                issno = issnum[:x].rstrip()
                                issno = re.sub('[\-\,\.\+]', '', issno).rstrip()
                                try:
                                    isschk = float(issno)
                                except ValueError, e:
                                    if len(issnum) == 1 and issnum.isalpha():
                                        logger.fdebug('detected lone alpha issue. Attempting to figure this out.')
                                        break
                                    logger.fdebug('[' + issno + '] invalid numeric for issue - cannot be found. Ignoring.')
                                    issno = None
                                    tstord = None
                                    invchk = "true"
                                break
                            x+=1

                        if tstord is not None and issno is not None:
                            a = 0
                            ordtot = 0
                            if len(issnum) == 1 and issnum.isalpha():
                                int_issnum = ord(tstord.lower())
                            else:
                                while (a < len(tstord)):
                                    ordtot += ord(tstord[a].lower())  #lower-case the letters for simplicty
                                    a+=1
                                int_issnum = (int(issno) * 1000) + ordtot
                        elif invchk == "true":
                            logger.fdebug('this does not have an issue # that I can parse properly.')
                            return
                        else:
                            if issnum == '9-5':
                                issnum = u'9\xbd'
                                logger.fdebug('issue: 9-5 is an invalid entry. Correcting to : ' + issnum)
                                int_issnum = (9 * 1000) + (.5 * 1000)
                            elif issnum == '112/113':
                                int_issnum = (112 * 1000) + (.5 * 1000)
                            else:
                                logger.error(issnum + ' this has an alpha-numeric in the issue # which I cannot account for.')
                                return
            #get the latest issue / date using the date.
            #logger.fdebug('issue : ' + str(issnum))
            #logger.fdebug('latest date: ' + str(latestdate))
            #logger.fdebug('first date: ' + str(firstdate))
            #logger.fdebug('issue date: ' + str(firstval['Issue_Date']))
            if firstval['Issue_Date'] >= latestdate:
                #logger.fdebug('date check hit for issue date > latestdate')
                if int_issnum > helpers.issuedigits(latestiss):
                    #logger.fdebug('assigning latest issue to : ' + str(issnum))
                    latestiss = issnum
                latestdate = str(firstval['Issue_Date'])
            if firstval['Issue_Date'] < firstdate and firstval['Issue_Date'] != '0000-00-00':
                firstiss = issnum
                firstdate = str(firstval['Issue_Date'])

            if issuechk is not None and issuetype == 'series':
                logger.fdebug('comparing ' + str(issuechk) + ' .. to .. ' + str(int_issnum))
                if issuechk == int_issnum:
                    weeklyissue_check.append({"Int_IssueNumber":    int_issnum,
                                              "Issue_Number":       issnum,
                                              "IssueDate":          issdate,
                                              "ReleaseDate":        storedate,
                                              "ComicID":            comicid,
                                              "IssueID":            issid})

            issuedata.append({"ComicID":            comicid,
                              "IssueID":            issid,
                              "ComicName":          comicname,
                              "IssueName":          issname,
                              "Issue_Number":       issnum,
                              "IssueDate":          issdate,
                              "ReleaseDate":        storedate,
                              "Int_IssueNumber":    int_issnum,
                              "ImageURL":           firstval['Image'],
                              "ImageURL_ALT":       firstval['ImageALT']})

            n+=1

    if calledfrom == 'futurecheck' and len(issuedata) == 0:
        logger.fdebug('This is a NEW series with no issue data - skipping issue updating for now, and assigning generic information so things don\'t break')
        latestdate = latestissueinfo[0]['latestdate']   # if it's from futurecheck, issuechk holds the latestdate for the given issue
        latestiss = latestissueinfo[0]['latestiss']
        lastpubdate = 'Present'
        publishfigure = str(SeriesYear) + ' - ' + str(lastpubdate)
    else:
        if calledfrom == 'weeklycheck':
            if len(issuedata) >= 1 and not calledfrom  == 'dbupdate':
                logger.fdebug('initiating issue updating - info & status')
                issue_collection(issuedata, nostatus='False')
            else:
                logger.fdebug('initiating issue updating - just the info')
                issue_collection(issuedata, nostatus='True')

        styear = str(SeriesYear)

        if firstdate[5:7] == '00':
            stmonth = "?"
        else:
            stmonth = helpers.fullmonth(firstdate[5:7])

        ltyear = re.sub('/s', '', latestdate[:4])
        if latestdate[5:7] == '00':
            ltmonth = "?"
        else:
            ltmonth = helpers.fullmonth(latestdate[5:7])

        #try to determine if it's an 'actively' published comic from above dates
        #threshold is if it's within a month (<55 days) let's assume it's recent.
        try:
            c_date = datetime.date(int(latestdate[:4]), int(latestdate[5:7]), 1)
        except:
            logger.error('Cannot determine Latest Date for given series. This is most likely due to an issue having a date of : 0000-00-00')
            latestdate = str(SeriesYear) + '-01-01'
            logger.error('Setting Latest Date to be ' + str(latestdate) + '. You should inform CV that the issue data is stale.')
            c_date = datetime.date(int(latestdate[:4]), int(latestdate[5:7]), 1)

        n_date = datetime.date.today()
        recentchk = (n_date - c_date).days

        if recentchk <= 55:
            lastpubdate = 'Present'
        else:
            lastpubdate = str(ltmonth) + ' ' + str(ltyear)

        if stmonth == '?' and ('?' in lastpubdate and '0000' in lastpubdate):
            lastpubdate = 'Present'
            newpublish = True
            publishfigure = str(styear) + ' - ' + str(lastpubdate)
        else:
            newpublish = False
            publishfigure = str(stmonth) + ' ' + str(styear) + ' - ' + str(lastpubdate)

        if stmonth == '?' and styear == '?' and lastpubdate =='0000' and comicIssues == '0':
            logger.info('No available issue data - I believe this is a NEW series.')
            latestdate = latestissueinfo[0]['latestdate']
            latestiss = latestissueinfo[0]['latestiss']
            lastpubdate = 'Present'
            publishfigure = str(SeriesYear) + ' - ' + str(lastpubdate)



    controlValueStat = {"ComicID":     comicid}

    newValueStat = {"Status":          "Active",
                    "Total":           comicIssues,
                    "ComicPublished":  publishfigure,
                    "NewPublish":      newpublish,
                    "LatestIssue":     latestiss,
                    "LatestDate":      latestdate,
                    "LastUpdated":     helpers.now()
                   }

    myDB = db.DBConnection()
    myDB.upsert("comics", newValueStat, controlValueStat)

    importantdates = {}
    importantdates['LatestIssue'] = latestiss
    importantdates['LatestDate'] = latestdate
    importantdates['LastPubDate'] = lastpubdate
    importantdates['SeriesStatus'] = 'Active'

    if calledfrom == 'weeklycheck':
        return weeklyissue_check

    elif len(issuedata) >= 1 and not calledfrom  == 'dbupdate':
        return {'issuedata': issuedata, 
                'annualchk': annualchk,
                'importantdates': importantdates,
                'nostatus':  False}

    elif calledfrom == 'dbupdate':
        return {'issuedata': issuedata,
                'annualchk': annualchk,
                'importantdates': importantdates,
                'nostatus':  True}

    else:
        return importantdates

def annual_check(ComicName, SeriesYear, comicid, issuetype, issuechk, annualslist):
        annualids = []   #to be used to make sure an ID isn't double-loaded
        annload = []
        anncnt = 0

        nowdate = datetime.datetime.now()
        now_week = datetime.datetime.strftime(nowdate, "%Y%U")

        myDB = db.DBConnection()

        annual_load = myDB.select('SELECT * FROM annuals WHERE ComicID=?', [comicid])
        logger.fdebug('checking annual db')
        for annthis in annual_load:
            if not any(d['ReleaseComicID'] == annthis['ReleaseComicID'] for d in annload):
                #print 'matched on annual'
                 annload.append({
                     'ReleaseComicID':   annthis['ReleaseComicID'],
                     'ReleaseComicName': annthis['ReleaseComicName'],
                     'ComicID':          annthis['ComicID'],
                     'ComicName':        annthis['ComicName']
                     })

        if annload is None:
            pass
        else:
            for manchk in annload:
                if manchk['ReleaseComicID'] is not None or manchk['ReleaseComicID'] is not None:  #if it exists, then it's a pre-existing add
                    #print str(manchk['ReleaseComicID']), comic['ComicName'], str(SeriesYear), str(comicid)
                    annualslist += manualAnnual(manchk['ReleaseComicID'], ComicName, SeriesYear, comicid, manualupd=True)
                annualids.append(manchk['ReleaseComicID'])

        annualcomicname = re.sub('[\,\:]', '', ComicName)

        if annualcomicname.lower().startswith('the'):
            annComicName = annualcomicname[4:] + ' annual'
        else:
            annComicName = annualcomicname + ' annual'
        mode = 'series'

        annualyear = SeriesYear  # no matter what, the year won't be less than this.
        logger.fdebug('[IMPORTER-ANNUAL] - Annual Year:' + str(annualyear))
        sresults = mb.findComic(annComicName, mode, issue=None)
        type='comic'

        annual_types_ignore = {'paperback', 'collecting', 'reprints', 'collected edition', 'print edition', 'tpb', 'available in print', 'collects'}

        if len(sresults) == 1:
            logger.fdebug('[IMPORTER-ANNUAL] - 1 result')
        if len(sresults) > 0:
            logger.fdebug('[IMPORTER-ANNUAL] - there are ' + str(len(sresults)) + ' results.')
            num_res = 0
            while (num_res < len(sresults)):
                sr = sresults[num_res]
                #logger.fdebug("description:" + sr['description'])
                for x in annual_types_ignore:
                    if x in sr['description'].lower():
                        test_id_position = sr['description'].find(comicid)
                        if test_id_position >= sr['description'].lower().find(x) or test_id_position == -1:
                            logger.fdebug('[IMPORTER-ANNUAL] - tradeback/collected edition detected - skipping ' + str(sr['comicid']))
                            continue

                if comicid in sr['description']:
                    logger.fdebug('[IMPORTER-ANNUAL] - ' + str(comicid) + ' found. Assuming it is part of the greater collection.')
                    issueid = sr['comicid']
                    logger.fdebug('[IMPORTER-ANNUAL] - ' + str(issueid) + ' added to series list as an Annual')
                    if issueid in annualids:
                        logger.fdebug('[IMPORTER-ANNUAL] - ' + str(issueid) + ' already exists within current annual list for series.')
                        num_res+=1 # need to manually increment since not a for-next loop
                        continue
                    issued = cv.getComic(issueid, 'issue')
                    if len(issued) is None or len(issued) == 0:
                        logger.fdebug('[IMPORTER-ANNUAL] - Could not find any annual information...')
                        pass
                    else:
                        n = 0
                        if int(sr['issues']) == 0 and len(issued['issuechoice']) == 1:
                            sr_issues = 1
                        else:
                            if int(sr['issues']) != len(issued['issuechoice']):
                                sr_issues = len(issued['issuechoice'])
                            else:
                                sr_issues = sr['issues']
                        logger.fdebug('[IMPORTER-ANNUAL] - There are ' + str(sr_issues) + ' annuals in this series.')
                        while (n < int(sr_issues)):
                            try:
                               firstval = issued['issuechoice'][n]
                            except IndexError:
                               break
                            try:
                               cleanname = helpers.cleanName(firstval['Issue_Name'])
                            except:
                                cleanname = 'None'
                            issid = str(firstval['Issue_ID'])
                            issnum = str(firstval['Issue_Number'])
                            issname = cleanname
                            issdate = str(firstval['Issue_Date'])
                            stdate = str(firstval['Store_Date'])
                            int_issnum = helpers.issuedigits(issnum)

                            iss_exists = myDB.selectone('SELECT * from annuals WHERE IssueID=?', [issid]).fetchone()
                            if iss_exists is None:
                                if stdate == '0000-00-00':
                                    dk = re.sub('-', '', issdate).strip()
                                else:
                                    dk = re.sub('-', '', stdate).strip() # converts date to 20140718 format
                                if dk == '00000000':
                                     logger.warn('Issue Data is invalid for Issue Number %s. Marking this issue as Skipped' % firstval['Issue_Number'])
                                     astatus = "Skipped"
                                else:
                                    datechk = datetime.datetime.strptime(dk, "%Y%m%d")
                                    issue_week = datetime.datetime.strftime(datechk, "%Y%U")
                                    if mylar.CONFIG.AUTOWANT_ALL:
                                        astatus = "Wanted"
                                    elif issue_week >= now_week and mylar.CONFIG.AUTOWANT_UPCOMING is True:
                                        astatus = "Wanted"
                                    else:
                                        astatus = "Skipped"
                            else:
                                astatus = iss_exists['Status']

                            annualslist.append({"Issue_Number":     issnum,
                                                "Int_IssueNumber":  int_issnum,
                                                "IssueDate":        issdate,
                                                "ReleaseDate":      stdate,
                                                "IssueName":        issname,
                                                "ComicID":          comicid,
                                                "IssueID":          issid,
                                                "ComicName":        ComicName,
                                                "ReleaseComicID":   re.sub('4050-', '', firstval['Comic_ID']).strip(),
                                                "ReleaseComicName": sr['name'],
                                                "Status":           astatus})

                            #myDB.upsert("annuals", newVals, newCtrl)

                            # --- don't think this does anything since the value isn't returned in this module
                            #if issuechk is not None and issuetype == 'annual':
                            #    #logger.fdebug('[IMPORTER-ANNUAL] - Comparing annual ' + str(issuechk) + ' .. to .. ' + str(int_issnum))
                            #    if issuechk == int_issnum:
                            #        weeklyissue_check.append({"Int_IssueNumber":    int_issnum,
                            #                                  "Issue_Number":       issnum,
                            #                                  "IssueDate":          issdate,
                            #                                  "ReleaseDate":        stdate})

                            n+=1
                num_res+=1
            manualAnnual(annchk=annualslist)
            return annualslist

        elif len(sresults) == 0 or len(sresults) is None:
            logger.fdebug('[IMPORTER-ANNUAL] - No results, removing the year from the agenda and re-querying.')
            sresults = mb.findComic(annComicName, mode, issue=None)
            if len(sresults) == 1:
                sr = sresults[0]
                logger.fdebug('[IMPORTER-ANNUAL] - ' + str(comicid) + ' found. Assuming it is part of the greater collection.')
            else:
                resultset = 0
        else:
            logger.fdebug('[IMPORTER-ANNUAL] - Returning results to screen - more than one possibility')
            for sr in sresults:
                if annualyear < sr['comicyear']:
                    logger.fdebug('[IMPORTER-ANNUAL] - ' + str(annualyear) + ' is less than ' + str(sr['comicyear']))
                if int(sr['issues']) > (2013 - int(sr['comicyear'])):
                    logger.fdebug('[IMPORTER-ANNUAL] - Issue count is wrong')

         #if this is called from the importer module, return the weeklyissue_check
