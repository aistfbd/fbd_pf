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

Module that implements the processing for the dumpglpsol operation
"""

from fbd.util import logutil
from fbd.pathfinder.ope import opebase, reserve


log = logutil.getLogger()


class Dumpglpsol(opebase.OpeBase):
    """
    Class that executes the dumpglpsol subcommand.
    
    Attributes:
        self.op_args: Option values.
                      Default values are set once at object creation,
                      and subsequently overwritten by the superclass values.
    
    Default values:
        defo_args = {'dump': False}
    """
    defo_args = opebase.OPT_DUMP[1]

    usage = "[true|false]"

    def __init__(
        self,
    ):
        super().__init__("dumpglpsol", None, Dumpglpsol.usage)
        self.op_args = Dumpglpsol.defo_args

    def parse_options(self, input_args: list[str]):
        """
        Parses options and sets values in self.op_args.
        """
        return super().parse_true_false_option(opebase.KEY_DUMP, input_args)

    def operation(self):
        """
        Main operation
        """
        opt_val: bool = super().get_bool_opt(opebase.KEY_DUMP)
        opebase.DUMP_GLPSOL = opt_val
        return f"Dump glpsol output : {opt_val}"
