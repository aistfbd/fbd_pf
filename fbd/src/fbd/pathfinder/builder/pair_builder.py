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

Module that keeps the class of PairBuilder
"""

from fbd.util import logutil
from fbd.topo import topology, channel_table, port
from fbd.pathfinder import GLPK_util
from fbd.pathfinder.builder import builder_base


log = logutil.getLogger()


class PairBuilder(builder_base.BuilderBase):
    """
    Constructs the following section in the `.data` file:
        param pair default 0 :=
    
    Attributes:
        self.topo: Topology
        self.channels: List of target channels
        self.target_ports: List of target ports
        self.varidx_table: VarIdxTable object
    """

    def __init__(
        self,
        topo: topology.Topology,
        channels: list[channel_table.Channel],
        target_ports: list[port.Port],
        varidx_t: builder_base.VarIdxTable,
    ):

        super().__init__()
        self.topo = topo
        self.channels: list[channel_table.Channel] = channels
        self.target_ports: list[port.Port] = target_ports
        self.varidx_table: builder_base.VarIdxTable = varidx_t

    def _get_pair_VT_idx(
        self,
        pair: port.PortPair,
        in_ch: channel_table.Channel,
        out_ch: channel_table.Channel,
    ):
        """
        Retrieve index information from the PortVarIdxTable
        """
        v = self.varidx_table.get_idx(
            pair.src.full_name,
            in_ch.full_no,
            pair.dst.full_name,
            out_ch.full_no,
        )
        if v is not None:
            return v
        else:
            log.warning(
                f"has no idx {pair.src.full_name}/{in_ch.full_no}/{pair.dst.full_name}/{out_ch.full_no}"
            )
            return super().NO_VT_IDX

    def build(self):
        portidx_tbl = builder_base.PortVarIdxTable()
        super().print_param_def("pair", 0)
        pairs: list[list[port.PortPair]]
        for ch in self.channels:
            for pairs in self.topo.get_all_portpairs_list():
                if len(pairs) != 2:
                    msg = (
                        "ERROR: port pair size should be 2 : {pairs.pairkey=}"
                    )
                    log.error(msg)
                    raise ValueError(msg)

                pair0: port.PortPair = pairs[0]
                pair1: port.PortPair = pairs[1]
                """
                Port pairs with the same pair key become pair0 and pair1.
                Example:
                - pair0
                <net code="2" name="/DN4_DN5_01-1" pair="/DN4_DN5_01-0">
                  <node ref="N1004" pin="12"/>
                  <node ref="N1209" pin="3"/>
                  <cost>0.1</cost>
                
                - pair1
                <net code="3" name="/DN4_DN5_01-0" pair="/DN4_DN5_01-1">
                  <node ref="N1004" pin="11"/>
                  <node ref="N1209" pin="4"/>
                  <cost>0.1</cost>
                
                Here, since we want to output the vt_idx of the other pair, 
                for pair1 we set the vt_idx of pair0 in the portidx_tbl.
                
                param vt =
                  [N1004_12,WDM32_1,*,WDM32_1] N1209_3 432  <- pair0
                  [N1209_4,WDM32_1,*,WDM32_1] N1004_11 701  <- pair1
                
                param pair =
                  [N1004_12,WDM32_1,N1209_3,WDM32_1] 701  <- vt_idx of pair1
                  [N1209_4,WDM32_1,N1004_11,WDM32_1] 432  <- vt_idx of pair0
                """

                if (pair0.src not in self.target_ports) or (
                    pair1.src not in self.target_ports
                ):
                    continue
                portidx_tbl.add(
                    pair0.src,
                    pair0.dst,
                    self._get_pair_VT_idx(pair1, ch, ch),
                )
                portidx_tbl.add(
                    pair1.src,
                    pair1.dst,
                    self._get_pair_VT_idx(pair0, ch, ch),
                )
            super().print_vtable_par_IJKL(
                ch.full_no,
                ch.full_no,
                portidx_tbl,
            )

        super().print_any(f";{GLPK_util.RET}")
        return super().build()
