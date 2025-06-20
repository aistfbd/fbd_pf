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

Module that handles the terminate and TERMINATEALL operations.
"""

from fbd.util import logutil
from fbd.pathfinder import GLPK_util
from fbd.pathfinder.ope import opebase
from fbd.pathfinder import reservation_manager


log = logutil.getLogger()


class Terminate(opebase.OpeBase):
    """
    Class to execute the `terminate` subcommand.
    
    Attributes:
        self.rsv_mgr: A ReservationManager object that manages reservation information.
    
    Option definition -> {option: number of arguments}  
    NONE_VAL means no argument (takes a True/False value), ANY_VAL means it takes any number of arguments.  
    options_def = {'-g': ONE_VAL, '-db': NONE_VAL}
    
    Default values:  
    defo_args = {'g': None, 'db': False}
    """

    options_def = opebase.OPT_GLOBALID[0] | opebase.OPT_DB[0]
    defo_args = opebase.OPT_GLOBALID[1] | opebase.OPT_DB[1]

    usage = "-g <globalid | id> [-db]"

    def __init__(
        self,
        rsv_mgr: reservation_manager.ReservationManager,
    ):

        super().__init__("terminate", None, Terminate.usage)
        self.rsv_mgr: reservation_manager.ReservationManager = rsv_mgr

    def parse_options(self, input_args: list[str]):
        """
        Parse options and set values to self.op_args.
        """
        return super().parse_options(
            Terminate.options_def, Terminate.defo_args, input_args
        )

    def operation(self):
        """
        Main process.  
        Deletes path reservation information.  
        If the db option is specified, delete both from memory and the database  
        based on the global ID specified with -g.  
        If the db option is not specified, determine the global ID from the ID specified with -g,  
        and delete only from memory.
        """
        id: str = super().get_required_opt(opebase.KEY_GLOBALID)
        db_opt: str = super().get_bool_opt(opebase.KEY_DB)

        delete_mem: bool = False
        delete_DB: bool = False
        errmsg = ""
        if db_opt:
            if id.startswith("urn") is False:
                msg = (
                    "when specifying the -db option, "
                    + "please specify globalid as -g"
                )
                log.error(msg)
                raise ValueError(msg)
            delete_mem = self.rsv_mgr.delete(id)
            try:
                delete_DB = self.rsv_mgr.delete_DB(id)
            except Exception as e:
                errmsg = f"{e}{GLPK_util.RET}"
        else:
            globalid: str | None = self.rsv_mgr.id_mgr.get_globalid_by_id(id)
            if globalid is not None:
                delete_mem = self.rsv_mgr.delete(globalid)

        if (delete_mem is False) and (delete_DB is False):
            return f"{errmsg}cannot find reservation: {id}"

        if delete_mem and delete_DB:
            return f"{errmsg}delete from memory and DB: {id}"

        return f"{errmsg}delete from {'memory' if delete_mem else 'DB'}: {id}"


class TERMINATEALL(opebase.OpeBase):
    """
    Class to execute the TERMINATEALL subcommand.
    
    Attributes:
        self.rsv_mgr: A ReservationManager object that manages reservation information.
    
    Option definition -> {option: number of arguments}  
    NONE_VAL means no argument (takes a True/False value), ANY_VAL means it takes any number of arguments.  
    options_def = {'-db': NONE_VAL}
    
    Default values:  
    defo_args = {'db': False}
    """

    options_def = opebase.OPT_DB[0]
    defo_args = opebase.OPT_DB[1]

    usage = "[-db]"

    def __init__(
        self,
        rsv_mgr: reservation_manager.ReservationManager,
    ):

        super().__init__("TERMINATEALL", None, TERMINATEALL.usage)
        self.rsv_mgr: reservation_manager.ReservationManager = rsv_mgr

    def parse_options(self, input_args: list[str]):
        """
        Parse options and set the values to self.op_args.
        """
        return super().parse_options(
            TERMINATEALL.options_def, TERMINATEALL.defo_args, input_args
        )

    def operation(self):
        """
        Main process.  
        Deletes all path reservation information.
        """
        db_opt: str = super().get_bool_opt(opebase.KEY_DB)
        self.rsv_mgr.delete_all()
        if db_opt:
            self.rsv_mgr.delete_DB_all()
            return "delete all reservation from memory and DB"
        else:
            return "delete all reservation from memory"
