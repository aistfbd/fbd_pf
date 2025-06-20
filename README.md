# FBD_PF

## 1. Overview

The Resource Allocation Program is a Python-based program that runs on Linux and uses GLPK for optimization calculations. This program calculates available connection information for each device and generates model and data files required for route computation.

## 2. Operating Environment

* Linux
* Python 3.10 or later
* GLPK

## 3. Package Contents

Below is the directory structure of the package. Entries marked with \* can be changed through parameter settings.

```
fbd/                             # Top directory  
├── README  
├── config/                      # Configuration files directory  
│   ├── logconfig.yaml          # Log configuration file *  
│   ├── param.json              # Configuration file for Python program  
│   └── requirements.txt        # Python library installation file  
├── db/                         # Directory to store NRM reservation database *  
├── glpk/                       # Directory for GLPK optimization computation *  
│   ├── ac/                     # Data files for available connections  
│   ├── pf-template.model       # Model base file for pf *  
│   └── solvec-template.model   # Model base file for solvec *  
├── src/                        # Python source directory  
│   └── fbd/                    # Directory for Python commands and libraries  
│       ├── MakeAvailableConnections.py  
│       ├── MakePathFinderGLPK.py  
│       ├── NRMClient.py  
│       ├── NRMServer.py  
│       └── __init__.py  
└── topo/                       # Topology file directory  
    ├── JournalTopo0_tpl.xml    # Example topology file *  
    └── topo_lxml.xsd           # Schema file  
```

## 4. Environment Setup

### Install Required Libraries

```bash
pip install -r config/requirements.txt  
```

### Install GLPK

GLPK is used as an external optimization engine. Download and install it from the following site, and make sure it is included in your system path:
[https://www.gnu.org/software/glpk/](https://www.gnu.org/software/glpk/)

### Path Settings

Add the full path of `fbd/src` to the environment variable `PYTHONPATH`:

```bash
cat ~/.bashrc  
export PYTHONPATH=/home/<user>/fbd/src:${PYTHONPATH}  
```

### Edit Python Configuration File

Edit `config/param.json` to suit your environment:

```json
{
  "logger":"enable",
  "log_config":"logconfig.yaml",
  "topo_xml":"JournalTopo0_tpl.xml",
  "glpk_dir":"glpk",
  "db_dir":"db",
  "nrm_host":"localhost",
  "nrm_Port":8080,
  "pf_tmp_model":"pf-template.model",
  "solvec_tmp_model":"solvec-templae.model",
  "num_comps":5
}
```

Descriptions of each field (directory paths are relative to the top directory `fbd`):

#### `logger`

* **Description**: Enable or disable the logging function
* **Examples**:

  * `enable`: Enabled
  * `disable`: Disabled

#### `log_config`

* **Description**: Log output configuration file

#### `topo_xml`

* **Description**: Topology file

#### `glpk_dir`

* **Description**: Path to store GLPK model base, model, and data files

#### `db_dir`

* **Description**: Path to store the updated NRM database

#### `nrm_host`

* **Description**: Hostname to connect to NRM

#### `nrm_port`

* **Description**: Port number to connect to NRM

#### `pf_tmp_model`

* **Description**: Model base file for route calculation

#### `solvec_tmp_model`

* **Description**: Model base file for solvec calculation

#### `num_comps`

* **Description**: Number of components processed per process during solvec calculation.
  If 0 is specified, all components in the device are calculated in one process.

### Edit Log Configuration File and Create Log Output Directory

Each process outputs logs.
Log settings are configured via the file specified in `log_config` in `param.json`.
Below is the default configuration. Adjust the file name and path as needed:

```yaml
# logconfig.yaml
version: 1
formatters:
  simple_fmt:
    format: '%(message)s'
  detail_fmt:
    format: '%(asctime)s %(levelname)s %(filename)s:%(lineno)d %(funcName)s() %(message)s'
handlers:
  console:
    class: logging.StreamHandler
    formatter: simple_fmt
    stream: ext://sys.stdout
  file:
    class: logging.handlers.RotatingFileHandler
    formatter: detail_fmt
    filename: logs/nrm.log  # *1 Log output file name
    maxBytes: 10485760      # *2
    backupCount: 10         # *2
    encoding: "utf-8"
    mode: "a"
root:
  level: INFO
  handlers: [file, console]  # *3
disable_existing_loggers: False
```

#### *1 About the `filename` field

* `filename` specifies the file path for log output.
* Path must be relative to the `fbd` top directory.
* If the parent directory does not exist, it must be created in advance:

```
mkdir /home/fbd/logs
```

* Otherwise, the Python command will fail with the following error:

```
File "/home/<user>/fbd/src/fbd/util/logutil.py", line 38, in init_logger
    raise Exception(e) from e
Exception: Unable to configure handler 'file'
```

#### *2 About log rotation settings

* `maxBytes: 10485760`: Limit log size to 10MB per file
* `backupCount: 10`: Keep up to 10 generations of log files
* Older logs are saved as:

```
fbd/logs/nrm.log.[1-10]_yyyy-MM-dd
```

#### *3 About output targets

* By default, logs are output to both file and console
* To output only to file, modify as follows:

```yaml
handlers: [file]
```

## 5. Command Specifications

The following Python files are provided as commands.
To execute route calculations, run the following in order:
If the topology does not change, you only need to run `MakeAvailableConnections.py` and `MakePathFinderGLPK.py` once. After that, run `NRMServer.py` and `NRMClient.py` in sequence.

* `MakeAvailableConnections.py`: Calculates available connection info for each device
* `MakePathFinderGLPK.py`: Generates model and data files for route calculation
* `NRMServer.py`: Launches the server to receive NRM requests
* `NRMClient.py`: Launches the client to send NRM requests to the server


## 7. List of Generated Files

The following files are created during the execution process:

| File Path                                        | Description                                                                                                             | Timing of Creation or Update               |
| ------------------------------------------------ | ----------------------------------------------------------------------------------------------------------------------- | ------------------------------------------ |
| `history.nrm`                                    | Stores command history in the interactive mode of `NRMClient.py`. Deleting this file does not affect route computation. | `NRMClient.py`                             |
| `logs/nrm.log`                                   | Log output file. If the parent directory does not exist, the process will fail.                                         | All processes                              |
| `glpk/ac/<device>.model`                         | Model file for available connections per device.                                                                        | `MakeAvailableConnections.py`              |
| `glpk/ac/<device>.conn.txt`                      | Connection info file after computing available connections.                                                             | `MakeAvailableConnections.py`              |
| `glpk/glpk/pf_<topo_xml>.model`                  | Path calculation model file (pf).                                                                                       | `MakePathFinderGLPK.py`                    |
| `glpk/glpk/pf_<topo_xml>_<channel>.data`         | Path calculation skeleton data file per channel (pf).                                                                   | `MakePathFinderGLPK.py`                    |
| `glpk/glpk/solvec_<topo_xml>_<device>.model`     | Model file per device for solvec.                                                                                       | `MakePathFinderGLPK.py` (with --solvec)    |
| `glpk/glpk/solvec_<topo_xml>_<device>_<no>.data` | Skeleton data file per device for solvec.                                                                               | `MakePathFinderGLPK.py` (with --solvec)    |
| `db/reserved.json`                               | Reservation database file.                                                                                              | `NRMServer.py` (with --db), `NRMClient.py` |
| `glpk/tmp/<UUID>.lp`, `glpk/tmp/<UUID>.sol`      | Temporary calculation files generated by GLPK.                                                                          | `NRMServer.py`, `NRMClient.py`             |




## 8. List of References to Topology File

The program reads the data from the topology file (.xml) and retains each item as an object. The following table describes how each item is referenced and used.

| Element      | Attribute          | Purpose of Use                                                                                                                                                                            |
| ------------ | ------------------ | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| channelTable | type               | If not "optical", a warning message is displayed, and that channelTable is ignored.                                                                                                       |
|              | id                 | Used as the ID of the ChannelTable object.                                                                                                                                                |
| channel      | no                 | Used as the "no" of the Channel object; the channel name is constructed as {channelTable id}\_{no}.                                                                                       |
| comp         | ref                | Used as the name of the Component object.                                                                                                                                                 |
|              | Model              | Used for generating GLPK constraint expressions in .data and .model files.                                                                                                                |
|              | GLPK               | Used as constraint expressions of the Model object.                                                                                                                                       |
|              | Controller         | Used together with the "Socket" attribute to determine whether to retain an intermediate controller. Components not retained are excluded from the solvec path calculation.               |
|              | Socket             | Used together with the "Controller" attribute to determine whether to retain an intermediate controller.                                                                                  |
|              | GLPKchannelTableId | Used to replace the string "Channels" in GLPK constraint expressions with "Channels\_<GLPKchannelTableId>". The replaced content is written to the .model files under the "ac" directory. |
|              | Cost               | Used as the cost of the Component, and for generating cost values and OUT\_OF\_SERVICES entries in skeleton data.                                                                         |
| Port         | number             | Used as the "no" of the Port object; the port name is constructed as {Component name}\_{no}.                                                                                              |
|              | supPortChannel     | Used to identify which channelTable the port supports.                                                                                                                                    |
|              | name               | Used as the name of the Port object and displayed in the output of the "query" subcommand.                                                                                                |
|              | (IN/OUT)           | Extracts the "IN" or "OUT" part and is used in the output of pathfind/query. Also used for identifying the IO type when the io element is missing, and identifying the opposite port.     |
|              | io                 | Used to determine whether the Port is input, output, or bidirectional.                                                                                                                    |
| net          | code               | Used in error messages when registering PortPairs.                                                                                                                                        |
|              | pair               | The value before the hyphen is used as the key of the PortPair object.                                                                                                                    |
| node         | ref                | Used as the component name.                                                                                                                                                               |
|              | pin                | Used as the Port name in the format {ref}\_{pin}.                                                                                                                                         |
|              | cost               | Used as the cost of the PortPair object and for generating cost values and OUT\_OF\_SERVICES entries in skeleton data.                                                                    |

For details on how to generate topology files, please refer to the following link.
**Note**: The provided resources are compatible with older versions of KiCAD. Support for the latest version of KiCAD is currently under consideration.
[https://unit.aist.go.jp/riaep/cppc/en/TDG\_Download/index.html](https://unit.aist.go.jp/riaep/cppc/en/TDG_Download/index.html)



## 9. License

This project is licensed under the Apache License 2.0.
For details, refer to the LICENSE file:
[https://www.apache.org/licenses/LICENSE-2.0.html](https://www.apache.org/licenses/LICENSE-2.0.html)



## 10. Acknowledgement

This work is partly based on results obtained from a project, JPNP16007, commissioned by the New Energy and Industrial Technology Development Organization (NEDO).

