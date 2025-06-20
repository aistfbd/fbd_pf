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

Module defining common functions for handling IJKL information.
"""

from fbd.util import logutil

log = logutil.getLogger()


def _txt2nos(txt: str | int):
    """
    Convert a string into a set of integers and return it.
    ex) "1-10,12,15,17-20 ->{1,2,3,4,5,6,7,8,9,10,12,15,17,18,19,20}"
    """
    if type(txt) is int:
        """
        If specified as a number like "j":1, return a set containing just that value.
        """
        return {txt}

    v = txt.split(",")
    num_set: set[int] = set()
    for p in v:
        t: str = p.split(r"-")
        try:
            if len(t) == 1:
                num_set.add(int(t[0]))
            elif len(t) == 2:
                start = int(t[0])
                end = int(t[1])
                for no in range(start, end + 1):
                    num_set.add(no)
        except Exception as e:
            raise Exception(e) from e
    return num_set


def is_match_ch(val: int | str, ch_no: int):
    """
    Check if ch_no exists in the ch_no written in val.
    """
    if val == "*":
        return True

    ch_set: set[int] = _txt2nos(val)
    return ch_no in ch_set


def get_ports(ports_txt: str | int):
    """
    Return a set of port numbers from ports_txt.
    """
    if type(ports_txt) is int:
        return {ports_txt}
    return _txt2nos(ports_txt)


def to_string(cost: dict):
    return f"{cost['i']},{cost['j']},{cost['k']},{cost['l']}"
