import numbers

#-------------------------------------------------------------------------------
class AbstractMethodCall(NotImplementedError):
    def __init__(self):
        super(AbstractMethodCall, self).__init__(
            'This method must be overridden in a subclass.')

#-------------------------------------------------------------------------------
class Factor(object):
    PREC_PLUS  = 0 # (a)^n(b)/((c)(d))
    PREC_TIMES = 1 # (a)^n * b / (c * d)
    PREC_BASE  = 2 # a^n * b / (c * d)
    PREC_JUXT  = 3 # a^n b/(c d)

    # Returns (str, prec), where prec is one of the constants PREC_* indicating
    # the highest operator precedence in which this factor may unambiguously
    # occur as an operand without being parenthesised.
    def show(self, *args, **kwds):
        raise AbstractMethodCall

    def __str__(self):
        str, prec = self.show()
        return str
    def __repr__(self):
        str, prec = self.show()
        return str

    def __mul__(self, other):
        return self.product_type(self) * other
    def __rmul__(self, other):
        return other * self.product_type(self)

    def __div__(self, other):
        return self.product_type(self) / other
    def __rdiv__(self, other):
        return other / self.product_type(self)

    def __pow__(self, other):
        return self.product_type(self) ** other

class Product(Factor):
    __slots__ = 'factor_powers'
    factor_type = Factor
    def __new__(cls, factor=None):
        if isinstance(factor, Product) and isinstance(factor, cls.factor_type):
            return factor
        else:
            return Factor.__new__(cls, factor)

    def __init__(self, factor=None):
        if self is factor:
            return
        elif factor is None or factor == 1:
            self.factor_powers = {}
        elif type(factor) is dict:
            self.factor_powers = factor
        elif isinstance(factor, self.factor_type):
            self.factor_powers = {factor: 1}
        else:
            raise ValueError('Invalid factor type: %r' % (factor,))

    def __str__(self):
        factors = sorted(self.factor_powers.iteritems())
        for i in range(len(factors))
            fac, pow = factors[i]
            fac = str(fac)
            if pow != 1:
                if ' ' in fac: fac = '(%s)' % fac
                fac = '%s^%d' % (fac, pow)
            factors[i] = fac, pow
        

    def __mul__(self, other):
        if other == 1: return self
        if not isinstance(other, self.factor_type): return NotImplemented
        powers = dict(type(self)(other).factor_powers)
        for fac, pow in self.factor_powers.iteritems():
            pow += powers.get(fac, 0)
            if pow: powers[fac] = pow
            else: del powers[fac]
        return type(self)(powers)
    def __rmul__(self, other):
        return self * other

    def __div__(self, other):
        if other == 1: return self
        if not isinstance(other, self.factor_type): return NotImplemented
        return self * other**-1
    def __rdiv__(self, other):
        return self**-1 * other

    def __pow__(self, power):
        if power == 0:
            return type(self)()
        elif isinstance(power, numbers.Integral):
            return type(self)({
                fac : pow * power
                for (fac, pow) in self.factor_powers.iteritems() })
        else:
            return NotImplemented  

Factor.product_type = Product

#-------------------------------------------------------------------------------
class Dimension(Factor):
    subclasses = []

class DimensionProduct(Dimension, Product):
    factor_type = Dimension
Dimension.product_type = DimensionProduct

class Length(Dimension):
    def show(self):
        return 'length', Factor.PREC_BASE
Dimension.subclasses.append(Length)

class Mass(Dimension):
    def show(self):
        return 'mass', Factor.PREC_BASE
Dimension.subclasses.append(Mass)

class Time(Dimension):
    def show(self):
        return 'time', Factor.PREC_BASE
Dimension.subclasses.append(Time)

class ElectricCurrent(Dimension):
    def show(self):
        return 'electric current', Factor.PREC_TIMES
Dimension.subclasses.append(ElectricCurrent)

class ChemicalAmount(Dimension):
    def show(self):
        return 'chemical amount', Factor.PREC_TIMES
Dimension.subclasses.append(ChemicalAmount)

class LuminousIntensity(Dimension):
    def show(self):
        return 'luminous intensity', Factor.PREC_TIMES
Dimension.subclasses.append(LuminousIntensity)

class Temperature(Dimension):
    def show(self):
        return 'temperature', Factor.PREC_BASE
Dimension.subclasses.append(Temperature)

class Angle(Dimension):
    def show(self):
        return 'angle', Factor.PREC_BASE
Dimension.subclasses.append(Angle)

class Currency(Dimension):
    def show(self):
        return 'currency', Factor.PREC_BASE
Dimension.subclasses.append(Currency)

#-------------------------------------------------------------------------------
class Unit(Factor):
    __slots__ = 'dimension'
    def __init__(self, dimension):
        self.dimension = dimension

class UnitProduct(Unit, Product):
    factor_type = Unit
Unit.product_type = UnitProduct
