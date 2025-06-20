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

Module that holds ChannelsListBuilder class
"""

from fbd.topo import topology, channel_table
from fbd.pathfinder import GLPK_util
from fbd.pathfinder.builder import builder_base


class ChannelsListBuilder(builder_base.BuilderBase):
    """
    In .data file, tha part of
      set Channels_WDM32 :=
      set Channels_Gray1_3 :=
      set AllChannels :=
      param chNo :=
      param nextCh :=
    
    Generate the part of
      set Channels_XX;
      param nextCh{AllChannels} symbolic;
    in .model file

    When generating skeleton data, use all the channel and generate only .model data
    When generating skeleton data for solvec, use all tha channel and generate both .data and .model data

    Attributes:
        self.topo: Topology
        self.ch_map: Dictionary of the target channel of {channeltableid: [Channel,..]}
        self.solvec: Whether solvec calculation
    """

    def __init__(
        self,
        topo: topology.Topology,
        channels: list[channel_table.Channel] | None,
        write_model: bool,
        solvec: bool,
    ):
        super().__init__(write_model=write_model)
        self.topo: topology.Topology = topo
        ch_map: dict[str : list[channel_table.Channel]] = {}
        for ch in channels:
            ch_map.setdefault(ch.channeltable_id, []).append(ch)
        self.ch_map = ch_map
        self.solvec = solvec

    def _build_channels(self):
        """
        Export Channel information
        """
        all_channels_buf = []
        chno_buf = []
        nextch_buf = []
        ch: channel_table.Channel
        all_channels_buf: list[channel_table.Channel] = []
        table: channel_table.ChannelTable
        for table in self.topo.get_all_channeltable():
            setname = f"Channels_{table.channeltable_id}"
            super().print_set_def(setname)
            channels_buf = []
            if (
                channels := self.ch_map.get(table.channeltable_id)
            ) is not None:

                for ch in channels:
                    channels_buf.append(ch.full_no)
                    chno_buf.append(ch.full_no)
                    chno_buf.append(str(ch.channel_no))

                super().print_list(channels_buf, sort=False)
            super().print_any(f";{GLPK_util.RET}")
            all_channels_buf.extend(channels_buf)

        super().print_set_def("AllChannels")
        super().print_list(all_channels_buf, sort=False)

        super().print_any(f";{GLPK_util.RET}")

        super().print_param("chNo")
        super().print_list(chno_buf, sort=False)
        super().print_any(f";{GLPK_util.RET}")

        super().print_param("nextCh")
        for idx, ch_no in enumerate(all_channels_buf):
            nextch_buf.append(ch_no)
            if idx < len(all_channels_buf) - 1:
                nextch_buf.append(all_channels_buf[idx + 1])
            else:
                nextch_buf.append(all_channels_buf[0])
        super().print_list(nextch_buf, sort=False)
        super().print_any(f";{GLPK_util.RET}")

        return super().build()

    def build(self):
        if self.modellines is not None:
            # When write_model=True
            if self.solvec:
                for table_id in self.ch_map.keys():
                    super().print_any_modelline(f"set Channels_{table_id};")
            else:
                for table in self.topo.get_all_channeltable():
                    super().print_any_modelline(
                        f"set Channels_{table.channeltable_id};"
                    )
            super().print_any_modelline("param nextCh{AllChannels} symbolic;")

        return self._build_channels()
