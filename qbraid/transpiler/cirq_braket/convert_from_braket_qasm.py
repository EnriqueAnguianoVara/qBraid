# Copyright (C) 2023 qBraid
#
# This file is part of the qBraid-SDK
#
# The qBraid-SDK is free software released under the GNU General Public License v3
# or later. You can redistribute and/or modify it under the terms of the GPL v3.
# See the LICENSE file in the project root or <https://www.gnu.org/licenses/gpl-3.0.html>.
#
# THERE IS NO WARRANTY for the qBraid-SDK, as per Section 15 of the GPL v3.

"""
Module for converting Braket circuits to Cirq circuit via OpenQASM

"""

from braket.circuits import Circuit as BKCircuit
from braket.circuits.serialization import IRType
from cirq import Circuit
from cirq.contrib.qasm_import.exception import QasmException

from qbraid.interface import convert_to_contiguous
from qbraid.transpiler.cirq_qasm import from_qasm
from qbraid.transpiler.exceptions import CircuitConversionError

QASMType = str


def to_qasm(circuit: BKCircuit) -> QASMType:
    """Converts a `braket.circuits.Circuit` to an OpenQASM 2.0 string.
    *DEPRECATAION NOTICE*: incomplete function, to be removed in next release.

    .. code-block:: python

        >>> from braket.circuits import Circuit
        >>> circuit = Circuit().h(0).cnot(0,1).cnot(1,2)
        >>> print(circuit)
        T  : |0|1|2|

        q0 : -H-C---
                |
        q1 : ---X-C-
                  |
        q2 : -----X-

        T  : |0|1|2|
        >>> print(circuit_to_qasm(circuit))
        OPENQASM 2.0;
        include "qelib1.inc";

        qreg q[3];

        h q[0];
        cx q[0],q[1];
        cx q[1],q[2];

    Args:
        circuit: Amazon Braket quantum circuit

    Returns:
        The OpenQASM string equivalent to the circuit

    """
    # A mapping from Amazon Braket gates to QASM gates
    gates = {
        "cnot": "cx",
        "ccnot": "ccx",
        "i": "id",
        "phaseshift": "p",
        "si": "sdg",
        "ti": "tdg",
        "v": "sx",
        "vi": "sxdg",
    }

    # Including the header
    code = 'OPENQASM 2.0;\ninclude "qelib1.inc";\n\n'

    # Initializing the quantum register
    code += "qreg q[" + str(circuit.qubit_count) + "];\n\n"

    circuit_instr = circuit.instructions
    # Building the QASM codelines by applying gates one at a time
    for ins in circuit_instr:
        # Appending the gate name
        if ins.operator.name.lower() not in gates:
            code += ins.operator.name.lower()
        else:
            code += gates[ins.operator.name.lower()]

        # Appending parameters, if any
        try:
            param = "(" + str(ins.operator.angle) + ") "
        except Exception:  # pylint: disable=broad-except
            param = " "
        code += param

        # Appending the gate targets
        targets = [int(q) for q in ins.target]
        code += f"q[{targets[0]}]"
        for t in range(1, len(targets)):
            code += f", q[{targets[t]}]"
        code += ";\n"

    return code


def braket_to_qasm3(circuit: BKCircuit) -> QASMType:
    """Converts a ``braket.circuits.Circuit`` to an OpenQASM 3.0 string.

    .. code-block:: python

        >>> from braket.circuits import Circuit
        >>> circuit = Circuit().h(0).cnot(0,1).cnot(1,2)
        >>> print(circuit)
        T  : |0|1|2|

        q0 : -H-C---
                |
        q1 : ---X-C-
                  |
        q2 : -----X-

        T  : |0|1|2|
        >>> print(circuit_to_qasm3(circuit))
        OPENQASM 3.0;
        bit[3] b;
        qubit[3] q;
        h q[0];
        cnot q[0], q[1];
        cnot q[1], q[2];
        b[0] = measure q[0];
        b[1] = measure q[1];
        b[2] = measure q[2];

    Args:
        circuit: Amazon Braket quantum circuit

    Returns:
        The OpenQASM 3.0 string equivalent to the circuit

    Raises:
        CircuitConversionError: If braket to qasm conversion fails

    """
    try:
        return circuit.to_ir(IRType.OPENQASM).source
    except Exception as err:
        raise CircuitConversionError("Error converting braket circuit to qasm3 string") from err


def from_braket(circuit: BKCircuit) -> Circuit:
    """Returns a Cirq circuit equivalent to the input Braket circuit.

    Note: The returned Cirq circuit acts on cirq.LineQubit's with indices equal
    to the qubit indices of the Braket circuit.

    Args:
        circuit: Braket circuit to convert to a Cirq circuit.

    Raises:
        CircuitConversionError: if circuit could not be converted
    """
    compat_circuit = convert_to_contiguous(circuit)
    qasm_str = to_qasm(compat_circuit)
    try:
        return from_qasm(qasm_str)
    except QasmException as err:
        raise CircuitConversionError("Error converting qasm string to Cirq circuit") from err
