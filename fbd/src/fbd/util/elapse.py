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

Module to measure execution time.
"""

import time
from fbd.util import logutil

log = logutil.getLogger()


class Elapse:
    """
    A class for measuring time

    Attributes:
        self.start: start time
    """

    def __init__(self):
        self.start: float = time.time()

    def show(self, msg: str):
        end = time.time()
        elapse = end - self.start
        log.info(f"{msg} : {elapse*1000:.0f}[msec]")
