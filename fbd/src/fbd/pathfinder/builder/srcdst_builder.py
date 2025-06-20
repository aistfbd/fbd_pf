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

Module that keeps the class of SrcDstBuilder
"""

from fbd.topo import port
from fbd.pathfinder import GLPK_util
from fbd.pathfinder.builder import builder_base


class SrcDstBuilder(builder_base.BuilderBase):
    """
    Constructs the following sections in the `.data` file:
        param src :=
        param dst :=
    
    Attributes:
        self.src: Source port
        self.dst: Destination port
    """

    def __init__(self, src: port.Port, dst: port.Port):
        self.src: port.Port = src
        self.dst: port.Port = dst
        super().__init__(None)

    def build(self):
        super().print_param("src")
        super().print_any(f"{self.src.full_name};{GLPK_util.RET}")
        super().print_param("dst")
        super().print_any(f"{self.dst.full_name};{GLPK_util.RET}")
        return super().build()
