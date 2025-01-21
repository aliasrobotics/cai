"""
This module provides a state representation for the system being tested.

┌─────────────┐
│ NetworkState│
└─────┬───────┘
      │ has
      │ many
┌─────▼───────┐
│EndpointState│
└─┬───┬───┬───┘
  │   │   │
  │   │   │ has many
  │   │   ├──────► [Dict] filesystem
  │   │   └──────► [str] users
  │   │
  │   │ has many
  │   ├──────────► PortState
  │   │            ├── port, open
  │   │            ├── name, version, cpe
  │   │            ├── routes
  │   │            ├── vulnerabilities
  │   │            └── exploits
  │   │
  │   │ has many
  └───┴──────────► ExploitState
                   ├── type_exploit
                   ├── launched
                   └── name

The NetworkState class represents the complete state of a network being tested,
containing a mapping of IP addresses to EndpointState objects. Each EndpointState
represents a single network endpoint with its exploits, ports, filesystem and users.
"""

import pprint
import copy
import numpy as np
from pydantic import BaseModel, Field
from typing import List, Dict, Optional, Union, Any
from cai.state import State

TARGET_IP_ADDRESSES = ["127.0.0.1"]


class ExploitState(BaseModel):
    type_exploit: str = ""
    launched: bool = False
    name: str = ""

    def __init__(self, type_exploit: str = "",
                 launched: bool = False, name: str = ""):
        super().__init__(type_exploit=type_exploit, launched=launched, name=name)

    @classmethod
    def from_dict(cls, data):
        return cls(
            type_exploit=data.get("type_exploit"),
            launched=data.get("launched", True),
            name=data.get("name", ""),
        )

    def __str__(self):
        return str(self.type_exploit) + "|" + str(self.launched)

    def __repr__(self) -> str:
        return self.__str__()

    def one_hot_encode(self):
        type_processed = np.array([self.type_exploit]).reshape(-1, 1)
        type_encoded = self.enc.transform(type_processed).flatten().tolist()
        launched_encoded = [1.0 if self.launched else 0.0]
        return type_encoded + launched_encoded

    def __eq__(self, other):
        if isinstance(other, ExploitState):
            return (
                self.type_exploit == other.type_exploit
                and self.launched == other.launched
            )
        return False

    def compare(self, other):
        differences = []
        if not isinstance(self, ExploitState) or not isinstance(
            other, ExploitState):
            differences.append(f"type mismatch: {type(self)} != {type(other)}")
            return differences

        if self.type_exploit != other.type_exploit:
            differences.append(
                f"type_exploit: {self.type_exploit} != {other.type_exploit}"
            )
        if self.launched != other.launched:
            differences.append(
    f"launched: {
        self.launched} != {
            other.launched}")
        if self.name != other.name:
            differences.append(f"name: {self.name} != {other.name}")
        return differences

    def prompt(self, indent=""):
        # return f"{indent}- Type: {self.type_exploit}, Launched:
        # {self.launched}, Name: {self.name}\n"
        return ""


class PortState(BaseModel):
    port: int
    open: bool = False
    name: Optional[str] = ""
    version: Optional[str] = ""
    cpe: Optional[str] = ""
    routes: Dict[str, str] = Field(default_factory=dict)
    vulnerabilities: List[Any] = Field(default_factory=list)
    exploits: List[Dict[str, Union[str, float]]] = Field(default_factory=list)

    def __init__(
        self,
        port: int,
        open: bool = False,
        name: str = None,
        version: str = None,
        cpe: str = None,
        routes: Dict[str, str] = None,
        vulnerabilities: List[Dict[str, Union[str, float]]] = None,
        exploits: List[Dict[str, Union[str, float]]] = None,
    ):
        super().__init__(
            port=port,
            open=open,
            name=name,
            version=version,
            cpe=cpe,
            routes=routes if routes is not None else {},
            vulnerabilities=vulnerabilities if vulnerabilities is not None else [],
            exploits=exploits if exploits is not None else [],
        )

    @classmethod
    def from_dict(cls, data):
        vulnerabilities = data.get("vulnerabilities", [])
        # Convert string vulnerabilities to dictionaries
        processed_vulnerabilities = []
        for vuln in vulnerabilities:
            if isinstance(vuln, str):
                processed_vulnerabilities.append(
                    {"type": "text", "cvss": "", "id": vuln, "url": ""}
                )
                # NOTE: see test_state_vulnerabilities.py for examples
            elif isinstance(vuln, dict):
                processed_vulnerabilities.append(vuln)
            else:
                # Skip invalid vulnerability entries
                continue

        return cls(
            port=data.get("port", 0),
            open=data.get("open", True),
            name=data.get("name", ""),
            version=data.get("version", ""),
            cpe=data.get("cpe", ""),
            routes=data.get("routes", {}),
            vulnerabilities=processed_vulnerabilities,
            exploits=data.get("exploits", []),
        )

    def copy(self):
        return copy.deepcopy(self)

    def __str__(self):
        return str(self.port) + "|" + str(self.open) + "|" + str(self.name)

    def __repr__(self) -> str:
        return self.__str__()

    def one_hot_encode(self):
        port_processed = np.array([self.port]).reshape(-1, 1)
        port_encoded = self.enc.transform(port_processed).flatten().tolist()
        open_encoded = [1.0 if self.open else 0.0]
        return port_encoded + open_encoded

    def __eq__(self, other):
        if isinstance(other, PortState):
            return (
                self.port == other.port
                and self.open == other.open
                and self.name == other.name
                and self.version == other.version
                and self.cpe == other.cpe
                and self.routes == other.routes
                and self.vulnerabilities == other.vulnerabilities
                and self.exploits == other.exploits
            )
        return False

    def compare(self, other):
        differences = []
        if self.port != other.port:
            differences.append(f"port: {self.port} != {other.port}")
        if self.open != other.open:
            differences.append(f"open: {self.open} != {other.open}")
        if self.name != other.name:
            differences.append(f"name: {self.name} != {other.name}")
        if self.version != other.version:
            differences.append(f"version: {self.version} != {other.version}")
        if self.cpe != other.cpe:
            differences.append(f"cpe: {self.cpe} != {other.cpe}")
        if self.routes != other.routes:
            differences.append(f"routes: {self.routes} != {other.routes}")
        if self.vulnerabilities != other.vulnerabilities:
            differences.append(
                f"vulnerabilities: {
    self.vulnerabilities} != {
        other.vulnerabilities}"
            )
        if self.exploits != other.exploits:
            differences.append(
    f"exploits: {
        self.exploits} != {
            other.exploits}")
        return differences

    def prompt(self, indent=""):
        output = f"{indent}- Port: {
    self.port}, Open: {
        self.open}, Name: {
            self.name}, Version: {
                self.version}\n"
        if self.cpe:
            output += f"{indent}  CPE: {self.cpe}\n"
        if self.routes:
            output += f"{indent}  Routes:\n"
            for key, value in self.routes.items():
                output += f"{indent}    {key}: {value}\n"
        if self.vulnerabilities:
            output += f"{indent}  Vulnerabilities:\n"
            for vuln in self.vulnerabilities:
                output += f"{indent}    - {vuln}\n"
        if self.exploits:
            output += f"{indent}  Exploits:\n"
            for exploit in self.exploits:
                output += f"{indent}    - {exploit}\n"
        return output


class EndpointState(State):
    """
    EndpointState class represents a network endpoint state containing exploits and ports information.

    Attributes:
        exploits (List[ExploitState]): A list of ExploitState objects.
        ports (List[PortState]): A list of PortState objects.
        filesystem (List[Dict]): A list of dictionaries containing file paths and permissions.
        users (List): A list of users inside the system.
        filesystem (List[Dict[str, str]]): A list of dictionaries containing file paths and permissions.

    Methods:
        from_dict(cls, data): Creates a EndpointState object from a dictionary.
        __str__(): Returns a string representation of the state.
        __repr__(): Returns a string representation of the state.
        __add__(self, newstate): Merges two state objects.
        one_hot_encode(): One-hot encodes all ExploitState and PortState objects in 'exploits' and 'ports'.

    NOTE: see tests/state/test_state_constructions.py for examples
    """

    exploits: List[ExploitState] = Field(default_factory=list)
    ports: List[PortState] = Field(default_factory=list)
    filesystem: List = Field(default_factory=list)
    users: List = Field(default_factory=list)

    def __init__(self, exploits=[], ports=[], filesystem=[], users=[]):
        super().__init__()
        self.exploits = exploits
        self.ports = ports
        self.filesystem = filesystem
        self.users = users

    @classmethod
    def from_dict(cls, data):
        exploits = [
            ExploitState.from_dict(exploit) if isinstance(
                exploit, dict) else exploit
            for exploit in data.get("exploits", [])
        ]
        ports = [
            PortState.from_dict(port) if isinstance(port, dict) else port
            for port in data.get("ports", [])
        ]
        filesystem = data.get("filesystem", [])
        users = data.get("users", [])

        return cls(exploits=exploits, ports=ports,
                   filesystem=filesystem, users=users)

    def __str__(self):
        d_return = {
            "exploits": [],
            "ports": [],
            "filesystem": self.filesystem,
            "users": self.users,
        }
        for expl in self.exploits:
            if isinstance(expl, ExploitState):
                if expl.launched:
                    if isinstance(expl.type_exploit, type):
                        # expl.type is a class
                        d_return["exploits"].append(
                            str(expl.type_exploit.__name__))
                    else:
                        # expl.type is an obj
                        d_return["exploits"].append(str(expl.type_exploit))
            elif isinstance(expl, str):
                # If expl is a string, just add it to the list
                d_return["exploits"].append(expl)
            else:
                # If it's neither ExploitState nor string, skip it
                continue

        for port in self.ports:
            if isinstance(port, PortState) and port.open:
                port_info = {
                    "port": str(port.port),
                    "name": str(port.name),
                    "version": str(port.version),
                }

                for attr in ["routes", "vulnerabilities"]:
                    items = getattr(port, attr)
                    if items:
                        if attr == "routes" and isinstance(items, dict):
                            limited_items = dict(list(items.items())[:3])
                            port_info[attr] = ", ".join(
                                f"{k}: {v}" for k, v in limited_items.items()
                            )
                            if len(items) > 3:
                                port_info[attr] += ", ..."
                        elif isinstance(items, list):
                            if len(items) > 3:
                                port_info[attr] = (
                                    f"{', '.join(map(str, items[:3]))}, ..."
                                )
                            else:
                                port_info[attr] = ", ".join(map(str, items))
                        else:
                            port_info[attr] = str(items)
                    else:
                        port_info[attr] = ""

                d_return["ports"].append(port_info)
        return str(pprint.pformat(d_return))

    def full_str(self):
        """
        Returns a string representation of the state, including all exploits and ports.
        Without any simplifications or shortenings.
        """
        d_return = {
            "exploits": [],
            "ports": [],
            "filesystem": self.filesystem,
            "users": self.users,
        }
        for expl in self.exploits:
            if isinstance(expl, ExploitState):
                if expl.launched:
                    if isinstance(expl.type_exploit, type):
                        # expl.type is a class
                        d_return["exploits"].append(
                            str(expl.type_exploit.__name__))
                    else:
                        # expl.type is an obj
                        d_return["exploits"].append(str(expl.type_exploit))
            elif isinstance(expl, str):
                # If expl is a string, just add it to the list
                d_return["exploits"].append(expl)
            else:
                # If it's neither ExploitState nor string, skip it
                continue

        for port in self.ports:
            if isinstance(port, PortState) and port.open:
                port_info = {
                    "port": str(port.port),
                    "name": str(port.name),
                    "version": str(port.version),
                    "routes": {},
                    "vulnerabilities": [],
                }

                for attr in ["routes", "vulnerabilities"]:
                    items = getattr(port, attr)
                    if items:
                        if attr == "routes" and isinstance(items, dict):
                            port_info[attr] = {k: v for k, v in items.items()}
                        elif isinstance(items, list):
                            port_info[attr] = [str(item) for item in items]
                        else:
                            port_info[attr] = str(items)
                    else:
                        port_info[attr] = {} if attr == "routes" else []

                d_return["ports"].append(port_info)
        return str(pprint.pformat(d_return))

    def __repr__(self) -> str:
        return self.__str__()

    def __add__(self, newstate):
        """Merge two state objects"""
        return newstate

    def one_hot_encode(self):
        exploits_encoded = [exploit.one_hot_encode()
                                                   for exploit in self.exploits]
        flattened_exploits_encoded = [
            item for sublist in exploits_encoded for item in sublist
        ]

        ports_encoded = [port.one_hot_encode() for port in self.ports]
        flattened_ports_encoded = [
            item for sublist in ports_encoded for item in sublist
        ]

        # return ports_encoded + exploits_encoded
        return flattened_ports_encoded + flattened_exploits_encoded

    def __eq__(self, other):
        if not isinstance(other, EndpointState):
            return False

        # Compare exploits
        if len(self.exploits) != len(other.exploits):
            return False
        for self_exploit, other_exploit in zip(self.exploits, other.exploits):
            if not isinstance(self_exploit, ExploitState) or not isinstance(
                other_exploit, ExploitState
            ):
                return False
            if (
                self_exploit.type_exploit != other_exploit.type_exploit
                or self_exploit.launched != other_exploit.launched
                or self_exploit.name != other_exploit.name
            ):
                return False

        # Compare ports
        if len(self.ports) != len(other.ports):
            return False
        for self_port, other_port in zip(self.ports, other.ports):
            if not isinstance(self_port, PortState) or not isinstance(
                other_port, PortState
            ):
                return False
            if (
                self_port.port != other_port.port
                or self_port.open != other_port.open
                or self_port.name != other_port.name
                or self_port.version != other_port.version
                or self_port.cpe != other_port.cpe
                or set(self_port.routes) != set(other_port.routes)
            ):
                return False

        # Compare filesystem
        if self.filesystem != other.filesystem:
            return False

        # Compare users
        if self.users != other.users:
            return False

        return True

    def compare(self, other):
        differences = []
        # Compare exploits
        max_exploits = max(len(self.exploits), len(other.exploits))
        for i in range(max_exploits):
            if i < len(self.exploits) and i < len(other.exploits):
                exploit_diff = self.exploits[i].compare(other.exploits[i])
                if exploit_diff:
                    differences.append(
                        f"Exploit difference at index {i}: {exploit_diff}"
                    )
            elif i < len(self.exploits):
                differences.append(
                    f"Extra exploit in self at index {i}: {self.exploits[i]}"
                )
            else:
                differences.append(
                    f"Extra exploit in other at index {i}: {other.exploits[i]}"
                )

        # Compare open ports
        self_open_ports = [port for port in self.ports if port.open]
        other_open_ports = [port for port in other.ports if port.open]
        max_open_ports = max(len(self_open_ports), len(other_open_ports))
        for i in range(max_open_ports):
            if i < len(self_open_ports) and i < len(other_open_ports):
                port_diff = self_open_ports[i].compare(other_open_ports[i])
                if port_diff:
                    differences.append(
                        f"PortState difference at index {i}: {port_diff}"
                    )
            elif i < len(self_open_ports):
                differences.append(
                    f"Extra open port in 'self' at index {
                        i}: {self_open_ports[i]}"
                )
            else:
                differences.append(
                    f"Extra open port in 'other' at index {
                        i}: {other_open_ports[i]}"
                )

        # Compare filesystem
        if self.filesystem != other.filesystem:
            differences.append(
                f"File system differences: {
                    set(self.filesystem) ^ set(other.filesystem)}"
            )

        # Compare users
        if self.users != other.users:
            differences.append(
                f"User differences: {set(self.users) ^ set(other.users)}"
            )

        return differences

    def prompt(self, indent=""):
        output = f"{indent}Endpoint State:\n"
        output += f"{indent}  Exploits:\n"
        for exploit in self.exploits:
            output += exploit.prompt(indent=indent + "    ")
        output += f"{indent}  Ports:\n"
        for port in self.ports:
            output += port.prompt(indent=indent + "    ")
        output += f"{indent}  File System:\n"
        if isinstance(self.filesystem, str):
            output += f"{indent}    {self.filesystem}\n"
        else:
            for filesystem_entry in self.filesystem:
                if isinstance(filesystem_entry, str):
                    output += f"{indent}    {filesystem_entry}\n"
                else:
                    for path, permissions in filesystem_entry.items():
                        output += f"{indent}    {path}: {permissions}\n"
        output += f"{indent}  Users:\n"
        for user in self.users:
            output += f"{indent}    {user}\n"
        return output


class NetworkState(State):
    """
    NetworkState class represents a collection of states, each associated with an IP address.
    Each state contains exploits and ports information.

    Attributes:
        states (Dict[str, EndpointState]): A dictionary where keys are IP addresses and values are EndpointState objects.

    Methods:
        from_dict(cls, data): Creates a NetworkState object from a dictionary.
        add(ip: str, state: EndpointState): Adds a new state for the given IP address.
        add_new(ip: str): Adds a new empty state for the given IP address.
        merge(newstate, target="127.0.0.1"): Merges the current object with a new State.
        __add__(self, newstate): Merges two state objects.
        __str__(): Returns a string representation of the states.
        __getitem__(self, key): Gets the state associated with the given IP address.
        __setitem__(self, key, value): Sets the state for the given IP address.
        one_hot_encode(): One-hot encodes all EndpointState objects in 'states'.

    NOTE: see tests/state/test_state_constructions.py for examples
    """

    states: Dict[str, EndpointState] = Field(default_factory=dict)

    def __init__(
        self,
        states: Optional[Dict[str, Union[EndpointState, dict]]] = None,
        *args,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)
        if states:
            self.states = {
                ip: EndpointState.from_dict(
                    state) if isinstance(state, dict) else state
                for ip, state in states.items()
            }
        else:
            self.states = {}

        for ip in TARGET_IP_ADDRESSES:
            if ip not in self.states:
                self.add_new(ip)

    @classmethod
    def from_dict(cls, data):
        if "states" not in data:
            raise ValueError("Input dictionary must contain a 'states' key")

        states = {
            ip: (
                EndpointState.from_dict(state_data)
                if isinstance(state_data, dict)
                else state_data
            )
            for ip, state_data in data["states"].items()
        }
        return cls(states=states)

    def add(self, ip: str, state: EndpointState) -> None:
        self.states[ip] = state

    def add_new(self, ip: str) -> None:
        state = deep_copy_state_v3(EndpointState())
        self.states[ip] = state

    def merge(self, newstate, target="127.0.0.1") -> None:
        """
        Merges the current object with a new State

        NOTE: overwrites self, with newstate.
        NOTE 2: see __add__ for the addition of two NetworkState objects.

        Supports both EndpointState and NetworkState.
        """
        if isinstance(newstate, EndpointState):
            self.states[target] = self._merge_states(
                self.states.get(target, EndpointState()), newstate
            )
        elif isinstance(newstate, NetworkState):
            aux_state = self + newstate  # NOTE: overwrites self, with newstate
            self.states = aux_state.states
        else:
            raise TypeError("Unknown state type")

    def _merge_states(self, state1, state2):
        """
        Helper function to merge two EndpointState objects
        """
        if isinstance(state1, dict):
            state1 = EndpointState.from_dict(state1)
        if isinstance(state2, dict):
            state2 = EndpointState.from_dict(state2)

        merged_state = copy.deepcopy(state1)

        # Merge exploits
        for expl in state2.exploits:
            if (
                isinstance(expl, ExploitState)
                and expl.launched
                and expl not in merged_state.exploits
            ):
                merged_state.exploits.append(expl)

        # Merge ports
        for port2 in state2.ports:
            if isinstance(port2, PortState) and port2.open:
                existing_port = next(
                    (p for p in merged_state.ports if p.port == port2.port), None
                )
                if existing_port:
                    # Update existing port information
                    existing_port.name = (
                        port2.name if port2.name else existing_port.name
                    )
                    existing_port.version = (
                        port2.version if port2.version else existing_port.version
                    )
                    existing_port.cpe = port2.cpe if port2.cpe else existing_port.cpe
                    existing_port.routes.update(port2.routes)
                    existing_port.vulnerabilities.extend(
                        [
                            v
                            for v in port2.vulnerabilities
                            if v not in existing_port.vulnerabilities
                        ]
                    )
                    existing_port.exploits.extend(
                        [e for e in port2.exploits if e not in existing_port.exploits]
                    )
                else:
                    # Add new port
                    merged_state.ports.append(port2)

        merged_state.filesystem = list(
            {
                tuple(item.items()) if isinstance(item, dict) else item
                for item in merged_state.filesystem + state2.filesystem
            }
        )

        merged_state.filesystem = list(
            {
                tuple(item.items()) if isinstance(item, dict) else item
                for item in merged_state.filesystem + state2.filesystem
            }
        )

        return merged_state

    def __add__(self, newstate):
        """
        Adds two instances of NetworkState content together to produce
        a new instance of NetworkState.

        The adding should account for all attributes of the two states and
        produce a new state with all the information from both, favouring
        the newstate when there is a conflict.
        """
        aux_state = copy.deepcopy(self)

        # NOTE: Adds each exploit and ports, for each ip
        for ip in newstate.states.keys():
            # if ip not in aux_state.states.keys(), add it
            if ip not in aux_state.states.keys():
                aux_state.add_new(ip)

            # Merge states for each IP
            aux_state.states[ip] = self._merge_states(
                aux_state.states[ip], newstate.states[ip]
            )

        return aux_state

    def __str__(self):
        return pprint.pformat(self.states)

    def full_str(self):
        return pprint.pformat(
            {ip: state.full_str() for ip, state in self.states.items()}
        )

    def __getitem__(self, key):
        if key not in self.states:
            self.add_new(key)
        return self.states[key]

    def __setitem__(self, key, value):
        self.states[key] = value

    def __repr__(self) -> str:
        return self.__str__()

    def dump(self) -> dict:
        return self.model_dump()

    def one_hot_encode(self):
        states_encoded = [state.one_hot_encode()
                                               for state in self.states.values()]
        flattened_states_encoded = [
            item for sublist in states_encoded for item in sublist
        ]
        return flattened_states_encoded

    def __eq__(self, other):
        if isinstance(other, NetworkState):
            if self.states.keys() != other.states.keys():
                return False
            return all(self.states[ip] == other.states[ip]
                       for ip in self.states)
        return False

    def compare(self, other):
        if not isinstance(other, NetworkState):
            return f"Cannot compare NetworkState with {type(other)}"

        differences = []

        # Compare IPs
        self_ips = set(self.states.keys())
        other_ips = set(other.states.keys())

        if self_ips != other_ips:
            differences.append(
                f"IP addresses differ: {
    self_ips.symmetric_difference(other_ips)}"
            )

        # Compare states for each IP
        for ip in self_ips.intersection(other_ips):
            state_diff = self.states[ip].compare(other.states[ip])
            if state_diff:
                differences.append(f"Differences for IP {ip}:")
                differences.extend(f"  {diff}" for diff in state_diff)

        return differences

    def prompt(self):
        output = "Network State:\n"
        for ip, endpoint in self.states.items():
            output += f"  IP: {ip}\n"
            if isinstance(endpoint, str):
                output += f"    {endpoint}\n"
            else:
                try:
                    output += endpoint.prompt(indent="    ")
                except AttributeError:
                    output += f"    {str(endpoint)}\n"
        return output


def deep_copy_state_v3(state_v3):
    new_exploits = []
    for exploit in state_v3.exploits:
        try:
            new_exploit = copy.deepcopy(exploit)
        except TypeError:
            # If deepcopy fails, create a new ExploitState with the same
            # attributes
            new_exploit = ExploitState(
                type_exploit=exploit.type_exploit,
                launched=exploit.launched,
                name=exploit.name,
            )
        new_exploits.append(new_exploit)

    new_ports = [copy.deepcopy(port) for port in state_v3.ports]
    new_filesystem = copy.deepcopy(state_v3.filesystem)
    return EndpointState(
        exploits=new_exploits, ports=new_ports, filesystem=new_filesystem
    )


def to_State(state: NetworkState, target: str = "127.0.0.1") -> NetworkState:
    """
    Returns a new state with deep copies of each object and subobject.
    """
    if type(state) == EndpointState:
        aux_state = NetworkState()
        aux_state.add(target, deep_copy_state_v3(state))
    elif type(state) == NetworkState:
        aux_state = NetworkState()
        for ip, state_v3 in state.states.items():
            if isinstance(state_v3, dict):
                state_v3 = EndpointState.from_dict(state_v3)
            elif isinstance(state_v3, str):
                # Handle the case where state_v3 is a string
                continue  # Skip this iteration or handle as needed
            aux_state.add(ip, deep_copy_state_v3(state_v3))
    else:
        aux_state = copy.deepcopy(state)

    return aux_state
