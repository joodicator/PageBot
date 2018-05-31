import weakref

# Any class whose __metaclass__ attribute is explicitly set to AbstractSlots (or
# a subclass thereof) becomes an abstract class. The __slots__ attribute of any
# direct subclass *without* an explicit __metaclass__ is extended with all of
# the names in the __slots__ attribute of each of its abstract superclasses.
class AbstractSlots(type):
    def __new__(mcs, name, bases, dict):
        __ab_slots = '_AbstractSlots__ab_slots'
        slots = []
        for base in bases:
            if not hasattr(base, __ab_slots): continue
            slots.extend(a for a in getattr(base, __ab_slots) if a not in slots)
        cls_slots = dict.get('__slots__')
        if cls_slots is not None:
            if isinstance(cls_slots, str): slots.append(cls_slots)
            else: slots.extend(a for a in cls_slots if a not in slots)

        if '__metaclass__' in dict:
            dict[__ab_slots] = tuple(slots)
            dict['__slots__'] = ()

            assert '__new__' not in dict
            def __new__(subcls, *args, **kwds):
                if getattr(subcls, __ab_slots): raise TypeError(
                    "Can't instantiate abstract class %s." % name)
                return super(cls, subcls).__new__(subcls, *args, **kwds)
            dict['__new__'] = __new__

        else:
            dict['__slots__'] = tuple(slots)
            dict[__ab_slots] = ()

        cls = super(AbstractSlots, mcs).__new__(mcs, name, bases, dict)
        return cls

# Instances of this metaclass will have an attribute, _subclasses, giving an
# iterable of direct subclasses that are also instances of this metaclass.
class SubclassRecorder(type):
    def __new__(mcs, name, bases, dict):
        cls = super(SubclassRecorder, mcs).__new__(mcs, name, bases, dict)
        cls.__weaksubs = []
        for base in bases:
            if not isinstance(base, SubclassRecorder): continue
            for _ in base._subclasses: pass
            base.__weaksubs.insert(0, weakref.ref(cls))
        return cls

    @property
    def _subclasses(cls):
        for i in xrange(len(cls.__weaksubs)-1, -1, -1):
            subcls = cls.__weaksubs[i]()
            if subcls is None:
                del cls.__weaksubs[i]
            else:
                yield subcls

# This mixin class provides a __repr__ method based on the instance's __slots__
# and type __name__, similar to that of collections.namedtuple.
class ReprSlots(object):
    __slots__ = ()
    def __repr__(self):
        slots = (a for a in iter_slots(self) if hasattr(self, a))
        attrs = ('%s=%r' % (a, getattr(self, a)) for a in slots)
        return '%s(%s)' % (type(self).__name__, ', '.join(attrs))

# This mixin class provides an __init__ method that assigns each keyword
# argument as an instance attribute, or raises TypeError if there is any
# keyword not corresponding to a slot, or any slot remaining without a set value.
class InitSlots(object):
    __slots__ = ()
    def __init__(self, **kwds):
        super(InitSlots, self).__init__()
        for slot in iter_slots(self):
            if slot in kwds:
                setattr(self, slot, kwds.pop(slot))
            elif not hasattr(self, slot):
                raise TypeError('Missing keyword argument: %s.' % slot)
        if kwds:
            raise TypeError('Unexpected keyword argument%s: %s.'
                  % ('s' if len(kwds) > 1 else '', ', '.join(kwds.iterkeys())))

# Return an iterator over the unique __slots__ names in the given class and
# its superclasses, ordered from superclass to subclass, from left to right.
def iter_slots(inst, seen=None):
    if seen is None: seen = set()
    for base in type(inst).__bases__:
        if base in seen: continue
        seen.add(base)
        for slot in iter_slots(base, seen): yield slot

    slots = getattr(inst, '__slots__', None)
    if slots is None: return
    for slot in (slots,) if isinstance(slots, str) else slots:
        if slot in seen: continue
        yield slot
        seen.add(slot)
