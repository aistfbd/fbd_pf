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

Module that holds available connection information within a device.
"""

from fbd.topo import channel_table


class ConnEntry:
    """
    Holds connection information from ac/.conn files.
    
    Attributes:
        self.in_pin: Pin number of the input channel
        self.in_ch: Channel object of the input channel
        self.out_pin: Pin number of the output channel
        self.out_ch: Channel object of the output channel
        self.key (str): Name to uniquely identify the object
    """

    def __init__(
        self,
        in_pin: int,
        in_ch: channel_table.Channel,
        out_pin: int,
        out_ch: channel_table.Channel,
    ):
        self.in_pin: int = in_pin
        self.in_ch: channel_table.Channel = in_ch
        self.out_pin: int = out_pin
        self.out_ch: channel_table.Channel = out_ch
        self.key = self.make_key(in_pin, in_ch, out_pin, out_ch)

    @staticmethod
    def make_key(
        in_pin: int,
        in_ch: channel_table.Channel,
        out_pin: int,
        out_ch: channel_table.Channel,
    ):
        return f"{in_pin}@{in_ch.full_no}-{out_pin}@{out_ch.full_no}"


class AvailableConnection:
    """
    Holds information from ac/.conn files.
    
    Attributes:
        self.bchange_ch: Indicates if there are cases where the input channel and output channel differ
        self.conn_set: Set of keys of ConnEntry objects
        self.in2outs_dic: Dictionary mapping {in_ch: {out_ch1, out_ch2, ...}}
    """
    def __init__(
        self,
        conn_set: set[str],
        in2outs_dic: dict[int : set[int]],
    ):
        self.conn_set: set[str] = conn_set
        self.in2outs_dic: dict[int : set[int]] = in2outs_dic

    def has_connection(self, in_pin: int, out_pin: int):
        """
        Determine whether there is available connection information.
        """
        out_set = self.in2outs_dic.get(in_pin)
        if out_set is None:
            return False
        return out_pin in out_set

    def has_connection_in_conn(
        self,
        in_pin: int,
        in_ch: channel_table.Channel,
        out_pin: int,
        out_ch: channel_table.Channel,
    ):
        """
        Determine whether there is available connection information.
        """
        return (
            ConnEntry.make_key(in_pin, in_ch, out_pin, out_ch) in self.conn_set
        )
