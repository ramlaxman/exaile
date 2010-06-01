# -*- coding: utf-8 -*-
# Copyright (C) 2008-2010 Adam Olsen
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2, or (at your option)
# any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.
#
#
# The developers of the Exaile media player hereby grant permission
# for non-GPL compatible GStreamer and Exaile plugins to be used and
# distributed together with GStreamer and Exaile. This permission is
# above and beyond the permissions granted by the GPL license by which
# Exaile is covered. If you modify this code, you may extend this
# exception to your version of the code, but you are not obligated to
# do so. If you do not wish to do so, delete this exception statement
# from your version.

import glib
import gtk
import pango

from xl import (
    event,
    main,
    settings,
    trax,
    xdg
)
from xl.formatter import (
    TrackFormatter,
    LengthTagFormatter,
    TrackNumberTagFormatter
)
from xl.nls import gettext as _
from xlgui import covers, icons

class TrackInfoPane(gtk.Alignment):
    """
        Displays cover art and track data
    """
    def __init__(self, display_progress=False, auto_update=False):
        """
            :param display_progress: Toggles the display
                of the playback indicator and progress bar
                if the current track is played
            :param auto_update: Toggles the automatic
                following of playback state and track changes
        """
        gtk.Alignment.__init__(self, xscale=1, yscale=1)

        builder = gtk.Builder()
        builder.add_from_file(xdg.get_data_path(
            'ui', 'widgets', 'track_info.ui'))

        info_box = builder.get_object('info_box')
        info_box.reparent(self)

        self._display_progress = display_progress
        self._auto_update = auto_update
        self._timer = None
        self.player = None
        self._track = None
        self._formatter = TrackFormatter(
            _('<span size="x-large" weight="bold">$title</span>\n'
              'by ${artist:compilate}\n'
              'from $album')
        )

        self.cover_image = builder.get_object('cover_image')
        self.info_label = builder.get_object('info_label')
        self.action_area = builder.get_object('action_area')
        self.progress_box = builder.get_object('progress_box')
        self.playback_image = builder.get_object('playback_image')
        self.progressbar = builder.get_object('progressbar')

        if self._auto_update:
            event.add_callback(self.on_playback_player_end,
                'playback_player_end')
            event.add_callback(self.on_playback_track_start,
                'playback_track_start')
            event.add_callback(self.on_playback_toggle_pause,
                'playback_toggle_pause')
            event.add_callback(self.on_playback_error,
                'playback_error')
            event.add_callback(self.on_track_tags_changed,
                'track_tags_changed')

        try:
            exaile = main.exaile()
        except AttributeError:
            event.add_callback(self.on_exaile_loaded, 'exaile_loaded')
        else:
            self.on_exaile_loaded('exaile_loaded', exaile, None)

    def get_info_format(self):
        """
            Gets the current format used
            to display the track data

            :rtype: string
        """
        return self._formatter.get_property('format')

    def set_info_format(self, format):
        """
            Sets the format used to display the track data

            :param format: the format, see the documentation
                of :class:`string.Template` for details
            :type format: string
        """
        self._formatter.set_property('format', format)

    def get_display_progress(self):
        """
            Returns whether the progress indicator
            is currently visible or not
        """
        return self._display_progress

    def set_display_progress(self, display_progress):
        """
            Shows or hides the progress indicator. The
            indicator will not be displayed if the
            currently displayed track is not playing.

            :param display_progress: Whether to show
                or hide the progress indicator
            :type display_progress: bool
        """
        self._display_progress = display_progress

    def set_track(self, track):
        """
            Updates the data displayed in the info pane

            :param track: A track to take the data from,
                clears the info pane if track is None
            :type track: :class:`xl.trax.Track`
        """
        if track is None:
            self.clear()
            return

        self._track = track

        image_data = covers.MANAGER.get_cover(track, use_default=True)
        width = settings.get_option('gui/cover_width', 100)
        pixbuf = icons.MANAGER.pixbuf_from_data(image_data, (width, width))
        self.cover_image.set_from_pixbuf(pixbuf)

        self.info_label.set_markup(self._formatter.format(track, markup_escape=True))

        if self._display_progress:
            state = self.player.get_state()

            if track == self.player.current and not self.player.is_stopped():
                stock_id = gtk.STOCK_MEDIA_PLAY
                
                if self.player.is_paused():
                    stock_id = gtk.STOCK_MEDIA_PAUSE

                self.playback_image.set_from_stock(stock_id,
                    gtk.ICON_SIZE_SMALL_TOOLBAR)

                self.__show_progress()
            else:
                self.__hide_progress()

    def clear(self):
        """
            Resets the info pane
        """
        pixbuf = icons.MANAGER.pixbuf_from_data(
            covers.MANAGER.get_default_cover())
        self.cover_image.set_from_pixbuf(pixbuf)
        self.info_label.set_markup('<span size="x-large" '
            'weight="bold">%s</span>' % _('Not Playing'))

        if self._display_progress:
            self.__hide_progress()

    def get_action_area(self):
        """
            Retrieves the action area
            at the end of the pane

            :rtype: :class:`gtk.VBox`
        """
        return self.action_area

    def __enable_timer(self):
        """
            Enables the timer, if not already
        """
        if self._timer is not None:
            return

        milliseconds = settings.get_option(
            'gui/progress_update/millisecs', 1000)

        if milliseconds % 1000 == 0:
            self._timer = glib.timeout_add_seconds(milliseconds / 1000,
                self.__update_progress)
        else:
            self._timer = glib.timeout_add(milliseconds,
                self.__update_progress)

    def __disable_timer(self):
        """
            Disables the timer, if not already
        """
        if self._timer is None:
            return

        glib.source_remove(self._timer)
        self._timer = None

    def __show_progress(self):
        """
            Shows the progress area and enables
            updates of the progress bar
        """
        self.__enable_timer()
        self.progress_box.set_no_show_all(False)
        self.progress_box.set_property('visible', True)

    def __hide_progress(self):
        """
            Hides the progress area and disables
            updates of the progress bar
        """
        self.progress_box.set_property('visible', False)
        self.progress_box.set_no_show_all(True)
        self.__disable_timer()

    def __update_progress(self):
        """
            Updates the state of the progress bar
        """
        track = self.player.current

        if track is not self._track:
            self.__hide_progress()
            return False

        fraction = 0
        text = _('Not Playing')

        if track is not None:
            total = track.get_tag_raw('__length')

            if total is not None:
                current = self.player.get_time()
                text = '%d:%02d / %d:%02d' % \
                    (current // 60, current % 60,
                     total // 60, total % 60)

                if self.player.is_paused():
                    self.__disable_timer()
                    fraction = self.progressbar.get_fraction()
                elif self.player.is_playing():
                    self.__enable_timer()
                    fraction = self.player.get_progress()
            elif not track.is_local():
                self.__disable_timer()
                text = _('Streaming...')

        self.progressbar.set_fraction(fraction)
        self.progressbar.set_text(text)

        return True

    def on_playback_player_end(self, event, player, track):
        """
            Clears the info pane on playback end
        """
        self.clear()

    def on_playback_track_start(self, event, player, track):
        """
            Updates the info pane on track start
        """
        self.set_track(track)

    def on_playback_toggle_pause(self, event, player, track):
        """
            Updates the info pane on playback pause/resume
        """
        self.set_track(track)

    def on_playback_error(self, event, player, track):
        """
            Clears the info pane on playback errors
        """
        self.clear()

    def on_track_tags_changed(self, event, track, tag):
        """
            Updates the info pane on tag changes
        """
        if self.player is not None and \
           not self.player.is_stopped() and \
           track is self._track:
            self.set_track(track)

    def on_exaile_loaded(self, e, exaile, nothing):
        """
            Sets up references after controller is loaded
        """
        self.player = exaile.player

        current_track = self.player.current

        if self._auto_update and current_track is not None:
            self.set_track(current_track)
        else:
            self.clear()

        event.remove_callback(self.on_exaile_loaded, 'exaile_loaded')

# TODO: Use single info label and formatter
class TrackListInfoPane(gtk.Alignment):
    """
        Displays cover art and data about a list of tracks
    """
    def __init__(self, display_tracklist=False):
        """
            :param display_tracklist: Whether to display
                a short list of tracks
        """
        gtk.Alignment.__init__(self)

        builder = gtk.Builder()
        builder.add_from_file(xdg.get_data_path(
            'ui', 'widgets', 'tracklist_info.ui'))

        info_box = builder.get_object('info_box')
        info_box.reparent(self)

        self._display_tracklist = display_tracklist

        self.cover_image = builder.get_object('cover_image')
        self.album_label = builder.get_object('album_label')
        self.artist_label = builder.get_object('artist_label')

        if self._display_tracklist:
            self.tracklist_table = builder.get_object('tracklist_table')
            self.tracklist_table.set_no_show_all(False)
            self.tracklist_table.set_property('visible', True)

            self.total_label = builder.get_object('total_label')
            self.total_label.set_no_show_all(False)
            self.total_label.set_property('visible', True)

            self.rownumber = 1
            self.pango_attributes = pango.AttrList()
            self.pango_attributes.insert(
                pango.AttrScale(pango.SCALE_SMALL, end_index=-1))
            self.pango_attributes.insert(
                pango.AttrStyle(pango.STYLE_ITALIC, end_index=-1))
            self.ellipse_pango_attributes = pango.AttrList()
            self.ellipse_pango_attributes.insert(
                pango.AttrWeight(pango.WEIGHT_BOLD, end_index=-1))

    def set_tracklist(self, tracks):
        """
            Updates the data displayed in the info pane
            :param tracks: A list of tracks to take the
                data from
        """
        tracks = trax.util.sort_tracks(['album', 'tracknumber'], tracks)

        image_data = covers.MANAGER.get_cover(tracks[0], use_default=True)
        width = settings.get_option('gui/cover_width', 100)
        pixbuf = icons.MANAGER.pixbuf_from_data(image_data, (width, width))
        self.cover_image.set_from_pixbuf(pixbuf)

        albums = []
        artists = []
        total_length = 0

        for track in tracks:
            albums += [track.get_tag_display('album')]
            artists += [track.get_tag_display('artist')]
            total_length += float(track.get_tag_raw('__length'))

        # Make unique
        albums = set(albums)
        artists = set(artists)

        if len(albums) == 1:
            self.album_label.set_text(albums.pop())
        else:
            self.album_label.set_text(_('Various'))

        if len(artists) == 1:
            self.artist_label.set_text(artists.pop())
        else:
            self.artist_label.set_text(_('Various Artists'))

        if self._display_tracklist:
            track_count = len(tracks)
            # Leaves us with a maximum of three tracks to display
            tracks = tracks[:3] + [None]

            for track in tracks:
                self.__append_row(track)

            self.tracklist_table.show_all()
            total_duration = LengthTagFormatter.format_value(total_length, 'long')

            text = _('%(track_count)d in total (%(total_duration)s)') % {
                'track_count': track_count,
                'total_duration': total_duration
            }

            self.total_label.set_text(text)

    def clear(self):
        """
            Resets the info pane
        """
        pixbuf = icons.MANAGER.pixbuf_from_data(
            covers.MANAGER.get_default_cover())
        self.cover_image.set_from_pixbuf(pixbuf)
        self.album_label.set_text('')
        self.artist_label.set_text('')

        if self._display_tracklist:
            items = self.tracklist_table.get_children()

            for item in items:
                self.tracklist_table.remove(item)
            self.rownumber = 1

            self.total_label.set_text('')

    def __append_row(self, track):
        """
            Appends a row to the internal
            track list table
            :param track: A track to build the row from,
                None to insert an ellipse
        """
        if track is None:
            ellipse_label = gtk.Label('⋮')
            ellipse_label.set_attributes(self.ellipse_pango_attributes)
            self.tracklist_table.attach(ellipse_label,
                1, 2, self.rownumber - 1, self.rownumber)
        else:
            tracknumber = track.get_tag_display('tracknumber')
            tracknumber = TrackNumberTagFormatter.format_value(tracknumber)
            tracknumber_label = gtk.Label(tracknumber)
            tracknumber_label.set_attributes(self.pango_attributes)
            tracknumber_label.props.xalign = 0
            self.tracklist_table.attach(tracknumber_label,
                0, 1, self.rownumber - 1, self.rownumber)

            title_label = gtk.Label(track.get_tag_display('title'))
            title_label.set_attributes(self.pango_attributes)
            self.tracklist_table.attach(title_label,
                1, 2, self.rownumber - 1, self.rownumber)

            length = float(track.get_tag_display('__length'))
            length = LengthTagFormatter.format_value(length, 'short')
            length_label = gtk.Label(length)
            length_label.set_attributes(self.pango_attributes)
            length_label.props.xalign = 0.9
            self.tracklist_table.attach(length_label,
                2, 3, self.rownumber - 1, self.rownumber)

        self.rownumber += 1

class ToolTip(object):
    """
        Custom tooltip class to allow for
        extended tooltip functionality
    """
    def __init__(self, parent, widget):
        """
            :param parent: the parent widget the tooltip
                should be attached to
            :param widget: the tooltip widget to be used
                for the tooltip
        """
        if self.__class__.__name__ == 'ToolTip':
            raise TypeError("cannot create instance of abstract "
                            "(non-instantiable) type `ToolTip'")

        self.__widget = widget
        self.__widget.unparent() # Just to be sure

        parent.set_has_tooltip(True)
        parent.connect('query-tooltip', self.on_query_tooltip)

    def on_query_tooltip(self, widget, x, y, keyboard_mode, tooltip):
        """
            Puts the custom widget into the tooltip
        """
        tooltip.set_custom(self.__widget)

        return True

class TrackToolTip(ToolTip):
    """
        Track specific tooltip class, displays
        track data and progress indicators
    """
    def __init__(self, parent, display_progress=False, auto_update=False):
        """
            :param parent: the parent widget the tooltip
                should be attached to
            :param display_progress: Toggles the display
                of the playback indicator and progress bar
                if the current track is played
            :param auto_update: Toggles the automatic
                following of playback state and track changes
        """
        self.info_pane = TrackInfoPane(display_progress, auto_update)
        self.info_pane.set_padding(6, 6, 6, 6)
        self.info_pane.info_label.set_ellipsize(pango.ELLIPSIZE_NONE)

        ToolTip.__init__(self, parent, self.info_pane)
    
    def set_track(self, track):
        """
            Updates data displayed in the tooltip
            :param track: A track to take the data from,
                clears the tooltip if track is None
        """
        self.info_pane.set_track(track)

    def clear(self):
        """
            Resets the tooltip
        """
        self.info_pane.clear()

class TrackListToolTip(ToolTip):

    def __init__(self, parent, display_tracklist=False):
        """
            :param parent: the parent widget the tooltip
                should be attached to
            :param display_tracklist: Whether to display
                a short list of tracks
        """
        self.info_pane = TrackListInfoPane(display_tracklist)
        self.info_pane.set_padding(6, 6, 6, 6)

        ToolTip.__init__(self, parent, self.info_pane)

    def set_tracklist(self, tracks):
        self.info_pane.set_tracklist(tracks)

    def clear(self):
        self.info_pane.clear()
