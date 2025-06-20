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

Module that holds the calculated route information.
"""

from __future__ import annotations
from fbd.util import logutil
from fbd.topo import topology, port, component, channel_table
from fbd.pathfinder import GLPK_util

log = logutil.getLogger()


class PortChannel:
    """
    Holds a set of Port and Channel used for path calculation.
    
    Attributes:
        self.port: Port object
        self.ch: Channel object, initially None
    """

    def __init__(self, p: port.Port, ch: channel_table.Channel | None):

        self.port: port.Port = p
        self.ch: channel_table.Channel | None = ch

    def is_used_channel(self, ch: channel_table.Channel):
        """
        Check if the channels match.
        """
        assert (
            self.ch is not None
        ), f"ASSERT! channel is None : {self.port.full_name}@None"

        return self.ch.full_no == ch.full_no

    def make_key(self):
        """
        Create a key to identify the object.
        """
        assert (
            self.ch is not None
        ), f"ASSERT! channel is None : {self.port.full_name}@None"

        return f"{self.port.full_name}@{self.ch.full_no}"


class GLPKRouteEntry:
    """
    Holds route information for src/dst.
    
    Attributes:
        self.src: src PortChannel
        self.dst: dst PortChannel
        self.x: Whether the route is used in pf calculation
        self.c: Whether the route is used in solvec calculation (always True for pf calculation)
        self.is_go: Whether it is a forward route
    """

    def __init__(
        self,
        src: PortChannel,
        dst: PortChannel,
        x: bool,
        c: bool,
        is_go: bool,
    ):
        self.src: PortChannel = src
        self.dst: PortChannel = dst
        self.x: bool = x
        self.c: bool = c
        self.is_go: bool = is_go

    def has_none_obj(self):
        """
        Returns whether there is a None object in PortChannel.
        """
        if (
            (self.src.port is None)
            or (self.dst.port is None)
            or (self.src.ch is None)
            or (self.dst.ch is None)
        ):
            log.error(
                f"{self.src.port.full_name if self.src.port is not None else 'None'}@"
                + f"{self.src.ch.full_no if self.src.ch is not None else 'None'}-"
                + f"{self.dst.port.full_name if self.dst.port is not None else 'None'}@"
                + f"{self.dst.ch.full_no if self.dst.ch is not None else 'None'}"
            )
            return True
        return False

    def dump(self):
        return (
            f"{self.src.make_key()} - {self.dst.make_key()},"
            + f" x={self.x}, c={self.c}, go={self.is_go}"
        )


class GLPKRoute:
    """
    Holds route information.
    
    Attributes:
        self.entry_list: List of GLPKRouteEntry objects
    """
    def __init__(self, entry_list: list[GLPKRouteEntry] | None):
        self.entry_list: list[GLPKRouteEntry] | None = entry_list

    def extend_list(self, entry_list: list[GLPKRouteEntry]):
        """
        Merge entry_list into self.entry_list.
        """
        if self.entry_list is None:
            self.entry_list = entry_list
        else:
            self.entry_list.extend(entry_list)

    def _entry2xkey(self, r_entry: GLPKRouteEntry):
        """
        Create a unique key from src, dst, and x.  
        NOTE: isC and isGo are ignored.  
        // In pathfind routes, isX=true, isC=true.  
        // In solveC newRoute, isX=false, isC=isGo=true.
        """

        return f"{r_entry.src.make_key()}@{r_entry.dst.make_key()}@{r_entry.x}"

    def merge_pf_route(self, new_list: list[GLPKRouteEntry]):
        """
        Add only GLPKRouteEntry objects from new_route whose src, dst, and x do not duplicate existing ones in self.entry_list.  
        GLPKRoute:appendPathFindRoute()
        """
        # Create an entry_set with no duplicate values of src, dst, and x
        entry_set: set[str] = {
            self._entry2xkey(entry) for entry in self.entry_list
        }

        for new_entry in new_list:
            assert new_entry.has_none_obj() is False, "ASSERT! channel is None"
            if new_entry.x and (self._entry2xkey(new_entry) not in entry_set):
                self.entry_list.append(new_entry)

    def _entry2ckey(self, r_entry: GLPKRouteEntry):
        """
        Create a unique key based on src, dst, and c.
        // NOTE: isX and isGo are ignored.
        // In pathfind routes, isX=true and isC=true.
        // In solveC newRoute, isX=false and isC=isGo=true.
        """

        return f"{r_entry.src.make_key()}@{r_entry.dst.make_key()}@{r_entry.c}"

    def merge_solvec_route(self, new_list: list[GLPKRouteEntry]):
        """
        Add only GLPKRouteEntry objects from new_route whose src, dst, and c do not duplicate those in self.entry_list.  
        GLPKRoute:appendSolveCRoute()
        """
        # Create an entry_set with unique src, dst, and c values (no duplicates)
        entry_set: set[str] = {
            self._entry2ckey(entry) for entry in self.entry_list
        }

        for new_entry in new_list:
            assert new_entry.has_none_obj() is False, "ASSERT! channel is None"
            if new_entry.c and (self._entry2ckey(new_entry) not in entry_set):
                self.entry_list.append(new_entry)

    def make_path_list(
        self,
        topo: topology.Topology,
        src: PortChannel,
        is_go: bool,
    ):
        """
        Starting from "src", follow the route entries in entry_list where x=true for src/dst,  
        and return the route information as a list of PortChannel objects.
        """
        map: dict[str:GLPKRouteEntry] = {
            entry.src.port.full_name: entry
            for entry in self.entry_list
            if (entry.x and (entry.is_go == is_go))
        }

        if (len(map) == 0) or (
            (is_go is False) and (src.port.full_name in map.keys() is False)
        ):
            return []

        port_channel_list: list[PortChannel] = []
        src_port: port.Port = topo.get_port_by_name(src.port.full_name)
        prev_port = None
        while len(map) > 0:
            e: GLPKRouteEntry | None = map.pop(src_port.full_name, None)
            if e is None:
                msg = f"Missing route entry for port {src_port.full_name}."
                +"Probably glpsol output is incorrect"
                log.error(msg)
                raise RuntimeError(msg)

            if (prev_port is None) or (
                e.src.port.full_name != prev_port.full_name
            ):
                port_channel_list.append(e.src)

            port_channel_list.append(e.dst)
            prev_port = src_port = e.dst.port

        return port_channel_list

    def _show_route(self, topo: topology.Topology, go_list: list[PortChannel]):
        """
        Outputs the route of go_list.
        """
        if go_list is None:
            return "null"
        if len(go_list) == 0:
            return "<empty>"

        route_list: list[str] = []
        for port_ch in go_list:
            # print(f"_show_route {port_ch.port.full_name}")
            comp: component.Component = topo.get_component_by_port(
                port_ch.port
            )
            route_list.append(
                f"{port_ch.port.full_name:8} ({port_ch.ch.full_no+')':15} "
                + f"{comp.model if comp.model is not None else 'null':33} "
                + f"{port_ch.port.io.upper():6} {port_ch.port.type}"
            )
        return GLPK_util.RET.join(route_list)

    def dump_route(self, topo: topology.Topology, src: PortChannel):
        """
        Outputs the bidirectional route starting from src.
        """
        go_list: list[PortChannel] = self.make_path_list(topo, src, True)
        buf: list[str] = []
        buf.append("go route")
        buf.append(self._show_route(topo, go_list))
        back_src: port.Port | None = go_list[-1].port.get_opposite_port()
        back_list: list[PortChannel] | None = None
        if back_src is not None:
            port_ch: PortChannel = PortChannel(back_src, src.ch)
            back_list = self.make_path_list(topo, port_ch, False)

        buf.append("back route")
        buf.append(self._show_route(topo, back_list))
        return GLPK_util.RET.join(buf)

    def dump(self):
        """
        for debug
        """
        return GLPK_util.RET.join([e.dump() for e in self.entry_list])
