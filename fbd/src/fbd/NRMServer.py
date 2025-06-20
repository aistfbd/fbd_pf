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
 """

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import argparse
from fbd.nrm import nrm_server
from fbd.util import param

# main
if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("-t", metavar="<topo_xml>", default=param.TOPO_XML)
    parser.add_argument("-g", metavar="<glpk_dir>", default=param.GLPK_DIR)
    parser.add_argument("--db", action="store_true")

    args = parser.parse_args()
    nrm_server.NRM_server(topo_xml=args.t, glpk_dir=args.g, db=args.db)
