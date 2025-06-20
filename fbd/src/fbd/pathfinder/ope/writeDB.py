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

Module that handles the writeDB operation.
"""

from fbd.util import logutil
from fbd.pathfinder import GLPK_util
from fbd.pathfinder.ope import opebase
from fbd.pathfinder import reservation_manager


log = logutil.getLogger()


class WriteDB(opebase.OpeBase):
    """
    Class to execute the reserve subcommand.
    
    Attributes:
        self.rsv_mgr: A ReservationManager object that manages reservation information.
        self.msg: A list that holds messages to be returned to the client.
                  Initialized in parse_options().
    """
    usage = ""

    def __init__(
        self,
        rsv_mgr: reservation_manager.ReservationManager,
    ):

        super().__init__("writeDB", None, "")
        self.rsv_mgr: reservation_manager.ReservationManager = rsv_mgr
        self.msg: list[str] = []

    def parse_options(self, input_args: list[str]):
        self.msg.clear()
        """
        writeDB does not take any options, so option parsing is not performed.  
        If any options are specified, a warning is output and the options are ignored.
        """
        if len(input_args) > 1:
            errmsg = (
                f"writeDB has no options, so options are ignored: {input_args}"
            )
            log.warning(errmsg)
            self.msg.append(errmsg)

    def operation(self):
        """
        Main process.  
        Writes reservation information that has not yet been written in ReservationManager to the database.
        """
        self.msg.append(self.rsv_mgr.write_DB())

        return GLPK_util.RET.join(self.msg)
