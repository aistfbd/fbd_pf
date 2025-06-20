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

Module that implements the processing for the pathfind　operation
"""

from __future__ import annotations

from fbd.util import logutil
from fbd.topo import topology
from fbd.pathfinder import GLPK_util, pathfind_request
from fbd.pathfinder.ope import reserve
from fbd.pathfinder import reservation_manager


log = logutil.getLogger()


class PathFind(reserve.Reserve):
    """
    Class that executes the pathfind subcommand.  
    Inherits from the Reserve class and uses the same options.
    """
    def __init__(
        self,
        topo: topology.Topology,
        topo_xml: str,
        glpk_dir: str,
        rsv_mgr: reservation_manager.ReservationManager,
    ):
        super().__init__("pathfind", topo, topo_xml, glpk_dir, rsv_mgr)

    def _pathfind(self, req: pathfind_request.PathFindRequest):
        """
        Executes path calculation and returns the path.  
        PathFind: runOperation()
        """
        self.globalid: str = (
            reservation_manager.ReservationManager.get_new_reservationID()
        )
        if (glpk_route := self.query(req)) is None:
            msg = f"PROBLEM HAS NO PRIMAL FEASIBLE SOLUTION{GLPK_util.RET} {req.get_errmsg()}"
            raise RuntimeError(msg)
        return glpk_route.dump_route(req.topo, req.src)

    def operation(self):
        """
        Main processing function.  
        Creates the request, executes path calculation, and returns the path.
        """

        # Initialize the globalid
        self.globalid = None
        req: pathfind_request.PathFindRequest = super()._make_request()
        return self._pathfind(req)
