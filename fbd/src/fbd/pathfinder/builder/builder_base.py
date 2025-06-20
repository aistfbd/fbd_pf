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

Module for common processing shared across all Builders
"""

from fbd.util import logutil
from fbd.pathfinder import GLPK_util
from fbd.topo import port, component


log = logutil.getLogger()


class VarIdxTable:
    """
    Attributes:
        self.conn2idx: dictionary of {"{in_port}@{in_ch}#{out_port}@{out_ch}" : self.next_idx} 
        self.flow_inch: dictionary of {in/output_port名: {in/out1_ChannelName, in/out2_ChannelName..} } 
        self.ijk2l: dictionary of {"{in_port}@{in_ch}#{out_port}@undef" : {out1_ChannelName, out2_ChannelName} }
        self.txt = output buffer for VarIdxTable
        self.next_idx: Index counter, incremented each time a new entry is added
    """

    def __init__(self):
        self.conn2idx: dict[str:int] = {}
        self.flow_inch: dict[str : set[str]] = {}
        self.ijk2l: dict[str : set[str]] = {}
        self.txt = None
        self.next_idx: int = BuilderBase.MIN_VT_IDX

    def add(
        self,
        in_port: str,
        in_ch: str,
        out_port: str,
        out_ch: str,
    ):
        """
        Add entries to each dictionary
        """
        key: str = GLPK_util.port_lambda_pairkey(
            in_port, in_ch, out_port, out_ch
        )
        self.conn2idx[key] = self.next_idx
        self.flow_inch.setdefault(in_port, set()).add(in_ch)
        self.flow_inch.setdefault(out_port, set()).add(out_ch)

        ijk_key = GLPK_util.port_lambda_pairkey_ijk(in_port, in_ch, out_port)
        self.ijk2l.setdefault(ijk_key, set()).add(out_ch)

        ret = self.next_idx
        self.next_idx += 1
        return ret

    def size(self):
        """
        Return the number of entries
        """
        return len(self.conn2idx)

    def get_idx(self, in_port: str, in_ch: str, out_port: str, out_ch: str):
        """
        Return the idx value
        """
        key = GLPK_util.port_lambda_pairkey(in_port, in_ch, out_port, out_ch)
        return self.conn2idx.get(key)

    def has_connection(
        self, in_port: str, in_ch: str, out_port: str, out_ch: str
    ):
        """
        Return whether the target entry exists in the object
        """
        return self.get_idx(in_port, in_ch, out_port, out_ch) is not None

    def get_flow_in_channels(self, port_name: str):
        """
        Return set() value of port of flow_in_channel
        """
        return self.flow_inch.get(port_name, set())

    def get_flow_out_channels(self, in_port: str, in_ch: str, out_port: str):
        """
        Return set() value of port of flow_out_channel
        """
        ijk_key = GLPK_util.port_lambda_pairkey_ijk(in_port, in_ch, out_port)
        return self.ijk2l.get(ijk_key, set())


class PortVarIdxTable:
    """
    Class that holds port_idx_map

    Attributes:
        self.port_idx_map: {inputportName: [(outputPortName, index),
                                          (outputPortName, index) ],
                    Dictionary having key: inputportName,
                            Value: list or set of tuples (outputPortName, index)
    """

    def __init__(self):
        self.port_idx_map: dict[
            str : list[tuple[str, int]] | set[tuple[str, int]]
        ] = {}

    def add(self, in_port: port.Port, out_port: port.Port, idx: int):
        """
        Add the entries
        Argument of (out_port,idx) should not be duplication of existing entries
        """
        assert (
            idx >= BuilderBase.MIN_VT_IDX
        ), f"ASSERT! invalid idx {in_port.full_name}/{out_port.full_name}/{idx}"

        self.port_idx_map.setdefault(in_port.full_name, []).append(
            (out_port.full_name, idx)
        )

    def add_set(self, in_port: port.Port, out_port: port.Port, idx: int):
        """
        Add entries
        Argument (out_port, idx) can be duplicated with the existing entries, 
        but the value is set, so the duplication is removed.
        """
        assert (
            idx >= BuilderBase.MIN_VT_IDX
        ), f"ASSERT! invalid idx {in_port.full_name}/{out_port.full_name}/{idx}"

        self.port_idx_map.setdefault(in_port.full_name, set()).add(
            (out_port.full_name, idx)
        )

    def clear(self):
        self.port_idx_map.clear()


class BuilderBase:
    """
    Base class for all Builders that construct .data and .model files
    
    Attributes:
        self.datalines: buffer for .data file export
        self.modellines: buffer for .model file export
    """

    MIN_VT_IDX: int = 1
    NO_VT_IDX: int = MIN_VT_IDX - 1

    def __init__(
        self,
        write_model: bool = False,
    ):
        self.datalines: list[str] = []
        if write_model:
            self.modellines: list[str] = []
        else:
            self.modellines = None

    def print_any_modelline(self, val: str):
        """
        Add arbitrary strings into self.modellines with line breaks
        """
        if self.modellines is not None:
            self.modellines.append(f"{val}{GLPK_util.RET}")

    def print_set_def(self, name: str):
        """
        Add "set XX :=" into self.datalines
        """
        self.datalines.append(f"set {name} :=")

    def print_set_def_idx(self, name: str, idx: str):
        """
        Add "set XX[XX] :=" into self.datalines
        """
        self.datalines.append(f"set {name}[{idx}] :=")

    def print_param_def(self, name: str, def_value: str):
        """
        Add "param XX default XX :=" into self.datalines
        """
        self.datalines.append(
            f"param {name} default {def_value} :={GLPK_util.RET}"
        )

    def print_param(self, name: str):
        """
        Make "param XX := " into self.datalines
        """
        self.datalines.append(f"param {name} := ")

    def print_any(self, val: str):
        """
        Add arbitrary strings into self.datalines
        """
        self.datalines.append(val)

    def print_list(self, values: list[str], sort=True):
        """
        Add entries of list of values into self.datalines
        Add line breaks every 10 entries
        """
        if len(values) == 0:
            return

        b_long: bool = len(values) > 10
        if b_long:
            self.datalines.append(f"\t# num={len(values)}")
        n: int = 0
        if sort is True:
            values = sorted(values, key=GLPK_util.natural_keys)
        for name in values:
            n += 1
            if b_long and ((n % 10) == 1):
                self.datalines.append(f"{GLPK_util.RET}\t")
            else:
                self.datalines.append(" ")
            self.datalines.append(name)

    def print_ports(self, ports: list[port.Port] | set[port.Port], sort=True):
        """
        Add port information into self.datalines
        """
        if (ports is None) or len(ports) == 0:
            return

        names: list[str] = [p.full_name for p in ports]
        self.print_list(names, sort)

    def build_modellines(self):
        """
        Translate self.modellines into strings
        """
        if self.modellines is not None:
            return "".join(self.modellines)

    def build(self):
        """
        Make strings from self.datalines, self.modellines
        """
        return "".join(self.datalines)

    def print_components(
        self,
        comps: list[component.Component] | set[component.Component],
        sort=False,
    ):
        """
        Add component information into self.datalines
        """
        if (comps is None) or (len(comps) == 0):
            return
        names: list[str] = [comp.name for comp in comps]
        self.print_list(names, sort)

    IJKL_IJK_FORMAT = "[%s,%s,*,%s]"
    IJKL_IJKL_FORMAT = "[%s,%s,%s,%s]"

    def print_vtable_par_IJL(
        self,
        in_ch: str,
        out_ch: str,
        table: PortVarIdxTable,
    ):
        """
        Make port connection information into the format of [INPORT,INCH,*,OUTCH] OUTPORT IDX
        """
        if len(table.port_idx_map) == 0:
            return ""

        for in_port in table.port_idx_map.keys():
            self.print_any(f"[{in_port},{in_ch},*,{out_ch}]")

            outidx_list = table.port_idx_map.get(in_port)
            values: list[str] = []
            for out_port, idx in outidx_list:
                values.append(out_port)
                values.append(f"{idx}")

            self.print_list(values, sort=False)
            self.print_any(GLPK_util.RET)

    def print_vtable_par_IJKL(
        self,
        in_ch: str,
        out_ch: str,
        table: PortVarIdxTable,
    ):
        """
        Make port connection information into the format of [INPORT,INCH,OUTPORT,OUTCH] OUTPORT IDX
        """
        map: list[tuple[str, int]] | set[tuple[str, int]]
        if len(table.port_idx_map) == 0:
            return
        for in_port in table.port_idx_map.keys():
            map = table.port_idx_map.get(in_port)
            for out_port, idx in map:
                self.print_any(f"[{in_port},{in_ch},{out_port},{out_ch}] ")
                self.print_any(f"{idx}{GLPK_util.RET}")
