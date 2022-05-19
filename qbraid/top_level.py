"""
Module containing top-level qbraid functionality, and any/all functions
that directly or indirectly utilize entrypoints via ``pkg_resources``.

"""

import os
from datetime import datetime
from time import time
from typing import Any, Optional, Union

import pkg_resources
from IPython.display import HTML, clear_output, display

from ._typing import QPROGRAM
from .api import ApiError, QbraidSession, ibmq_least_busy_qpu
from .exceptions import QbraidError
from .ipython_utils import running_in_jupyter

# pylint: disable=too-many-locals


def _get_entrypoints(group: str):
    """Returns a dictionary mapping each entry of ``group`` to its loadable entrypoint."""
    return {entry.name: entry for entry in pkg_resources.iter_entry_points(group)}


def circuit_wrapper(program: QPROGRAM):
    """Apply qbraid quantum program wrapper to a supported quantum program.

    This function is used to create a qBraid :class:`~qbraid.transpiler.QuantumProgramWrapper`
    object, which can then be transpiled to any supported quantum circuit-building package.
    The input quantum circuit object must be an instance of a circuit object derived from a
    supported package.

    .. code-block:: python

        cirq_circuit = cirq.Circuit()
        q0, q1, q2 = [cirq.LineQubit(i) for i in range(3)]
        ...

    Please refer to the documentation of the individual qbraid circuit wrapper objects to see
    any additional arguments that might be supported.

    Args:
        circuit (:data:`~qbraid.QPROGRAM`): A supported quantum circuit / program object

    Returns:
        :class:`~qbraid.transpiler.QuantumProgramWrapper`: A wrapped quantum circuit-like object

    Raises:
        :class:`~qbraid.QbraidError`: If the input circuit is not a supported quantum program.

    """
    try:
        package = program.__module__.split(".")[0]
    except AttributeError as err:
        raise QbraidError(
            f"Error applying circuit wrapper to quantum program \
            of type {type(program)}"
        ) from err

    ep = package.lower()

    transpiler_entrypoints = _get_entrypoints("qbraid.transpiler")

    if package in transpiler_entrypoints:
        circuit_wrapper_class = transpiler_entrypoints[ep].load()
        return circuit_wrapper_class(program)

    raise QbraidError(f"Error applying circuit wrapper to quantum program of type {type(program)}")


def _get_devices_request(params=None):
    session = QbraidSession()
    params = {} if not params else params
    resp = session.get("/public/lab/get-devices", params=params)
    return resp.json()


def device_wrapper(qbraid_device_id: str):
    """Apply qbraid device wrapper to device from a supported device provider.

    Args:
        qbraid_device_id: unique ID specifying a supported quantum hardware device/simulator

    Returns:
        :class:`~qbraid.devices.DeviceLikeWrapper`: A wrapped quantum device-like object

    Raises:
        :class:`~qbraid.QbraidError`: If ``qbraid_id`` is not a valid device reference.

    """
    if qbraid_device_id == "ibm_q_least_busy_qpu":
        qbraid_device_id = ibmq_least_busy_qpu()

    device_info = _get_devices_request(params={"qbraid_id": qbraid_device_id})

    if isinstance(device_info, list):
        if len(device_info) == 0:
            raise QbraidError(f"{qbraid_device_id} is not a valid device ID.")
        device_info = device_info[0]

    if device_info is None:
        raise QbraidError(f"{qbraid_device_id} is not a valid device ID.")

    devices_entrypoints = _get_entrypoints("qbraid.devices")

    del device_info["_id"]  # unecessary for sdk
    del device_info["statusRefresh"]
    vendor = device_info["vendor"].lower()
    code = device_info.pop("_code")
    spec = ".local" if code == 0 else ".remote"
    ep = vendor + spec
    device_wrapper_class = devices_entrypoints[ep].load()
    return device_wrapper_class(**device_info)


def job_wrapper(qbraid_job_id: str):
    """Retrieve a job from qBraid API using job ID and return job wrapper object.

    Args:
        qbraid_job_id: qBraid Job ID

    Returns:
        :class:`~qbraid.devices.job.JobLikeWrapper`: A wrapped quantum job-like object

    """
    session = QbraidSession()
    job_data = session.post(
        "/get-user-jobs", json={"qbraidJobId": qbraid_job_id, "numResults": 1}
    ).json()

    if isinstance(job_data, list):
        if len(job_data) == 0:
            raise QbraidError(f"{qbraid_job_id} is not a valid job ID.")
        if len(job_data) > 1:
            raise QbraidError(f"Job retrieval error: job ID '{qbraid_job_id}' is not unique.")
        job_data = job_data[0]

    if not isinstance(job_data, dict):
        raise QbraidError(
            f"Expected job data of type 'dict', but instead got job data of type {type(job_data)}."
        )

    status_str = job_data["status"]
    vendor_job_id = job_data["vendorJobId"]
    qbraid_device_id = job_data["qbraidDeviceId"]
    qbraid_device = device_wrapper(qbraid_device_id)
    vendor = qbraid_device.vendor.lower()
    if vendor == "google":
        raise QbraidError(f"API job retrieval not supported for {qbraid_device.id}")
    devices_entrypoints = _get_entrypoints("qbraid.devices")
    ep = vendor + ".job"
    job_wrapper_class = devices_entrypoints[ep].load()
    return job_wrapper_class(
        qbraid_job_id, vendor_job_id=vendor_job_id, device=qbraid_device, status=status_str
    )


def _print_progress(start: float, count: int) -> None:
    """Internal :func:`~qbraid.get_devices` helper for
    printing quasi-progress-bar.

    Args:
        start: Time stamp marking beginning of function execution
        count: The total number of iterations completed so far
    """
    num_devices = 37  # i.e. number of iterations
    time_estimate = num_devices * 1.1  # estimated time for ~0.9 iters/s
    progress = count / num_devices
    elapsed_sec = int(time_estimate - (time() - start))
    stamp = f"{max(1, elapsed_sec)}s" if count > 0 else "1m"
    time_step = f"{stamp} remaining"
    dots = "." * count
    spaces = " " * (num_devices - count)
    percent = f"{int(progress*100)}%"
    clear_output(wait=True)
    print(f"{percent} | {dots} {spaces} | {time_step}", flush=True)


def refresh_devices() -> None:
    """Refreshes status for all qbraid supported devices. Requires credential for each vendor."""

    devices = _get_devices_request()
    session = QbraidSession()
    count = 0
    start = time()
    for document in devices:
        _print_progress(start, count)
        if document["statusRefresh"] is not None:  # None => internally not available at moment
            qbraid_id = document["qbraid_id"]
            device = device_wrapper(qbraid_id)
            status = device.status.name
            session.put("/lab/update-device", data={"qbraid_id": qbraid_id, "status": status})
        count += 1
    clear_output(wait=True)


def get_jobs(filters: Optional[dict] = None) -> Any: # pylint: disable=too-many-statements
    """Displays a list of quantum jobs submitted by user, tabulated by job ID,
    the date/time it was submitted, and status. You can specify filters to
    narrow the search by supplying a dictionary containing the desired criteria.

    **Request Syntax:**

    .. code-block:: python

        get_jobs(
            filters={
                'qbraidJobId': 'string',
                'vendorJobId': 'string',
                'qbraidDeviceId: 'string',
                'circuitNumQubits': 123,
                'circuitDepth': 123,
                'shots': 123,
                'status': 'string',
                'numResults': 123
            }
        )

    **Filters:**

        * **qbraidJobId** (str): The qBraid ID of the quantum job
        * **vendorJobId** (str): The Job ID assigned by the software provider to
            whom the job was submitted
        * **qbraidDeviceId** (str): The qBraid ID of the device used in the job
        * **circuitNumQubits** (int): The number of qubits in the quantum circuit
            used in the job
        * **circuitDepth** (int): The depth the quantum circuit used in the job
        * **shots** (int): Number of shots used in the job
        * **status** (str): The status of the job
        * **numResults** (int): Maximum number of results to display.
            Defaults to 10 if not specified.

    Args:
        filters: A dictionary containing any filters to be applied.

    """
    from qbraid.devices import is_status_final  # pylint: disable=import-outside-toplevel

    query = {} if filters is None else filters

    session = QbraidSession()
    jobs = session.post("/get-user-jobs", json=query).json()

    max_results = 10
    if "numResults" in query:
        max_results = query["numResults"]
        query.pop("numResults")

    count = 0
    num_jobs = len(jobs)
    job_data = []
    for document in jobs:
        count += 1
        progress = count / num_jobs
        dots = ".." * count
        spaces = "  " * (num_jobs - count)
        percent = f"{int(progress*100)}%"
        clear_output(wait=True)
        print(f"{percent} |{dots}{spaces}|", flush=True)
        job_id = document["qbraidJobId"]
        timestamp = document["timeStamps"]["jobStarted"]
        status = document["status"]
        if not is_status_final(status):
            qbraid_job = job_wrapper(job_id)
            qbraid_device = qbraid_job.device
            if qbraid_device.requires_cred:
                status_obj = qbraid_job.status()
                status = status_obj.raw()
            else:
                status = "COMPLETED"
        job_data.append([job_id, timestamp, status])
    clear_output(wait=True)

    if num_jobs == 0:  # Design choice whether to display anything here or not
        if len(query) == 0:
            msg = f"No jobs found for user {os.getenv('JUPYTERHUB_USER')}"
        else:
            msg = "No jobs found matching given criteria"
    elif num_jobs < max_results:
        msg = f"Displaying {num_jobs}/{num_jobs} jobs matching query"
    elif len(query) > 0:
        msg = f"Displaying {num_jobs} most recent jobs matching query"
    else:
        msg = f"Displaying {num_jobs} most recent jobs"

    # pylint: disable=consider-using-f-string
    if not running_in_jupyter():
        if num_jobs == 0:
            print(msg)
        else:
            print("{:<50} {:<25} {:<15}".format("Job ID", "Submitted", "Status"))
            for job_id, timestamp, status in job_data:
                print("{:<50} {:<25} {:<25}".format(job_id, timestamp, status))
            print()
            print(msg)
        return None

    html = """<h3>Quantum Jobs</h3><table><tr>
    <th style='text-align:left'>qBraid ID</th>
    <th style='text-align:left'>Submitted</th>
    <th style='text-align:left'>Status</th></tr>
    """

    # import numpy as np

    # status_test = [
    #     "INITIALIZING",
    #     "QUEUED",
    #     "VALIDATING",
    #     "RUNNING",
    #     "CANCELLING",
    #     "CANCELLED",
    #     "COMPLETED",
    #     "FAILED",
    #     "UNKNOWN"
    # ]

    for job_id, timestamp, status_str in job_data:

        # index = np.random.randint(0, len(status_test))
        # status_str = status_test[index]

        if status_str == "COMPLETED":
            color = "green"
        elif status_str == "FAILED":
            color = "red"
        elif status_str in ["INITIALIZING", "QUEUED", "VALIDATING", "RUNNING"]:
            color = "blue"
        else:
            color = "grey"

        status = f"<span style='color:{color}'>{status_str}</span>"

        html += f"""<tr>
        <td style='text-align:left'>{job_id}</td>
        <td style='text-align:left'>{timestamp}</td>
        <td style='text-align:left'>{status}</td></tr>
        """

    html += f"<tr><td colspan='4'; style='text-align:right'>{msg}</td></tr>"

    html += "</table>"

    return display(HTML(html))


def _get_device_data(query):
    """Internal :func:`~qbraid.get_devices` helper function that connects with the MongoDB database
    and returns a list of devices that match the ``filter_dict`` filters. Each device is
    represented by its own length-4 list containing the device provider, name, qbraid_id,
    and status.
    """
    session = QbraidSession()

    # get-devices must be a POST request with kwarg `json` (not `data`) to
    # encode the query. This is because certain queries contain regular
    # expressions which cannot be encoded in GET request `params`.
    devices = session.post("/public/lab/get-devices", json=query).json()

    if isinstance(devices, str):
        raise ApiError(devices)
    device_data = []
    tot_dev = 0
    tot_lag = 0
    for document in devices:
        qbraid_id = document["qbraid_id"]
        name = document["name"]
        provider = document["provider"]
        status_refresh = document["statusRefresh"]
        timestamp = datetime.utcnow()
        lag = 0
        if status_refresh is not None:
            format_datetime = str(status_refresh)[:10].split("-") + str(status_refresh)[
                11:19
            ].split(":")
            format_datetime_int = [int(x) for x in format_datetime]
            mk_datime = datetime(*format_datetime_int)
            lag = (timestamp - mk_datime).seconds
        status = document["status"]
        tot_dev += 1
        tot_lag += lag
        device_data.append([provider, name, qbraid_id, status])
    if tot_dev == 0:
        return [], 0  # No results matching given criteria
    device_data.sort()
    lag_minutes, _ = divmod(tot_lag / tot_dev, 60)
    return device_data, int(lag_minutes)


def get_devices(filters: Optional[dict] = None, refresh: bool = False) -> Union[Any, dict]:
    """Displays a list of all supported devices matching given filters, tabulated by provider,
    name, and qBraid ID. Each device also has a status given by a solid green bubble or a hollow
    red bubble, indicating that the device is online or offline, respectively. You can narrow your
    device search by supplying a dictionary containing the desired criteria.

    **Request Syntax:**

    .. code-block:: python

        get_devices(
            filters={
                'name': 'string',
                'vendor': 'AWS'|'IBM'|'Google',
                'provider: 'AWS'|'IBM'|'Google'|'D-Wave'|'IonQ'|'Rigetti'|'OQC',
                'type': 'QPU' | 'Simulator',
                'numberQubits': 123,
                'paradigm': 'gate-based'|'quantum-annealer',
                'requiresCred': True|False,
                'status': 'ONLINE'|'OFFLINE'
            }
        )

    **Filters:**

        * **name** (str): Name quantum device name
        * **vendor** (str): Company whose software facilitaces access to quantum device
        * **provider** (str): Company providing the quantum device
        * **type** (str): If the device is a quantum simulator or hardware
        * **numberQubits** (int): The number of qubits in quantum device
        * **paradigm** (str): The quantum model through which the device operates
        * **requiresCred** (bool): Whether the device requires credentialed access
        * **status** (str): Availability of device

    **Examples:**

    .. code-block:: python

        from qbraid import get_devices

        # Search for gate-based devices provided by Google that are online/available
        get_devices(
            filters={"paradigm": "gate-based", "provider": "Google", "status": "ONLINE"}
        )

        # Search for QPUs with at least 5 qubits that are available through AWS or IBM
        get_devices(
            filters={"type": "QPU", "numberQubits": {"$gte": 5}, "vendor": {"$in": ["AWS", "IBM"]}}
        )

        # Search for open-access simulators that have "Unitary" contained in their name
        get_devices(
            filters={"type": "Simulator", "name": {"$regex": "Unitary"}, "requiresCred": False}
        )

    For a complete list of search operators, see `Query Selectors`__. To refresh the device
    status column, call :func:`~qbraid.get_devices` with ``refresh=True`` keyword argument.
    The bottom-right corner of the device table indicates time since the last status refresh.

    .. __: https://docs.mongodb.com/manual/reference/operator/query/#query-selectors

    Args:
        filters: A dictionary containing any filters to be applied.
        refresh: If True, calls :func:`~qbraid.refresh_devices` before execution.

    """
    if refresh:
        refresh_devices()
    query = {} if filters is None else filters
    device_data, lag = _get_device_data(query)

    if not running_in_jupyter():
        device_dict = {}
        for data in device_data:
            provider = data[0]
            if provider not in device_dict:
                device_dict[provider] = {}
            qbraid_id = data[2]
            info = {"name": data[1], "status": data[3]}
            device_dict[provider][qbraid_id] = info
        return device_dict

    hours, minutes = divmod(lag, 60)
    min_10, _ = divmod(minutes, 10)
    min_display = min_10 * 10
    if hours > 0:
        if minutes > 30:
            msg = f"Device status updated {hours}.5 hours ago"
        else:
            hour_s = "hour" if hours == 1 else "hours"
            msg = f"Device status updated {hours} {hour_s} ago"
    else:
        if minutes < 10:
            min_display = minutes
        msg = f"Device status updated {min_display} minutes ago"

    html = """<h3>Supported Devices</h3><table><tr>
    <th style='text-align:left'>Provider</th>
    <th style='text-align:left'>Name</th>
    <th style='text-align:left'>qBraid ID</th>
    <th style='text-align:left'>Status</th></tr>
    """

    online = "<span style='color:green'>●</span>"
    offline = "<span style='color:red'>○</span>"

    for data in device_data:
        if data[3] == "ONLINE":
            status = online
        else:
            status = offline

        html += f"""<tr>
        <td style='text-align:left'>{data[0]}</td>
        <td style='text-align:left'>{data[1]}</td>
        <td style='text-align:left'><code>{data[2]}</code></td>
        <td>{status}</td></tr>
        """

    if len(device_data) == 0:
        html += (
            "<tr><td colspan='4'; style='text-align:center'>No results matching "
            "given criteria</td></tr>"
        )

    else:  # Design choice whether to display anything here or not
        html += f"<tr><td colspan='4'; style='text-align:right'>{msg}</td></tr>"

    html += "</table>"

    return display(HTML(html))
