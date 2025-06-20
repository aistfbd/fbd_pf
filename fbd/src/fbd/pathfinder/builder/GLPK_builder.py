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

A module that calls Builders to create .data files for model data, skeleton data, and glosol.
"""

import os
from fbd.util import logutil
from fbd.topo import GLPK, topology, component, channel_table, port
from fbd.pathfinder import pathfind_request, GLPK_util
from fbd.pathfinder.builder import (
    builder_base,
    inuse_builder,
    v_builder,
    vinuse_builder,
    such_that_data_builder,
    flow_inoutport_builder,
    channels_list_builder,
    varidx_table_builder,
    flow_in_channels_builder,
    IJK2Ls_builder,
    pair_builder,
    cost_builder,
    srcdst_builder,
    multi_width_builder,
    next_ero_builder,
    end_builder,
)


log = logutil.getLogger()


def _build(builders: list[builder_base.BuilderBase]):
    """
    Calls the build() method of each Builder object.
    """
    data_buf: list[str] = []
    model_buf: list[str] = []
    for builder in builders:
        datalines = builder.build()
        modellines = builder.build_modellines()
        if datalines is not None:
            data_buf.append(datalines)
        if modellines is not None:
            model_buf.append(modellines)

    data_file_data: str = "".join(data_buf)
    model_file_data: str = "".join(model_buf)
    return data_file_data, model_file_data


def _remove_old_varidx_t_file(varidx_t_file: str):
    """
    If an old varidx_t_file with the same name exists, delete it.
    This is because the component structure of solvec may have changed due to changes in num_comps.
    """
    try:
        os.remove(varidx_t_file)
    except FileNotFoundError:
        pass
    except PermissionError as e:
        msg = f"failed to remove {varidx_t_file} : {e}"
        log.warning(msg)


def _get_pf_target_ports(
    topo: topology.Topology,
    pf_target_comps: set[component.Component],
    channeltable_id: str,
):
    """
    Creates a list of output target ports.
    The content is the same as set V:.
    For pf, only ports that support the target channel are included.
    If there is only one channel in the channel_table, all ports are included.
    """
    ports: list[port.Port]
    if len(topo.get_all_channeltable()) == 1:
        return topo.get_all_port()

    ports = []
    p: port.Port
    for comp in pf_target_comps:
        for p in comp.get_all_ports():
            if p.is_same_support_channel(channeltable_id) is True:
                ports.append(p)

    return list(
        sorted(ports, key=lambda p: GLPK_util.natural_keys(p.full_name))
    )


def _get_solvec_target_ports(
    solvec_target: tuple[GLPK.Model : set[component.Component]],
):
    """
    Creates a list of output target ports.
    The content is the same as set V:.
    For solvec, includes all ports within the target components.
    """
    ports: list[port.Port] = []
    for comp in sorted(
        solvec_target[1], key=lambda c: GLPK_util.natural_keys(c.name)
    ):
        ports.extend(comp.get_all_ports())
    return ports


def make_skeleton_data(
    topo: topology.Topology,
    solvec: bool,
    write_model: bool,
    channels: list[channel_table.Channel],
    varidx_t_file: str,
    pf_name2model: dict[str : GLPK.Model] | None = None,
    solvec_target: tuple[GLPK.Model : set[component.Component]] | None = None,
):
    """
    Creates skeleton data for .model and .data files.

    write_model: Whether to write to the model file.
    channels: List of target channels.
    pf_name2model: A dictionary of {ModelName: Model} specified when solvec=False.
    solvec_target: A tuple of (Model, {Component, ...}) specified when solvec=True.
    varidx_t_file: Filename for outputting the VarIdxTable.
    """

    if solvec is False:
        target_comps: list[component.Component] = sorted(
            topo.get_support_comps(channels[0].channeltable_id),
            key=lambda c: GLPK_util.natural_keys(c.name),
        )
        target_ports: list[port.Port] = _get_pf_target_ports(
            topo, target_comps, channels[0].channeltable_id
        )
    else:
        target_comps = []
        target_ports: list[port.Port] = _get_solvec_target_ports(solvec_target)

    _remove_old_varidx_t_file(varidx_t_file)

    builder: list[builder_base.BuilderBase] = []

    builder.append(v_builder.VBuilder(target_ports))

    if (solvec is False) or (write_model is True):
        """
        In solvec, SuchThatDataCompsBuilder and SuchThatDataPortsBuilder only write .model files.
        Therefore, when solvec is True and write_model is False,
         there is no need to write .model files,
          so SuchThatDataCompsBuilder and SuchThatDataPortsBuilder are not called.
        """
        builder.append(
            such_that_data_builder.SuchThatDataCompsBuilder(
                solvec,
                write_model,
                pf_name2model,
                target_comps,
                solvec_target,
            )
        )

        builder.append(
            such_that_data_builder.SuchThatDataPortsBuilder(
                solvec,
                write_model,
                pf_name2model,
                target_comps,
                target_ports,
                solvec_target,
            )
        )

    if solvec is False:
        builder.append(
            flow_inoutport_builder.FlowInOutPortBuilder(
                solvec, topo, target_ports, target_comps
            )
        )

    builder.append(
        channels_list_builder.ChannelsListBuilder(
            topo, channels, write_model, solvec
        )
    )

    # varidx_tを作成する
    varidx_t_builder = varidx_table_builder.VarIdxTableBuilder(
        topo, channels, target_ports
    )
    varidx_t: builder_base.VarIdxTable = varidx_t_builder.make_varidx_table(
        varidx_t_file
    )

    builder.append(varidx_t_builder)

    builder.append(
        flow_in_channels_builder.FlowInChannelsBuilder(varidx_t, target_ports)
    )

    if solvec is False:
        builder.append(
            IJK2Ls_builder.IJK2LsBuilder(
                solvec, topo, varidx_t, target_ports, target_comps
            )
        )
        builder.append(multi_width_builder.MultiWidthBuilder(channels))
        builder.append(
            pair_builder.PairBuilder(topo, channels, target_ports, varidx_t)
        )

        builder.append(
            cost_builder.CostBuilder(topo, channels, target_comps, varidx_t)
        )

        builder.append(
            cost_builder.OutOfServiceBuilder(channels, target_comps, varidx_t)
        )

    data_file_data, model_file_data = _build(builder)

    return data_file_data, model_file_data


def make_GLPK_data(
    req: pathfind_request.PathFindRequest,
    solvec_used_comps: set[component.Component],
    solvec: bool,
    varidx_t_file: str,
):
    """
    Creates data for the .data file to append to the skeleton data file.
    """
    builder: list[builder_base.BuilderBase] = []

    if solvec is False:
        target_comps: list[component.Component] = sorted(
            req.topo.get_support_comps(req.channels[0].channeltable_id),
            key=lambda c: GLPK_util.natural_keys(c.name),
        )
        # target_ports(対象comp内の対象chのport) ∈ target_comps(対象comp)内のすべてのport
        target_ports: list[port.Port] = _get_pf_target_ports(
            req.topo, target_comps, req.channels[0].channeltable_id
        )
    else:
        # solvec_used_comps(pfで使用済のportをもつcomponent)から、このリクエストの対象componentを絞り込む
        target_comps: list[component.Component] = [
            comp
            for comp in sorted(
                solvec_used_comps, key=lambda c: GLPK_util.natural_keys(c.name)
            )
            if comp in req.solvec_target[1]
        ]
        # target_comps(pfで使用済の対象comp)内のすべてのport ∈ target_ports(対象comp内のすべてのport)
        target_ports: list[port.Port] = _get_solvec_target_ports(
            req.solvec_target
        )

    builder.append(srcdst_builder.SrcDstBuilder(req.src.port, req.dst.port))

    """
    Restores varidx_t from the varidx_t_file created during skeleton data creation.
    """
    varidx_t_builder = varidx_table_builder.VarIdxTableBuilder(
        req.topo,
        req.channels,
        target_ports,
    )
    varidx_t: builder_base.VarIdxTable = varidx_t_builder.make_varidx_table(
        varidx_t_file
    )

    if solvec is True:

        builder.append(
            vinuse_builder.VinUseBuilder(
                req,
                target_comps,
            )
        )
        builder.append(
            such_that_data_builder.SuchThatDataCompsBuilder(
                solvec,
                False,
                None,
                target_comps,
                req.solvec_target,
            )
        )
        builder.append(
            such_that_data_builder.SuchThatDataPortsBuilder(
                solvec,
                False,
                None,
                target_comps,
                None,
                req.solvec_target,
            )
        )

        builder.append(
            flow_inoutport_builder.FlowInOutPortBuilder(
                solvec, req.topo, target_ports, target_comps
            )
        )
        builder.append(
            IJK2Ls_builder.IJK2LsBuilder(
                solvec, req.topo, varidx_t, target_ports, target_comps
            )
        )
    else:
        builder.append(next_ero_builder.NextEROBuilder(req.next_used_ero))
        builder.append(
            inuse_builder.InuseCBuilder(target_ports, req, varidx_t)
        )

    builder.append(inuse_builder.InuseXBuilder(target_ports, req, varidx_t))
    builder.append(end_builder.EndBuilder())

    data_file_data, model_file_data = _build(builder)
    return data_file_data
