from typing import Union

from qiskit.circuit import Parameter as QiskitParameter
from sympy import Symbol as CirqParameter

from .transpiler import QbraidTranspiler

ParameterInput = Union[float, int, str]


class ParamID:

    """
    An itermediate representation for storing abstract parameters during the transpilation
    process. This class is needed, as opposed to a serial number, in order to distinguish
    abstract parameters from numbers.

    Attributes:
        index (integer): a serial number given to arbitrarily to each parameter
        name (str): name of the parameter as string
    """

    def __init__(self, index: int, name: str):
        self.index = index
        self.name = name


class ParameterWrapper(QbraidTranspiler):
    """Wrap a 'parameter' for parametrized circuits"""

    def __init__(self):
        self.name = None
        self.parameter = None

    def _create_cirq(self):
        return CirqParameter(self.name)

    def _create_qiskit(self):
        return QiskitParameter(self.name)

    def transpile(self, package, *args, **kwargs):
        return NotImplementedError
