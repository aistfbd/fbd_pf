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

Module that holds the results of glpsol for path calculation.
"""

from __future__ import annotations
import re
import sys
from fbd.util import logutil
from fbd.topo import topology, port, channel_table
from fbd.pathfinder import (
    GLPK_util,
    GLPK_route,
    GLPK_constant,
    pathfind_request,
)


log = logutil.getLogger()


class GLPKResult:
    """
    Holds the results of glpsol.
    
    Attributes:
        self.req: PathFindRequest
        self.cost: Cost
        self.stdout: Output result from glpsol
    """

    def __init__(
        self, req: pathfind_request.PathFindRequest, cost: int, stdout: str
    ):
        super().__init__()
        self.req: pathfind_request.PathFindRequest | None = req
        self.cost: float | None = cost
        self.stdout: str | None = stdout

    def dump_solution(self):
        """
        Output the results of the path calculation to the log.
        """
        tl: list[str] = []
        tl.append("solution")
        # print(f"------------------------STDOUT=> {self.stdout} <======")
        for line in self.stdout.splitlines():
            if line.startswith("#"):
                tl.append(line)
        log.info(str.strip(GLPK_util.RET.join(tl)))

    def has_answer(self):
        """
        Returns whether there is a solution.
        """
        return self.cost < GLPK_constant.NOT_FOUND_COST

    def make_route_entry_list(self):
        """
        Create a list of GLPKRouteEntry from the pf glpsol result,  
        add it to GLPKRoute, and return it.  
        GLPKUtil.java: makeRouteEntryList()
        """
        topo: topology.Topology = self.req.topo
        route_list: list[GLPK_route.GLPKRouteEntry] = []
        lines: list[str] = self.stdout.splitlines()
        # print(self.stdout)
        for line in lines:
            if line.startswith("#") is False:
                continue

            v: list[str] = re.split(r"[ \t]+", line)
            if len(v) != 10:
                continue

            isX = v[5] == "1"
            isC = v[6] == "1"
            if (isX is False) or (isC is False):
                continue

            src: GLPK_route.PortChannel = GLPK_route.PortChannel(
                topo.get_port_by_name(v[1]),
                topo.get_channel_by_fullno(v[2]),
            )
            dst: GLPK_route.PortChannel = GLPK_route.PortChannel(
                topo.get_port_by_name(v[3]),
                topo.get_channel_by_fullno(v[4]),
            )
            route_entry: GLPK_route.GLPKRouteEntry = GLPK_route.GLPKRouteEntry(
                src, dst, isX, isC, True
            )

            if route_entry.has_none_obj():
                msg = "glpsol output is invalid"
                log.error(msg)
                raise RuntimeError(msg)

            route_list.append(route_entry)

        return GLPK_route.GLPKRoute(route_list)

    def make_conn_entry_list(self):
        """
        Create a list of GLPKRouteEntry from the glpsol results of solvec,  
        add it to GLPKRoute, and return it.
        """
        topo: topology.Topology = self.req.topo
        route_list: list[GLPK_route.GLPKRouteEntry] = []
        lines: list[str] = self.stdout.splitlines()

        b_found: bool = False
        for line in lines:
            if line.startswith("#") is False:
                if "SOLUTION FOUND" in line:
                    b_found = True
                continue

            v: list[str] = re.split(r"[ \t]+", line)
            if len(v) != 7:
                continue

            isC = v[5] == "1"
            if isC is False:
                continue

            src: GLPK_route.PortChannel = GLPK_route.PortChannel(
                topo.get_port_by_name(v[1]),
                topo.get_channel_by_fullno(v[2]),
            )
            dst: GLPK_route.PortChannel = GLPK_route.PortChannel(
                topo.get_port_by_name(v[3]),
                topo.get_channel_by_fullno(v[4]),
            )

            route_entry: GLPK_route.GLPKRouteEntry = GLPK_route.GLPKRouteEntry(
                src, dst, False, isC, True
            )

            if route_entry.has_none_obj():
                msg = "solvec glpsol output is invalid"
                log.error(msg)
                raise RuntimeError(msg)

            route_list.append(route_entry)
            b_found = True

        if b_found:
            return GLPK_route.GLPKRoute(route_list)
        else:
            return None

    @staticmethod
    def compare_key(result: GLPKResult):
        """
        Return the list used for comparison when sorting the result list.  
        result = [cost, channel number]  
        Elements are compared in order from the first element of the list.  
        GLPKWork: compareTo()
        """
        return [
            result.cost if result.cost is not None else 0,
            (
                result.req.channels[0].channel_no
                if result.req is not None
                else sys.maxsize
            ),
        ]
