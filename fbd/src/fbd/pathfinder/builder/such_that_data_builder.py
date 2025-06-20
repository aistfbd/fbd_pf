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

Module that keeps the classes of SuchThatDataCompsBuilder and SuchThatDataPortsBuilder
"""

import re
from fbd.topo import component, port, GLPK
from fbd.pathfinder import GLPK_util
from fbd.pathfinder.builder import builder_base


class SuchThatDataBuilder(builder_base.BuilderBase):
    """
    Base class for SuchThatDataCompsBuilder and SuchThatDataPortsBuilder.  
    Defines functions commonly used by both.
    
    Attributes:
        self.sovec: Whether this is a 'solvec' computation
        self.target_comps: List of target components
        self.pf_target_models: Dictionary of {ModelName: Model}, specified when solvec is False
        self.solvec_target: Dictionary of {Model: {comp, comp}}, used when solvec is True
    """

    def __init__(
        self,
        solvec: bool,
        write_model: bool,
        pf_name2model: dict[str : GLPK.Model] | None,
        target_comps: list[component.Component],
        solvec_target: tuple[GLPK.Model : set[component.Component]] | None,
    ):
        super().__init__(write_model=write_model)
        self.solvec: bool = solvec
        self.target_comps: list[component.Component] = target_comps
        #TopologyGLPKManager() excludes components that do not have 'st' or 'controller', in the previous implementation in Java.
        self.pf_target_models: dict[str : GLPK.Model] | None = pf_name2model
        self.solvec_target: (
            tuple[GLPK.Model : set[component.Component]] | None
        ) = solvec_target

    def get_target_models(self):
        """
        Returns the list of target models
        """
        tgt_models: list[GLPK.Model] = None
        if self.pf_target_models is not None:
            tgt_models = self.pf_target_models.values()
        elif self.solvec_target is not None:
            tgt_models = [self.solvec_target[0]]
        return tgt_models

    def get_model_by_comp(self, model_name: str):
        """
        Returns the target model.
        
        - In the case of 'pf', returns the value from `pf_target_models` using the model name as the key.
        - In the case of 'solvec', returns the model from `solvec_target`.
        """
        if self.pf_target_models is not None:
            return self.pf_target_models.get(model_name)
        elif self.solvec_target is not None:
            return self.solvec_target[0]

    def get_target_component_in_model(self, model: GLPK.Model):
        """
        Returns the list of target components within the model.
        
        - In the case of 'pf': returns the components in the Model object that are included in get_target_component().
        - In the case of 'solvec': since there is only one model, returns the result of get_target_component().
        """
        if self.solvec is False:
            """
            https://qiita.com/Mt_Snow/items/6af7f94295dc572598a1
            """
            return [
                comp
                for comp in model.components
                if (comp in self.target_comps)
            ]

        return self.target_comps


class SuchThatDataCompsBuilder(SuchThatDataBuilder):
    """
    Constructs the 'set Comps_' line in the .model and .data files
    """

    def __init__(
        self,
        solvec: bool,
        write_model: bool,
        pf_name2model: dict[str : GLPK.Model] | None,
        target_comps: list[component.Component],
        solvec_target: tuple[GLPK.Model : set[component.Component]] | None,
    ):
        super().__init__(
            solvec,
            write_model,
            pf_name2model,
            target_comps,
            solvec_target,
        )

    def build(self):
        """
        Constructs the 'set Comps_' line in the .model and .data files.
        
        Example:
            set Comps_TAWG_C401C60F21_05 := N1203 N1216;
        """
        if (len(self.target_comps) == 0) and (self.modellines is not None):
            for model in super().get_target_models():
                setname = f"Comps_{GLPK_util.escape(model.name)}"
                super().print_any_modelline(f"set {setname};")
            return

        for model in super().get_target_models():
            setname = f"Comps_{GLPK_util.escape(model.name)}"
            super().print_any_modelline(f"set {setname};")
            super().print_set_def(setname)
            super().print_components(
                super().get_target_component_in_model(model)
            )
            super().print_any(f";{GLPK_util.RET}")
        return super().build()


class SuchThatDataPortsBuilder(SuchThatDataBuilder):
    """
    Constructs the following lines in the .model and .data files:
        set Comps_InputPort / OutputPort
        set InputPort / OutputPort
    
    Attributes:
        self.target_ports: List of target ports  
                           Used only when solvec is False
    """
    def __init__(
        self,
        solvec: bool,
        write_model: bool,
        pf_name2model: dict[str : GLPK.Model] | None,
        target_comps: list[component.Component],
        target_ports: list[port.Port] | None,
        solvec_target: tuple[GLPK.Model : list[component.Component]] | None,
    ):
        super().__init__(
            solvec,
            write_model,
            pf_name2model,
            target_comps,
            solvec_target,
        )
        self.target_ports: set[port.Port] = (
            set(target_ports) if target_ports is not None else None
        )

    def _make_modelset(self):
        """
        Creates the `model2sets` dictionary.
        
        Example:
        model2sets = {
            'A0496_FABLS_D735A': {'OutputPort', 'InputPort'},
            'TAWG_C401C60F21_05': {'OutputPort', 'InputPort'},
            'DWP_EK_AA': {'OutputPort', 'InputPort'},
            'WSS_100_4': {'OutputPort', 'InputPort'},
            'DIV1X5': {'OutputPort', 'InputPort'},
            'WSS_100_9': {'OutputPort', 'InputPort'},
            'Si_TPA': {'InputPortA', 'OutputPortA', 'InputPortD', 'OutputPortD'},
            'TF100': {'OutputPort', 'InputPort'},
            'GG112_C_SYSTEM100_16': {'OutputPort', 'InputPort'},
            'OMS_UNIT': {'OutputPort', 'InputPort'}
        }
        """
        model2sets: dict[str : set[str]] = {}
        model: GLPK.Model

        for model in super().get_target_models():
            glpk: GLPK.GLPK = model.glpk
            for st in glpk.stdefs:
                domain: GLPK.Domain = glpk.get_domain(st)
                domains: set[GLPK.Domain] = {domain}
                if isinstance(st.stdef, GLPK.SumCond):
                    sumcond: GLPK.SumCond = st.stdef
                    domains.add(sumcond.domain)
                for d in domains:
                    for key, val in d.var_inset.items():
                        if re.fullmatch("[ik]", key):
                            # Only i:InputPort and k:OutputPort are included in model2sets
                            model2sets.setdefault(model.name, set()).add(val)
        return model2sets

    def _make_compset(self, model2sets: dict[str : set[str]]):
        """
        Creates set2comps and valsets.
        
        set2comps = {
            InputPort: {comp1, comp2, comp3},
            InputPortA: {comp1, comp2, comp3}
        }
        
        valsets is a list containing only the keys of set2comps.
        
        This is created because during solvec skeleton data generation,  
        get_target_component_in_model() may return empty,  
        so there are no values to assign to keys, but keys alone are needed  
        for writing the model file.
        """
        set2comps: dict[str : set[component.Component]] = {}
        valsets: set[str] = set()
        model: GLPK.Model

        for model in super().get_target_models():
            for valset in model2sets.get(model.name, set()):
                for comp in super().get_target_component_in_model(model):
                    set2comps.setdefault(valset, set()).add(comp)
                valsets.add(valset)
        return valsets, set2comps

    def build(self):
        """
        Constructs InputPort/OutputPort information.
        
        Example:
            "set Comps_InputPortD := N211 N511 N1210;"
            "set Comps_InputPortF := N403 N602 N605 N1403;"
            "set InputPort[N206] := N206_1;"
        """

        model2sets = self._make_modelset()
        valsets, set2comps = self._make_compset(model2sets)
        set_names = list(sorted(valsets))
        if len(set2comps) == 0 and (self.modellines is not None):
            """
            There are two cases where set2comps becomes empty:
            
            1. During solvec skeleton data creation → self.modellines is not None
            2. During solvec route calculation execution when used_comps has no target components,  
               or during pf skeleton data creation when the target Model has no target components
            
            In case 1, only model data is written out.  
            In case 2, empty data such as `set Comps_DWP_EK_AA :=;` is written to the data file.
            """
            """
            During solvec skeleton data creation, since there is no component information,  
            only the data for the model file is written out.
            
            Example:
                set Comps_InputPortA;
                set Comps_InputPortD;
            """

            for valset in set_names:
                super().print_any_modelline(f"set Comps_{valset};")
                super().print_any_modelline(f"set {valset}{{Comps_{valset}}};")
            return

        for valset in set_names:
            setname = f"Comps_{valset}"
            super().print_any_modelline(f"set {setname};")
            super().print_set_def(setname)
            super().print_components(set2comps.get(valset), sort=True)
            super().print_any(f";{GLPK_util.RET}")

        """
         "set InputPortA[N211] := N211_25 N211_26 N211_27 N211_28 N211_29
          N211_30 N211_31 N211_32;"
         "set InputPortA[N511] := N511_25 N511_26 N511_27 N511_28 N511_29
          N511_30 N511_31 N511_32;"
        """
        for valset in set_names:
            super().print_any_modelline(f"set {valset}{{Comps_{valset}}};")
            comp_set: set[component.Component] = set2comps.get(valset, set())
            # Sort Components in comp_set by name.
            # Since names contain numbers, use natural_keys() for natural sorting.
            for comp in sorted(
                comp_set, key=lambda t: GLPK_util.natural_keys(t.name)
            ):
                super().print_set_def_idx(valset, comp.name)
                model: GLPK.Model = super().get_model_by_comp(comp.model)
                setdef: GLPK.SetDef = model.glpk.setdefs.get(valset)
                ports: list[port.Port] = []
                for num in setdef.nums:
                    p: port.Port | None = comp.get_port(num)
                    if p is not None:
                        if (self.solvec is False) and (
                            p not in self.target_ports
                        ):
                            """
                            For pf, ports that do not support the target channel are excluded.  
                            For solvec, all channels are targeted, so no check is necessary.
                            """
                            continue
                        ports.append(p)
                    """
                    If a port is deleted from the topology file after creating the ac file,  
                    p becomes None.
                    """

                super().print_ports(ports, sort=False)
                super().print_any(f";{GLPK_util.RET}")
        return super().build()
