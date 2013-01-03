try:
    from collections import OrderedDict
except ImportError:
    from ordereddict import OrderedDict
from mode import *

class Dispatch(Mode):
    """
        This class works similarly to Mode except
        it drives events sequentially.

        Example:

        x = Mode()

        x.link('bar', alpha)
        x.link('bar', beta)
        x.link('bar', zeta)

        x.drive('bar')
        We would have alpha being called first than beta and 
        beta first than zeta.
        That behavior isn't warranted in the Mode root class instance.
    """

    def __init__(self, default=lambda event, *args: None):
        """ constructor """

        #since we aim a order 
        #we just use lists
        self.base = OrderedDict()

        self.default = default

 
