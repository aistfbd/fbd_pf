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

Module that keeps the class of VinUseBuilder
"""

from fbd.topo import port, component
from fbd.pathfinder import GLPK_util, GLPK_route, pathfind_request
from fbd.pathfinder.builder import builder_base


class VinUseBuilder(builder_base.BuilderBase):
    """
    Constructs the following section in the `.data` file:
        set Vinuse :=
    
    Attributes:
        self.req: PathFindRequest
        self.target_comps: Set of target components
    """

    def __init__(
        self,
        req: pathfind_request.PathFindRequest,
        target_comps: list[component.Component],
    ):
        super().__init__()
        self.req: pathfind_request.PathFindRequest = req
        self.target_comps: set[component.Component] = set(target_comps)

    def build(self):
        used_ports: set[port.Port] = set()
        entry: GLPK_route.GLPKRouteEntry
        for entry in self.req.used_route.entry_list:
            assert entry.x is True, f"ASSERT! x is False: {entry.dump()}"
            if (
                (
                    self.req.topo.get_component_by_port(entry.src.port)
                    in self.target_comps
                )
                is False
            ) or (
                (
                    self.req.topo.get_component_by_port(entry.dst.port)
                    in self.target_comps
                )
                is False
            ):
                continue

            used_ports.add(entry.src.port)
            used_ports.add(entry.dst.port)

        super().print_set_def("Vinuse")
        super().print_ports(used_ports)
        super().print_any(f";{GLPK_util.RET}")
        return super().build()
