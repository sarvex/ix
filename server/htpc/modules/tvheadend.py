#!/usr/bin/env python
# -*- coding: utf-8 -*-

import cherrypy
import htpc
import logging
import urllib2
import urllib
import base64
import json
from cherrypy.lib.auth2 import require


class TVHeadend(object):
    def __init__(self):
        self.logger = logging.getLogger('modules.tvheadend')
        htpc.MODULES.append({
            'name': 'TVHeadend',
            'id': 'tvheadend',
            'test': htpc.WEBDIR + 'TVHeadend/ping',
            'fields': [
                {'type': 'bool', 'label': 'Enable', 'name': 'tvheadend_enable'},
                {'type': 'text', 'label': 'Menu name', 'name': 'tvheadend_name'},
                {'type': 'text', 'label': 'IP / Host *', 'name': 'tvheadend_host'},
                {'type': 'text', 'label': 'Port *', 'name': 'tvheadend_port'},
                {'type': 'text', 'label': 'Username', 'name': 'tvheadend_username'},
                {'type': 'password', 'label': 'Password', 'name': 'tvheadend_password'},
                {'type': 'text', 'label': 'Reverse proxy link', 'placeholder': '', 'desc': 'Reverse proxy link, e.g. https://domain.com/tvh', 'name': 'tvheadend_reverse_proxy_link'},

            ]
        })

    @cherrypy.expose()
    @require()
    def index(self):
        return htpc.LOOKUP.get_template("tvheadend.html").render(scriptname="tvheadend", webinterface=self.webinterface())

    def webinterface(self):
        ip = htpc.settings.get('tvheadend_host')
        port = htpc.settings.get('tvheadend_port')
        url = 'http://%s:%s/' % (ip, port)

        if htpc.settings.get('tvheadend_reverse_proxy_link'):
            url = htpc.settings.get('tvheadend_reverse_proxy_link')

        return url

    @cherrypy.expose()
    @require()
    @cherrypy.tools.json_out()
    def GetEPG(self, strLimit="300", strChannel=""):
        return self.fetch("api/epg/events/grid", {'limit': strLimit, 'start': "0", 'channel': strChannel})

    @cherrypy.expose()
    @require()
    @cherrypy.tools.json_out()
    def GetChannels(self):
        #return self.fetch("api/channel/grid", { 'dir': 'ASC', 'sort': 'tags', 'limit': 1000 })
        return self.fetch("api/channel/grid", { 'sort': 'number', 'limit': 1000 })

    @cherrypy.expose()
    @require()
    @cherrypy.tools.json_out()
    def GetChannelTags(self):
        return self.fetch("api/channeltag/list", {'op': 'listTags'})
 
    @cherrypy.expose()
    @require()
    @cherrypy.tools.json_out()
    def DVRAdd(self, strEventID=""):
        return self.fetch("api/dvr/entry/create_by_event", {'event_id': strEventID, 'config_uuid': ''})

    @cherrypy.expose()
    @require()
    @cherrypy.tools.json_out()
    def DVRDel(self, strEntryID=""):
        return self.fetch("api/idnode/delete", {'uuid': strEntryID})

    @cherrypy.expose()
    @require()
    @cherrypy.tools.json_out()
    def DVRList(self, strType=""):
        return self.fetch("api/dvr/entry/grid_" + strType, None)
        #return self.fetch("dvrlist_" + strType, None)

    def fetch(self, strQuery, rgpData):
        rgpHeaders = {}
        username = htpc.settings.get("tvheadend_username", "")
        password = htpc.settings.get("tvheadend_password", "")

        if username and password:
            rgpHeaders['Authorization'] = 'Basic %s' % base64.encodestring('%s:%s' % (username, password)).strip('\n')

        # Lame debug to get as much info as possible
        self.logger.debug('strQuery: %s' % strQuery)
        self.logger.debug('rgpData: %s' % rgpData)

        strResponse = None
        strData = None

        if rgpData is not None:
            strData = urllib.urlencode(rgpData)

        url = "http://%s:%s/%s" % (htpc.settings.get("tvheadend_host", ""), htpc.settings.get("tvheadend_port", ""), strQuery)
        self.logger.debug('url: %s' % url)
        self.logger.debug('encoded: %s' % strData)
        try:

            pRequest = urllib2.Request("http://%s:%s/%s" % (htpc.settings.get("tvheadend_host", ""), htpc.settings.get("tvheadend_port", ""), strQuery), data = strData, headers = rgpHeaders)
            strResponse = urllib2.urlopen(pRequest).read()
            return json.loads(strResponse)
        except Exception as e:
            self.logger.error('%s %s failed error: %s' % strQuery, rgpData, e)
