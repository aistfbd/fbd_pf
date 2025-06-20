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
 */

Module for parsing parameters from param.json
"""

import os
import json
from pathlib import Path

p_file = Path(__file__)
TOPDIR = p_file.parents[3]
os.chdir(TOPDIR)

try:
    appsetting = json.load(open(os.path.join("config", "param.json"), "r"))
    LOGGER: str = appsetting["logger"]
    LOG_CONFIG: str = appsetting["log_config"]
    TOPO_XML: str = appsetting["topo_xml"]
    GLPK_DIR: str = appsetting["glpk_dir"]
    DB_DIR: str = appsetting["db_dir"]
    NRM_HOST: str = appsetting["nrm_host"]
    NRM_PORT: int = appsetting["nrm_port"]
    PF_TMP: str = appsetting["pf_tmp_model"]
    SOLVEC_TMP: str = appsetting["solvec_tmp_model"]
    NUM_COMPS: int = appsetting["num_comps"]
except Exception as e:
    print(f"Error loading param.json: {e}")
    raise Exception(e) from e
