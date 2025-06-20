"""
 * Copyright 2024 National Institute of Advanced Industrial Science and Technology
 * 
 * Licensed under the Apache License, Version 2.0 (the "License")
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

Module that implements common processing for all operations.
"""

import os
from fbd.topo import topology
from fbd.util import logutil

log = logutil.getLogger()

DUMP_GLPSOL = False
DELTMP = True

# 値を持たない
NONE_VAL: int = -1

# 値を1つ持つ
ONE_VAL: int = 1

# 複数の値を持つ
ANY_VAL: int = 0

KEY_BI = "bi"
KEY_SRC = "s"
KEY_DST = "d"
KEY_ERO = "ero"
KEY_CH = "ch"
KEY_WDMSA = "wdmsa"
KEY_PROCESS = "p"
KEY_GLOBALID = "g"
KEY_QUIET = "q"
KEY_DB = "db"
KEY_MODEL = "model"
KEY_DATA = "data"
KEY_DELTMP = "deltmp"
KEY_DUMP = "dump"

# List of tuples: [{option definitions}, {default values}]
OPT_BI = ({f"-{KEY_BI}": NONE_VAL}, {KEY_BI: False})
OPT_SRC = ({f"-{KEY_SRC}": ONE_VAL}, {KEY_SRC: None})
OPT_DST = ({f"-{KEY_DST}": ONE_VAL}, {KEY_DST: None})
OPT_ERO = ({f"-{KEY_ERO}": ANY_VAL}, {KEY_ERO: None})
OPT_CH = ({f"-{KEY_CH}": ANY_VAL}, {KEY_CH: None})
OPT_WDMSA = ({f"-{KEY_WDMSA}": NONE_VAL}, {KEY_WDMSA: False})
OPT_PROCESS = (
    {f"-{KEY_PROCESS}": ONE_VAL},
    {KEY_PROCESS: f"{os.cpu_count()}"},
)
OPT_GLOBALID = ({f"-{KEY_GLOBALID}": ONE_VAL}, {KEY_GLOBALID: None})
OPT_BI = ({f"-{KEY_BI}": NONE_VAL}, {KEY_BI: False})
OPT_QUIET = ({f"-{KEY_QUIET}": NONE_VAL}, {KEY_QUIET: False})
OPT_DB = ({f"-{KEY_DB}": NONE_VAL}, {KEY_DB: False})
OPT_MODEL = ({f"-{KEY_MODEL}": ONE_VAL}, {KEY_MODEL: None})
OPT_DATA = ({f"-{KEY_DATA}": ONE_VAL}, {KEY_DATA: None})
OPT_DELTMP = ({KEY_DELTMP: ONE_VAL}, {KEY_DELTMP: DELTMP})
OPT_DUMP = ({KEY_DUMP: ONE_VAL}, {KEY_DUMP: DUMP_GLPSOL})


class OpeBase:
    """
    Base class for all operation classes.
    
    Attributes:
        self.name: Name of the operation
        self.topo: Topology
        self.op_args: Option values
        self.usage: Usage string
    """

    def __init__(self, name: str, topo: topology.Topology, usage: str):
        self.name: str = name
        self.topo: topology.Topology = topo
        self.op_args: dict[str : str | set(str)] = None
        self.usage: str = usage

    def parse_options(
        self,
        options_def: dict[str:str],
        defo_args: dict[str:str],
        input_args: list[str],
    ):
        """
        Parses options in input_args based on options_def and defo_args provided by the subclass,
        and sets them in self.op_args.
        """

        # Set default values each time the operation is called
        self.op_args = defo_args.copy()

        for key in options_def.keys():
            """
            options_def = {'-bi': NONE_VAL, '-s': ONE_VAL, '-d': ONE_VAL ..}
            options_def.keys() = ['-bi', '-s', '-d' ..]
            input_args = ['reserve', '-d', '123', '-s', '345', '-wdm', 'WDM32_5', 'WDM32_7']
            op_args = {'bi': False, 's': None, 'd': None, 'ero': None, ..}
            """
            if key not in input_args:
                continue

            idx: int = input_args.index(key)
            if options_def[key] == ONE_VAL:
                """
                An argument that takes a single value.
                Example: -d <dst>
                """

                if len(input_args) <= (idx + 1):
                    raise ValueError(f"option {key} must have a value")

                value: str = input_args[idx + 1]

                if value.startswith("-"):
                    raise ValueError(f"option {key} must have a value")

            # Remove the leading "-" and set it as a key in op_args
                self.op_args[key[1:]] = value

                # Remove the parts set in self.op_args

                del input_args[idx : idx + 2]
            elif options_def[key] == NONE_VAL:
                """
                Argument without a value.
                Example: -bi
                """

                self.op_args[key[1:]] = True
                del input_args[idx]
            else:
                """
                Argument with a variable number of values.  
                Example: -ero <ero1 ero2 ero3 ...>
                """

                valset: list[str] = []
                num = 1
                if len(input_args) <= (idx + 1):
                    raise ValueError(f"option {key} must have some values")

                for val in input_args[idx + 1 :]:
                    if val.startswith("-"):
                        break
                    valset.append(val)
                    num += 1
                if len(valset) == 0:
                    raise ValueError(f"option {key} must have some values")
                self.op_args[key[1:]] = valset
                del input_args[idx : idx + num]

    def parse_true_false_option(self, key: str, input_args: list[str]):
        """
        Parses options specified as [true|false]  
        and sets self.op_args[TRUEFALSE] to True or False.
        
        Example: input_args = {'dump', True}
        """

        if len(input_args) <= 1:
            return
        if input_args[1] == "true":
            self.op_args[key] = True
        elif input_args[1] == "false":
            self.op_args[key] = False
        else:
            raise ValueError(f"specify with [true|false]: {input_args[1]}")

    def get_required_opt(self, key: str):
        """
        Returns the required option value.  
        Raises an error if the value is missing.
        """
        value: str | bool | None = self.op_args[key]
        if value is None:
            msg = f"-{key} is Required options"
            log.error(msg)
            raise ValueError(msg)
        return value

    def get_int_opt(self, key: str):
        """
        Returns an option value that has a numeric value.
        """
        value: str | None = self.op_args[key]
        try:
            return int(value)
        except Exception as e:
            msg = f"-{key} {value} is invalid: {e}"
            log.error(msg)
            raise Exception(msg) from e

    def get_bool_opt(self, key: str):
        """
        Returns a boolean option value.
        """
        return self.op_args[key]

    def get_opt(self, key: str):
        """
        Returns an optional option value.
        """
        return self.op_args[key]
