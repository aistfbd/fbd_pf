"""
 * Copyright 2024 National Institute of Advanced Industrial Science and Technology
 * 
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use self file except in compliance with the License.
 * You may obtain a copy of the License at
 * 
 *     http://www.apache.org/licenses/LICENSE-2.0
 * 
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.

Module that defines PathFindRequest and related functions.
"""

from __future__ import annotations
import copy
from fbd.topo import topology, channel_table, port, component, GLPK
from fbd.pathfinder import GLPK_util, GLPK_route, reservation_manager


class PathFindRequest:
    """
    Holds data for path calculation.
    
    Attributes:
        self.topo: Topology
        self.src: Source PortChannel
        self.dst: Destination PortChannel
        self.channels: List of channels to use
        self.solvec_target: Components used during solvec execution, stored as {Model: {Component, ...}}
        self.org_ero: List of ERO ports. None if the request is divided by ERO.
        self.next_used_ero: List of ERO ports for the next request; set when the request is divided by ERO.
        self.bidi: Boolean indicating if it is bidirectional
        self.used_route: Reserved useX routes
        self.used_conn: Reserved useC routes
        self.parent_req: PathFindRequest | None = parent request
        self.errors: list[str] = []
    """

    NO_SOCKET_PORT = -1

    def __init__(
        self,
        topo: topology.Topology,
        src: GLPK_route.PortChannel,
        dst: GLPK_route.PortChannel,
        channels: list[channel_table.Channel],
        solvec_target: tuple[GLPK.Model : set[component.Component]] | None,
        org_ero: list[port.Port] | None,
        next_used_ero: list[port.Port] | None,
        bidi: bool,
        used_route: GLPK_route.GLPKRoute,
        used_conn: GLPK_route.GLPKRoute,
        parent_req: PathFindRequest | None,
    ):
        self.topo: topology.Topology = topo
        self.src: GLPK_route.PortChannel = src
        self.dst: GLPK_route.PortChannel = dst
        self.channels: list[channel_table.Channel] = channels
        self.solvec_target: (
            tuple[GLPK.Model : set[component.Component]] | None
        ) = solvec_target
        self.org_ero: list[port.Port] | None = org_ero
        self.next_used_ero: list[port.Port] | None = next_used_ero
        self.bidi: bool = bidi
        self.used_route: GLPK_route.GLPKRoute = used_route
        self.used_conn: GLPK_route.GLPKRoute = used_conn
        self.parent_req: PathFindRequest | None = parent_req
        self.errors: list[str] = []


    @staticmethod
    def print_ero(ero: list[port.Port] | None):
        """
        Output the list of ero
        """
        if ero is None:
            return "None"
        return ",".join([p.full_name for p in ero])

    def make_next_ero(self, ero_in_topo: list[port.Port], req_idx: int):
        """
        Return a list of entries after req_idx plus self.dst.port.
        ex)ero_in_topo = [port1, port2, port3]
           req_idx = 0
           next_ero_ports = [port2, port3, dst_port]
        """
        next_idx = req_idx + 1
        if next_idx < len(ero_in_topo):
            next_ero_ports = ero_in_topo[next_idx:]
        else:
            next_ero_ports = []

        next_ero_ports.append(self.dst.port)
        return next_ero_ports

    def add_errmsg(self, msg: str):
        """
        Add the message into self.errors
        """
        self.errors.append(msg)
        if self.parent_req:
            self.parent_req.add_errmsg(msg)

    def get_errmsg(self):
        """
        Return the array of error messages as a single string
         joined by newlines.
        """
        return GLPK_util.RET.join(self.errors)

    def has_err(self):
        """
        Check whether there are any error messages.
        """
        return len(self.errors) > 0

    def dump_req(self, dump_parent: bool):
        """
        Output the PathFindRequest
        """
        tl: list[str] = []
        if dump_parent and self.parent_req is not None:
            tl.append("PARENT REQUEST")
            tl.append(self.parent_req.dump_req(False))
            tl.append()

        s: port.Port = self.src.port
        d: port.Port = self.dst.port
        tl.append(f"src = {s.full_name}, {s.support_channel}")
        tl.append(f"dst = {d.full_name}, {d.support_channel}")

        tl.append(f"channels = {[ch.full_no for ch in self.channels]}")
        tl.append(f"biDirection = {self.bidi}")
        tl.append(f"orgERO = {PathFindRequest.print_ero(self.org_ero)}")
        tl.append(
            f"nextUsedERO = {PathFindRequest.print_ero(self.next_used_ero)}"
        )
        return GLPK_util.RET.join(tl)


def make_new_req(
    topo: topology.Topology,
    src: GLPK_route.PortChannel,
    dst: GLPK_route.PortChannel,
    ch_list: list[channel_table.Channel],
    org_ero: list[port.Port] | None,
    bidi: bool,
    rsv_mgr: reservation_manager.ReservationManager | None,
):
    """
    Create a new PathFindRequest
    """

    used_route: GLPK_route.GLPKRoute = rsv_mgr.find_used_path()
    used_conn: GLPK_route.GLPKRoute = rsv_mgr.make_use_connection_list()
    return PathFindRequest(
        topo,
        src,
        dst,
        ch_list,
        None,
        org_ero,
        None,
        bidi,
        used_route,
        used_conn,
        None,
    )


def make_ero_req(
    src: GLPK_route.PortChannel,
    dst: GLPK_route.PortChannel,
    org: PathFindRequest,
    org_ero: list[port.Port],
    next_used_ero: list[port.Port],
    used_route: GLPK_route.GLPKRoute,
    used_conn: GLPK_route.GLPKRoute,
):
    """
    Partially copy org to create a new PathFindRequest for ERO path calculation.  
    used_route and used_conn are appended to with each subreq execution,  
    so they are shared across all subreqs.
    """
    return PathFindRequest(
        org.topo,
        src,
        dst,
        org.channels,
        org.solvec_target,
        org_ero,
        next_used_ero,
        org.bidi,
        used_route,
        used_conn,
        org,
    )


def make_pf_req(ch: channel_table.Channel, org: PathFindRequest):
    """
    Copy everything except ch from org to create
     a new PathFindRequest for pf.
    """
    return PathFindRequest(
        org.topo,
        org.src,
        org.dst,
        [ch],
        None,
        org.org_ero,
        org.next_used_ero,
        org.bidi,
        org.used_route,
        org.used_conn,
        org,
    )


def make_bi_req(
    org: PathFindRequest,
):
    """
    Create a new PathFindRequest for bidirectional calculation
     based on the GLPKRoute calculated per channel by pf.
    """
    return PathFindRequest(
        org.topo,
        org.src,
        org.dst,
        org.channels,
        org.solvec_target,
        org.org_ero,
        org.next_used_ero,
        org.bidi,
        GLPK_route.GLPKRoute(copy.copy(org.used_route.entry_list)),
        GLPK_route.GLPKRoute(copy.copy(org.used_conn.entry_list)),
        None,
    )


def make_solvec_req(
    channels: list[channel_table.Channel],
    org: PathFindRequest,
    solvec_target: tuple[GLPK.Model : set[component.Component]],
):
    """
    Create a new PathFindRequest for solvec based 
    on the GLPKRoute calculated by pf.
    """
    return PathFindRequest(
        org.topo,
        org.src,
        org.dst,
        channels,
        solvec_target,
        org.org_ero,
        org.next_used_ero,
        org.bidi,
        org.used_route,
        org.used_conn,
        org,
    )
