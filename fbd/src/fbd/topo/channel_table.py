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

Module that contains the ChannelTable and Channel classes.
"""

from lxml import objectify
from fbd.pathfinder import GLPK_util, GLPK_constant


class ChannelTable:
    """
    Holds information from the "channelTable" element in the topology file.
    
    Attributes:
        self.channeltable_id: Stores the value of the "id" attribute
        self.channels: Stores channel information as a list of Channel objects
    """

    ANY: str = "ANY"

    def __init__(self, table: objectify.ObjectifiedElement):
        self.channeltable_id: str = GLPK_util.escape(table.get("id"))
        self.channels: list[Channel] = [
            Channel(ch, self.channeltable_id) for ch in table.channel
        ]

    def isWDM(self):
        return self.channeltable_id.startswith(GLPK_constant.WDM_ID)


class Channel:
    """
    Holds information from the "channel" element in the topology file.
    
    Attributes:
        self.channel_no: Stores the value of the "no" attribute
        self.channeltable_id: Stores the value of the "channeltable_id"
        self.full_no: A unique identifier composed of "channeltable_id" and "channel_no"
    """

    def __init__(
        self, channel: objectify.ObjectifiedElement, channeltable_id: str
    ):
        self.channel_no: int = int(channel.get("no"))
        self.channeltable_id: str = channeltable_id
        self.full_no: str = f"{channeltable_id}_{self.channel_no}"
