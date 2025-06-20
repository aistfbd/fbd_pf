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

Module describing common processing for path calculation.  
Used in reserve.py and make_pathfinder.py.
"""

from __future__ import annotations
import os
from fbd.util import param, logutil
from fbd.topo import topology, component, GLPK, port, channel_table
from fbd.pathfinder import GLPK_util, GLPK_constant, available_connection


log = logutil.getLogger()


def _load_modelfile(model_file: str):
    """
    Read the model_file and store it in GLPK.
    """
    txt = GLPK_util.read_file(model_file)
    return GLPK.GLPK(txt)


def load_all_modelfiles(topo: topology.Topology, glpk_dir: str):
    """
    Read the ac/.model file and save it in a dictionary
     name2model={model_name: Model}, then return it.  
    Models with glpk.stdefs=None are excluded.
    """

    acconndir_path = GLPK_constant.get_available_connectionsdir(glpk_dir)
    name2model: dict[str : GLPK.Model] = {}

    for comp in topo.get_all_component():
        model_name: str | None = comp.model

        if model_name is None:
            continue

        model_object: None | GLPK.Model = name2model.get(model_name)

        if model_object is not None:
            model_object.add_component(comp)
            continue

        glpk = _load_modelfile(
            os.path.join(
                acconndir_path, GLPK_constant.get_ac_model_filename(comp.model)
            ),
        )
        if len(glpk.stdefs) > 0:
            # In Java, this exclusion is done in MakePathFinderGLPK.java:loadCompModels()
            # For example, N1007's EDFA_A16_00_00_23_20_09_1_LC_PC has no stdefs
            model_object: GLPK.Model = GLPK.Model(model_name, glpk)
            model_object.add_component(comp)
            name2model[model_name] = model_object

    return name2model


def make_solvec_target(name2model: dict[str : GLPK.Model]):
    """
    Create targets for solvec calculation.  
    Models that do not have "Controller" as a component are excluded.  
    Return a list for each Model.
    
    Example: when param.NUM_COMPS=2  
    solvec_idx_target_list = [  
      [(WSS_100_9, {N1211, N1212}, 1), (WSS_100_9, {N1213, N1214}, 2)],  
      [(Si_TPA, {N211, N1210}, 1)]  
    ]
    """
    solvec_idx_target_list: list[
        list[tuple[GLPK.Model, set[component.Component], int]]
    ] = []

    num_comps: int = param.NUM_COMPS
    if num_comps < 0:
        msg = f"num_comps must be greater than 0 : {num_comps}"
        log.error(msg)
        raise ValueError(msg)

    file_idx: int
    for model in name2model.values():
        model_target_list: list[
            tuple[GLPK.Model, set[component.Component], int]
        ] = []
        if model.hascon is False:
            # JAVAだとMakePathFinderGLPK.java:outputModel()で除外している
            continue

        file_idx = 1

        comps_in_model: int = len(model.components)

        if comps_in_model <= num_comps:
            comps_set: set[component.Component] = model.components
            model_target_list.append((model, comps_set, file_idx))
            solvec_idx_target_list.append(model_target_list)
            #            print(
            #                f"{model.name}/{[comp.name for comp in comps_set]}/{file_idx}"
            #            )
            continue

        num: int = 0
        comps_set = set()
        for comp in model.components:
            # Include information of num_comps components in a single file
            comps_set.add(comp)
            num += 1
            comps_in_model -= 1
            if (num == num_comps) or (comps_in_model == 0):
                model_target_list.append((model, comps_set, file_idx))
                #                print(
                #                    f"{model.name}/{[comp.name for comp in comps_set]}/{file_idx}"
                #                )
                num = 0
                file_idx += 1
                # Allocate a new set()
                comps_set = set()
        solvec_idx_target_list.append(model_target_list)
    return solvec_idx_target_list


def _is_supported(
    in_port: port.Port,
    in_ch: channel_table.Channel,
    out_port: port.Port,
    out_ch: channel_table.Channel,
):
    """
    Determine whether in_ch is an in_port and out_ch is
     an out_port of the support_channel.
    """
    return in_port.is_same_support_channel(in_ch.channeltable_id) and (
        out_port.is_same_support_channel(out_ch.channeltable_id)
    )


def has_connection(
    topo: topology.Topology,
    in_port: port.Port,
    in_ch: channel_table.Channel,
    out_port: port.Port,
    out_ch: channel_table.Channel,
):
    """
    Determine whether available connection information exists.
    """

    if in_port.full_name == out_port.full_name:
        return False

    has_conn: bool = False
    in_comp: component.Component = topo.get_component_by_port(in_port)
    if in_comp == topo.get_component_by_port(out_port):
        ac: available_connection.AvailableConnection | None = in_comp.ac
        if ac is not None:
            # Connection within the device with constraint information
            has_conn = ac.has_connection_in_conn(
                in_port.number, in_ch, out_port.number, out_ch
            )
        elif in_comp.is_pseude():
            # There is no in -> out connection at the Application terminal.
            has_conn = False
        else:
            """
            For device-internal connections without constraint
             information, allow only the same channel.
            isInput() : INPUT or BI_DI
            isOutput() : OUTPUT or BI_DI
            """
            has_conn = (
                in_port.is_in
                and out_port.is_out
                and (in_ch.full_no == out_ch.full_no)
                and _is_supported(in_port, in_ch, out_port, out_ch)
            )
    else:
        # For inter-device connections, only allow the same supported channel.
        if (in_ch.full_no == out_ch.full_no) and _is_supported(
            in_port, in_ch, out_port, out_ch
        ):
            if in_port.is_connected(out_port):
                has_conn = True
            elif in_port.is_bidi() and out_port.is_connected(in_port):
               # If it’s a bidirectional port, also allow connections in the reverse direction.
                has_conn = True

    return has_conn


def check_arg_bool(arg: any):
    """
    Check if the argument is of bool type.
    """
    if type(arg) is not bool:
        msg = f"{arg} should be of type bool, not {type(arg)}"
        log.error(msg)
        raise ValueError(msg)


def check_arg_str(arg: any):
    """
    Check whether the argument is of type str.
    """
    if type(arg) is not str:
        msg = f"{arg} should be of type str, not {type(arg)}"
        log.error(msg)
        raise ValueError(msg)
