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

Module that keeps the classes of InuseXBuilder and InuseCBuilder
"""

from fbd.util import logutil
from fbd.topo import port
from fbd.pathfinder import pathfind_request, GLPK_util, GLPK_route
from fbd.pathfinder.builder import builder_base

log = logutil.getLogger()


class InuseXBuilder(builder_base.BuilderBase):
    """
    Construct the
    `.data` file section:
    `param inuse_X default 0 :=`
    
    **Attributes:**
    
    * `self.target_ports`: Set of target ports
    * `self.req`: `PathFindRequest`
    * `self.varidx_t`: `VarIdxTable`
    """

    def __init__(
        self,
        target_ports: list[port.Port],
        req: pathfind_request.PathFindRequest,
        varidx_t: builder_base.VarIdxTable,
    ):
        super().__init__()
        self.target_ports: set[port.Port] = set(target_ports)
        self.req: pathfind_request.PathFindRequest = req
        self.varidx_t: builder_base.VarIdxTable = varidx_t

    def build_main(self, name: str, route: GLPK_route.GLPKRoute):
        """
        Output GLPKRoute information
        """
        super().print_param_def(name, 0)

        table = builder_base.PortVarIdxTable()
        all_ch = self.req.channels
        for in_ch in all_ch:
            for out_ch in all_ch:
                table.clear()
                r_entry: GLPK_route.GLPKRouteEntry
                for r_entry in route.entry_list:
                    # "Exclude if not a GLPKRouteEntry channel
                    if (r_entry.src.is_used_channel(in_ch) is False) or (
                        r_entry.dst.is_used_channel(out_ch) is False
                    ):
                        continue

                    # Exclude if not a port within the target component.
                    if (r_entry.src.port not in self.target_ports) or (
                        r_entry.dst.port not in self.target_ports
                    ):
                        continue

                    if (
                        self.varidx_t.has_connection(
                            r_entry.src.port.full_name,
                            in_ch.full_no,
                            r_entry.dst.port.full_name,
                            out_ch.full_no,
                        )
                        is False
                    ):
                        log.warning(
                            "There is no connection to the reserved route. "
                            + "The topology.xml may have been changed. : "
                            + r_entry.dump()
                        )
                        continue
                    table.add_set(r_entry.src.port, r_entry.dst.port, 1)

                super().print_vtable_par_IJKL(
                    in_ch.full_no, out_ch.full_no, table
                )
        super().print_any(f";{GLPK_util.RET}")
        return super().build()

    def build(self):
        return self.build_main("inuse_X", self.req.used_route)


class InuseCBuilder(InuseXBuilder):
    """
    Build the `.data` file section:
    `param inuse_C default 0 :=`
    
    **Attributes:**
    
    * `self.used_conn`: A list or set of used connections
    """

    def __init__(
        self,
        target_ports: list[port.Port],
        req: pathfind_request.PathFindRequest,
        varidx_t: builder_base.VarIdxTable,
    ):
        super().__init__(target_ports, req, varidx_t)

    def build(self):
        return super().build_main("inuse_C", self.req.used_conn)
