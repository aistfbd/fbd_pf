""""
 * Copyright 2024 National Institute of Advanced Industrial Science and Technology
 * 
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 * 
 *     http://www.apache.org/licenses/LICENSE-2.0
 * 
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.

Module that holds the Port and PortPair classes.
"""

from __future__ import annotations
import re
from lxml import objectify
from fbd.util import logutil
from fbd.topo import channel_table

log = logutil.getLogger()


class Port:
    """
    Holds information of the "port" element from the topology file.

    Attributes:
        self.number: Value of the "number" attribute
        self.name: Value of the "name" attribute
        self.io: Value of the "io" attribute
        self.support_channel: Value of the "supportChannel" attribute
        self.full_name: Unique identifier name constructed as "{comp_name}_{self.number}"
        self.connected_ports: Set of ports paired as PortPair
        self.flow_ins: Set of ports that flow into this port
        self.flow_outs: Set of destination ports that output from this port
        self.type: Extracted "IN" or "OUT" from the "name" attribute value
        self.is_in: Whether this is INPUT or BiDi
        self.is_out: Whether this is OUTPUT or BiDi
        self.opposite_port: The opposite port
    """

    INPUT = "input"
    OUTPUT = "output"
    BIDI = "BiDi"

    def __init__(self, port: objectify.StringElement, comp_name: str):
        self.number: int | None = int(port.get("number"))
        self.name: str = port.get("name")
        self.io: str | None = port.get("io")
        self.support_channel: str = port.get("supportChannel")
        self.full_name: str = f"{comp_name}_{self.number}"
        self.connected_ports: set[Port] = set()
        self.flow_ins: set[Port] | None = None
        self.flow_outs: set[Port] | None = None
        """
        Extract the substring of uppercase letters (A-Z) that is enclosed by non-A-Z characters and also at the end of the string.
        Example:  
        /TEST_AWG32JD100_N1216_OUT17 -> OUT
        """
        self.type = re.sub(".+[^A-Z]([A-Z]+)[^A-Z]*$", r"\1", self.name)
        if self.io is not None:
            # INPUT or BiDi
            self.is_in: bool = self.io != self.OUTPUT
            # OUTPUT or BiDi
            self.is_out: bool = self.io != self.INPUT
        else:
            self.is_in: bool = "IN" in self.type
            self.is_out: bool = not self.is_in

        self.opposite_port: Port | None = None

    def add_connected_ports(self, port: Port):
        """
        Append the entry into self.connected_port
        """
        self.connected_ports.add(port)

    def is_connected(self, port: Port):
        """
        Return whether the given port is included in self.connected_ports.
        """
        return port in self.connected_ports

    def is_bidi(self):
        """
        Return whether it is bidirectional.
        """
        return self.io == self.BIDI

    def set_flow_inouts(self, flow_ins: set[Port], flow_outs: set[Port]):
        """
        Set values for self.flow_ins and self.flow_outs.
        """
        self.flow_ins = flow_ins
        self.flow_outs = flow_outs

    def set_opposite_port(self, p: Port):
        """
        Set the opposite port
        """
        self.opposite_port = p

    def get_opposite_port(self):
        """
        Get the opposite port
        """
        return self.opposite_port

    def has_opposite_port(self):
        """
        Whether to have the opposite port
        """
        return self.get_opposite_port() is not None

    def is_same_support_channel(self, input_support_channel: str):
        """
        Determine whether support_channel matches the input value.
        If either one is ANY, consider it a match.
        """
        if (input_support_channel == channel_table.ChannelTable.ANY) or (
            self.support_channel == channel_table.ChannelTable.ANY
        ):
            return True
        return self.support_channel == input_support_channel

    def is_opposite_name(self, tgt: Port):
        """
        Determine whether self.name corresponds to tgt.name as a pair.
        Return True if self.name is the port name with IN/OUT replaced.
        ex)self.name="/TEST_NetgearM4300_P207_SFP21_IN"
           tgt.name="/TEST_NetgearM4300_P207_SFP21_OUT"
           return True
        """
        if self.type == "IN":
            result = re.sub(r"(.+[^A-Z])IN([^A-Z]*$)", r"\1OUT\2", self.name)
        else:
            result = re.sub(r"(.+[^A-Z])OUT([^A-Z]*$)", r"\1IN\2", self.name)
        return result == tgt.name


class PortPair:
    """
    Holds connection information from the "net" element in the topology file.

    Attributes:
        self.pairkey: A unique key created based on the "pair" attribute
        self.src: Source Port
        self.dst: Destination Port
        self.cost: Value of the "cost" attribute
    """

    def __init__(self, key: str | None, src: Port, dst: Port, cost: float):
        if key is None:
            self.pairkey: str | None = None
        else:
            """
            /Dnode1/WXC_TPA_1-0 ->/Dnode1/WXC_TPA_1
            /DN4_DN5_03-1 ->/DN4_DN5_03
            """
            self.pairkey = re.sub("(.+)-[01]$", r"\1", key, 1)
        self.src: Port = src
        self.dst: Port = dst
        self.cost: float = cost

        if src.is_same_support_channel(dst.support_channel) is False:
            msg = f"invalid Net supportChannel are different: {src.full_name} -> {dst.full_name}"
            log.error(msg)
            raise ValueError(msg)
