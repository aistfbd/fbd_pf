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

A module that contains the CostBuilder and OutOfServiceBuilder classes.
"""

from fbd.util import logutil
from fbd.topo import topology, channel_table, port, component, IJKL
from fbd.pathfinder import GLPK_util
from fbd.pathfinder.builder import builder_base

log = logutil.getLogger()


class IJKLCostBuiler(builder_base.BuilderBase):
    """
    A base class for CostBuilder and OutOfServiceBuilder
    Attributes:
        self.channels: A list of target Channels
        self.target_comps: A list of target components
        self.varidx_table: A VarIdxTable object
    """

    def __init__(
        self,
        channels: list[channel_table.Channel],
        target_comps: list[component.Component],
        varidx_t: builder_base.VarIdxTable,
    ):

        super().__init__()
        self.channels: list[channel_table.Channel] = channels
        self.target_comps: list[component.Component] = target_comps
        self.varidx_table: builder_base.VarIdxTable = varidx_t

    def _get_ports(self, val: str | int, comp: component.Component):
        """
        Returns a set of Ports determined from the value of "i" or "k"
        If * is specified, all Ports within the component are included.
        """
        if val == "*":
            return comp.get_all_ports()

        ports: set[port.Port] = set()
        for port_num in IJKL.get_ports(val):
            if (src := comp.get_port(port_num)) is None:
                log.error(
                    f"invalid Cost value: {port_num} is not exist {comp.name}"
                )
            else:
                ports.add(src)
        return ports

    def _print_value(
        self,
        comp: component.Component,
        src: port.Port,
        in_ch: channel_table.Channel,
        dst: port.Port,
        out_ch: channel_table.Channel,
        cost: dict[str : str | int],
        is_cost: bool,
        ijkl_set: set[str],
    ):
        """
        Outputs the values.
        If is_cost=True, also outputs the 'cost' value.
        """
        ijklkey = GLPK_util.port_lambda_pairkey(
            src.full_name,
            in_ch.full_no,
            dst.full_name,
            out_ch.full_no,
        )
        if ijklkey in ijkl_set:
            log.warning(
                f"Duplicate {'Cost' if is_cost else 'OutOfService'} "
                + f"description: {comp.name}/{cost} "
                + f"[{src.full_name},{in_ch.full_no},{dst.full_name},"
                + f"{out_ch.full_no}]"
            )
            return

        ijkl_set.add(ijklkey)

        if is_cost:
            super().print_any(
                f"[{src.full_name},{in_ch.full_no},{dst.full_name},"
                + f"{out_ch.full_no}] {cost['cost']}{GLPK_util.RET}"
            )
        else:
            super().print_any(
                f"({src.full_name},{in_ch.full_no},{dst.full_name},"
                + f"{in_ch.full_no}){GLPK_util.RET}"
            )

    def print_IJKL_cost(
        self,
        is_cost: bool,
    ):
        """
        Outputs the value of the "Cost" attribute of the Component.
        """
        for comp in self.target_comps:
            if is_cost:
                cost_list: list[dict] | None = comp.get_cost()
            else:
                cost_list: list[dict] | None = comp.get_outofservice()
            if cost_list is None:
                # print(f"{comp.name} is hot has cost")
                continue

            ijkl_set: set[str] = set()

            for cost in cost_list:
                # cost={'i': 29, 'j': '*', 'k': 14, 'l': '*', 'cost': 0.2}
                src_ports = self._get_ports(cost["i"], comp)
                dst_ports = self._get_ports(cost["k"], comp)

                for src in sorted(
                    src_ports,
                    key=lambda t: GLPK_util.natural_keys(t.full_name),
                ):
                    for dst in sorted(
                        dst_ports,
                        key=lambda t: GLPK_util.natural_keys(t.full_name),
                    ):
                        for in_ch in self.channels:
                            if (
                                IJKL.is_match_ch(cost["j"], in_ch.channel_no)
                                is False
                            ):
                                continue
                            if self.varidx_table.has_connection(
                                src.full_name,
                                in_ch.full_no,
                                dst.full_name,
                                in_ch.full_no,
                            ):
                                self._print_value(
                                    comp,
                                    src,
                                    in_ch,
                                    dst,
                                    in_ch,
                                    cost,
                                    is_cost,
                                    ijkl_set,
                                )


class OutOfServiceBuilder(IJKLCostBuiler):
    """
    Constructs the 
    set OUT_OF_SERVICES :=
     section of the .data file.

    """

    def __init__(
        self,
        channels: list[channel_table.Channel],
        target_comps: list[component.Component],
        varidx_t: builder_base.VarIdxTable,
    ):

        super().__init__(channels, target_comps, varidx_t)

    def build(self):
        super().print_set_def("OUT_OF_SERVICES")
        super().print_any(GLPK_util.RET)
        super().print_IJKL_cost(False)
        super().print_any(f";{GLPK_util.RET}")
        return super().build()


class CostBuilder(IJKLCostBuiler):
    """
    Constructs the 
    param cost default 0 :=
     section of the .data file.
    """

    def __init__(
        self,
        topo: topology.Topology,
        channels: list[channel_table.Channel],
        target_comps: list[component.Component],
        varidx_t: builder_base.VarIdxTable,
    ):

        super().__init__(channels, target_comps, varidx_t)
        self.topo: topology.Topology = topo

    def _print_net_cost(self):
        """
        Outputs the cost of the PortPair.
        """
        super().print_any(f"# net cost{GLPK_util.RET}")
        pair: port.PortPair
        for pair in self.topo.all_portpairs:
            for ch in self.channels:
                if self.varidx_table.has_connection(
                    pair.src.full_name,
                    ch.full_no,
                    pair.dst.full_name,
                    ch.full_no,
                ):
                    super().print_any(
                        f"[{pair.src.full_name},{ch.full_no},"
                        + f"{pair.dst.full_name},{ch.full_no}] "
                        + f"{pair.cost}{GLPK_util.RET}"
                    )

    def _print_comp_cost(self):
        """
        Output the cost  of Components.
        """
        super().print_any(f"# comp cost{GLPK_util.RET}")
        super().print_IJKL_cost(True)

    def build(self):
        super().print_param_def("cost", 0)
        self._print_net_cost()
        self._print_comp_cost()
        super().print_any(f";{GLPK_util.RET}")
        return super().build()
