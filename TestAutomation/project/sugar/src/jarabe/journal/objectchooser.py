# Copyright (C) 2007, One Laptop Per Child
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

from gettext import gettext as _
import logging

from gi.repository import GObject
from gi.repository import Gtk
from gi.repository import Gdk
from gi.repository import Wnck

from sugar3.graphics import style
from sugar3.graphics.toolbutton import ToolButton
from sugar3.graphics.objectchooser import FILTER_TYPE_MIME_BY_ACTIVITY
from sugar3.graphics.popwindow import PopWindow

from jarabe.journal.listview import BaseListView
from jarabe.journal.listmodel import ListModel
from jarabe.journal.journaltoolbox import MainToolbox
from jarabe.journal.volumestoolbar import VolumesToolbar
from jarabe.model import bundleregistry

from jarabe.journal.iconview import IconView


class ObjectChooser(PopWindow):

    __gtype_name__ = 'ObjectChooser'

    __gsignals__ = {
        'response': (GObject.SignalFlags.RUN_FIRST, None, ([int])),
    }

    def __init__(self, parent=None, what_filter='', filter_type=None,
                 show_preview=False):
        if parent is None:
            parent_xid = 0
        elif hasattr(parent, 'get_window') and hasattr(parent.get_window(),
                                                       'get_xid'):
            parent_xid = parent.get_window().get_xid()
        else:
            parent_xid = parent
        PopWindow.__init__(self, window_xid=parent_xid)

        self._selected_object_id = None
        self._show_preview = show_preview

        self.add_events(Gdk.EventMask.VISIBILITY_NOTIFY_MASK)
        self.connect('visibility-notify-event',
                     self.__visibility_notify_event_cb)
        self.connect('delete-event', self.__delete_event_cb)
        self.connect('key-press-event', self.__key_press_event_cb)

        vbox = self.get_vbox()

        title_box = self.get_title_box()

        volumes_toolbar = VolumesToolbar()
        tool_item = Gtk.ToolItem()
        tool_item.set_expand(True)
        tool_item.add(volumes_toolbar)
        title_box.insert(tool_item, 0)
        tool_item.show()

        title = _('Choose an object')
        if filter_type == FILTER_TYPE_MIME_BY_ACTIVITY:
            registry = bundleregistry.get_registry()
            bundle = registry.get_bundle(what_filter)
            if bundle is not None:
                title = _('Choose an object to open with %s activity') % \
                    bundle.get_name()
        title_box.set_title(title)

        volumes_toolbar.connect('volume-changed', self.__volume_changed_cb)
        title_box.close_button.connect('clicked',
                                       self.__close_button_clicked_cb)
        title_box.set_size_request(-1, style.GRID_CELL_SIZE)
        vbox.pack_start(title_box, False, True, 0)
        title_box.show()

        separator = Gtk.HSeparator()
        vbox.pack_start(separator, False, True, 0)
        separator.show()

        self._toolbar = MainToolbox(default_what_filter=what_filter,
                                    default_filter_type=filter_type)
        self._toolbar.connect('query-changed', self.__query_changed_cb)
        self._toolbar.set_size_request(-1, style.GRID_CELL_SIZE)
        vbox.pack_start(self._toolbar, False, True, 0)
        self._toolbar.show()

        if not self._show_preview:
            self._list_view = ChooserListView(self._toolbar)
            self._list_view.connect('entry-activated',
                                    self.__entry_activated_cb)
            self._list_view.connect('clear-clicked', self.__clear_clicked_cb)
            vbox.pack_start(self._list_view, True, True, 0)
            self._list_view.show()
        else:
            self._icon_view = IconView(self._toolbar)
            self._icon_view.connect('entry-activated',
                                    self.__entry_activated_cb)
            self._icon_view.connect('clear-clicked', self.__clear_clicked_cb)
            vbox.pack_start(self._icon_view, True, True, 0)
            self._icon_view.show()

        width = Gdk.Screen.width() - style.GRID_CELL_SIZE * 2
        height = Gdk.Screen.height() - style.GRID_CELL_SIZE * 2
        self.set_size_request(width, height)

        self._toolbar.update_filters('/', what_filter, filter_type)

    def __entry_activated_cb(self, list_view, uid):
        self._selected_object_id = uid
        self.emit('response', Gtk.ResponseType.ACCEPT)

    def __delete_event_cb(self, chooser, event):
        self.emit('response', Gtk.ResponseType.DELETE_EVENT)

    def __key_press_event_cb(self, widget, event):
        keyname = Gdk.keyval_name(event.keyval)
        if keyname == 'Escape':
            self.emit('response', Gtk.ResponseType.DELETE_EVENT)

    def __close_button_clicked_cb(self, button):
        self.emit('response', Gtk.ResponseType.DELETE_EVENT)

    def get_selected_object_id(self):
        return self._selected_object_id

    def __query_changed_cb(self, toolbar, query):
        if not self._show_preview:
            self._list_view.update_with_query(query)
        else:
            self._icon_view.update_with_query(query)

    def __volume_changed_cb(self, volume_toolbar, mount_point):
        logging.debug('Selected volume: %r.', mount_point)
        self._toolbar.set_mount_point(mount_point)

    def __visibility_notify_event_cb(self, window, event):
        logging.debug('visibility_notify_event_cb %r', self)
        visible = event.get_state() == Gdk.VisibilityState.FULLY_OBSCURED
        if not self._show_preview:
            self._list_view.set_is_visible(visible)
        else:
            self._icon_view.set_is_visible(visible)

    def __clear_clicked_cb(self, list_view):
        self._toolbar.clear_query()


class ChooserListView(BaseListView):
    __gtype_name__ = 'ChooserListView'

    __gsignals__ = {
        'entry-activated': (GObject.SignalFlags.RUN_FIRST,
                            None,
                            ([str])),
    }

    def __init__(self, toolbar):
        BaseListView.__init__(self, None)
        self._toolbar = toolbar

        self.tree_view.props.hover_selection = True

        self.tree_view.connect('button-release-event',
                               self.__button_release_event_cb)

    def _can_clear_query(self):
        return self._toolbar.is_filter_changed()

    def __entry_activated_cb(self, entry):
        self.emit('entry-activated', entry)

    def _favorite_clicked_cb(self, cell, path):
        pass

    def create_palette(self, x, y):
        # We don't want show the palette in the object chooser
        pass

    def __button_release_event_cb(self, tree_view, event):
        if event.window != tree_view.get_bin_window():
            return False

        pos = tree_view.get_path_at_pos(int(event.x), int(event.y))
        if pos is None:
            return False

        path, column_, x_, y_ = pos
        uid = tree_view.get_model()[path][ListModel.COLUMN_UID]
        self.emit('entry-activated', uid)

        return False
