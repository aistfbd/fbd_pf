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

A module that contains the FlowInOutPortBuilder class.
"""

from fbd.topo import topology, component, port
from fbd.pathfinder import GLPK_util
from fbd.pathfinder.builder import builder_base


class FlowInOutPortBuilder(builder_base.BuilderBase):
    """
    Constructs the
    set FlowInPorts[XX] :=
    and
    set FlowOutPorts[XX] :=
    sections of the .data file.
    
    When creating skeleton data for solvec, get_target_component() returns an empty list, so nothing is output.
    When creating solvec data, ports that are not targets for output are not included.
    
    Attributes:
        self.solvec: Indicates whether it is a solvec calculation
        self.topo: Topology
        self.target_ports: List of target ports
        self.target_comps: List of target components
    """

    def __init__(
        self,
        solvec: bool,
        topo: topology.Topology,
        target_ports: list[port.Port],
        target_comps: list[component.Component],
    ):
        super().__init__()
        self.solvec: bool = solvec
        self.topo: topology.Topology = topo
        self.target_ports: list[port.Port] = target_ports
        self.target_comps: set[component.Component] = set(target_comps)

    def build(self):
        for p in self.target_ports:
            if (self.solvec is True) and (
                self.topo.get_component_by_port(p) in self.target_comps
            ) is False:
                continue
            super().print_set_def_idx("FlowInPorts", p.full_name)
            super().print_ports(
                {
                    flow_port
                    for flow_port in p.flow_ins
                    if flow_port in self.target_ports
                }
            )
            super().print_any(f";{GLPK_util.RET}")
            super().print_set_def_idx("FlowOutPorts", p.full_name)
            super().print_ports(
                {
                    flow_port
                    for flow_port in p.flow_outs
                    if flow_port in self.target_ports
                }
            )
            super().print_any(f";{GLPK_util.RET}")
        return super().build()
