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

Module that defines functions commonly used throughout the program.
"""

import re
from fbd.util import logutil

log = logutil.getLogger()

# RET = os.linesep
RET = "\n"
VAR = r"\w+"  # [a-zA-Z0-9_]+"


def atoi(text):
    """
    Convert the value to int if it is numeric.
    """
    return int(text) if text.isdigit() else text


def natural_keys(text):
    """
    Split the text into an array of numeric and non-numeric parts.  
    Convert numeric parts to int.  
    If the non-numeric parts are the same, comparison is done based on the numeric values.  
    Example: "N206" becomes ["N", 206].
    
    Function for sorting strings containing numbers.  
    Reference: https://dlrecord.hatenablog.com/entry/2020/07/30/230234
    """

    return [atoi(c) for c in re.split(r"(\d+)", text)]


def escape(txt: str | None):
    """
    Replace characters in txt that are not alphanumeric or underscore (_) with an underscore (_).
    """
    if txt is not None:
        return re.sub(r"[^\w]", "_", txt)
    else:
        return None


def write_file(filename: str, mode: str, txt: str):
    """
    Write to a file.
    """
    try:
        with open(filename, mode) as fd:
            fd.write(txt)
    except Exception as e:
        errmsg = f"Error write {filename}: {e}"
        log.error(errmsg)
        raise Exception(errmsg) from e
    else:
        return filename


def read_file(filename: str):
    """
    Read from a file.
    """
    try:
        with open(filename, "r") as fd:
            return fd.read()
    except Exception as e:
        errmsg = f"Error read {filename}: {e}"
        log.error(errmsg)
        raise Exception(errmsg) from e


def format_GLPK(glpk: str):
    """
    Remove or add spaces, and insert a newline after semicolons (;).
    """
    glpk = re.sub(" *:= *", " := ", glpk)  # ":=" -> ":= "
    glpk = re.sub(", *", ", ", glpk)  # "," -> ", "
    glpk = re.sub(
        r" *([<>&:=\+\-\*/]+) *", r" \1 ", glpk
    )  # Insert spaces before and after the symbols [<>&:=+-*/]
    glpk = re.sub(r"\( +", "(", glpk)
    glpk = re.sub(r" +\)", ")", glpk)
    glpk = re.sub("; *", ";" + RET, glpk)  # ";" -> ";\n"
    glpk = re.sub(r"} *: *", "} : ", glpk)  # "}:" ->"} : "
    glpk = re.sub(r" +\[", r"\[", glpk)
    return glpk


def port_lambda_pairkey(
    in_port: str,
    in_ch: str,
    out_port: str,
    out_ch: str,
):
    """
    Create a unique key from the in/out port and channel.
    """
    return f"{in_port}@{in_ch}#{out_port}@{out_ch}"


def port_lambda_pairkey_ijk(
    in_port: str,
    in_ch: str,
    out_port: str,
):
    """
    Create a key in the format of in/out port and channelijk.
    """
    return f"{in_port}@{in_ch}#{out_port}@undef"
