import numbers

#===============================================================================
class Factor(object)
    product = Product

    def __mul__(self, other):
        if type(other) not in type(self), self.product: return NotImplemented
        return self.product(self) * other

    def __div__(self, other):
        if type(other) not in type(self), self.product: return NotImplemented
        return self.product(self) / other

    def __rmul__(self, other):
        if type(other) not in type(self), self.product: return NotImplemented
        return other * product(type(self))

    def __rdiv__(self, other):
        if type(other) not in type(self), self.product: return NotImplemented
        return other / product(type(self))

    def __pow__(self, exponent):
        if type(other) not in type(self), self.product: return NotImplemented
        return self.product(self) ** exponent

    def __hash__(self):
        return hash(type(self))

    def __eq__(self, other):
        return type(self) is type(other)

class Product(object):
    def __init__(self, *factors, **kwds):
        if 'powers' in kwds:
            self.powers = kwds['powers']
        else:
            self.powers = defaultdict(lambda: 0)
        for factor in factors:
            self.powers[factor] += 1

    def __mul__(self, other):
        if type(other) is not type(self): return NotImplemented
        powers = defaultdict(lambda: 0)
        powers.update(self.powers)
        for factor, power in other.powers.iteritems():
            powers[factor] += power
            if powers[factor] == 0:
                del powers[factor]
        return type(self)(powers=powers)

    def __div__(self, other):
        if type(other) is not type(self): return NotImplemented
        return self * other**(-1)

    def __pow__(self, exponent):
        if not isinstance(exponent, numbers.Integral): return NotImplemented
        powers = defaultdict(lambda: 0)
        for factor, power in self.powers.iteritems():
            powers[factor] = power * exponent
        return type(self)(powers=powers)

    def __hash__(self):
        return hash(self.powers)

    def __eq__(self, other):
        return type(other) is type(self) and self.powers == other.powers

#===============================================================================
class Dim(Factor):
    pass

class DimProduct(Dim, Product):
    pass

Dim.product = DimProduct

#===============================================================================
class Unit(Factor):
    pass

class UnitProduct(Unit, Product):
    def __init__(self, *args, **kwds):
        super(UnitProduct, self).__init__(*args, **kwds)
        self.dim = product(u.dim**p for (u, p) in self.powers.iteritems())

Unit.product = UnitProduct

#===============================================================================
class Length(Dim):
    repr = 'length', 1, 'L', 0

