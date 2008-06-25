# this program is free software; you can redistribute it and/or modify
# it under the terms of the gnu general public license as published by
# the free software foundation; either version 3, or (at your option)
# any later version.
#
# this program is distributed in the hope that it will be useful,
# but without any warranty; without even the implied warranty of
# merchantability or fitness for a particular purpose.  see the
# gnu general public license for more details.
#
# you should have received a copy of the gnu general public license
# along with this program; if not, write to the free software
# foundation, inc., 675 mass ave, cambridge, ma 02139, usa.

from xlgui import panel

class CollectionPanel(panel.Panel):
    """
        The collection panel
    """
    gladeinfo = ('collection_panel.glade', 'CollectionPanelWindow')

    def __init__(self, controller, collection):
        """
            Initializes the collection panel
        """
        panel.Panel.__init__(self, controller)

        self.collection = collection
