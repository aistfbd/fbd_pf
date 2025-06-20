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

Module implementing the reserve operation
"""

from __future__ import annotations
import os
import shutil
import tempfile
import subprocess
import re
from concurrent.futures import ThreadPoolExecutor
import functools
from fbd.util import param, logutil, elapse
from fbd.topo import topology, channel_table, port, component, GLPK
from fbd.pathfinder import (
    GLPK_util,
    GLPK_route,
    GLPK_constant,
    GLPK_result,
    pathfind_request,
    reservation_manager,
    simple_path_finder,
    pathfinder_util,
)
from fbd.pathfinder.ope import opebase
from fbd.pathfinder.builder import GLPK_builder


log = logutil.getLogger()


class Reserve(opebase.OpeBase):
    """
    Class that executes the reserve subcommand.
    
    Attributes:
        self.rsv_mgr: ReservationManager object that manages reservation information
        self.skeletondir_path: Directory for skeleton data files
        self.topo_xml: Topology file name
        self.simpleFinder:
        self.name2model: Dictionary of target models {model_name: Model}. Models with glpk.stdefs=None are excluded
        self.globalid: UUID assigned for each path calculation
        wdmsa_channel_idx: Channel index used when wdmsa is specified, incremented per specification
    
    Option definitions -> {option: number of arguments}  
    NONE_VAL means no argument (boolean True/False), ANY_VAL means variable number of arguments  
    options_def = {'-bi': NONE_VAL, '-s': ONE_VAL, '-d': ONE_VAL,
                   '-ero': ANY_VAL, '-ch': ANY_VAL, '-wdmsa': NONE_VAL,
                   '-p': ONE_VAL,
                   '-model': ONE_VAL, '-data': ONE_VAL}
    
    Default values:  
    defo_args = {'bi': False, 's': None, 'd': None, 'ero': None,
                 'ch': None, 'wdmsa': False, 'p': 'os.cpu_count()',
                 '-model': None, '-data': None}
    """


    options_def = (
        opebase.OPT_BI[0]
        | opebase.OPT_SRC[0]
        | opebase.OPT_DST[0]
        | opebase.OPT_ERO[0]
        | opebase.OPT_CH[0]
        | opebase.OPT_WDMSA[0]
        | opebase.OPT_PROCESS[0]
        | opebase.OPT_MODEL[0]
        | opebase.OPT_DATA[0]
    )
    defo_args = (
        opebase.OPT_BI[1]
        | opebase.OPT_SRC[1]
        | opebase.OPT_DST[1]
        | opebase.OPT_ERO[1]
        | opebase.OPT_CH[1]
        | opebase.OPT_WDMSA[1]
        | opebase.OPT_PROCESS[1]
        | opebase.OPT_MODEL[1]
        | opebase.OPT_DATA[1]
    )

    usage = """[-bi] -d <dst> [-ero <ero1 ero2 ero3..>] -s <src>
                [-ch <ch1 chX..chY chZ  ...>] [-wdmsa] [-p <num_threads>]
                [-model <model_file_key> [-data <data_file_key>]
        -bi                            solve bidirectional route
        -d <dst>                       destination
        -ero <ero1 ero2 ero3 ...>      ERO Port names
        -s <src>                       source
        -ch <ch1 chX..chY chZ  ...>    use channel names (chX..chY means {chX,chX+1, ..., chY})
        -wdmsa                         use one WDM channel in round robin order
        -p                             number of concurrent threads
        -model <model_file_key>        key of GLPK model file name
        -data <data_file_key>          key of skeleton data file name"""

    wdmsa_channel_idx = 0

    def __init__(
        self,
        name: str | None,
        topo: topology.Topology,
        topo_xml: str,
        glpk_dir: str,
        rsv_mgr: reservation_manager.ReservationManager,
    ):
        super().__init__(name, topo, Reserve.usage)
        self.rsv_mgr: reservation_manager.ReservationManager = rsv_mgr
        self.skeletondir_path: str = GLPK_constant.get_model_data_file_dir(
            glpk_dir
        )
        self.topo_xml: str = topo_xml
        self.simple_finder = simple_path_finder.SimplePathFinder(topo)
        self.name2model: dict[str : GLPK.Model] = (
            pathfinder_util.load_all_modelfiles(topo, glpk_dir)
        )
        self.globalid: str | None = None

    def parse_options(self, input_args: list[str]):
        """
        Parses options and sets values in self.op_args.
        """

        return super().parse_options(
            Reserve.options_def, Reserve.defo_args, input_args
        )

    def _make_port_lambda(self, name: str):
        """
        Creates a PortChannel object from a name.
        """
        p: port.Port | None = self.topo.get_port_by_name(name)
        if p is None:
            err_msg = f"invalid port name : {name}"
            log.error(err_msg)
            raise ValueError(err_msg)

        return GLPK_route.PortChannel(p, None)

    def _make_ero(self):
        """
        Converts the port names specified by the -ero option into a list of Port objects  
        and returns it.
        
        Example return: [Port(N1214_2), Port(N1209_2)]
        """
        names: list[str] | None = super().get_opt(opebase.KEY_ERO)
        if (names is None) or (len(names) == 0):
            return None

        ero: list[port.Port] = []
        for name in names:
            p: port.Port | None = self.topo.get_port_by_name(name)
            if p is None:
                err_msg = f"invalid port name in ERO : {name}"
                log.error(err_msg)
                raise ValueError(err_msg)
            ero.append(p)
        return ero

    def _get_channel(self, name: str):
        """
        Returns a Channel object from a channel name.  
        Raises a ValueError if not found.
        """

        ch: channel_table.ChannelTable | None = (
            self.topo.get_channel_by_fullno(name)
        )
        if ch is None:
            err_msg = f"invalid channel name : {name}"
            log.error(err_msg)
            raise ValueError(err_msg)
        return ch

    def _get_channel_set(self, start: str, end: str):
        """
        Returns a list of channels from the specified start and end channel names.  
        Example: start="WDM32_1", end="WDM32_5"  
        ch_list = [WDM32_1, WDM32_2, WDM32_3, WDM32_4, WDM32_5]
        """

        start_ch: channel_table.Channel = self._get_channel(start)
        end_ch: channel_table.Channel = self._get_channel(end)

        if start_ch.channeltable_id != end_ch.channeltable_id:
            err_msg = f"different ChannelTable : {start}-{end}"
            log.error(err_msg)
            raise ValueError(err_msg)

        ch_table: channel_table.ChannelTable = (
            self.topo.get_channeltable_by_id(start_ch.channeltable_id)
        )
        ch_set: set[channel_table.Channel] = {
            ch
            for ch in ch_table.channels
            if (start_ch.channel_no <= ch.channel_no)
            and (ch.channel_no <= end_ch.channel_no)
        }
        return ch_set

    def _make_channels(self):
        """
        Parses the -wdm, -wdmsa, and -wdmfull options and  
        returns the channels to use as a set of {Channel, ...}.
        
        OpeBase: addChannels
        
        ● When -wdmsa is specified:  
           Channels are selected from the WDM group in a round-robin manner.
        
           Example:
           > pathfind -s P1201_2 -d P204_1  
           WDM32_1
        
           > pathfind -s P1201_2 -d P204_1  
           WDM32_2
        
           > pathfind -s P1201_2 -d P204_1  
           WDM32_3
        
        ● When -ch is specified:  
           The explicitly specified channels are used.
        
           Example:
           > pathfind -s P1201_2 -d P204_1 -ch WDM32_1 WDM32_5  
           WDM32_1  
           WDM32_5
        
        ● When no specific option is provided:  
           All channels are used.
        
           Example:
           > pathfind -s P1201_2 -d P204_1  
           WDM32_1  
             :  
           WDM32_32  
           Gray1_3_1
        
        ● If both -ch and -wdmsa are specified, -wdmsa is ignored.
        """
        ch_list: list[channel_table.Channel] | None = None

        if (chs := super().get_opt(opebase.KEY_CH)) is not None:
            """
            Adds the channels specified with the -ch option.
            """

            ch_set = set()
            for ch_name in chs:
                v = re.split(r"\.\.", ch_name)
                if len(v) == 1:
                    # "WDM32_1"
                    ch_set.add(self._get_channel(v[0]))
                elif len(v) == 2:
                    # "WDM32_1..WDM32_5"
                    child_ch_set: set[channel_table.Channel] = (
                        self._get_channel_set(v[0], v[1])
                    )
                    if len(child_ch_set) > 0:
                        ch_set |= child_ch_set
                    else:
                        msg = f"invalid channels : {ch_name}"
                        log.error(msg)
                        raise ValueError(msg)
            ch_list = list(
                sorted(ch_set, key=lambda c: GLPK_util.natural_keys(c.full_no))
            )
        elif super().get_bool_opt(opebase.KEY_WDMSA) is True:
            """
            Cycles through WDM channels in a round-robin manner.
            """
            for table in self.topo.get_all_channeltable():
                if table.isWDM() is False:
                    continue
                wdm_table_len = len(table.channels)
                ch_list = [table.channels[Reserve.wdmsa_channel_idx]]
                if Reserve.wdmsa_channel_idx < wdm_table_len - 1:
                    Reserve.wdmsa_channel_idx += 1
                else:
                    Reserve.wdmsa_channel_idx = 0
            if ch_list is None:
                msg = "there are no WDM channels"
                log.error(msg)
                raise ValueError(msg)
        else:
            """
            If neither -wdmsa nor -ch is specified, add all channels.
            """
            ch_list = self.topo.get_all_channel()
        return ch_list

    def _is_bi_available(self, pc: GLPK_route.PortChannel):
        """
        Returns whether bi can be specified
        """
        p: port.Port = pc.port
        # Ports that are bidirectional or have a uniquely determined reverse port can be specified with -bi.
        return p.has_opposite_port()

    def _make_request(self):
        """
        Creates a request for path computation.
        Reserve:makeRequest
        """
        src: GLPK_route.PortChannel = self._make_port_lambda(
            super().get_required_opt(opebase.KEY_SRC)
        )
        dst: GLPK_route.PortChannel = self._make_port_lambda(
            super().get_required_opt(opebase.KEY_DST)
        )
        if src.port.full_name == dst.port.full_name:
            err_msg = f"src == dst : {src.port.full_name}"
            log.error(err_msg)
            raise ValueError(err_msg)

        bidi: bool = super().get_bool_opt(opebase.KEY_BI)
        ero: list[port.Port] | None = self._make_ero()

        ch_list: list[channel_table.Channel] = self._make_channels()
        if bidi and (
            (self._is_bi_available(src) is False)
            or (self._is_bi_available(dst) is False)
        ):
            msg = (
                f"-{opebase.KEY_BI} option not supported for "
                + src.port.full_name
                + f"({src.port.support_channel},{src.port.io})"
                + f" and {dst.port.full_name}"
                + f"({dst.port.support_channel},{dst.port.io})"
            )
            log.error(msg)
            raise ValueError(msg)

        return pathfind_request.make_new_req(
            self.topo,
            src,
            dst,
            ch_list,
            ero,
            bidi,
            self.rsv_mgr,
        )

    def _get_ero_split_requests(self, req: pathfind_request.PathFindRequest):
        """
        Split the request into ERO paths.

        PathFindRequest:getEROSplitRequests()

        ex)
        CMD = reserve -s P1201_2 -d P204_1 -ero N1214_2 N1209_2
        # original request
        src = P1201_2
        dst = P204_1
        org_ero = [N1214_2, N1209_2]
        next_used_ero = None

        # sub request No.0
        src = P1201_2
        dst = N1214_2
        org_ero = None
        next_used_ero = [N1209_2, P204_1]

        # sub request No.1
        src = N1214_2
        dst = N1209_2
        org_ero = None
        next_used_ero = [P204_1]

        # sub request No.2
        src = N1209_2
        dst = P204_1
        org_ero = None
        next_used_ero = None
        """

        ero_in_topo: list[port.Port] | None = req.org_ero

        if ero_in_topo is None:
            return None

        req_list: list[pathfind_request.PathFindRequest] = []
        log_line = []
        log_line.append("# original request")
        log_line.append(req.dump_req(True))
        log_line.append("# ERO in topology")
        log_line.append(
            pathfind_request.PathFindRequest.print_ero(ero_in_topo)
        )

        """
        Create used_route and used_conn for subreq.
        Since used_route and used_conn are appended
         with each subreq execution,
        they are kept as separate objects from the original 
        request and shared across all subreqs.
        """

        used_route: GLPK_route.GLPKRoute = GLPK_route.GLPKRoute(
            req.used_route.entry_list.copy()
        )
        used_conn: GLPK_route.GLPKRoute = GLPK_route.GLPKRoute(
            req.used_conn.entry_list.copy()
        )
        req0: pathfind_request.PathFindRequest = pathfind_request.make_ero_req(
            req.src,
            GLPK_route.PortChannel(ero_in_topo[0], None),
            req,
            None,
            req.make_next_ero(ero_in_topo, 0),
            used_route,
            used_conn,
        )

        req_list.append(req0)

        for i in range(len(ero_in_topo) - 1):
            subreq: pathfind_request.PathFindRequest = (
                pathfind_request.make_ero_req(
                    GLPK_route.PortChannel(ero_in_topo[i], None),
                    GLPK_route.PortChannel(ero_in_topo[i + 1], None),
                    req,
                    None,
                    req.make_next_ero(ero_in_topo, i + 1),
                    used_route,
                    used_conn,
                )
            )
            req_list.append(subreq)

        req_last: pathfind_request.PathFindRequest = (
            pathfind_request.make_ero_req(
                GLPK_route.PortChannel(ero_in_topo[-1], None),
                req.dst,
                req,
                None,
                None,
                used_route,
                used_conn,
            )
        )
        req_list.append(req_last)

        for idx, subreq in enumerate(req_list):
            log_line.append(f"# sub request No. {idx}")
            log_line.append(subreq.dump_req(False))

        log.info(GLPK_util.RET.join(log_line))
        return req_list

    def _parse_cost(self, sol_file: str):
        """
        Reads the .sol file output from glpsol and returns 
        the numeric value of "PATH_COST = XXX (MINimum)".
        If no solution exists, returns sys.float_info.max.
        GLPKWork: parseCost()
        """
        if os.path.isfile(sol_file) is False:
            return GLPK_constant.NOT_FOUND_COST

        PATH_COST = re.compile("PATH_COST = ([0-9\\.]+)")
        n: int = 0
        with open(sol_file, "r") as fd:
            try:
                for line in fd:
                    m = re.search(PATH_COST, line)
                    if m:
                        c: float = float(m.group(1))
                        if c > 0:
                            return c
                        else:
                            break

                    n += 1
                    if n >= 10:
                        break
            except Exception as e:
                msg = f"Error parse cost {sol_file}: {e}"
                log.error(msg)
                raise Exception(msg) from e

        return GLPK_constant.NOT_FOUND_COST

    def _get_file_key(self, opt_key: str | None):
        """
        Returns the key for the filename.
        If opt_key is not specified, returns the value of topo_xml.
        """
        return opt_key if opt_key is not None else self.topo_xml

    def _make_data_file_pf(
        self,
        req: pathfind_request.PathFindRequest,
        data_file_key,
        temp_mydir: str,
    ):
        """
        Process executed in parallel.
        Copies the skeleton data and appends necessary constraint expressions
        to generate a pf data file for glpsol.
        """
        elp = elapse.Elapse()
        ch: channel_table.Channel = req.channels[0]
        name = os.path.join(
            self.skeletondir_path, f"pf_{data_file_key}_{ch.full_no}"
        )
        skeleton_file = f"{name}.data"
        varidx_t_file = f"{name}.pickle"

        name = os.path.join(
            temp_mydir,
            f"pf_{data_file_key}_{ch.full_no}_{req.src.port.full_name}-"
            + req.dst.port.full_name,
        )

        data_file = f"{name}.data"
        sol_file = f"{name}.sol"

        try:
            shutil.copy(skeleton_file, data_file)
        except Exception as e:
            msg = f"failed to copy skeleton_file {skeleton_file} {data_file}: {e}"
            log.error(msg)
            raise Exception(msg) from e

        # log.info(f"copy {skeleton_file} {data_file}")
        # print(req.dump_req(False))
        data_file_data = GLPK_builder.make_GLPK_data(
            req, None, False, varidx_t_file
        )
        GLPK_util.write_file(data_file, "a", data_file_data)
        elp.show(f"reserve#_make_data_file_pf {data_file}")

        return data_file, sol_file

    def _make_data_file_solvec(
        self,
        req: pathfind_request.PathFindRequest,
        used_comps: set[component.Component],
        data_file_key,
        temp_mydir: str,
        file_idx: str,
    ):
        """
        Process executed in parallel.  
        Copies the skeleton data and appends necessary constraint expressions  
        to generate a solvec data file for glpsol.
        """
        elp = elapse.Elapse()
        model: GLPK.Model = req.solvec_target[0]
        name = os.path.join(
            self.skeletondir_path,
            f"solvec_{data_file_key}_{model.name}_{file_idx}",
        )
        skeleton_file = f"{name}.data"
        varidx_t_file = f"{name}.pickle"

        name = os.path.join(
            temp_mydir,
            f"solvec_{data_file_key}_{model.name}_{file_idx}_"
            + f"{req.src.port.full_name}-{req.dst.port.full_name}",
        )

        data_file = f"{name}.data"
        sol_file = f"{name}.sol"

        try:
            shutil.copy(skeleton_file, data_file)
        except Exception as e:
            msg = f"failed to copy skeleton_file {skeleton_file} {data_file}: {e}"
            log.error(msg)
            raise Exception(msg) from e

        # log.info(f"copy {skeleton_file} {data_file}")
        # print(req.dump_req(False))
        data_file_data = GLPK_builder.make_GLPK_data(
            req, used_comps, True, varidx_t_file
        )
        GLPK_util.write_file(data_file, "a", data_file_data)
        elp.show("reserve#_make_data_file_solvec")
        return data_file, sol_file

    def _GLPK_work(
        self,
        model_file_key: str,
        data_file_key: str,
        temp_mydir: str,
        solvec: bool,
        used_comps: set[component.Component] | None,
        arg: (
            pathfind_request.PathFindRequest
            | bool
            | tuple[pathfind_request.PathFindRequest, int]
        ),
    ):
        """
        Process executed in parallel.  
        Creates a data file, runs glpsol, and returns the result as a GLPKResult.  
        GLPLWork: run()
        """

        if solvec:
            solvec_req_idx: tuple[pathfind_request.PathFindRequest, int] = arg
            req: pathfind_request.PathFindRequest = solvec_req_idx[0]
            idx: int = solvec_req_idx[1]
            data_file, sol_file = self._make_data_file_solvec(
                req, used_comps, data_file_key, temp_mydir, idx
            )
            max_sec = GLPK_constant.MAX_SEC_SOLVEC
            model_file = os.path.join(
                self.skeletondir_path,
                f"solvec_{model_file_key}_{req.solvec_target[0].name}.model",
            )

        else:
            if arg is False:
                """
                If req=False, glpsol is not executed and no solution is returned.
                """
                return GLPK_result.GLPKResult(
                    None, GLPK_constant.NOT_FOUND_COST, None
                )
            req: pathfind_request.PathFindRequest = arg
            data_file, sol_file = self._make_data_file_pf(
                req, data_file_key, temp_mydir
            )
            max_sec = GLPK_constant.MAX_SEC_PATH_FIND
            model_file = os.path.join(
                self.skeletondir_path,
                f"pf_{model_file_key}.model",
            )
        tl = ["=========================================================="]
        tl.append("solveC" if solvec else "pathfind")
        tl.append(model_file)
        tl.append(data_file)
        tl.append("request")
        tl.append(req.dump_req(False))
        log.info(GLPK_util.RET.join(tl))

        cmd_args = [
            GLPK_constant.GLPK_SOLVER,
            "--model",
            os.path.abspath(model_file),
            "--data",
            os.path.abspath(data_file),
            "--output",
            os.path.abspath(sol_file),
            "--tmlim",
            f"{max_sec}",
        ]
        elp = elapse.Elapse()
        ret = subprocess.run(cmd_args, capture_output=True, text=True)
        elp.show(f"reserve#exec --data={data_file}")
        if solvec is False:
            cost: float = self._parse_cost(sol_file)
            result = GLPK_result.GLPKResult(req, cost, ret.stdout)
        else:
            result = GLPK_result.GLPKResult(req, None, ret.stdout)

        if opebase.DUMP_GLPSOL is False:
            result.dump_solution()
        else:
            log.info(ret.stdout)
        return result

    def _new_used_route(self, results: list[GLPK_result.GLPKResult]):
        """
        Creates GLPKRoutes from results and merges them into a single GLPKRoute to return.
        This prevents all routes found in earlier requests during ERO-split request executions
        from being used in subsequent requests.
        The choice of which solution to select is made after all ERO requests are completed.
        """
        new_route = GLPK_route.GLPKRoute(None)
        for result in results:
            if result.has_answer() is False:
                continue

            sub_route: GLPK_route.GLPKRoute = result.make_route_entry_list()
            new_route.extend_list(sub_route.entry_list)
        return new_route

    def _get_answer_idx_list(
        self, sub_results_list: list[list[GLPK_result.GLPKResult]]
    ):
        """
        Looks at the head of each sub_results list and returns a list of (i, cost) tuples
        for all sub_results[i] that have a solution.
        """
        # The length of the result list is the same for all subreqs = the number of used channels since there is a result for each channel
        n_ch = len(sub_results_list[0])
        costs: dict[int:float] = {i: 0 for i in range(n_ch)}
        # Accumulate costs for each channel. Exclude channels with any subreq that has no solution from comparison.
        for i in range(n_ch):
            answer_num: int = 0
            for sub_results in sub_results_list:
                if sub_results[i].has_answer():
                    costs[i] += sub_results[i].cost
                    answer_num += 1
            if answer_num != len(sub_results_list):
            # Remove indices of results with no solution in all subreqs from costs
                costs.pop(i)
        if len(costs) == 0:
            return None
        costs_sorted: list[tuple[int:float]] = sorted(
            costs.items(), key=lambda x: x[1]
        )
        # Returns a list of (idx, cost) tuples sorted by the accumulated cost values
        return costs_sorted

    def _merge_sub_results(
        self, sub_results_list: list[list[GLPK_result.GLPKResult]]
    ):
        """
        Merges results from sub_reqs that have solutions and returns a list of GLPKRoutes.  
        sub_results_list is a list of lists of GLPKResults from ERO-split requests, for example:  
        [  
          [GLPKResult=has_solution, GLPKResult=has_solution], <- sub_results for [WDM32_1, WDM32_2, WDM32_3 ... 32]  
          [GLPKResult=has_solution, GLPKResult=no_solution], ...  
          [GLPKResult=has_solution, GLPKResult=has_solution], ...  
        ]  
        Returns the routes from idx0 and idx2 as route_list.  
        """

        if (
            idx_tuple_list := self._get_answer_idx_list(sub_results_list)
        ) is None:
            return None

        route_list: list[GLPK_route.GLPKRoute] = []

        for idx_tuple in idx_tuple_list:
            route: GLPK_route.GLPKRoute = GLPK_route.GLPKRoute(None)
            for sub_results in sub_results_list:
                result: GLPK_result.GLPKResult = sub_results[idx_tuple[0]]
                sub_route: GLPK_route.GLPKRoute = (
                    result.make_route_entry_list()
                )
                route.extend_list(sub_route.entry_list)
            route_list.append(route)
        return route_list

    def _query_with_ERO(
        self,
        req_list: list[pathfind_request.PathFindRequest],
        model_file_key: str,
        data_file_key: str,
        temp_mydir: str,
    ):
        """
        Executes path computation for each request split by ERO routes and merges the results.
        PathFinderBase: queryWithERO
        """

        sub_results_list: list[list[GLPK_result.GLPKResult]] = []
        for subreq in req_list:
            results: list[GLPK_result.GLPKResult] = self._pf_query_path(
                subreq, model_file_key, data_file_key, temp_mydir
            )
            answer_num = 0
            for result in results:
                if result.has_answer():
                    answer_num += 1
                    break
            if answer_num == 0:
                subreq.add_errmsg(
                    "cannot find ERO sub route : "
                    + f"{subreq.src.port.full_name}-{subreq.dst.port.full_name}"
                )
                return None

            new_route: GLPK_route.GLPKRoute = self._new_used_route(results)
            
            """
            Merge new_route into used_route and used_conn.  
            Since used_route and used_conn share the same memory space across all subreqs,  
            they are continuously appended with each merge.  
            The merged used_route and used_conn are used in the next subreq.
            """

            subreq.used_route.merge_pf_route(new_route.entry_list)
            # log.info("merge subreq_route")
            # log.info(subreq.used_route.dump())
            subreq.used_conn.merge_solvec_route(new_route.entry_list)
            sub_results_list.append(results)

        if (route_list := self._merge_sub_results(sub_results_list)) is None:
            req_list[0].add_errmsg(
                "cannot find all suitable path for each ERO sub path"
            )

        return route_list

    def _add_sub_path(
        self,
        full_back_list: list[GLPK_route.GLPKRouteEntry],
        src: port.Port,
        dst: port.Port,
        ch: channel_table.Channel,
    ):
        """
        PathFindBase:addSubPath()
        Calculates the route between src and dst and adds it to full_back_list.
        """
        # Calculate the route between src and dst based on flow_outs information

        ports: list[port.Port] | None = self.simple_finder.search(
            self.topo, src, dst
        )

        if ports is None:
            log.error(
                f"cannot find sub path : {src.full_name}-{dst.full_name}"
            )
            return False
        """
        log.error(
            f"{GLPK_util.port_lambda_pairkey(src.full_name, ch.full_no,dst.full_name, ch.full_no)}"
        )
        log.error(f"{[p.full_name for p in ports]}")
        """
        """
        Check if the calculated route has an AC connection; if so, create a GLPKRouteEntry
        and add it to full_back_list.
        """

        for i in range(len(ports) - 1):
            sub_src: GLPK_route.PortChannel = GLPK_route.PortChannel(
                ports[i], ch
            )
            if (
                pathfinder_util.has_connection(
                    self.topo, ports[i], ch, ports[i + 1], ch
                )
                is False
            ):
                log.error(
                    "has not connection : "
                    + f"{ports[i].full_name}@{ch.full_no} -"
                    + f"{ports[i+1].full_name}@{ch.full_no}"
                )
                return False

            sub_dst: GLPK_route.PortChannel = GLPK_route.PortChannel(
                ports[i + 1], ch
            )

            sub_entry = GLPK_route.GLPKRouteEntry(
                sub_src, sub_dst, True, True, False
            )
            full_back_list.append(sub_entry)

        return True

    def _make_full_back_route(
        self,
        go_dst: GLPK_route.PortChannel,
        go_src: GLPK_route.PortChannel,
        back_list: list[GLPK_route.GLPKRouteEntry],
    ):
        """
        Using back_list created from port pairs of src/dst at the end of the pf-computed route and their paired port pairs,  
        construct full_back_list that connects each entry in back_list.
        
        Example:  
        back_list = [pc10-pc9, pc6-pc5]  
        full_back_list = [pc10-pc9, pc9-pc8, pc8-pc7, pc6-pc6, pc6-pc5]
        """
        full_back_list: list[GLPK_route.GLPKRouteEntry] = []
        """
        Check whether there is a reverse port for src/dst.
        """
        back_src: port.Port | None = go_dst.port.get_opposite_port()
        back_dst: port.Port | None = go_src.port.get_opposite_port()
        if (back_src is None) or (back_dst is None):
            return None
        """
        Since all pf-computed routes use the same channel, and the back_list channels
        also use the channels from the pf-computed routes, there is only one channel.
        """
        ch: channel_table.Channel | None = go_dst.ch

        before_dst: port.Port = back_src
        """
        ex)
        back_list=[pc10-pc9, pc6-pc5]
        _add_sub_path(src=pc9(<-before_dst), dst=pc6(entry.src.port))
        """
        for entry in back_list:
            if before_dst.full_name != entry.src.port.full_name:
                if (
                    self._add_sub_path(
                        full_back_list,
                        before_dst,
                        entry.src.port,
                        ch,
                    )
                    is False
                ):
                    return None
            full_back_list.append(entry)
            before_dst = entry.dst.port

        if before_dst.full_name != back_dst.full_name:
            if (
                self._add_sub_path(
                    full_back_list,
                    before_dst,
                    back_dst,
                    ch,
                )
                is False
            ):
                return None

        return full_back_list

    def _add_pair_connections(
        self,
        glpk_route: GLPK_route.GLPKRoute,
        req: pathfind_request.PathFindRequest,
    ):
        """
        Calculates and returns the back route of the route computed by pf.
        PathFinderBase: addPairConnections()
        """
        # Convert the forward route computed by pf into a list of PortChannels
        port_channel_list: list[GLPK_route.PortChannel] = (
            glpk_route.make_path_list(self.topo, req.src, True)
        )
        """
        log.error("port_channel_list")
        log.error(
            f"{GLPK_util.RET}{GLPK_util.RET.join([pc.port.full_name for pc in port_channel_list])}"
        )
        """
        assert len(port_channel_list) >= 2, "ASSERT! Invalid route"
        back_list: list[GLPK_route.GLPKRouteEntry] = []
        answer_src: GLPK_route.PortChannel = port_channel_list[0]
        answer_dst: GLPK_route.PortChannel = port_channel_list[-1]
        """
        Search from the end of port_channel_list for a pair with the same pair key as the src/dst pair,  
        and add it to back_list.
        
        Example:  
        port_channel_list = [pc1@ch1, pc2@ch1, pc3@ch1, pc4@ch1, pc5@ch1, pc6@ch1]  
        go_src = pc5 → the pair with the same pair key is src=pc6 / dst=pc5  
        go_dst = pc6
        
        go_src = pc4 → the pair with the same pair key is src=pc5 / dst=pc4  
        go_dst = pc5
        
        back_list = [GLPKRouteEntry(pc6@ch1/pc5@ch1), GLPKRouteEntry(pc5@ch1/pc4@ch1)]
        """
        for i in reversed(range(len(port_channel_list))):
            go_src: GLPK_route.PortChannel = port_channel_list[i - 1]
            go_dst: GLPK_route.PortChannel = port_channel_list[i]
            if (
                pair := self.topo.find_portpair(go_src.port, go_dst.port)
            ) is None:
                continue
            """
            Since all pf-computed routes use the same channel, go_src.ch and go_dst.ch are the same.
            """
            assert (
                go_src.ch.full_no == go_dst.ch.full_no
            ), "ASSERT! Multiple channels are used in the pf path."
            entry: GLPK_route.GLPKRouteEntry = GLPK_route.GLPKRouteEntry(
                GLPK_route.PortChannel(pair.src, go_src.ch),
                GLPK_route.PortChannel(pair.dst, go_dst.ch),
                True,
                True,
                False,
            )
            back_list.append(entry)
            """
            log.error(
                f"add  backlist go_src/go_dst={go_src.make_key()}/{go_dst.make_key()}: {entry.dump()}"
            )
            """
        """
        log.error("back_list")
        log.error(
            f"{GLPK_util.RET}{GLPK_util.RET.join([entry.dump() for entry in back_list])}"
        )
        """
        full_back_list: list[GLPK_route.GLPKRouteEntry] | None = (
            self._make_full_back_route(answer_dst, answer_src, back_list)
        )
        if full_back_list is None:
            req.add_errmsg("cannot find back path")
            return None
        """
        log.error("full_back_list")
        log.error(
            f"{GLPK_util.RET}{GLPK_util.RET.join([entry.dump() for entry in full_back_list])}"
        )
        """
        return full_back_list

    def _is_used_entry(
        self, entry: GLPK_route.GLPKRouteEntry, used_set: set[str]
    ):
        """
        Whether the route is reserved.
        """
        assert entry.has_none_obj() is False, "ASSERT! channel is None"
        return (
            GLPK_util.port_lambda_pairkey(
                entry.src.port, entry.src.ch, entry.dst.port, entry.dst.ch
            )
            in used_set
        )

    def _is_back_route_used(
        self,
        full_back_list: list[GLPK_route.GLPKRouteEntry],
        req: pathfind_request.PathFindRequest,
    ):
        """
        Checks if the forward path uses a route that is already reserved.
        """
        used_set: set[str] = {
            GLPK_util.port_lambda_pairkey(
                entry.src.port, entry.src.ch, entry.dst.port, entry.dst.ch
            )
            for entry in req.used_route.entry_list
        }
        for entry in full_back_list:
            if entry.x and self._is_used_entry(entry, used_set):
                req.add_errmsg(f"back path is already used : {entry.dump()}")
                return True
        return False

    def _make_used_comps_by_port(
        self, p: port.Port, used_comps: set[component.Component]
    ):
        """
        Create a set of Components used by pf starting from the port.
        """
        comp: component.Component = self.topo.get_component_by_port(p)
        if comp.has_controller():
            used_comps.add(comp)

    def _make_used_comps_by_route(
        self,
        glpk_route: GLPK_route.GLPKRoute,
        used_comps: set[component.Component],
    ):
        """
        Create a set of Components used by pf based on the GLPKRoute.
        """
        for entry in glpk_route.entry_list:
            self._make_used_comps_by_port(entry.src.port, used_comps)
            self._make_used_comps_by_port(entry.dst.port, used_comps)

    def _make_used_comps(self, req: pathfind_request.PathFindRequest):
        """
        Create a set of Components used by pf from the used_conn and used_req members of PathFindRequest.
        VinUseBuilder: addUsedBBComp()
        """
        used_comps: set[component.Component] = set()
        self._make_used_comps_by_route(req.used_conn, used_comps)
        self._make_used_comps_by_route(req.used_route, used_comps)

        return used_comps

    def _solvec_query_path(
        self,
        req: pathfind_request.PathFindRequest,
        model_file_key: str,
        data_file_key: str,
        temp_mydir: str,
    ):
        """
        Create PathFindRequest per device based on the GLPKRoute computed by pf,  
        and execute path computation in parallel.  
        In solvec, all channels are used.  
        PathFindBase: solveC()
        """
        used_comps: set[component.Component] = self._make_used_comps(req)

        channels: list[channel_table.Channel] = list(
            self.topo.get_all_channel()
        )

        solvec_idx_target_list: list[
            tuple[GLPK.Model, set[component.Component], int]
        ] = pathfinder_util.make_solvec_target(self.name2model)

        """
        Create a PathFindRequest for each solvec_idx_target,  
        and generate tuples of (PathFindRequest, index of the skeleton data filename).
        """
        solvec_req_idx_list: list[
            tuple[pathfind_request.PathFindRequest, int]
        ] = [
            (
                pathfind_request.make_solvec_req(
                    channels,
                    req,
                    (model_target[0], model_target[1]),
                ),
                model_target[2],
            )
            for model_target_list in solvec_idx_target_list
            for model_target in model_target_list
        ]
        """
        #for debug single thread
        results = []
        for solvec_req_idx in solvec_req_idx_list:
            results.append(
                self._GLPK_work(
                    model_file_key,
                    data_file_key,
                    temp_mydir,
                    True,
                    used_comps,
                    solvec_req_idx,
                )
            )
        return results
        """
        with ThreadPoolExecutor(
            max_workers=super().get_int_opt(opebase.KEY_PROCESS)
        ) as executor:
            results: list[GLPK_result.GLPKResult] = list(
                executor.map(
                    functools.partial(
                        self._GLPK_work,
                        model_file_key,
                        data_file_key,
                        temp_mydir,
                        True,
                        used_comps,
                    ),
                    solvec_req_idx_list,
                )
            )
            return results
        # """

    def _pf_query_path(
        self,
        req: pathfind_request.PathFindRequest,
        model_file_key: str,
        data_file_key: str,
        temp_mydir: str,
    ):
        """
        Create a list of requests for each channel and execute them in parallel on separate threads.  
        WDMPathFinder: queryPath()
        """
        req_list: list[pathfind_request.PathFindRequest | bool] = []
        for ch in req.channels:
            if (
                req.src.port.is_same_support_channel(ch.channeltable_id)
                is False
            ) or (
                req.dst.port.is_same_support_channel(ch.channeltable_id)
                is False
            ):
                log.info(
                    f"{ch.full_no} does not support src/dst port SKIP glpsol"
                )
                """
                If the channel does not support src/dst, add False to the list.  
                If not added, the indices for each ero_req will be misaligned during _get_answer_idx_list() calculation.
                """
                req_list.append(False)
            else:
                req_list.append(pathfind_request.make_pf_req(ch, req))

        """
        # for debug single thread

        results: list[GLPK_result.GLPKResult] = []
        for req in req_list:
            result = self._GLPK_work(
                model_file_key, data_file_key, temp_mydir, False, None, req
            )
            results.append(result)

        return results
        """
        with ThreadPoolExecutor(
            max_workers=super().get_int_opt(opebase.KEY_PROCESS)
        ) as executor:
            results: list[GLPK_result.GLPKResult] = list(
                executor.map(
                    functools.partial(
                        self._GLPK_work,
                        model_file_key,
                        data_file_key,
                        temp_mydir,
                        False,
                        None,
                    ),
                    req_list,
                )
            )
            return results
        # """

    def _pf_query(
        self,
        req: pathfind_request.PathFindRequest,
        model_file_key: str,
        data_file_key: str,
        temp_mydir: str,
    ):
        """
        Execute path calculation using pf.  
        PathFinderBase: query()
        """
        # log.error("before req.used_route=")
        # log.error(req.used_route.dump())
        # GLPKRoute route;
        req_list: list[pathfind_request.PathFindRequest] | None = (
            self._get_ero_split_requests(req)
        )
        route_list: list[GLPK_route.GLPKRoute] | None = None
        if req_list is None:
            results: list[GLPK_result.GLPKResult] = self._pf_query_path(
                req, model_file_key, data_file_key, temp_mydir
            )
            results_sorted = sorted(
                results, key=GLPK_result.GLPKResult.compare_key
            )
            # Create a GLPKRoute from the GLPKResult at the front of results with the lowest cost
            route_list: list[GLPK_route.GLPKRoute] = [
                results.make_route_entry_list()
                for results in results_sorted
                if results.has_answer()
            ]

            if len(route_list) == 0:
                req.add_errmsg("cannot find usable route")
        else:
            route_list: list[GLPK_route.GLPKRoute] = self._query_with_ERO(
                req_list, model_file_key, data_file_key, temp_mydir
            )

        if (route_list is None) or (len(route_list) == 0):
            return None

        return route_list

    def _solvec_query(
        self,
        req: pathfind_request.PathFindRequest,
        route: GLPK_route.GLPKRoute,
        model_file_key: str,
        data_file_key: str,
        temp_mydir: str,
    ):
        """
        Perform solvec computation based on the route calculated by pf.
        """
        results: list[GLPK_result.GLPKResult] = self._solvec_query_path(
            req, model_file_key, data_file_key, temp_mydir
        )
        for result in results:
            dev_route: GLPK_route.GLPKRoute | None = (
                result.make_conn_entry_list()
            )
            if dev_route is None:
                log.error(result.stdout)
                req.add_errmsg("cannot find suitable c")
                return None
            route.merge_solvec_route(dev_route.entry_list)
            # log.error("merge_solvec_route")
            # log.error(route.dump())
        return route

    def query(
        self,
        req: pathfind_request.PathFindRequest,
    ):
        """
        Perform the path computation process.
        PathFinder:query()
        PathFinderBase:query()

        """
        solvec_route: GLPK_route.GLPKRoute = None

        model_file_key = self._get_file_key(super().get_opt(opebase.KEY_MODEL))
        data_file_key = self._get_file_key(super().get_opt(opebase.KEY_DATA))

        temp_glpkdir = os.path.join(
            param.GLPK_DIR, GLPK_util.escape(self.globalid)
        )
        temp_mydir = os.path.join(tempfile.gettempdir(), temp_glpkdir)
        os.makedirs(temp_mydir, exist_ok=False)

        route_list: list[GLPK_route.GLPKRoute] | None = self._pf_query(
            req, model_file_key, data_file_key, temp_mydir
        )
        if route_list is not None:
            for route in route_list:
                bi_req = pathfind_request.make_bi_req(req)

                # log.error("after req.used_route=")
                # log.error(req.used_route.dump())

                # pfで算出したrouteをreqのused_route,used_connに設定する
                bi_req.used_route.merge_pf_route(route.entry_list)
                bi_req.used_conn.merge_solvec_route(route.entry_list)
                #log.error("route=")
                #log.error(route.dump())
                if req.bidi:
                    full_back_list: list[GLPK_route.GLPKRouteEntry] | None = (
                        self._add_pair_connections(route, bi_req)
                    )
                    if full_back_list is not None:
                        if self._is_back_route_used(full_back_list, bi_req):
                            assert (
                                bi_req.has_err()
                            ), "ASSERT! Err not set in req"

                    if bi_req.has_err():
                        log.error(
                            f"{route.entry_list[0].src.ch.full_no} is no bi answer"
                            + f" : {bi_req.get_errmsg()}"
                        )
                        continue

                    route.extend_list(full_back_list)
                    bi_req.used_route.merge_pf_route(full_back_list)
                    bi_req.used_conn.merge_solvec_route(full_back_list)
                    # log.error("back_route=")
                    # log.error(route.dump())

                solvec_route = self._solvec_query(
                    bi_req, route, model_file_key, data_file_key, temp_mydir
                )
                if solvec_route is not None:
                    break
                else:
                    log.error(
                        f"{route.entry_list[0].src.ch.full_no} is no solvec answer"
                    )

            """
            If all pf computations have no solution, merge the error message from the last executed bi_req into the original req.
            """
            if solvec_route is None:
                req.add_errmsg(bi_req.get_errmsg())

        if opebase.DELTMP:
            """
            Do not delete /tmp/glpk because directories for other UUIDs may exist;  
            only delete the /tmp/glpk/<globalId> directory.
            """
            shutil.rmtree(temp_mydir)

        return solvec_route

    def _reserve(self, req: pathfind_request.PathFindRequest):
        """
        Perform path calculation and add reservation information.
        NRM:reserve()
        """
        self.globalid: str = (
            reservation_manager.ReservationManager.get_new_reservationID()
        )
        if (glpk_route := self.query(req)) is None:
            return None
        #        log.error(glpk_route.dump())
        go_list: list[GLPK_route.PortChannel] = glpk_route.make_path_list(
            self.topo, req.src, True
        )
        assert len(go_list) >= 2, "ASSERT! invalid route"
        rsv = reservation_manager.Reservation(
            self.globalid, go_list[0], go_list[-1], glpk_route
        )
        self.rsv_mgr.add(rsv)
        self.globalid = None
        return rsv

    def operation(self):
        """
        Main process.  
        Create a request, execute path calculation, save reservation information,  
        and return the reservation ID and reservation global ID.
        """

        # Initialize globalid
        self.globalid = None

        req: pathfind_request.PathFindRequest = self._make_request()
        rsv: reservation_manager.Reservation | None = self._reserve(req)
        if rsv is None:
            msg = f"PROBLEM HAS NO PRIMAL FEASIBLE SOLUTION{GLPK_util.RET}{req.get_errmsg()}"
            raise RuntimeError(msg)

        id: str = self.rsv_mgr.id_mgr.add_globalid(rsv.globalid)
        if req.has_err():
            """
            When the process completes successfully but there are warning messages.
            """
            msg = GLPK_util.RET.join(
                [req.get_errmsg(), f"id={id}, globalId={rsv.globalid}"]
            )
        else:
            msg = f"id={id}, globalId={rsv.globalid}"
        log.info(msg)
        return msg


"""
for debug 
"""

from fbd.util import param
from fbd.pathfinder import request_handler

if __name__ == "__main__":
    topo_xml: str = param.TOPO_XML
    glpk_dir: str = param.GLPK_DIR
    db: bool = True

    acconndir_path: str = GLPK_constant.get_available_connectionsdir(glpk_dir)

    topo: topology.Topology = topology.Topology(
        topology.topology_filename(topo_xml), acconndir_path, True
    )

    handler: request_handler.RequestHandler = request_handler.RequestHandler(
        topo, topo_xml, glpk_dir, db
    )
    """
    replay = handler.handle_req(
        "pathfind -s P1201_2 -d P204_1 -ero N1214_2 N1209_2"
    )
    handler.handle_req("reserve -s P1201_2 -d P204_1 -ero N1214_2 N1209_2")
    handler.handle_req("reserve -s P1201_2 -d P204_1 -ero N1214_2 N1209_2")

    print(f"replay= {replay}")
    """

    while True:
        data = input(">")
        replay = handler.handle_req(data)
        print(f"replay={replay}")
