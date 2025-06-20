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

A module that contains the IJK2LsBuilder class.
"""

from fbd.topo import topology, component, port
from fbd.pathfinder import GLPK_util
from fbd.pathfinder.builder import builder_base


class IJK2LsBuilder(builder_base.BuilderBase):
    """
    Constructs the
    set IJK2Ls[INPORT,INCH,OUTPORT] := OUTCH;
    section of the .data file.

    Attributes:
        self.solvec: Indicates whether it is a solvec calculation
        self.topo: Topology
        self.varidx_table: A VarIdxTable object
        self.target_ports: List of target ports
        self.target_comps: Set of target components
    """

    def __init__(
        self,
        solvec: bool,
        topo: topology.Topology,
        varidx_t: builder_base.VarIdxTable,
        target_ports: list[port.Port],
        target_comps: list[component.Component],
    ):
        super().__init__()
        self.solvec: bool = solvec
        self.topo: topology.Topology = topo
        self.varidx_table: builder_base.VarIdxTable = varidx_t
        self.target_ports: list[port.Port] = target_ports
        self.target_comps: set[component.Component] = set(target_comps)

    def build(self):
        for in_port in self.target_ports:
            """
            When using solvec,
            the relationship involves all ports within target_comps (components already used in pf)
             ∈ 
            target_ports (all ports within the target components).
            Therefore, target_ports includes ports that have not been used in pf as well.            
            """
            if (self.solvec is True) and (
                self.topo.get_component_by_port(in_port) in self.target_comps
            ) is False:
                continue
            for in_ch_name in sorted(
                self.varidx_table.get_flow_in_channels(in_port.full_name),
                key=GLPK_util.natural_keys,
            ):
                for out_port in sorted(
                    in_port.flow_outs,
                    key=lambda t: GLPK_util.natural_keys(t.full_name),
                ):
                    if out_port not in self.target_ports:
                        continue
                    super().print_set_def_idx(
                        "IJK2Ls",
                        f"{in_port.full_name},{in_ch_name},{out_port.full_name}",
                    )
                    super().print_list(
                        self.varidx_table.get_flow_out_channels(
                            in_port.full_name,
                            in_ch_name,
                            out_port.full_name,
                        )
                    )
                    super().print_any(f";{GLPK_util.RET}")
        return super().build()
