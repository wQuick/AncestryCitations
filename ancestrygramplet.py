#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2016 Tom Samstag
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
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
#

"""
Ancestry Gramplet.
"""

import re

#------------------------------------------------------------------------
#
# GTK modules
#
#------------------------------------------------------------------------
from gi.repository import Gtk
from gi.repository import Gdk

#------------------------------------------------------------------------
#
# Gramps modules
#
#------------------------------------------------------------------------
from gramps.gen.plug import Gramplet
from gramps.gui.dbguielement import DbGUIElement
from gramps.gen.display.name import displayer as name_displayer
from gramps.gen.errors import WindowActiveError
from gramps.gen.db import DbTxn
from gramps.gen.lib import Attribute

#------------------------------------------------------------------------
#
# Internationalisation
#
#------------------------------------------------------------------------
from gramps.gen.const import GRAMPS_LOCALE as glocale
try:
    _trans = glocale.get_addon_translator(__file__)
except ValueError:
    _trans = glocale.translation
_ = _trans.gettext

#------------------------------------------------------------------------
#
# AncestryGramplet class
#
#------------------------------------------------------------------------
class AncestryGramplet(Gramplet, DbGUIElement):
    """
    Gramplet to display Ancestry record IDs for people in the active citation.
    """
    def __init__(self, gui, nav_group=0):
        Gramplet.__init__(self, gui, nav_group)
        DbGUIElement.__init__(self, self.dbstate.db)

    def init(self):
        """
        Initialise the gramplet.
        """
        root = self.__create_gui()
        self.gui.get_container_widget().remove(self.gui.textview)
        self.gui.get_container_widget().add_with_viewport(root)
        root.show_all()

    def _connect_db_signals(self):
        """
        called on init of DbGUIElement, connect to db as required.
        """
        self.callman.register_callbacks({'citation-update': self.changed})
        self.callman.register_callbacks({'source-update': self.changed})
        self.callman.connect_all(keys=['citation', 'source'])

    def changed(self, handle):
        """
        Called when a registered event is updated.
        """
        self.update()

    def __create_gui(self):
        """
        Create and display the GUI components of the gramplet.
        """
        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)

        self.model = Gtk.ListStore(object, str, int)
        view = Gtk.TreeView(self.model)
        renderer = Gtk.CellRendererText()
        column = Gtk.TreeViewColumn(_("Person"), renderer, text=1)
        view.append_column(column)
        renderer = Gtk.CellRendererText()
        renderer.set_property('editable', True)
        renderer.connect('edited', self.__cell_edited)
        column = Gtk.TreeViewColumn(_("ID"), renderer, text=2)
        view.append_column(column)

        vbox.pack_start(view, expand=True, fill=True, padding=0)
        return vbox

    def __edit(self, widget, selection):
        """
        Edit the selected person.
        """
        model, iter_ = selection.get_selected()
        if iter_:
            person = model.get_value(iter_, 0)
            try:
                Editor(self.gui.dbstate, self.gui.uistate, [], person)
            except WindowActiveError:
                pass

    def __cell_edited(self, cell, path, new_text):
        person = self.model[path][0]
        print("HERE: {}".format(new_text))
        if new_text.isdigit():
            self.set_person_attribute(person, int(new_text))
        else:
            match = re.search(r'[?&]h=(\d+)\b', new_text)
            if match:
                self.set_person_attribute(person, int(match.group(1)))

        self.update()

    def get_person_attribute(self, person):
        attr_name = 'Ancestry APID H:{}'.format(self._dbid)
        existing_attrs = [a for a in person.get_attribute_list() if(str(a.get_type()) == attr_name)]
        if existing_attrs:
            try:
                return int(existing_attrs[0].get_value())
            except:
                pass
        return 0

    def set_person_attribute(self, person, record_id):
        attr_name = 'Ancestry APID H:{}'.format(self._dbid)

        existing_attrs = [a for a in person.get_attribute_list() if(str(a.get_type()) == attr_name)]
        if existing_attrs:
            existing_attrs[0].set_value(str(record_id))
            for extra_attr in existing_attrs[1:]:
                person.remove_attribute(extra_attr)
        else:
            attr = Attribute()
            attr.set_type(attr_name)
            attr.set_value(str(record_id))
            person.add_attribute(attr)

        with DbTxn(_("Setting Ancestry Record ID"), self.dbstate.db) as trans:
            self.dbstate.db.commit_person(person, trans)


    def main(self):
        """
        Called to update the display.
        """
        self.model.clear()
        active_citation = self.get_active_object("Citation")
        if not active_citation:
            return

        self.callman.unregister_all()
        self.callman.register_obj(active_citation)
        self.callman.register_handles({'citation': [active_citation.get_handle()]})

        db = self.dbstate.db
        source_handle = active_citation.get_reference_handle()
        source = db.get_source_from_handle(source_handle)
        person_list = []
        self._dbid = 0

        try:
            for attr in source.get_attribute_list():
                if str(attr.get_type()) == 'Ancestry DBID' and int(attr.get_value()) > 0:
                    self._dbid = int(attr.get_value())
        except:
            pass

        if self._dbid:
            for _type, event_handle in \
                    db.find_backlink_handles(active_citation.handle, include_classes=['Event']):
                participants = list()
                for _type, participant_handle in db.find_backlink_handles(event_handle,
                        include_classes=['Person']):
                    order = 0
                    person = self.dbstate.db.get_person_from_handle(participant_handle)

                    for event_ref in person.get_event_ref_list():
                        if (event_ref.ref == event_handle):
                            for attr in event_ref.get_attribute_list():
                                attr_type = str(attr.get_type())
                                print(attr_type)
                                if attr_type == 'Order':
                                    order = int(attr.get_value())

                    participants.append([order, person])

                participants.sort(key=lambda item: item[0])
                print(participants)
                for _order, participant in participants:
                    self.add_person(participant)

    def add_person(self, person):
        name = name_displayer.display(person)
        self.model.append((person, name, self.get_person_attribute(person)))


    def db_changed(self):
        """
        Called when the database is changed.
        """
        self.connect_signal('Citation', self.update)
        self.update()
