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

Module that keeps the class of MultiWidthBuilder
"""

from fbd.topo import channel_table
from fbd.pathfinder import GLPK_util
from fbd.pathfinder.builder import builder_base


class MultiWidthBuilder(builder_base.BuilderBase):
    """
    Constructs the following sections in the `.data` file:
        param widthOK default 1 := ;
        set ChannelRange[CHANNEL] := ;
    
    Attributes:
        self.channel: Target channel
    """

    def __init__(
        self,
        channels: list[channel_table.Channel],
    ):
        super().__init__()
        # The pf has only a single channel, and its width is fixed to 1
        self.channel: channel_table.Channel = channels[0]

    def build(self):
        # PF has only one channel, and its width is fixed at 1
        super().print_param_def("widthOK", 1)
        super().print_any(f";{GLPK_util.RET}")
        super().print_set_def_idx("ChannelRange", self.channel.full_no)
        super().print_any(f" {self.channel.full_no}")
        super().print_any(f";{GLPK_util.RET}")
        return super().build()
