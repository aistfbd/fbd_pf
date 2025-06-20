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

A module that contains the EndBuilder class.
"""

from fbd.pathfinder import GLPK_util
from fbd.pathfinder.builder import builder_base


class EndBuilder(builder_base.BuilderBase):
    """
    Constructs the 
    end;
     section of the .data file.
    """

    def __init__(
        self,
    ):
        super().__init__()

    def build(self):
        super().print_any(f"end;{GLPK_util.RET}")
        return super().build()
