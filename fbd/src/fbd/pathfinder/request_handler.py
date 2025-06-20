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

Module that manages and calls each operation.
"""

from fbd.topo import topology
from fbd.util import logutil, elapse
from fbd.pathfinder import reservation_manager
from fbd.pathfinder import GLPK_util
from fbd.pathfinder.ope import (
    opebase,
    pathfind,
    reserve,
    terminate,
    writeDB,
    query,
    deltmp,
    dumpglpsol,
)

log = logutil.getLogger()


class RequestHandler:
    """
    Class that holds operation objects for each subcommand,  
    and parses and executes requests from clients.
    
    Attributes:
        self.cmd2op: Dictionary {subcommand name: operation object}
    """

    def __init__(
        self,
        topo: topology.Topology,
        topo_xml: str,
        glpk_dir: str,
        db: bool,
    ):

        self.cmd2op: dict[str : opebase.OpeBase] = {}
        self.rsv_mgr = reservation_manager.ReservationManager(
            topo, topo_xml, db
        )
        self._init_cmd2op(topo, topo_xml, glpk_dir)

    def _add_ope(self, ope: opebase.OpeBase):
        self.cmd2op[ope.name] = ope

    def _init_cmd2op(
        self,
        topo: topology.Topology,
        topo_xml: str,
        glpk_dir: str,
    ):
        """
        Create new operation objects for each subcommand and build cmd2op.
        """
        cmd2op: dict[str : opebase.OpeBase] = {}
        self._add_ope(
            pathfind.PathFind(topo, topo_xml, glpk_dir, self.rsv_mgr)
        )
        self._add_ope(
            reserve.Reserve("reserve", topo, topo_xml, glpk_dir, self.rsv_mgr)
        )
        self._add_ope(writeDB.WriteDB(self.rsv_mgr))
        self._add_ope(terminate.Terminate(self.rsv_mgr))
        self._add_ope(terminate.TERMINATEALL(self.rsv_mgr))
        self._add_ope(query.Query(topo, self.rsv_mgr))
        self._add_ope(deltmp.Deltmp())
        self._add_ope(dumpglpsol.Dumpglpsol())
        return cmd2op

    def _print_all_usage(self):
        """
        Return the usage for all operations.
        """
        usage_buf: list[str] = [
            f"usage: {op.name} {op.usage}" for op in self.cmd2op.values()
        ]
        return GLPK_util.RET.join(usage_buf)

    def handle_req(self, data: str):
        """
        Parse the string data and execute the corresponding operation.  
        If no matching operation is found, return the usage.
        """

        """
        Convert a string into a list.
        ex) reserve -d 123 -s 345 -wdm WDM32_5 WDM32_7
        ->['reserve', '-d', '123', '-s', '345', '-wdm', 'WDM32_5', 'WDM32_7']
        """
        args: list[str] = data.split()

        ope: opebase.OpeBase | None = self.cmd2op.get(args[0])
        if ope is None:
            return self._print_all_usage()
        try:
            ope.parse_options(args)
        except ValueError as e:
            log.error(e)
            return f"usage: {ope.name} {ope.usage}"

        # For debug
        """
        elp = elapse.Elapse()
        reply = ope.operation()
        elp.show(ope.name)
        log.info(reply)
        """
        elp = elapse.Elapse()

        try:
            reply = ope.operation()
        except Exception as e:
            errmsg = f"ERROR: {e}"
            elp.show(ope.name)
            log.error(errmsg)
            reply = errmsg
        else:
            elp.show(ope.name)
            log.info(reply)

        return reply

    def close_DB(self):
        self.rsv_mgr.rsv_DB_mgr.close()
