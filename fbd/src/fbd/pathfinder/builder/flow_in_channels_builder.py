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
 
A module that contains the FlowInChannelsBuilder class.
"""

from fbd.topo import port
from fbd.pathfinder import GLPK_util
from fbd.pathfinder.builder import builder_base


class FlowInChannelsBuilder(builder_base.BuilderBase):
    """
    Constructs the 
    set FlowInChannels[PORT] :=
     section of the .data file.
     Attributes:
        self.varidx_table: A VarIdxTable object
        self.target_ports: A list of target ports

    """

    def __init__(
        self,
        varidx_t: builder_base.VarIdxTable,
        target_ports: list[port.Port],
    ):
        super().__init__()
        self.varidx_table: builder_base.VarIdxTable = varidx_t
        self.target_ports: list[port.Port] = target_ports

    def build(self):
        for p in self.target_ports:
            super().print_set_def_idx("FlowInChannels", p.full_name)
            super().print_list(
                self.varidx_table.get_flow_in_channels(p.full_name)
            )
            super().print_any(f";{GLPK_util.RET}")
        return super().build()
