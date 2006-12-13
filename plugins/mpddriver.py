#!/usr/bin/env python
# Copyright (C) 2006 Adam Olsen <arolsen@gmail.com>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.

import gtk, plugins, gobject, mpdclient2, re
from xl import xlmisc, common, media, tracks

PLUGIN_NAME = "MPD Driver"
PLUGIN_AUTHORS = ['Adam Olsen <arolsen@gmail.com>']
PLUGIN_VERSION = '0.1'
PLUGIN_DESCRIPTION = r"""An MPD driver for the Devices panel"""
PLUGIN_ENABLED = False
PLUGIN_ICON = None

TIMER_ID = None
PLUGIN = None
MPD = None

class MPDTrack(plugins.DriverTrack):
    def __init__(self, *info):
        plugins.DriverTrack.__init__(self, *info)
        self.mpd_track = None
        self.mpd = MPD
        self.next = None

    def play(self, next_func=None): 
        if next_func: self.next = next_func

        if not self.is_paused():
            self.mpd.clear()
            self.mpd.add(self.loc.replace('device://', ''))
            self.mpd.play(0)
        else:
            self.mpd.play()
        self.playing = 1

    def current_position(self):
        status = self.mpd.status()
        if status.has_key('time'):
            current = float(status['time'].replace(":", "."))
            return current / self.duration * 100.0 

    def get_id(self):
        for i, item in enumerate(self.mpd.playlistinfo()):            
            if item.file == self.loc.replace('device://', ''):
                return int(item.pos)

        return -1

    id = property(get_id)

    def seek(self, value):
        xlmisc.log("mpd seeking to %s" % value)
        self.mpd.seek(self.id, int(value)) 

    def pause(self):
        self.playing = 2
        self.mpd.pause(1)

    def stop(self):
        self.playing = False
        self.mpd.stop()

class MPDDriver(object):
    def __init__(self):
        self.mpd = None

    def connect(self, stuff):
        global MPD, TIMER_ID
        self.mpd = mpdclient2.connect()
        MPD = self.mpd
        status = self.mpd.status()
        self.mpd.random(0)
        self.mpd.repeat(0)
        self.all = self.load_tracks()
        APP.device_panel.all = self.all
        if status.state == 'play' or status.state == 'pause':
            if APP.current_track:   
                APP.current_track.stop()
            APP.current_track = APP.device_panel.all.for_path('device://%s' %
                self.mpd.currentsong()['file'])
            if status.state == 'play':
                APP.current_track.playing = 1
            else:
                APP.current_track.playing = 2
            APP.update_track_information()

        songs = tracks.TrackData()
        for item in self.mpd.playlistinfo():
            song = self.all.for_path('device://%s' % item.file)
            songs.append(song)

        APP.new_page("MPD Playlist", songs)
        TIMER_ID = gobject.timeout_add(1000, self.ping)

    def disconnect(self):
        """
            Disconnects the driver
        """
        if TIMER_ID:
            gobject.source_remove(TIMER_ID)
            TIMER_ID = None

    def load_tracks(self):
        songs = tracks.TrackData()
        for mtrack in self.mpd.listallinfo():
            if mtrack.type == 'file':
                song = MPDTrack('device://%s' % mtrack.file)
                if hasattr(mtrack, 'time'):
                    song.length = mtrack.time

                for item in ('artist', 'album', 'title', 'track'):
                    if hasattr(mtrack, item):
                        setattr(song, item, getattr(mtrack, item))

                song.mpd_track = mtrack
                songs.append(song)

        songs.sort(self.sortit)
        return songs

    def search_tracks(self, keyword, all):
        return tracks.search(APP, all, keyword)

    def sortit(self, a, b):
        first = a.artist.lower()
        second = b.artist.lower()

        if first > second: return 1
        elif first == second: return 0
        elif first < second: return -1

    def ping(self):
        if self.mpd:
            self.mpd.ping()

        # check to see if the current track has stopped, and if it has, go to
        # the next track
        track = APP.current_track
        if isinstance(track, MPDTrack):
            if track.is_playing():
                status = self.mpd.status()
                if not status.has_key('time'):
                    if track.next:
                        track.next()
        return True

def initialize():
    global TIMER_ID, PLUGIN
    
    PLUGIN = MPDDriver()
    APP.device_panel.add_driver(PLUGIN, PLUGIN_NAME)

    return True

def destroy():
    global TIMER_ID, PLUGIN

    APP.device_panel.remove_driver(PLUGIN)

    if TIMER_ID:
        gobject.source_remove(TIMER_ID)
        TIMER_ID = None

    if PLUGIN:
        PLUGIN = None
