"""
Module containing pytket programs used for testing

"""
import numpy as np
from pytket.circuit import Circuit as TKCircuit

from qbraid.interface.qbraid_pytket.tools import _convert_to_contiguous_pytket


def pytket_bell() -> TKCircuit:
    """Returns pytket bell circuit"""
    circuit = TKCircuit(2)
    circuit.H(0)
    circuit.CX(0, 1)
    return circuit


def pytket_shared15():
    """Returns pytket `Circuit` for qBraid `TestSharedGates`."""

    circuit = TKCircuit(4)

    for i in range(4):
        circuit.H(i)
    for i in range(2):
        circuit.X(i)
    circuit.Y(2)
    circuit.Z(3)
    circuit.S(0)
    circuit.Sdg(1)
    circuit.T(2)
    circuit.Tdg(3)
    circuit.Rx(np.pi / 4, 0)
    circuit.Ry(np.pi / 2, 1)
    circuit.Rz(3 * np.pi / 4, 2)
    circuit.U1(np.pi / 8, 3)
    circuit.SX(0)
    circuit.SXdg(1)
    circuit.ISWAPMax(2, 3)
    for i in range(2):
        circuit.SWAP(i, i + 2)
    circuit.CX(0, 1)
    circuit.CU1(np.pi / 4, 2, 3)

    return _convert_to_contiguous_pytket(circuit, rev_qubits=True)
