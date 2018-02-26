#!/usr/bin/env python

import os
import sys
import time
import feedparser
import re
import logger
import mylar
import unicodedata
import urllib

def Startit(searchName, searchIssue, searchYear, ComicVersion, IssDateFix):
    #searchName = "Uncanny Avengers"
    #searchIssue = "01"
    #searchYear = "2012"
    if searchName.lower().startswith('the '):
        searchName = searchName[4:]
    cName = searchName
    #clean up searchName due to webparse.
    searchName = searchName.replace("%20", " ")
    if "," in searchName:
        searchName = searchName.replace(",", "")
    #logger.fdebug("name:" + str(searchName))
    #logger.fdebug("issue:" + str(searchIssue))
    #logger.fdebug("year:" + str(searchYear))
    encodeSearch = urllib.quote_plus(searchName)
    splitSearch = encodeSearch.split(" ")

    joinSearch = "+".join(splitSearch) +"+" +searchIssue
    searchIsOne = "0" +searchIssue
    searchIsTwo = "00" +searchIssue

    if mylar.CONFIG.PREFERRED_QUALITY == 1: joinSearch = joinSearch + " .cbr"
    elif mylar.CONFIG.PREFERRED_QUALITY == 2: joinSearch = joinSearch + " .cbz"

    if "-" in searchName:
        searchName = searchName.replace("-", '((\\s)?[-:])?(\\s)?')

    regexName = searchName.replace(" ", '((\\s)?[-:])?(\\s)?')


    #logger.fdebug('searchName:' + searchName)
    #logger.fdebug('regexName:' + regexName)

    if mylar.CONFIG.USE_MINSIZE:
        size_constraints = "minsize=" + str(mylar.CONFIG.MINSIZE)
    else:
        size_constraints = "minsize=10"

    if mylar.CONFIG.USE_MAXSIZE:
        size_constraints = size_constraints + "&maxsize=" + str(mylar.CONFIG.MAXSIZE)

    if mylar.CONFIG.USENET_RETENTION != None:
        max_age = "&age=" + str(mylar.CONFIG.USENET_RETENTION)

    feeds = []
    feed1 = "http://nzbindex.nl/rss/alt.binaries.comics.dcp/?sort=agedesc&" + str(size_constraints) + str(max_age) + "&dq=%s&max=50&more=1" %joinSearch
    feeds.append(feedparser.parse("http://nzbindex.nl/rss/alt.binaries.comics.dcp/?sort=agedesc&" + str(size_constraints) + str(max_age) + "&dq=%s&max=50&more=1" %joinSearch))
    time.sleep(3)
    if mylar.CONFIG.ALTEXPERIMENTAL:
        feed2 = "http://nzbindex.nl/rss/?dq=%s&g[]=41&g[]=510&sort=agedesc&hidespam=0&max=&more=1" %joinSearch
        feeds.append(feedparser.parse("http://nzbindex.nl/rss/?dq=%s&g[]=41&g[]=510&sort=agedesc&hidespam=0&max=&more=1" %joinSearch))
        time.sleep(3)

    entries = []
    mres = {}
    tallycount = 0

    for feed in feeds:
        totNum = len(feed.entries)
        tallycount += len(feed.entries)

        #keyPair = {}
        keyPair = []
        regList = []
        countUp = 0

        #logger.fdebug(str(totNum) + " results")

        while countUp < totNum:
     	    urlParse = feed.entries[countUp].enclosures[0]
	    #keyPair[feed.entries[countUp].title] = feed.entries[countUp].link
	    #keyPair[feed.entries[countUp].title] = urlParse["href"]
            keyPair.append({"title":     feed.entries[countUp].title,
                            "link":      urlParse["href"],
                            "length":    urlParse["length"],
                            "pubdate":   feed.entries[countUp].updated})
            countUp=countUp +1
        #logger.fdebug('keypair: ' + str(keyPair))


        # thanks to SpammyHagar for spending the time in compiling these regEx's!

        regExTest=""

        regEx = "(%s\\s*(0)?(0)?%s\\s*\\(%s\\))" %(regexName, searchIssue, searchYear)
        regExOne = "(%s\\s*(0)?(0)?%s\\s*\\(.*?\\)\\s*\\(%s\\))" %(regexName, searchIssue, searchYear)

        #Sometimes comics aren't actually published the same year comicVine says - trying to adjust for these cases
        regExTwo = "(%s\\s*(0)?(0)?%s\\s*\\(%s\\))" %(regexName, searchIssue, int(searchYear) +1)
        regExThree = "(%s\\s*(0)?(0)?%s\\s*\\(%s\\))" %(regexName, searchIssue, int(searchYear) -1)
        regExFour = "(%s\\s*(0)?(0)?%s\\s*\\(.*?\\)\\s*\\(%s\\))" %(regexName, searchIssue, int(searchYear) +1)
        regExFive = "(%s\\s*(0)?(0)?%s\\s*\\(.*?\\)\\s*\\(%s\\))" %(regexName, searchIssue, int(searchYear) -1)

        regexList=[regEx, regExOne, regExTwo, regExThree, regExFour, regExFive]

        except_list=['releases', 'gold line', 'distribution', '0-day', '0 day']

        for entry in keyPair:
            title = entry['title']
            #logger.fdebug("titlesplit: " + str(title.split("\"")))
            splitTitle = title.split("\"")
            noYear = 'False'
            _digits = re.compile('\d')

            for subs in splitTitle:
                #logger.fdebug('sub:' + subs)
                regExCount = 0
                if len(subs) >= len(cName) and not any(d in subs.lower() for d in except_list) and bool(_digits.search(subs)) is True:
                #Looping through dictionary to run each regEx - length + regex is determined by regexList up top.
#                while regExCount < len(regexList):
#                    regExTest = re.findall(regexList[regExCount], subs, flags=re.IGNORECASE)
#                    regExCount = regExCount +1
#                    if regExTest:
#                        logger.fdebug(title)
#                        entries.append({
#                                  'title':   subs,
#                                  'link':    str(link)
#                                  })
                    # this will still match on crap like 'For SomeSomayes' especially if the series length < 'For SomeSomayes'
                    if subs.lower().startswith('for'):
                        if cName.lower().startswith('for'):
                            pass
                        else:
                            #this is the crap we ignore. Continue (commented else, as it spams the logs)
                            #logger.fdebug('this starts with FOR : ' + str(subs) + '. This is not present in the series - ignoring.')
                            continue
                    #logger.fdebug('match.')
                    if IssDateFix != "no":
                        if IssDateFix == "01" or IssDateFix == "02": ComicYearFix = str(int(searchYear) - 1)
                        else: ComicYearFix = str(int(searchYear) + 1)
                    else:
                        ComicYearFix = searchYear

                    if searchYear not in subs and ComicYearFix not in subs:
                        noYear = 'True'
                        noYearline = subs

                    if (searchYear in subs or ComicYearFix in subs) and noYear == 'True':
                        #this would occur on the next check in the line, if year exists and
                        #the noYear check in the first check came back valid append it
                        subs = noYearline + ' (' + searchYear + ')'
                        noYear = 'False'

                    if noYear == 'False':

                        entries.append({
                                  'title':     subs,
                                  'link':      entry['link'],
                                  'pubdate':   entry['pubdate'],
                                  'length':    entry['length']
                                  })
                        break  # break out so we don't write more shit.

#    if len(entries) >= 1:
    if tallycount >= 1:
        mres['entries'] = entries
        return mres
    else:
        logger.fdebug("No Results Found")
        return "no results"
