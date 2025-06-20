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
 */

Module that holds constraint expression information.
"""

import re
from typing import NamedTuple
from fbd.util import logutil
from fbd.topo import component

log = logutil.getLogger()

_VAR = "[a-zA-Z0-9_]+"


class Domain:
    """
    Holds the domain part.
    
    Attributes:
        self.var_inset: A dictionary holding strings of the form "A in BBB" as {"A": "BBB"}
        self.domain: Holds the string before the colon ":"
        self.cond: Holds the string after the colon ":"
    """

    VAR_INSET_STATEMENT = re.compile(f"({_VAR}) in ({_VAR})")

    def __init__(self, txt: str):
        """
        ex) str = "i in InputPort, j in Channels_WDM32, k in OutputPort,
            l in Channels_WDM32 : chNo[j] = chNo[l] && k = i + 1"

        self.domain = "i in InputPort, j in Channels_WDM32, k in OutputPort,
            l in Channels_WDM32"

        self.cond = "chNo[j] = chNo[l] && k = i + 1"

        self.var_inset = {"i": "InputPort", "j": "Channels_WDM32",
            "k": "OutputPort", "l": " Channels_WDM32"}
        """
        self.var_inset: dict[str:str] = {}

        v = re.split(" *: *", txt)
        if len(v) == 1:
            self.domain: str | None = txt
            self.cond: str | None = None
        elif len(v) == 2:
            self.domain = v[0]
            self.cond = v[1]
        else:
            self.domain = None
            self.cond = None
            errmsg = f"SYNTAX ERROR: {txt}"
            log.error(errmsg)
            raise ValueError(errmsg)
        """
        i in InputPort, j in Channels_WDM32
        ->self.var_inset = {"i": "InputPort", "j": "Channels_WDM32"}
        """
        m_iter = self.VAR_INSET_STATEMENT.finditer(self.domain)
        for m in m_iter:
            self.var_inset[m.group(1)] = m.group(2)

    def has_var_inset(self):
        """
        Whether to have self.var_inset
        """
        return len(self.var_inset) > 0


class SetDef:
    """
    Holds data in the form "set XX := {XXX}"  
    e.g.  
    set InputPort := {1, 3, 5, 7, 9, 11, 13, 15};  
    set OutputPort := {2, 4, 6, 8, 10, 12, 14, 16};  
    set AvailableConnection := {XXX}
    
    Attributes:
        self.name: Holds the string after "set"
        self.setdef: Holds the string inside ":= {}"
        self.nums: Holds the numbers inside self.setdef as a tuple of ints
        self.domain: Holds the characters inside {} as a Domain object
    """

    STATEMENT = re.compile("set +(" + _VAR + r") *:= *\{([^\{\}]+)\};")

    def __init__(self, m: re.Match):
        self.name: str = m.group(1)  # self.name="InputPort"
        self.setdef: str = re.sub(
            "[\t\r\n]+", "", m.group(2)
        )  # self.setdef= "1, 3, 5, 7, 9, 11, 13, 15"

        if re.fullmatch("[0-9, ]+", self.setdef):
            """
            If numbers are written, they are stored in self.nums as integers.
            """
            self.nums: tuple[int] | None = self._parse_nums(
                self.setdef
            )  # self.nums= (1, 3, 5, 7, 9, 11, 13, 15)
            self.domain: Domain | None = None
        else:            
            """
            If it’s characters, store them in self.domain.  
            Example:  
            m.group() corresponds to the case `set AvailableConnection := {XXX}`  
            self.setdef = XXX  
            """
            self.nums = None
            self.domain = Domain(self.setdef)

    def _parse_nums(self, txt: str):
        """
        Convert a string of numbers into a tuple of ints.  
        e.g.) "2, 3, 4" -> (2, 3, 4)
        """
        v = re.split(" *, *", txt)
        int_v: tuple[int] = tuple(int(i) for i in v)
        return int_v


class VarDim4:
    """
    Holds a string separated by commas as a list.
    
    Attributes:
        self.index: List of strings
    """

    def __init__(self, txt: str):
        self.index: list[str] = self._build_vardim4(txt)

    def _build_vardim4(self, txt: str):
        """
        Check a string separated by commas and convert it into an array.
        ex)
        txt = "i,j,k,l"
        index = ["i", "j", "k", "l"]
        """
        index = re.split(" *, *", txt)
        if len(index) != 4:
            errmsg = f"SYNTAX ERROR (must have 4 index): {txt}"
            log.error(errmsg)
            raise ValueError(errmsg)
        if not index[0].startswith("i"):
            errmsg = f"SYNTAX ERROR (1st index must be i): {txt}"
            log.error(errmsg)
            raise ValueError(errmsg)

        if not index[1].startswith("j"):
            errmsg = f"SYNTAX ERROR (2nd index must be j): {txt}"
            log.error(errmsg)
            raise ValueError(errmsg)

        if not index[2].startswith("k"):
            errmsg = f"SYNTAX ERROR (3rd index must be k): {txt}"
            log.error(errmsg)
            raise ValueError(errmsg)

        if (not index[3].startswith("l")) and (not index[3].startswith("j")):
            errmsg = f"SYNTAX ERROR (4th index must be l or j): {txt}"
            log.error(errmsg)
            raise ValueError(errmsg)
        return index

    def to_type(self):
        """
        Return the type of the value
        [i, j + 1, k, j + 1] -> return "i,j,k,j,"
        [i, j, k, j]-> return "i,j,k,j,"
        """
        if self.index[3].startswith("l"):
            return "i,j,k,l"
        else:
            return "i,j,k,j"

    def to_str(self):
        """
        Construct a string from the index array.
        """
        return ", ".join(self.index)


class SumCond(NamedTuple):
    """
    Holds a conditional expression containing "sum".
    
    Attributes:
        domain (Domain): Holds the domain part
        varC (VarDim4): Holds the XXX part of "c[XXX]"
        cond_op (str): Holds the comparison operator (e.g., inequality or equality signs)
        cond_num (int): Holds the constraint value
    """

    domain: Domain
    varC: VarDim4
    cond_op: str
    cond_num: int


class VarCond(NamedTuple):
    """
    Holds a comparison condition expression (without "sum").
    
    Attributes:
        org (str): The original condition expression
        c_left (VarDim4): Holds the expression on the left-hand side
        cond_op (str): Holds the comparison operator such as inequality or equality signs
        c_right (VarDim4): Holds the expression on the right-hand side
        num_right (int): Holds the numerical value on the right-hand side
    
    Note:
        c_right and num_right are never both set at the same time.
    """

    org: str
    c_left: VarDim4
    cond_op: str
    c_right: VarDim4
    num_right: int


class StDef:
    """
    Holds a constraint expression (starting with "s.t. XXX")
    e.g. 
    # s.t. input{j in Channels_WDM32, k in OutputPort} : sum{i in InputPort} c[i, j, k, j] <= 1;
    # s.t. demux{AvailableConnection} : c[i, j, k, l] = 1;
    
    Attributes:
        self.org: Stores the original constraint expression starting with "s.t. "
        self.name: Stores the constraint name (the string following "s.t. ")
        self.domain: Stores the domain of the constraint (the expression inside the braces in "s.t. AAA{BBB}") as a Domain object
        self.stdef: Stores the constraint expression (the part after the colon ":") as a SumCond or VarCond object
    """

    STATEMENT = re.compile(
        r"s\.t\. +(" + _VAR + r") *\{([^\{\}]+)\} *: *(.+);"
    )
    SUMCOND_STATEMENT = re.compile(
        r"sum *\{([^\{\}]+)\} *c\[([^\[\]]+)\] *([<>=]+) *([0-9]+)"
    )
    VARCOND_STATEMENT = re.compile(
        r"c\[([^\[\]]+)\] *([<>=]+) *([0-9]+|c\[([^\[\]]+)\])"
    )

    def __init__(self, m: re.Match):
        """
        ex)
        self.org = "s.t. demux{AvailableConnection} : c[i, j, k, l] = 1;"
        self.name = "demux"
        self.domain = Domain("AvailableConnection")
        self.stdef_org = "c[i, j, k, l] = 1"
        self.stdef = _ST_def_with_varcond("c[i, j, k, l] = 1")
        """
        self.org: str = m.group()
        self.name: str = m.group(1)
        self.domain: Domain = Domain(m.group(2))
        self.stdef_org: str = m.group(3)
        if "sum" in m.group(3):
            self.stdef: SumCond | VarCond = self._ST_def_with_sumcond(
                m.group(3)
            )
        else:
            self.stdef = self._ST_def_with_varcond(m.group(3))

    def _ST_def_with_sumcond(self, val: str):
        """
        Create a named tuple SumCond object from a summation constraint expression containing "sum".
        ex)
        val = "sum{i in InputPort} c[i, j, k, j] <= 1"
        cond_m.group(1) = "i in InputPort"
        cond_m.group(2) = "i, j, k, j"
        cond_m.group(3) = "<="
        cond_m.group(4) = "1"

        SumCond =
            domain = Domain("i in InputPort")
            varC = VarDim4("i, j, k, j")
            cond_op = "<="
            cond_num = "1"

        """
        cond_m = self.SUMCOND_STATEMENT.search(val)
        if cond_m is None:
            errmsg = f"SYNTAX ERROR (or not supported format): {self.STdef}"
            log.error(errmsg)
            raise ValueError(errmsg)
        else:
            return SumCond(
                Domain(cond_m.group(1)),
                VarDim4(cond_m.group(2)),
                cond_m.group(3),
                int(cond_m.group(4)),
            )

    def _ST_def_with_varcond(self, val: str):
        """
        Create a named tuple VarCond object from a condition expression without "sum".
        ex)
        val = "c[i, j, k, l] = 1"
        cond_m.group(1) = "i, j, k, l"
        cond_m.group(2) = "="
        cond_m.group(3) = "1"
        cond_m.group(4) = None

        VarCond =
            orig = "c[i, j, k, l] = 1"
            c_left = VarDim4("i, j, k, l")
            cond_op = "="
            c_right = None
            num_right = 1
        """
        cond_m = self.VARCOND_STATEMENT.search(val)
        if cond_m is None:
            errmsg = f"SYNTAX ERROR (or not supported format): {val}"
            log.error(errmsg)
            raise ValueError(errmsg)
        else:
            cleft = VarDim4(cond_m.group(1))
            right = cond_m.group(3)
            if right.startswith("c"):
                """
                val = "c[i, j, k, j] = c[i, j + 1, k, j + 1]" のケース
                cond_m.group(1) = "i, j, k, l"
                cond_m.group(2) = "="
                cond_m.group(3) = "c[i, j + 1, k, j + 1]"
                cond_m.group(4) = "i, j + 1, k, j + 1"
                VarCond =
                    org = "c[i, j, k, j] = c[i, j + 1, k, j + 1]"
                    c_left = VarDim4("i, j, k, l")
                    cond_op = "="
                    c_right = VarDim4("i, j + 1, k, j + 1")
                    num_right = 0
                """
                c_right = VarDim4(cond_m.group(4))
                num_right = 0
            else:
                """
                VarCond =
                orig = "c[i, j, k, l] = 1"
                c_left = VarDim4("i, j, k, l")
                cond_op = "="
                c_right = None
                num_right = 1
                """
                c_right = None
                num_right = int(right)

            return VarCond(
                val,
                cleft,
                cond_m.group(2),
                c_right,
                num_right,
            )


class GLPK:
    """
    Holds data from the .model file under the 'ac' directory.
    
    Attributes:
        self.glpk (str): The original string labeled "GLPK"
        self.setdefs (dict[str, SetDef]): A dictionary storing SetDef objects with their names as keys
        self.stdefs (set[StDef]): A set storing StDef objects
    """
    def __init__(self, txt: str):
        self.glpk: str = txt
        self.setdefs: dict[str:SetDef] = {}
        self.stdefs: list[StDef] = []
        self._parse()

    def _parse(self):
        self._parse_set()
        self._parse_ST()

    def _parse_set(self):
        """
        Convert the "set" line information into a SetDef object and store it in self.setdefs.
        """
        m_iter = SetDef.STATEMENT.finditer(self.glpk)
        for m in m_iter:
            setdef = SetDef(m)
            self.setdefs[setdef.name] = setdef

    def _parse_ST(self):
        """
        Convert the "s.t." line information into an StDef object and store it in self.stdefs.
        """
        m_iter = StDef.STATEMENT.finditer(self.glpk)
        for m in m_iter:
            stdef = StDef(m)
            self.stdefs.append(stdef)

    def get_domain(self, stdef: StDef):
        """
        Get the Domain
        """
        st_domain = stdef.domain
        """
        In Python, if the AvailableConnection domain is used within a 's.t.' expression,
        use the Domain:
        "i in InputPort, j in Channels, k in OutputPort, l in Channels : j = l"
        """
        if st_domain.domain == "AvailableConnection":
            st_domain = Domain(
                "i in InputPort, j in Channels, k in OutputPort, l in Channels : j = l"
            )

        return st_domain


class Model:
    """
    Holds GLPK objects and Components within a Model.
    
    Attributes:
        self.name: Model name
        self.glpk (str): GLPK object
        self.components: Set of Component objects
        self.hascon: Whether the Components include an address labeled "Controller"
    """

    def __init__(self, name: str, glpk: GLPK):
        self.name: str = name
        self.glpk: GLPK = glpk
        self.components: list[component.Component] = []
        self.hascon: bool = False

    def add_component(self, comp: component.Component):
        """
        Add the Component to self.components and set self.hascon.
        """
        self.components.append(comp)

        if comp.has_controller():
            self.hascon = True
        else:
            if self.hascon is True:
                # Components belong to the same Model but differ in the presence of a Controller.
                log.warning(
                    f"invalid Controller Model={self.name} comp={comp.name}"
                )


# print(f"{self.name}.add {comp.name} {self.hascon=}")
