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

Module defining default values used by the program.
"""

import sys
import os
from fbd.pathfinder import GLPK_util


GLPK_SOLVER = "glpsol"

AVAILABLE_CONNECTIONS_DIR = "ac"
MODEL_DATA_FILE_DIR = "glpk"
VARIDX_T_FILE = "v"


def get_ac_model_filename(model_name: str):
    """
    Returns the model filename used for calculating available connections.
    """
    model = GLPK_util.escape(model_name)
    return f"{model}.model"


def get_ac_conn_filename(model_name: str):
    """
    Returns the filename for describing available connections.
    """
    model = GLPK_util.escape(model_name)
    return f"{model}.conn.txt"


def get_available_connectionsdir(glpk_dir: str):
    """
    Returns the parent directory name of the ac file ("glpk_dir"/ac).
    """
    return os.path.join(glpk_dir, AVAILABLE_CONNECTIONS_DIR)


def get_model_data_file_dir(glpk_dir: str):
    """
    Returns the parent directory name of the skeleton data file and .model file ("glpk_dir"/glpk).
    """
    return os.path.join(glpk_dir, MODEL_DATA_FILE_DIR)


WDM_ID = "WDM"
NOT_FOUND_COST = sys.float_info.max

MAX_SEC_PATH_FIND = 120
MAX_SEC_SOLVEC = 120
MAX_SMALL_CHNO = 2
