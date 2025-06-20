"""
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

Module that holds Component class
"""

import re
from lxml import objectify
import json
from fbd.util import logutil
from fbd.topo import port, channel_table
from fbd.pathfinder import available_connection

log = logutil.getLogger()


class Component:
    """
    Holds information for each "comp" element in the topology file.
    
    Attributes:
        self.name: str = Holds the attribute value of the "ref" element
        self.model: Holds the value of the "Model" attribute
        self.GLPK: Holds the value of the "GLPK" attribute
        self.controller: Holds the value of the "Controller" attribute
        self.port: Holds the value of the "Socket" attribute
        self.tableid: Holds the attribute value of the "GLPKchannelTableId" element
        self.supchs: Set of supportChannels for each Port
        self.ac: AvailableConnection object
        self.cost_txt: Holds the value of the "Cost" attribute (in JSON format) as a dictionary
        self.all_ports: Dictionary of {port number: Port object}
    """

    NO_SOCKET_PORT = -1

    def __init__(self, comp: objectify.ObjectifiedElement):
        self.name: str = comp.get("ref")
        self.model: str | None = None
        self.GLPK: str | None = None
        self.controller: str | None = None
        self.port: int | None = None
        self.tableid: str | None = None
        self.supchs: set[str] | None = None
        self.ac: available_connection.AvailableConnection | None = None
        self.cost_txt: (
            dict[str : list[dict[str : int | float | str]]] | None
        ) = None
        self.all_ports: dict[int : port.Port] = self._make_all_ports(comp)
        self._set_opposite_port()

        for f in comp.field:
            name = f.get("name")
            if name == "Model":
                self.model = f.text
            elif name == "GLPK":
                self.GLPK = f.text
            elif name == "Controller":
                self.controller = f.text
            elif name == "Socket":
                self.port = int(f.text)
            elif name == "Cost":
                # JAVAだとCompCost.java:getInstance()で&quote;を置換している
                txt = f.text.replace("&quot;", '"')
                try:
                    self.cost_txt = json.loads(txt)
                except Exception as e:
                    msg = f"Error loading Cost by {self.name}: {e}"
                    log.error(msg)
                    raise Exception(msg) from e
            tableid = f.get("GLPKchannelTableId")
            if tableid is not None:
                self.tableid = tableid

    def _make_all_ports(self, comp: objectify.ObjectifiedElement):
        """
        Create Port object and append it into ports_dic
        """
        ports_dic: dict[int : port.Port] = {}
        for p in comp.ports.port:
            port_obj: port.Port = port.Port(p, self.name)
            ports_dic[port_obj.number] = port_obj
        return ports_dic

    def set_supchs(self, all_channeltable_id: set[str]):
        """
        Hold the port object's support_channel as a set.  
        If set to ANY, all channel tables will be considered support channels.
        """
        p: port.Port
        self.supchs = set()
        for p in self.get_all_ports():
            if p.support_channel == channel_table.ChannelTable.ANY:
                self.supchs = all_channeltable_id
                return
            self.supchs.add(p.support_channel)

    def get_all_ports(self):
        """
        Return all the Port object
        """
        return self.all_ports.values()

    def _search_opposite_port(self, p: port):
        """
        Return the opposite port for port `p`.

        The opposite port is defined as one that satisfies one of the following conditions:
        1. If io = "BiDi", the port itself is returned.
        2. A port exists whose name is the same as `p` but with "IN"/"OUT" swapped, and whose io is in the opposite direction.
        3. Within the same Comp, if there is only one port with an io type different from `p` (input vs output), that port is returned.
        """
        #JAVAではPort.java:getOppositePort()で設定

        if p.is_bidi():
            # 1, If io=”BiDi”, return the self port
            return p
        opposite_ports: set[port.Port] | None = set()

        for tgt in self.get_all_ports():
            if (p.is_in == tgt.is_in) or (
                p.is_same_support_channel(tgt.support_channel) is False
            ):
                continue
            if p.is_opposite_name(tgt) is True:
                # 2, A port exists whose name is the same as `p` but with "IN"/"OUT" swapped, and whose io is in the opposite direction.
                return tgt

            opposite_ports.add(tgt)
            # 3. Within the same Comp, if there is only one port with an io type different from `p` (input vs output), that port is returned.
            
        if len(opposite_ports) == 1:
            return list(opposite_ports)[0]

    def _set_opposite_port(self):
        """
        Set the opposite port for the Port object
        """
        p: port.Port
        for p in self.get_all_ports():
            p.set_opposite_port(self._search_opposite_port(p))

    def has_controller(self):
        """
        Whether to hold (store) the address of the intermediate controller.
        """
        return (
            (self.controller is not None)
            and (len(self.controller) > 0)
            and (self.controller != "TBD")
            and (self.port is not None)
            and (self.port > self.NO_SOCKET_PORT)
        )

    def get_port(self, num: int):
        """
        Obtain a port from its number.
        """
        return self.all_ports.get(num)

    def set_ac(self, ac: available_connection.AvailableConnection | None):
        """
        Set the AvailableConnection object
        """
        self.ac = ac

    def is_pseude(self):
        """
        Determine whether the "ref" name indicates 
        an Application terminal (pseudo-component)
         that starts with "p".
        """
        return self.name.startswith("P")

    def get_cost(self):
        """
        Return the value of the "Cost" key in the "Cost" attribute.
        """
        if self.cost_txt is not None:
            return self.cost_txt.get("Cost")
        return None

    def get_outofservice(self):
        """
        Return the value of the "OutOfService" key in the "Cost" attribute.
        """
        if self.cost_txt is not None:
            return self.cost_txt.get("OutOfService")
        return None
