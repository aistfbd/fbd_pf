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

Module that implements the processing for the deltmp operation.
"""

from fbd.util import logutil
from fbd.pathfinder.ope import opebase, reserve


log = logutil.getLogger()


class Deltmp(opebase.OpeBase):
    """
    Class that executes the deltmp subcommand.
    
    Attributes:
        self.op_args: Option values
            Default values are set once when the object is created,
            and thereafter overwritten by the superclass values.
    
    Default values:
        defo_args = {'deltmp': True}
    """

    defo_args = opebase.OPT_DELTMP[1]

    usage = "[true|false]"

    def __init__(
        self,
    ):
        super().__init__("deltmp", None, Deltmp.usage)
        self.op_args = Deltmp.defo_args

    def parse_options(self, input_args: list[str]):
        """
        Parses options and sets the values in self.op_args.
        """
        return super().parse_true_false_option(opebase.KEY_DELTMP, input_args)

    def operation(self):
        """
        Main operation
        """
        opt_val: bool = super().get_bool_opt(opebase.KEY_DELTMP)
        opebase.DELTMP = opt_val
        return f"Delete GLPK temporary files : {opt_val}"
