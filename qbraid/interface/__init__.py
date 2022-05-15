"""
===============================================
Interface (:mod:`qbraid.interface`)
===============================================

.. currentmodule:: qbraid.interface

.. autosummary::
   :toctree: ../stubs/

   to_unitary
   convert_to_contiguous
   circuits_allclose
   random_circuit
   draw
   ContiguousConversionError
   UnitaryCalculationError

"""
from .calculate_unitary import UnitaryCalculationError, circuits_allclose, to_unitary
from .convert_to_contiguous import ContiguousConversionError, convert_to_contiguous
from .draw_circuit import draw
from .programs import random_circuit
