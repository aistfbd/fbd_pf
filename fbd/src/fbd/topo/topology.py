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

Module that parses and holds topology files as objects.
"""

import os
import re
from lxml import etree, objectify
from fbd.util import logutil, param
from fbd.topo import channel_table, component, port
from fbd.pathfinder import available_connection, GLPK_constant, GLPK_util

log = logutil.getLogger()


def topology_filename(filename):
    return os.path.join("topo", filename)


class Topology:
    """
    Reads the topology file and holds the information.

    Attributes:
        self.topo: The root object of the topology information read with ObjectifiedElement
        self.name2table: Dictionary {ChannelTable name : ChannelTable object}
        self.name2comp: Dictionary {Component name : Component object}
        self.table2comp: Dictionary {ChannelTable name : Set of Components supporting that ChannelTable}
        self.fullno2ch: Dictionary {Channel name : Channel object}
        self.port2comp: Dictionary {Port object : Component object}
        self.name2port: Dictionary {Port name : Port object}
        self.srcdst2portpair: Dictionary {(src, dst) : PortPair object}
        self.pairkey2port: Dictionary {portpair key : [PortPair, PortPair]}
        self.all_portpairs: Set of all PortPairs
    """

    def __init__(self, filename: str, ac_conn_dir: str, init_full: bool):
        self.topo: objectify.ObjectifiedElement = self._make_topology_type(
            filename
        )
        self.name2table: dict[str : channel_table.ChannelTable] | None = None
        self.name2comp: dict[str : component.Component] | None = None
        self.table2comp: dict[str : set[component.Component]] | None = None
        self.fullno2ch: dict[str : channel_table.Channel] | None = None
        self.port2comp: dict[str : component.Component] | None = None
        self.name2port: dict[str : port.Port] | None = None
        self.srcdst2portpair: dict[tuple[str] : port.PortPair] | None = None
        self.pairkey2port: dict[str : list[port.PortPair]] | None = None
        self.all_portpairs: list[port.PortPair] | None = None
        self._init_child(ac_conn_dir, init_full)

    def _make_topology_type(self, filename: str):
        """
        Read the XML topology and create objects.
        """
        log.info(f"load topology: {os.path.join(param.TOPDIR, filename)}")
        try:
            schema = etree.XMLSchema(
                file=os.path.join("topo", "topo_lxml.xsd")
            )
            parser = objectify.makeparser(schema=schema)
        except Exception as e:
            errmsg = f"Error loading schema file: {e}"
            log.error(errmsg)
            raise Exception(errmsg) from e

        try:
            topology_root = objectify.parse(filename, parser=parser).getroot()
        except Exception as e:
            errmsg = f"Error loading topology file: {e}"
            log.error(errmsg)
            raise Exception(errmsg) from e
        return topology_root

    # TopologyType topology, File acConnDir
    def _init_child(self, ac_conn_dir: str, init_full: bool):
        """
        Create a list of child element objects.
        If self.topo.design or self.topo.components do not exist,
        checking here is unnecessary because make_topology_type() will produce an error
        when validating against topo_lxml.xsd.
        """
        channel_info = self.topo.design.channelInfo
        self.name2table = {}
        for table in channel_info.channelTable:
            if table.get("type") != "optical":
                log.warning(
                    f"not optical channelTable SKIP {table.get('id')}/{table.get('type')}"
                )
                continue
            c_table: channel_table.ChannelTable = channel_table.ChannelTable(
                table
            )
            self.name2table[c_table.channeltable_id] = c_table

        # set self.name2comp[]
        components = self.topo.components
        self.name2comp = {}
        self.port2comp = {}
        self.name2port = {}
        self.table2comp = {}

        comps: set[component.Component] = {
            component.Component(c) for c in components.comp
        }
        comp: component.Component
        p: port.Port
        all_channeltable_id: set[str] = {
            table.channeltable_id for table in self.get_all_channeltable()
        }
        for comp in sorted(
            comps, key=lambda t: GLPK_util.natural_keys(t.name)
        ):
            self.name2comp[comp.name] = comp
            for p in comp.get_all_ports():
                self.port2comp[p.full_name] = comp
                self.name2port[p.full_name] = p
            comp.set_supchs(all_channeltable_id)
            self._set_support_channeltable(comp)

        """
        for debug
        print_dic = {}
        for ch_no, comps in self.table2comp.items():
            for comp in comps:
                print_dic.setdefault(ch_no, set()).add(comp.name)
        print(print_dic)
        """
        if init_full is False:
            # In make_available_connection(), creating all objects is unnecessary.
            return

        # Create a dictionary mapping channel names to Channel objects, e.g. {WDM32_12: ch}
        self.fullno2ch = {
            ch.full_no: ch
            for table in self.get_all_channeltable()
            for ch in table.channels
        }

        self._load_all_connfiles(ac_conn_dir)
        self._make_portpair()
        self._make_flow_inout()

    def _set_support_channeltable(self, comp: component.Component):
        """
        Append the component into self.table2comp
        """
        for table in self.get_all_channeltable():
            if table.channeltable_id in comp.supchs:
                self.table2comp.setdefault(table.channeltable_id, set()).add(
                    comp
                )

    def _load_all_connfiles(self, ac_conn_dir: str):
        """
        Read the .conn files under the ac directory and store them in components.
        """
        checked_conn: dict[str : available_connection.AvailableConnection] = {}

        count = 0
        for comp in self.get_all_component():
            model = comp.model

            if model is None:
                # Those without a model name do not have connection information.
                continue

            if model in checked_conn.keys():
                """
                Since ac data with the same model name has already been created, use it.
                If load_connfile results in an error and ac=None, set it to None.
                """

                ac = checked_conn.get(model)
                comp.set_ac(ac)
                continue

            ac = self._load_connfile(
                os.path.join(
                    ac_conn_dir, GLPK_constant.get_ac_conn_filename(comp.model)
                ),
            )
            if ac:
                count = count + 1
                comp.set_ac(ac)
            checked_conn[model] = ac

        log.info(
            f"load {count} AvailableConnection files from "
            + os.path.abspath(ac_conn_dir)
        )

    def _load_connfile(self, conn_file: str):
        """
        Read the ac/.conn file and create an AvailableConnection object.
        """
        conn_set: set[str] = set()
        in2outs_dic: dict[int : set[int]] = {}

        try:
            with open(conn_file, "r") as fd:
                for line in fd:
                    """
                    line="(1,WDM32_1,2,WDM32_1)"
                    m.group(2)="WDM32_1"
                    m.group(4)="WDM32_1"
                    """
                    m = re.search(
                        r"\(([0-9]+),([^,]+),([0-9]+),([^,]+)\)", line
                    )
                    if m is None:
                        continue
                    inch: channel_table.Channel | None = (
                        self.get_channel_by_fullno(m.group(2))
                    )
                    outch: channel_table.Channel | None = (
                        self.get_channel_by_fullno(m.group(4))
                    )

                    if (
                        (inch is None)
                        or (outch is None)
                        or (inch.full_no != outch.full_no)
                    ):
                        errmsg = f"invalid channel : {line=}"
                        log.error(errmsg)
                        raise ValueError(errmsg)

                    conn = available_connection.ConnEntry(
                        int(m.group(1)), inch, int(m.group(3)), outch
                    )
                    conn_set.add(conn.key)
                    in2outs_dic.setdefault(conn.in_pin, set()).add(
                        conn.out_pin
                    )
        except Exception as e:
            msg = f"Error readlines {conn_file}: {e}"
            log.error(msg)
            raise Exception(e) from e
        ac = available_connection.AvailableConnection(conn_set, in2outs_dic)
        return ac

    def _make_portpair(self):
        """
        Create PortPair objects from the <nets> information in the topology file,
        and add them to srcdst2portpair and the connected_ports member of each port.
        """
        self.all_portpairs = []
        self.srcdst2portpair = {}
        self.pairkey2port = {}
        for net in self.topo.nets.net:
            node_list = net.node

            """
            len(node_list) is determined by topo_lxml.xsd, so it will not be anything other than 2.
            """
            comp: component.Component = self.get_component_by_name(
                node_list[0].get("ref")
            )
            if comp is not None:
                port1: port.Port | None = comp.get_port(
                    int(node_list[0].get("pin"))
                )
            else:
                port1 = None
            comp = self.get_component_by_name(node_list[1].get("ref"))
            if comp is not None:
                port2: port.Port | None = comp.get_port(
                    int(node_list[1].get("pin"))
                )
            else:
                port2 = None

            if (port1 is None) or (port2 is None):
                code = net.get("code")
                msg = f"invalid net. port is not exist code={code}"
                log.error(msg)
                continue

            pair_key: str | None = net.get("pair")
            cost: float | None = net.cost.text

            if port1.is_out:
                # port1 -> port2
                port1.add_connected_ports(port2)
                pair = port.PortPair(pair_key, port1, port2, cost)
            else:
                # port2 -> port1
                port2.add_connected_ports(port1)
                pair = port.PortPair(pair_key, port2, port1, cost)

            self.all_portpairs.append(pair)
            if pair_key is not None:
                self.srcdst2portpair[
                    (pair.src.full_name, pair.dst.full_name)
                ] = pair
                self.pairkey2port.setdefault(pair.pairkey, []).append(pair)
                """
            The following two portpairs have the same pairkey (= DN4_DN5_01).
                <net code="2" name="/DN4_DN5_01-1" pair="/DN4_DN5_01-0">
                <node ref="N1004" pin="12"/>
                <node ref="N1209" pin="3"/>
                <cost>0.1</cost>
                </net>
                <net code="3" name="/DN4_DN5_01-0" pair="/DN4_DN5_01-1">
                <node ref="N1004" pin="11"/>
                <node ref="N1209" pin="4"/>
                <cost>0.1</cost>
                """

    def _make_flow_inout(self):
        """
        Create lists of flow_in/flow_out ports and register them to each Port.

        A dictionary of {port name: {Port}}  
        flow_in_map: Ports flowing into the key port (value port -> key port)  
        flow_out_map: Ports flowing out from the key port (key port -> value port)
        """
        flow_in_map: dict[str : set[port.Port]] = {}
        flow_out_map: dict[str : set[port.Port]] = {}
        p: port.Port
        comp: component.Component

        for comp in self.get_all_component():
            ac: available_connection.AvailableConnection | None = comp.ac
            dst_port: port.Port
            for src_port in comp.get_all_ports():
                for dst_port in comp.get_all_ports():
                    has_conn: bool = False
                    if ac is not None:
                        # Check if there is an input/output pair in the component's ac
                        has_conn = ac.has_connection(
                            src_port.number, dst_port.number
                        )
                    elif src_port.full_name != dst_port.full_name:
                        has_conn = src_port.is_in and dst_port.is_out
                    else:
                        has_conn = False

                    if has_conn is True:
                        # src -> dst
                        flow_out_map.setdefault(src_port.full_name, set()).add(
                            dst_port
                        )
                        flow_in_map.setdefault(dst_port.full_name, set()).add(
                            src_port
                        )
                    for conn in dst_port.connected_ports:
                        # Search for connection information including ports outside the component
                        # dst -> conn
                        flow_out_map.setdefault(dst_port.full_name, set()).add(
                            conn
                        )
                        flow_in_map.setdefault(conn.full_name, set()).add(
                            dst_port
                        )
                        if dst_port.is_bidi():
                            # In the case of a bidirectional port
                            # conn -> dst also
                            flow_out_map.setdefault(conn.full_name, set()).add(
                                dst_port
                            )
                            flow_in_map.setdefault(
                                dst_port.full_name, set()
                            ).add(conn)

        for p in self.get_all_port():
            p.set_flow_inouts(
                flow_in_map.get(p.full_name, set()),
                flow_out_map.get(p.full_name, set()),
            )

    def get_all_channeltable(self):
        """
        Return all the Channel_Table
        """
        return self.name2table.values()

    def get_channeltable_by_id(self, id: str):
        """
        Return Channel_Table from channeltable_id
        """
        return self.name2table.get(id)

    def get_all_channel(self):
        """
        Return all the Channel
        """
        return self.fullno2ch.values()

    def get_channel_by_fullno(self, fullno: str):
        """
        Return channel from channel No
        """
        return self.fullno2ch.get(fullno)

    def get_all_component(self):
        """
        Return all the Component
        """
        return self.name2comp.values()

    def get_component_by_name(self, name: str):
        """
        Return Component from component name
        """
        return self.name2comp.get(name)

    def get_component_by_port(self, port: port.Port):
        """
        Return Component based on port
        """
        return self.port2comp[port.full_name]

    def get_all_port(self):
        """
        Return all the Port
        """
        return self.name2port.values()

    def get_port_by_name(self, name: str):
        """
        Return Port based on port name
        """
        return self.name2port.get(name)

    def find_portpair(self, src: port.Port, dst: port.Port):
        """
        Return the other PortPair with the same pair key
         as the src port and dst port.
        """
        pair: port.PortPair | None = self.srcdst2portpair.get(
            (src.full_name, dst.full_name)
        )
        if pair is None:
            return None

        pairs: list[port.PortPair] | None = self.pairkey2port[pair.pairkey]

        for p in pairs:
            if (p.src.full_name != src.full_name) and (
                p.dst.full_name != dst.full_name
            ):
                return p
        return None

    def get_all_portpairs_list(self):
        """
        Return a list of lists of PortPairs that have the same pairkey.
        ex)
        [ [portpair, portpair], [portpair, portpair], [portpair, portpair].. ]
        """
        return self.pairkey2port.values()

    def get_support_comps(self, channeltable_id: str):
        """
        Return the set of components that support
         the channel_table with the given channeltable_id.
        """
        return self.table2comp.get(channeltable_id, set())
