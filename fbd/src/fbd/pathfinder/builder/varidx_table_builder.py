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

Module that keeps the class of VarIdxTableBuilder
"""

import os
import pickle
from fbd.util import logutil
from fbd.topo import port, topology, channel_table
from fbd.pathfinder import GLPK_util, pathfinder_util
from fbd.pathfinder.builder import builder_base


log = logutil.getLogger()


class VarIdxTableBuilder(builder_base.BuilderBase):
    """
    Sets values in the VarIdxTable object and constructs the
    param vt default 0 :=
    section in the .data file.
    If all channels are targeted, execution is performed in parallel for each channel.
    
    Attributes:
        self.topo: Holds the Topology object
        self.channels: List of target channels
        self.target_ports: List of target ports
        self.varidx_table: VarIdxTable object, created by make_varidx_table()
    """
    def __init__(
        self,
        topo: topology.Topology,
        channels: list[channel_table.Channel],
        target_ports: list[port.Port],
    ):
        super().__init__()
        self.topo: topology.Topology = topo
        self.channels: list[channel_table.Channel] = channels
        self.target_ports: list[port.Port] = target_ports
        self.varidx_table: builder_base.VarIdxTable | None = None

    def _build_channels(self):
        """
        Determines available connection information for each channel using parallel processing,
        stores the results in varidx_t, and returns it.
        """
        varidx_t = builder_base.VarIdxTable()

        results = []
        for ch in self.channels:
            results.append(self._work(ch))

        super().print_param_def("vt", super().NO_VT_IDX)
        for in_ch, conn_map in zip(self.channels, results):
            for out_ch_no in sorted(
                conn_map.keys(), key=GLPK_util.natural_keys
            ):
                portidx_tbl = builder_base.PortVarIdxTable()
                """
                portidx_tbl is the data format used to construct "vt" data.
                VarIdxTable does not maintain the correspondence between inport and outport.
                """

                for in_port, out_port in sorted(
                    conn_map[out_ch_no],
                    key=lambda t: GLPK_util.natural_keys(t[0].full_name),
                ):
                    idx = varidx_t.add(
                        in_port.full_name,
                        in_ch.full_no,
                        out_port.full_name,
                        out_ch_no,
                    )
                    portidx_tbl.add(in_port, out_port, idx)

                super().print_vtable_par_IJL(
                    in_ch.full_no, out_ch_no, portidx_tbl
                )
        super().print_any(f";{GLPK_util.RET}")

        super().print_param("NUM_VARS")
        super().print_any(f"{varidx_t.size()};{GLPK_util.RET}")

        varidx_t.txt = super().build()
        return varidx_t

    def _work(
        self,
        in_ch: channel_table.Channel,
    ):
        """
        Aggregates connection information for each channel.  
        Returns a dictionary `conn_map` where keys are channel names and values are lists of (in_port, out_port) tuples.
        """
        conn_map: dict[str : list[tuple(port.Port, port.Port)]] = {}
        in_port: port.Port
        out_port: port.Port

        for in_port in self.target_ports:
            for out_port in sorted(
                in_port.flow_outs,
                key=lambda t: GLPK_util.natural_keys(t.full_name),
            ):
                if out_port not in self.target_ports:
                    continue

                if pathfinder_util.has_connection(
                    self.topo, in_port, in_ch, out_port, in_ch
                ):
                    conn_map.setdefault(in_ch.full_no, []).append(
                        (in_port, out_port)
                    )
        return conn_map

    def _restore_varidx_table(self, varidx_t_file: str):
        """
        Reconstructs the VarIdxTable
        """
        if os.path.isfile(varidx_t_file):
            try:
                with open(varidx_t_file, "rb") as f:
                    self.varidx_table = pickle.load(f)
                    VarIdxTableBuilder.varidx_table_cache = self.varidx_table
                    return self.varidx_table
            except Exception as e:
                log.warning(f"load {varidx_t_file} is failed :{e}")
        return None

    def _save_varidx_table(self, varidx_t_file: str):
        """
        Saves the VarIdxTable to the varidx_t_file.
        """
        try:
            with open(varidx_t_file, "wb") as f:
                pickle.dump(self.varidx_table, f)
        except Exception as e:
            log.warning(f"write {varidx_t_file} is failed :{e}")

    def make_varidx_table(self, varidx_t_file: str | None):
        """
        Creates and returns the VarIdxTable.  
        In the case of solvec, since verification involves multiple channels and takes time,  
        the table created by make_skeleton_data() is saved to a file and then restored  
        in make_GLPK_data().
        """
        self.varidx_table = self._restore_varidx_table(varidx_t_file)
        if self.varidx_table is None:
            self.varidx_table = self._build_channels()
            self._save_varidx_table(varidx_t_file)
        return self.varidx_table

    def build(self):
        return self.varidx_table.txt
