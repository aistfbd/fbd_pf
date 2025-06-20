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

Main process of MakePathFinderGLPK
"""

import os
import re
from fbd.util import param, logutil
from fbd.topo import GLPK, topology, component, channel_table
from fbd.pathfinder import GLPK_constant, GLPK_util, pathfinder_util
from fbd.pathfinder.builder import GLPK_builder

log = logutil.getLogger()


def format_GLPK(glpk: str, var_cname: str):
    """
    Insert newlines and tabs for each unit of the constraint expression.

    ex)
    <output>
    s.t. WSS_100_9_input{
        comp in Comps_WSS_100_9, j in Channels_WDM32, k in OutputPort[comp]} :
        sum{i in InputPort[comp]
                        : vt[i, j, k, j] > 0}
                c2[vt[i, j, k, j]]
        <=
        1;
    """
    glpk = GLPK_util.format_GLPK(glpk)
    glpk = re.sub(
        r"s\.t\. +([^\{]+) *\{([^\}:]+) *: *([^\}]+)\} *: *(.+?) *([<>=]+) *(.+);",
        "s.t. \\1{"
        + GLPK_util.RET
        + "\t\\2"
        + GLPK_util.RET
        + "\t\t: \\3} :"
        + GLPK_util.RET
        + "\t\\4"
        + GLPK_util.RET
        + "\t\\5"
        + GLPK_util.RET
        + "\t\\6;",
        glpk,
    )
    glpk = re.sub(
        r"s\.t\. +([^\{]+) *\{([^\}]+)\} *: *sum\{([^\}:]+) *: *([^\}]+)\} *(.+?) *([<>=]+) *(.+);",
        "s.t. \\1{"
        + GLPK_util.RET
        + "\t\\2} :"
        + GLPK_util.RET
        + "\tsum{\\3"
        + GLPK_util.RET
        + "\t\t\t: \\4}"
        + GLPK_util.RET
        + "\t\t\\5"
        + GLPK_util.RET
        + "\t\\6"
        + GLPK_util.RET
        + "\t\\7;",
        glpk,
    )
    glpk = re.sub(
        var_cname + r"\[([^,]+, *[^,]+, *[^,]+, *[^,]+)\]",
        var_cname + "[vt[\\1]]",
        glpk,
    )
    return glpk


def _fix_domain(domain: GLPK.Domain, hasvars: set[str]):
    """
    Format the part of domain
    ex)
    <in>
    domain.domain = i in InputPort, j in Channels_WDM32,
         k in OutputPort, l in Channels_WDM32
    domain.var_inset = {"i": "InputPort", "j": "Channels_WDM32",
         "k": "OutputPort", "l": " Channels_WDM32"}
    <out>
    buf = "i in InputPort[comp],j in FlowInChannels[i],k in FlowOutPorts[i],l in IJK2Ls[i,j,k]"
    hasvars={"i", "j", "k", "l"}
    """
    buf: str = []
    for key, val in domain.var_inset.items():
        if len(buf) > 0:
            buf.append(",")
        buf.append(f"{key} in ")
        if key == "i":
            buf.append(f"{val}[comp]")
        elif key == "j":
            # If "i" appears first, add "FlowInChannels[i]"
            if "i" in hasvars:
                buf.append("FlowInChannels[i]")
            else:
                buf.append(val)
        elif key == "k":
            # If "i" appears first, add "FlowOutPorts[i]"
            if "i" in hasvars:
                buf.append("FlowOutPorts[i]")
            else:
                buf.append(f"{val}[comp]")
        elif key == "l":
            if {"i", "j", "k"} <= hasvars:
                buf.append("IJK2Ls[i,j,k]")
            else:
                buf.append(val)
        else:
            buf.append(val)
        hasvars.add(key)
    return "".join(buf)


def _output_model_constraint(
    model: GLPK.Model,
    var_cname: str,
):
    """
    Format the GLPK information in the .model file, store it in model_line: list[str], and return it.
    """
    glpk: GLPK.GLPK = model.glpk
    stdefs = glpk.stdefs
    model_line = ["", "#", f"# {model.name}"]
    for st in stdefs:
        model_line.append(f"#   {st.org}")

    model_line.append("#")

    model_id = GLPK_util.escape(model.name)
    for st in stdefs:
        """
        s.t. wavelength{i in InputPort, k in OutputPort, j in Channels_WDM32 : j + 1 in Channels_WDM32} : c[i, j, k, j] = c[i, j + 1, k, j + 1];

        st.name = 'wavelength'
        st_domain.domain = 'i in InputPort, k in OutputPort, j in Channels_WDM32'
        st_domain.cond = 'j + 1 in Channels_WDM32'
        VarCond.org='c[i, j, k, j] = c[i, j + 1, k, j + 1]',
        VarCond.c_left= ['i', 'j', 'k', 'j']
        VarCond.cond_op='=',
        VarCond.c_right=['i', 'j + 1', 'k', 'j + 1']
        """
        """
        Not used in python version
        st_domain = glpk.get_domain(st)
        """
        st_domain = st.domain
        # print(f"{model_id} {st_domain.domain=} {st_domain.cond=}")
        if st_domain.domain == "AvailableConnection":
            st_buf = [
                f"s.t. {model_id}_{st.name}{{comp in Comps_{model_id}, "
                + "i in InputPort[comp], j in FlowInChannels[i], "
                + "k in FlowOutPorts[i], l in IJK2Ls[i, j, k] "
                + ": vt[i, j, k, l] > 0"
            ]
            varcond: GLPK.VarCond = st.stdef
            stdefstr: str = varcond.org
            stdefstr = stdefstr.replace("c[", f"{var_cname}[")
            st_buf.append(f"}}:{stdefstr}")
        else:
            hasvars: set[str] = set()
            st_buf = [
                f"s.t. {model_id}_{st.name}{{comp in Comps_{model_id}, "
                + _fix_domain(st_domain, hasvars)
            ]
            # ['s.t. DIV1X5_divide{comp in Comps_DIV1X5, ']
            if isinstance(st.stdef, GLPK.SumCond):
                sumcond: GLPK.SumCond = st.stdef
                st_buf.append("}:sum{")
                st_buf.append(
                    f"{_fix_domain(sumcond.domain, hasvars)}"
                    f":vt[{sumcond.varC.to_type()}] > 0}}"
                )

                st_buf.append(
                    f"{var_cname}[{sumcond.varC.to_str()}] "
                    f"{sumcond.cond_op} {sumcond.cond_num}"
                )
            elif isinstance(st.stdef, GLPK.VarCond):
                varcond: GLPK.VarCond = st.stdef
                cond: str | None = st.domain.cond
                stdefstr: str = varcond.org
                st_buf.append(f" : vt[{varcond.c_left.to_type()}] > 0")
                if cond is not None:
                    # Reaplace "j + 1" with "nextCh[j]"
                    cond = re.sub(r"j *\+ *1", "nextCh[j]", cond)
                    stdefstr = re.sub(r"j *\+ *1", "nextCh[j]", stdefstr)
                    st_buf.append(f"  && {cond}")
                stdefstr = stdefstr.replace("c[", f"{var_cname}[")
                st_buf.append(f"}}:{stdefstr}")
            else:
                errmsg = f"PROGRAM ERROR: invalid type: {type(st.stdef)}"
                log.error(errmsg)
                raise TypeError(errmsg)

        st_buf.append(";")
        s = format_GLPK("".join(st_buf), var_cname)
        #        s = fixChannelTableForODU(topo, comp, s);
        model_line.append(s)
    return GLPK_util.RET.join(model_line)


def _output_model_all(name2model: dict[str : GLPK.Model]):
    """
    Return the GLPK information from all models
     as a list of strings in model_constraint.
    """
    model_constraint: list[str] = [
        _output_model_constraint(model, "c2") for model in name2model.values()
    ]
    return model_constraint


CONSTRAINT_STATEMENTS = "### CONSTRAINT_STATEMENTS ###"


def _write_model_file(
    base_model_dataset: tuple[str],
    out_model_name: str,
    allmodel_footer: list[str],
    model_file_data: list[str],
):
    buf: list[str] = []
    buf.append(base_model_dataset[0])
    buf.append(GLPK_util.RET)
    buf.append(model_file_data)
    buf.extend(allmodel_footer)
    buf.append(base_model_dataset[1])
    GLPK_util.write_file(out_model_name, "w", "".join(buf))


def _read_base_model_file(modelbase_file: str):
    """
    Read the model base file, split the data 
    into front and back parts, and return them as a tuple.
    """
    base_model_data = GLPK_util.read_file(modelbase_file)

    try:
        idx = base_model_data.index(CONSTRAINT_STATEMENTS)
    except ValueError as e:
        msg = f"cannot find {CONSTRAINT_STATEMENTS} in {modelbase_file} :{e}"
        log.error(msg)
        raise ValueError(msg) from e

    log.info(
        f"load modelbase_file: {os.path.join(param.TOPDIR, modelbase_file)}"
    )
    idx += len(CONSTRAINT_STATEMENTS)
    base_model_dataset: tuple[str] = (
        base_model_data[0:idx],
        base_model_data[idx:],
    )
    return base_model_dataset


def _make_pathfinder_pf(
    glpk_dir: str,
    modelbase_file: str,
    model_file_key: str,
    data_file_key: str,
    topo: topology.Topology,
    name2model: dict[str : GLPK.Model],
):
    """
    Create .model and .data files for each channel.
    """
    base_model_dataset: tuple[str] = _read_base_model_file(modelbase_file)
    model_constraint: list[str] = _output_model_all(name2model)

    data_file_data: str = None
    model_file_data: str = None
    parent_dir = GLPK_constant.get_model_data_file_dir(glpk_dir)

    write_model = True
    ch: channel_table.Channel
    for ch in topo.get_all_channel():
        if len(topo.get_support_comps(ch.channeltable_id)) == 0:
            log.info(f"{ch.full_no} has no support ports SKIP glpsol")
            continue

        out_model_name = os.path.join(parent_dir, f"pf_{model_file_key}.model")
        file_name = os.path.join(
            parent_dir, f"pf_{data_file_key}_{ch.full_no}"
        )
        skeleton_file = f"{file_name}.data"
        varidx_t_file = f"{file_name}.pickle"

        data_file_data, model_file_data = GLPK_builder.make_skeleton_data(
            topo,
            False,
            write_model,
            [ch],
            varidx_t_file,
            pf_name2model=name2model,
        )
        if write_model:
            _write_model_file(
                base_model_dataset,
                out_model_name,
                model_constraint,
                model_file_data,
            )
            log.info(out_model_name)
            write_model = False

        GLPK_util.write_file(skeleton_file, "w", data_file_data)
        log.info(skeleton_file)
    return


def _make_pathfinder_solvec(
    glpk_dir: str,
    modelbase_file: str,
    model_file_key: str,
    data_file_key: str,
    topo: topology.Topology,
    name2model: dict[str : GLPK.Model],
):
    """
    For each model in name2model, create .data and .model files for solvec.  
    Models that do not have "Controller" as a component are excluded.
    """
    parent_dir = GLPK_constant.get_model_data_file_dir(glpk_dir)

    base_model_dataset: tuple[str] = _read_base_model_file(modelbase_file)
    """
    In the skeleton data, all channels are targeted.
    """
    channels: list[channel_table.Channel] = list(topo.get_all_channel())

    solvec_idx_target_list: list[
        tuple[GLPK.Model, set[component.Component], int]
    ] = pathfinder_util.make_solvec_target(name2model)

    model: GLPK.Model | None = None
    comps_set: set[component.Component] | None = None
    file_idx: int | None = None
    write_model = True

    for model_target_list in solvec_idx_target_list:
        write_model = True
        for model_target in model_target_list:
            model = model_target[0]
            comps_set = model_target[1]
            file_idx = model_target[2]

            model_constraint: str = _output_model_constraint(model, "c")
            out_model_name = os.path.join(
                parent_dir, f"solvec_{model_file_key}_{model.name}.model"
            )

            file_name = os.path.join(
                parent_dir, f"solvec_{data_file_key}_{model.name}_{file_idx}"
            )
            skeleton_file = f"{file_name}.data"
            varidx_t_file = f"{file_name}.pickle"

            data_file_data, model_file_data = GLPK_builder.make_skeleton_data(
                topo,
                True,
                write_model,
                channels,
                varidx_t_file,
                solvec_target=(model, comps_set),
            )
            GLPK_util.write_file(skeleton_file, "w", data_file_data)
            log.info(skeleton_file)
            if write_model:
                # Multiple components share one model file.  
                # The model file is written only once.
                _write_model_file(
                    base_model_dataset,
                    out_model_name,
                    model_constraint,
                    model_file_data,
                )
                log.info(out_model_name)
                write_model = False
    return


def _check_args(
    topo_xml: str = param.TOPO_XML,
    glpk_dir: str = param.GLPK_DIR,
    pf_modelbase_file: str = param.PF_TMP,
    solvec_modelbase_file: str = param.SOLVEC_TMP,
    model_file_key: str = param.TOPO_XML,
    data_file_key: str = param.TOPO_XML,
    solvec: bool = False,
):
    """
    Check the argument types
    """
    pathfinder_util.check_arg_str(topo_xml)
    pathfinder_util.check_arg_str(glpk_dir)
    pathfinder_util.check_arg_str(pf_modelbase_file)
    pathfinder_util.check_arg_str(solvec_modelbase_file)
    pathfinder_util.check_arg_str(model_file_key)
    pathfinder_util.check_arg_str(data_file_key)
    pathfinder_util.check_arg_bool(solvec)


def make_pathfinder_GLPK(
    topo_xml: str = param.TOPO_XML,
    glpk_dir: str = param.GLPK_DIR,
    pf_modelbase_file: str = param.PF_TMP,
    solvec_modelbase_file: str = param.SOLVEC_TMP,
    model_file_key: str = param.TOPO_XML,
    data_file_key: str = param.TOPO_XML,
    solvec: bool = False,
):
    """
    Read topology file, ac/.model, and ac/.conn.txt, 
    and create skeleton data files for route calculation.
    """
    _check_args(
        topo_xml,
        glpk_dir,
        pf_modelbase_file,
        solvec_modelbase_file,
        model_file_key,
        data_file_key,
        solvec,
    )
    acconndir_path = GLPK_constant.get_available_connectionsdir(glpk_dir)

    topo = topology.Topology(
        topology.topology_filename(topo_xml), acconndir_path, True
    )

    name2model: dict[str : GLPK.Model] = pathfinder_util.load_all_modelfiles(
        topo, glpk_dir
    )
    os.makedirs(GLPK_constant.get_model_data_file_dir(glpk_dir), exist_ok=True)

    _make_pathfinder_pf(
        glpk_dir,
        os.path.join(glpk_dir, pf_modelbase_file),
        model_file_key,
        data_file_key,
        topo,
        name2model,
    )
    if solvec is False:
        return

    _make_pathfinder_solvec(
        glpk_dir,
        os.path.join(glpk_dir, solvec_modelbase_file),
        model_file_key,
        data_file_key,
        topo,
        name2model,
    )
    return


if __name__ == "__main__":
    make_pathfinder_GLPK(solvec=True)
