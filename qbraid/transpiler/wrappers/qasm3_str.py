# Copyright (C) 2023 qBraid
#
# This file is part of the qBraid-SDK
#
# The qBraid-SDK is free software released under the GNU General Public License v3
# or later. You can redistribute and/or modify it under the terms of the GPL v3.
# See the LICENSE file in the project root or <https://www.gnu.org/licenses/gpl-3.0.html>.
#
# THERE IS NO WARRANTY for the qBraid-SDK, as per Section 15 of the GPL v3.

# pylint: disable=invalid-name


"""
Module defining Qasm3CircuitWrapper Class

"""
from qbraid.interface.qbraid_qasm.tools import qasm3_depth, qasm_3_num_qubits, qasm_qubits
from qbraid.transpiler.wrappers.abc_qprogram import QuantumProgramWrapper


class Qasm3CircuitWrapper(QuantumProgramWrapper):
    """Wrapper class for OpenQASM 3 strings."""

    def __init__(self, qasm_str: str):
        """Create a Qasm3CircuitWrapper

        Args:
            circuit: the OpenQASM 3 string to be wrapped

        """
        # coverage: ignore
        super().__init__(qasm_str)

        self._qubits = qasm_qubits(qasm_str)
        self._num_qubits = qasm_3_num_qubits(qasm_str)
        self._depth = qasm3_depth(qasm_str)
        self._package = "qasm3"
        self._program_type = "str"
