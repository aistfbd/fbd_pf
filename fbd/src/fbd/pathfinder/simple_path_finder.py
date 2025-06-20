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

Module that calculates routes based on the flow_outs information of a Port.  
Used for calculating bi-directional routes.
"""

from __future__ import annotations
from enum import IntEnum, auto
from fbd.topo import topology, port
from fbd.util import logutil

log = logutil.getLogger()


class Status(IntEnum):
    """
    Class that holds the status during pred setting.  
    INIT: Initialization state  
    APPEND: Value has been set in self.pred  
    FIN: For each port in flow_outs, self has been set in their self.pred  
    """

    INIT = auto()
    APPEND = auto()
    FIN = auto()


class Entry:
    """
    Object paired with each port used in the SimplePathFinder class.
    
    Attributes:
        self.port: Port
        self.pred: Source port of flow_outs
        self.status: Status
        self.flow_outs: List of flow_outs ports
    """

    def __init__(self, port: port.Port):
        self.port: port.Port = port
        self.pred = None
        self.status = Status.INIT
        self.flow_outs: list[Entry] | None = None

    def clear(self):
        self.pred = None
        self.status = Status.INIT

    def set_flow_outs(self, entry_list: list[Entry]):
        self.flow_outs = entry_list


class SimplePathFinder:
    """
    Class for constructing paths based on the flow_outs information of each port.

    Attributes:
        self.name2entry:
    """

    def __init__(self, topo: topology.Topology):
        self.name2entry: dict[str:Entry] = {}
        for p in topo.get_all_port():
            entry: Entry = Entry(p)
            self.name2entry[p.full_name] = entry

        for entry in self.name2entry.values():
            entry.set_flow_outs(
                [
                    self.name2entry[out.full_name]
                    for out in entry.port.flow_outs
                ]
            )

    def _clear(self):
        for entry in self.name2entry.values():
            entry.clear()

    def search(
        self, topo: topology.Topology, src_port: port.Port, dst_port: port.Port
    ):
        path: list[port.Port] = []
        """
        Construct a path based on the flow_outs information of the port and return it as a list of Ports.
        """
        """
        If src and dst are within the same component, return src and dst as they are.
        """
        if (
            topo.get_component_by_port(src_port).name
            == topo.get_component_by_port(dst_port).name
        ):
            path.append(src_port)
            path.append(dst_port)
            return path

        self._clear()

        """
        Set the src entry as the pred for each entry in src's flow_outs.  
        For each flow_outs entry whose pred was set, also set its flow_outs entries’ pred similarly  
        to the original flow_outs entry.  
        Repeat this process until there are no more flow_outs.
        """
        src: Entry = self.name2entry[src_port.full_name]
        dst: Entry = self.name2entry[dst_port.full_name]

        src.status = Status.APPEND
        queue: list[Entry] = [src]
        while len(queue) > 0:
            u: Entry = queue[0]
            for v in u.flow_outs:
                if v.status != Status.INIT:
                    continue
                v.pred = u
                v.status = Status.APPEND
                queue.append(v)

            del queue[0]
            u.status = Status.FIN

        """
        Trace back from dst using pred, inserting each entry at the beginning of the path.
        """
        path.append(dst.port)
        e: Entry | None = dst.pred
        while e:
            path.insert(0, e.port)
            e = e.pred

        if len(path) > 1:
            return path
        else:
            return None
