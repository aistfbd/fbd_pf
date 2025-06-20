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

Module that keeps the class of VBuilder
"""

from fbd.topo import port
from fbd.pathfinder import GLPK_util
from fbd.pathfinder.builder import builder_base


class VBuilder(builder_base.BuilderBase):
    """
    Constructs the following section in the `.data` file:
        set V :=
    
    Attributes:
        self.target_ports: List of target ports
    """

    def __init__(self, target_ports: list[port.Port]):
        super().__init__()
        self.target_ports: list[port.Port] = target_ports

    def build(self):
        super().print_set_def("V")
        super().print_ports(self.target_ports, sort=False)
        super().print_any(f";{GLPK_util.RET}")
        return super().build()
