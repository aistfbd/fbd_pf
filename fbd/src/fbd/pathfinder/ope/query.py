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

Module implementing the query operation.  
For path calculation, it calls the functionality in reserve.py.
"""

from fbd.util import logutil
from fbd.topo import topology
from fbd.pathfinder import GLPK_util, reservation_manager
from fbd.pathfinder.ope import opebase


log = logutil.getLogger()


class Query(opebase.OpeBase):
    """
    Class that executes the query subcommand.
    
    Attributes:
        self.topo: Topology
        self.rsv_mgr: ReservationManager object that manages reservation information
    
    Option definitions -> {option value: number of arguments}  
    NONE_VAL indicates no argument (boolean True/False),  
    ANY_VAL indicates any number of arguments.  
    options_def = {'-g': ONE_VAL, '-q': NONE_VAL, '-db': NONE_VAL}
    
    Default values:  
    defo_args = {'g': None, 'q': False, 'db': False}
    """

    options_def = (
        opebase.OPT_GLOBALID[0] | opebase.OPT_QUIET[0] | opebase.OPT_DB[0]
    )
    defo_args = (
        opebase.OPT_GLOBALID[1] | opebase.OPT_QUIET[1] | opebase.OPT_DB[1]
    )

    usage = "-g <globalid | id> [-q] [-db]"

    def __init__(
        self,
        topo: topology.Topology,
        rsv_mgr: reservation_manager.ReservationManager,
    ):

        super().__init__("query", None, Query.usage)
        self.topo: topology.Topology = topo
        self.rsv_mgr: reservation_manager.ReservationManager = rsv_mgr

    def parse_options(self, input_args: list[str]):
        """
        Parses options and sets the values in self.op_args.
        """
        return super().parse_options(
            Query.options_def, Query.defo_args, input_args
        )

    def _dump_all_reserve(
        self, rsv_list: list[reservation_manager.Reservation], quiet: bool
    ):
        """
        Output the reservation information of rsv_list
        """
        buf: list[str] = []
        for rsv in rsv_list:
            buf.append("----------------------------------------------------")
            rsv.dump(buf)
            if quiet is False:
                buf.append(rsv.glpk_route.dump_route(self.topo, rsv.src))
        return GLPK_util.RET.join(buf)

    def operation(self):
        """
        Main processing function.  
        Displays path reservation information.  
        
        If the db option is specified, outputs reservation info both in memory and in the database  
        based on the global ID given by the -g option.  
        
        If the db option is not specified, retrieves the global ID from the ID given by -g  
        and outputs the reservation info in memory only.  
        
        If the -g option is not provided, outputs all reservation information.
        """
        id: str = super().get_opt(opebase.KEY_GLOBALID)
        db_opt: str = super().get_bool_opt(opebase.KEY_DB)
        rsv_list: list[reservation_manager.Reservation] | None = None
        if id is not None:
            rsv: reservation_manager.Reservation | None = None
            if db_opt:
                if id.startswith("urn") is False:
                    msg = (
                        "when specifying the -db option, "
                        + "please specify globalid as -g"
                    )
                    log.error(msg)
                    raise ValueError(msg)
                globalid = id
            else:
                globalid: str | None = self.rsv_mgr.id_mgr.get_globalid_by_id(
                    id
                )
            if globalid is not None:
                rsv = self.rsv_mgr.get(globalid, db_opt)
                rsv_list = [rsv]
            if rsv is None:
                return f"cannot find reservation: {id}"
        else:
            rsv_list = self.rsv_mgr.get_all(db_opt)

        reply = self._dump_all_reserve(
            rsv_list, super().get_bool_opt(opebase.KEY_QUIET)
        )
        if len(reply) == 0:
            return "No Reservation"
        return reply
