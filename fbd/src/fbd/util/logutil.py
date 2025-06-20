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

Module for log output
"""

import os
from logging import config, getLogger
import datetime
import yaml
from fbd.util import param


def namer(name: str):
    """
    Return the filename for log file archiving.
    """
    # logs/nrm.log.1 -> logs/nrm.log.1_yyyy-MM-dd
    dt_now = datetime.datetime.now()
    return name + "_" + dt_now.strftime("%Y-%m-%d")


def init_logger():
    """
    Initialize logging functionality.
    """
    try:
        with open(os.path.join("config", param.LOG_CONFIG)) as file:
            config.dictConfig(yaml.load(file.read(), yaml.FullLoader))
    except Exception as e:
        msg = f"Error loading {param.LOG_CONFIG}: {e}"
        print(msg)
        raise Exception(msg) from e
    else:
        logger = getLogger()
        for rh in logger.handlers:
            rh.namer = namer


if param.LOGGER == "enable":
    #    print(f"call init_logger from LogUtil.main() {init=}")
    init_logger()
else:
    #If disabled, calling log = logutil.getLogger() and writing to log will result in no output and no errors.
    print("logger is disable")
