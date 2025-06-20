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

Main process of MakeAvailableConnections
"""

import subprocess
import os
import re
import html
from fbd.util import param, logutil
from fbd.topo import topology, component, port
from fbd.pathfinder import GLPK_constant, GLPK_util, pathfinder_util

_CANNELS_FILENAME = "channels.data"
log = logutil.getLogger()


_NUM_RANGE = re.compile(r"\{ *([0-9]+) *.. *([0-9]+) *(by *([0-9]+) *)?\}")


def _expand_numset(glpk: str):
    """
    Convert glpk notation "{1..10}" to "{1,2,3,4,5,6,7,8,9,10}",
    and "{1..9 by 2}" to "{1,3,5,7,9}".
    """
    m_iter = _NUM_RANGE.finditer(glpk)
    buf = []
    idx = 0
    for m in m_iter:
        """
        ex) XXXXX set InputPortD := {1..8};
            m.group() = "{1..8}"
            m.group(1) = "1"
            m.group(2) = "8"
        ex) XXXXX set InputPortD := {1..9 by 2};
            m.group() = "{1..9 by 2}"
            m.group(1) = "1"
            m.group(3) = "by 2"
            m.group(4) = "2"
        """
        # Append the string up to just before m.group(1) plus "XXXXX set InputPortD := {"
        buf.append(glpk[idx : m.start(1)])

        start = int(m.group(1))
        end = int(m.group(2))
        by = m.group(4)
        step = 1 if (by is None) else int(by)
        buf.append(f"{start}")
        for i in range(start + step, end + 1, step):
            buf.append(f",{i}")
        buf.append("}")
        idx = m.end()

    if idx == 0:
        return glpk

    buf.append(glpk[idx:])
    return "".join(buf)


def _formatGLPK(glpk: str):
    """
    Format the string.
    """
    glpk = _expand_numset(glpk)
    glpk = GLPK_util.format_GLPK(glpk)
    glpk = re.sub(r"s\. *t\. *", "# s.t. ", glpk)
    return glpk


def _make_channels_def(topo: topology.Topology):
    """
    Parse topology data and write channel names for ac/XX.model output.
    """
    buf = [
        f"set Channels_{table.channeltable_id};"
        for table in topo.get_all_channeltable()
    ]
    buf.append("set AllChannels;")
    buf.append("param chNo{AllChannels};")
    return "".join(buf)


def _make_channels_data(topo: topology.Topology):
    """
    Parse topology data and output all channel information for writing to ac/channels.data.
    """
    buf = []
    allnos = []
    allchnos = []
    for table in topo.get_all_channeltable():
        id = table.channeltable_id
        buf.append(f"set Channels_{id} :=")
        # ex) Channels_WDM32 := WDM32_1 WDM32_2
        for ch in table.channels:
            txt = f" {ch.full_no}"
            buf.append(txt)
            allnos.append(txt)
            allchnos.append(txt)
            allchnos.append(f" {ch.channel_no}")
        buf.append(";")

    # set AllChannels := WDM32_1 WDM32_2
    buf.append("set AllChannels :=")
    buf.extend(allnos)
    buf.append(";")

    # param chNo := WDM32_1 1 WDM32_2 2 ...
    buf.append("param chNo :=")
    buf.extend(allchnos)
    buf.append(";")

    return _formatGLPK("".join(buf))


def _output_channels_data(acconndir_path: str, topo: topology.Topology):
    """
    Create the ac/channels.data file.
    """
    data = f"{_make_channels_data(topo)}end;{GLPK_util.RET}"
    return GLPK_util.write_file(
        os.path.join(acconndir_path, _CANNELS_FILENAME), "w", data
    )


def _make_channel_conv(comp: component.Component):
    """
    Create a dictionary of {"Channels": <GLPKchannelTableId>}.  
    Example: GLPKchannelTableId = "WDM32, Gray1.3"  
    -> {Channels1: Channels_WDM32, Channels2: Channels_Gray1.3}
    """
    chmap = {}
    # ex) GLPKchannelTableId="WDM32, Gray1.3"
    # v[0] = "WDM32" , v[1]="Gray1.3"
    v = re.split(" *, *", comp.tableid)
    if len(v) == 1:
        chmap["Channels"] = f"Channels_{GLPK_util.escape(v[0])}"
    else:
        id = 1
        for name in v:
            chmap[f"Channels{id}"] = f"Channels_{GLPK_util.escape(name)}"
            id = id + 1
    return chmap


def _fix_channels_name(comp: component.Component, glpk: str):
    """
    Replace the string "Channels" in glpk with "Channels_<GLPKchannelTableId>".
    """
    chmap = _make_channel_conv(comp)
    for k, v in chmap.items():
        glpk = glpk.replace(k, v)
    return glpk


def _append_port(buf: list[str], p: port.Port):
    """
    Add the port number to buf
    """
    if len(buf) > 0:
        buf.append(",")
    buf.append(f"{p.number}")


def _make_IO_port_def(comp: component.Component):
    """
    Return the "number" of each port as a string, separated by input/output types.
    ex)
    <port number="1" XXX io="input"/>
    <port number="2" XXX io="output"/>
    <port number="3" XXX io="output"/>
    <port number="4" XXX io="output"/>
    return "1", "2,3,4"
    """
    inbuf = []
    outbuf = []

    for p in comp.all_ports.values():
        if p.io == p.INPUT:
            _append_port(inbuf, p)
        elif p.io == p.OUTPUT:
            _append_port(outbuf, p)
        elif p.io == p.BIDI:
            _append_port(inbuf, p)
            _append_port(outbuf, p)

    return "".join(inbuf), "".join(outbuf)


def _fix_set_condition(set: str):
    """
    Replace "j" and "l" after ":" with "chNo[j]" and "chNo[l]" and return the result.
    """
    v = re.split(" *: *", set)
    if len(v) == 1:
        return set
    elif len(v) > 2:
        raise ValueError("SYNTAX ERROR: " + set)

    v[1] = re.sub("([jl])", r"chNo[\1]", v[1])
    return f"{v[0]}{GLPK_util.RET}\t: {v[1]}"
    # return f"{v[0]}: {v[1]}"


_AC = re.compile(r"set +(AvailableConnection[^ ]*) *:= *{([^}]+)} *;?")


def _make_modelfile(
    ch_def: str, comp: component.Component, acconndir_path: str
):
    """
    Format the "GLPK" data of components in the topology file
     and create ac/*.model files.
    """
    glpk = comp.GLPK
    html.unescape(glpk)

    buf = []
    idx = 0
    ac_names = set()
    m_iter = _AC.finditer(glpk)
    for m in m_iter:
        """
        ex) glpk= set AvailableConnection := {AAA : j = l && k = j +1}; BBB;
            m.group(1) = "AvailableConnection"
            m.group(2) = "AAA : j = l && k = j +1"
        """
        cond = _fix_set_condition(m.group(2))
        # Append the string up to just before m.group(2) plus "set AvailableConnection := {"
        buf.append(glpk[idx : m.start(2)])
        # Append the string with m.group(2) replaced by "AAA\n\t: chNo[j] = chNo[l] && k = chNo[j] + 1"
        buf.append(cond)
        ac_names.add(m.group(1))
        idx = m.end(2)
        if not m.group(0).endswith(";"):
            log.warning(
                f"missing ; in {comp.model} {GLPK_util.RET} \t{m.group(0)}"
            )

    if idx < len(glpk):
        # Remaining strings to append "}; BBB;"
        buf.append(glpk[idx:])

    if len(ac_names) >= 2:
        """
        If there are two definitions of AvailableConnection, such as AvailableConnectionD and AvailableConnectionA,  
        you must write  
        "set AvailableConnection := AvailableConnectionD union AvailableConnectionA;"  
        If this is not written, add it.
        """
        if re.fullmatch(".*set +AvailableConnection *:=.+", glpk) is None:
            buf.append("set AvailableConnection := ")
            bfirst = True
            for name in ac_names:
                if bfirst:
                    buf.append(name)
                    bfirst = False
                else:
                    buf.append(" union ")
                    buf.append(name)
            buf.append(";")
            log.info(f"append AvailableConnection definition for {comp.model}")
        else:
            log.info(
                f"original AvailableConnection definition in {comp.model}"
            )

    glpk = "".join(buf)
    glpk = _fix_channels_name(comp, glpk)
    in_buf, out_buf = _make_IO_port_def(comp)
    glpk_buf = [
        ch_def,
        "set InputPort := {",
        in_buf,
        "};set OutputPort := {",
        out_buf,
        "};",
        glpk,
        "display AvailableConnection;end;",
    ]
    S = "".join(glpk_buf)
    glpk = _formatGLPK(S)
    modelfile = GLPK_util.write_file(
        os.path.join(
            acconndir_path, GLPK_constant.get_ac_model_filename(comp.model)
        ),
        "w",
        glpk,
    )
    return modelfile


def _output_GLPK(
    ch_def: str, comp: component.Component, acconndir_path: str, datafile: str
):
    """
    Create a *.model file, then use glpsol with the datafile (= channels.data) and the *.model file  
    to output available connection information.  
    The result from glpsol is saved to *.conn.txt.
    """

    modelfile = _make_modelfile(ch_def, comp, acconndir_path)
    cmd_args = [
        GLPK_constant.GLPK_SOLVER,
        "--model",
        os.path.abspath(modelfile),
        "--data",
        os.path.abspath(datafile),
    ]
    ret = subprocess.run(cmd_args, capture_output=True, text=True)
    if ret.returncode == 0:
        connfile = GLPK_util.write_file(
            os.path.join(
                acconndir_path, GLPK_constant.get_ac_conn_filename(comp.model)
            ),
            "w",
            ret.stdout,
        )
        log.info("OK\t" + os.path.abspath(connfile))
    else:
        log.error(f"**** GLPK ERROR (cmd={cmd_args})****")
        log.error(ret.stderr + ret.stdout)


def _check_args(topo_xml: str, glpk_dir: str):
    """
    Check the type of the argument.
    """
    pathfinder_util.check_arg_str(topo_xml)
    pathfinder_util.check_arg_str(glpk_dir)


def make_available_connection(
    topo_xml: str = param.TOPO_XML, glpk_dir: str = param.GLPK_DIR
):
    """
    Read the topology file and generate ac/*.conn.txt, *.model, and channels.data files.
    """
    _check_args(topo_xml, glpk_dir)

    acconndir_path = GLPK_constant.get_available_connectionsdir(glpk_dir)
    topo = topology.Topology(topology.topology_filename(topo_xml), None, False)

    os.makedirs(acconndir_path, exist_ok=True)
    datafile = _output_channels_data(acconndir_path, topo)
    ch_def = _make_channels_def(topo)
    glpk_set = set()

    for comp in topo.get_all_component():
        model = comp.model
        if model in glpk_set:
            continue

        glpk = comp.GLPK
        if glpk is not None:
            _output_GLPK(ch_def, comp, acconndir_path, datafile)
            glpk_set.add(model)


if __name__ == "__main__":
    make_available_connection()
