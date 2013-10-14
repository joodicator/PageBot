# Copyright (C) 2011  Iury O. G. Figueiredo
#
# This library is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 2.1 of the License, or (at your option) any later version.
#
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public
# License along with this library; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA 02111-1307  USA
#
# Iury <robatsch@hotmail.com>


""" The untwisted core. """


from untwisted.mode import *
from untwisted.dispatch import *
from untwisted.magic import *
from socket import *
from core import gear

def default(event, child=None, *args):
    if isinstance(child, Mode):
        child.drive(event, child, *args)

class Poll(Mode):
    def __init__(self):
        Mode.__init__(self, default)
        self.gear = gear

class Hook(Dispatch):
    def __init__(self):
        Dispatch.__init__(self, default)
        self.gear = gear

class Work(socket):
    def __init__(self, poll, sock, is_read=True, is_write=False):
        socket.__init__(self, _sock=sock)

        self.is_read  = is_read

        """ 
            To use yield hold(obj, WRITE)
            you need to pass is_write = True
            to tell the core to add this socket instance
            to the list of selectable objects for writting.
        """
        self.is_write = is_write

        """ Initially we aren't dumping anything. """

        self.poll = poll
        self.sock = sock

        #If it is not a socket server.
        self.server = False

        #Registering itself.
        gear.rlist.append(self)
        gear.wlist.append(self)
        gear.xlist.append(self)
        gear.tick_list.append(self)

        self.BLOCK = 1024
        self.SIZE = 1024

        #The socket stack.
        self.stack = ''
        self.data = ''

        self.queue = ''

    def dump(self, data):
        """ If you are going to use send 
            then you can't use dump.
            Otherwise you might have some odd behavior.

        """
        if type(data) is unicode:
            self.queue += data.encode('utf8')
        else:
            self.queue += data

    def destroy(self):
        for l in gear.rlist, gear.wlist, gear.xlist, gear.tick_list:
            if self in l: l.remove(self)

""" These are exotic names for classes.
    Howevr, the intention isn't being meaningful
    since we have docs for it.
    The aim is being as succinct as possible.
"""

class Fish(Work, Mode):
    def __init__(self, poll, sock, is_read=True, is_write=False):
        Work.__init__(self, poll, sock, is_read, is_write)
        Mode.__init__(self)

class Shell(Work, Dispatch):
    def __init__(self, poll, sock, is_read=True, is_write=False):
        Work.__init__(self, poll, sock, is_read, is_write)
        Dispatch.__init__(self)

class Shark(Shell):
    def __init__(self, poll, sock, is_read=True, is_write=False):
        Shark.__init__(self, self, sock, is_read, is_write)

class Mac(Fish):
    def __init__(self, sock, is_read=True, is_write = False):
        Fish.__init__(self, self, sock, is_read, is_write)



_all__ = [
            'Work', 
            'Poll', 
            'Fish',
            'sign',
            'hold',
            'wait',
            'Shell',
            'Shark',
            'sign',
            'Stop',
            'Kill',
            'Mac',
            'Hook',
            'gear'
          ]


