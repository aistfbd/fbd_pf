# FBD_PF 
 
## 1. 概要 
資源割り当てプログラムは、Linux上で動作するPythonベースのプログラムで、GLPKを使用して最適化計算を行います。このプログラムは、デバイスごとの利用可能な接続情報を算出し、経路計算を行うためのモデルファイルとデータファイルを生成します。 
 
## ２．動作環境 
- Linux 
- Python 3.10以降 
- GLPK 
 
## ３．パッケージ内容 
以下がパッケージのディレクトリ構成です。＊はファイル名やパスをパラメタ設定で変更可能です。 
```
fbd/                             # トップディレクトリ
├── README
├── config/                      # 設定ファイル用ディレクトリ
│   ├── logconfig.yaml          # log機能の設定ファイル＊
│   ├── param.json              # pythonプログラムの設定ファイル
│   └── requirements.txt        # python用ライブラリインストール設定ファイル
├── db/                         # NRMの予約データベースを置くディレクトリ＊
├── glpk/                       # GLPK最適化計算用ディレクトリ＊
│   ├── ac/                     # 利用可能な接続情報に関するデータファイル用ディレクトリ
│   ├── pf-template.model       # pf用モデルベースファイル＊
│   └── solvec-template.model   # solvec用モデルベースファイル＊
├── src/                        # pythonソース用ディレクトリ
│   └── fbd/                    # pythonコマンド、ライブラリ用ディレクトリ
│       ├── MakeAvailableConnections.py
│       ├── MakePathFinderGLPK.py
│       ├── NRMClient.py
│       ├── NRMServer.py
│       └── __init__.py
└── topo/                       # トポロジーファイル用ディレクトリ
    ├── JournalTopo0_tpl.xml    # トポロジーファイルの例＊
    └── topo_lxml.xsd           # スキーマーファイル
```
 
## ４．環境構築 
### 必要ライブラリのインストール 
```bash
pip install -r config/requirements.txt 
``` 
 

### GLPKのインストール 

外部最適化計算エンジンとしてGLPKを使用します。下記サイトからGLPKをインストールし、パスを通しておいてください。 

https://www.gnu.org/software/glpk/ 

 
### パス設定 
環境変数PYTHONPATHにfbd/srcのフルパスを追加します。 

```bash
cat ~./bashrc
    
export PYTHONPATH=/home/<user>/fbd/src:${PYTHONPATH} 
``` 
 
### Python設定ファイルの編集 
`config/param.json`を環境に応じて編集します。
   
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

各項目の説明は以下の通りです。ディレクトリのパスはトップディレクトリのfbdからの相対パスで指定します。

#### `logger`
- **説明**: log機能の有効／無効を指定する
- **設定例**:
  - `enable`: 有効
  - `disable`: 無効
#### `log_config`
- **説明**: log出力設定ファイル
#### `topo_xml`
- **説明**: トポロジファイル
#### `glpk_dir`
- **説明**: GLPKのモデルベースファイル、モデルファイル、データファイルを置くディレクトリパス
#### `db_dir`
- **説明**: NRMの更新データベースを置くディレクトリパス
#### `nrm_host`
- **説明**: NRMの接続ホスト名
#### `nrm_port`
- **説明**: NRMの接続ポート番号
#### `pf_tmp_model`
- **説明**: パス計算用モデルベースファイル
#### `solvec_tmp_model`
- **説明**: solveC計算用モデルベースファイル
#### `num_comps`
- **説明**: solveC計算時に1プロセスで計算するコンポーネント数。
  0 が指定された場合はデバイス内の全コンポーネントが1プロセスで計算される。

### ログ用設定ファイルの編集、ログ出力用ディレクトリの作成
各処理はログに出力される。 
ログの設定は`param.json`の`log_config`に記述するファイルにより行う。 
以下がデフォルトの設定値である。ファイル名やパスなど環境に応じて変更をする。 

```yaml
#logconfig.yaml
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
#   class: logging.StreamHandler
    formatter: detail_fmt
    filename: logs/nrm.log  # ★① ログ出力用ファイル名
    maxBytes: 10485760      # ★②
    backupCount: 10         # ★②
    encoding: "utf-8"
    mode: "a"
root:
  level: INFO
  handlers: [file,console]  # ★③
disable_existing_loggers: False
```
#### ★① `filename` の項目について
- `filename` はログ出力用ファイルパスを指定します。
- ファイルパスはトップディレクトリの `fbd` からの**相対パス**で指定してください。
- ログ出力用ファイルの**親ディレクトリが存在しない場合は、事前に作成しておく必要があります**。
```
mkdir /home/fbd/logs
```
- 親ディレクトリが存在しない場合、Pythonコマンドが以下のようなエラーで終了してしまいます。
```
File "/home/<user>/fbd/src/fbd/util/logutil.py", line 38, in init_logger
    raise Exception(e) from e
Exception: Unable to configure handler 'file'
```
#### ★② ローテーション設定について
- `maxBytes: 10485760` は、**1ファイルあたり最大10MB**までログを保存する設定です。
- `backupCount: 10` は、**最大10世代までログファイルを保存**することを意味します。
- 古いログファイルは以下のような形式で保存されます：
```
fbd/logs/nrm.log.[1-10]_yyyy-MM-dd
```
#### ★③ 出力先の設定について
- デフォルトでは、ログは**ファイルとコンソールの両方**に出力されます。
- **ファイルのみに出力したい場合**は、以下のように設定を変更してください：
```yaml
handlers: [file]
```


## ５．コマンド仕様 
以下のPythonファイルをコマンドとして提供します。経路計算実行時には下記を順に実行する必要があります。`MakeAvailableConnections.py`と`MakePathFinderGLPK.py`はトポロジを変更しない限り、1度だけ実行すれば、その後は、`NRMServer.py`と`NRMClient.py`を順に実行すればよいです。 
 
- `MakeAvailableConnections.py`: デバイス毎の利用可能な接続情報を算出します。 
- `MakePathFinderGLPK.py`: 経路計算用モデルファイルとデータファイルを生成します。 
- `NRMServer.py`: NRMのリクエストを受け付けるサーバを起動します。 
- `NRMClient.py`: NRMリクエストをサーバに送信するためのクライアントを起動します。

### MakeAvailableConnections.py
経路計算の事前準備として、デバイス毎の利用可能な接続情報を算出します。計算に必要なchannels.data、<デバイス名>.modelと、計算結果を保持した<デバイス名>.conn.txtをparam.json で指定した”glpk_dir”/ac 配下 (デフォルトはfbd/glpk/ac配下に作成します。-t , -gが省略された場合はparam.jsonの設定が反映されます。
```
usage: MakeAvailableConnections.py [-t <topo_xml>] [-g <glpk_dir>]
```

### MakePathFinderGLPK.py
経路計算の事前準備用に経路計算用モデルファイルとチャンネル、デバイス毎のスケルトンデータファイル を”glpk_dir”/glpk 配下 (デフォルトはfbd/glpk/glpk配下)に作成する。
```
usage: MakePathFinderGLPK.py [-t <topo_xml>] [-g <glpk_dir>] 
[--inmodel_pf <pf_modebase_file>] 
[--inmodel_solvec <solvec_modebase_file>] 
[--outmodel <model_file_key>] 
[--outdata <data_file_key>] [--solvec]

 -t <topo_xml>		         topology xml file
-g <glpk_dir>               　　　  directory to output model_file and 
modeldata_file are placed
--inmodel_pf <pf_modelbase_file>     GLPK model base file
--inmodel_solvec <solvec_modelbase_file>     GLPK model base file for solvec
--outmodel <model_file_key>         key of GLPK model file name to output
--outdata <data_file_key>              key of skeleton data file name to output
--solvec

```
-t ,-g,--inmodel_pf , --inmodel_solvec が省略された場合はparam.jsonの設定が反映されます。
--solvecオプションを指定しない場合は--inmodel_solvecの値は無視されます。
--outdata、--outmodel、--slove が省略または指定された場合に作成されるファイルは以下の通りです。--sloveオプション指定時はpf(パス計算)用モデルファイル/データファイルに加えて、solvec用にデバイス毎のモデルファイル/データを作成します。
経路計算時にデバイス毎に並列で計算を実行できるようにするため、--solvecオプション有の場合はデバイス毎にモデルファイル/データファイルを作成します。一つのデータファイル内に含むコンポネント数(経路計算時に1プロセスで処理をするコンポネント数)はparam.jsonの”num_comps”で指定できます。

| `--solvec` | オプション | 指定有無 | 作成ファイル名 |
|-----------|------------|----------|----------------|
| 無        | `--outdata` | 省略     | `pf_<topo_xml>_<チャンネル名>.data` |
|           |            | 指定     | `pf_<指定値>_<チャンネル名>.data` |
|           | `--outmodel` | 省略     | `pf_<topo_xml>.model` |
|           |            | 指定     | `pf_<指定値>.model` |
| 有        | `--outdata` | 省略     | `pf_<topo_xml>_<チャンネル名>_<チャンネル番号>.data`<br>`solvec_<topo_xml>_<デバイス名>_<no>.data` |
|           |            | 指定     | `pf_<指定値>_<チャンネル名>_<チャンネル番号>.data`<br>`solvec_<指定値>_<デバイス名>.data` |
|           | `--outmodel` | 省略     | `pf_<topo_xml>.model`<br>`solvec_<topo_xml>_<デバイス名>.model` |
|           |            | 指定     | `pf_<指定値>.model`<br>`solvec_<指定値>_<デバイス名>.model` |

### NRMServer.py
NRMのリクエストを受け付けるサーバを起動します。
-t ,-g が省略された場合はparam.jsonの設定が反映されます。
--dbオプションが指定された場合はサーバ起動時にDBから予約情報を読み込み、idを採番してメモリ上に反映し、コンソールに表示します。
```
usage: NRMServer.py [-t <topo_xml>] [-g <glpk_dir>]  [--db]

-t <topo_xml>		         topology xml file
-g <glpk_dir>               　　　  directory to output model_file and 
modeldata_file are placed
-db
```

### NRMClient.py
NRMリクエストをサーバに送信するためのクライアントを起動します。
引数なしで起動した場合は、サブコマンドの入力を受け付けるインタラクティブモードとなります。
引数としてサブコマンドを実行する場合は以下のように”” でサブコマンド部分を囲みます。
```bash
python NRMClient.py "reserve -s P201_2 -d P1201_1 -bi" 
```
サブコマンドの仕様は以下の通りです。
```
usage: pathfind [-bi] -d <dst> [-ero <ero1 ero2 ero3..>] -s <src> 
[-ch <ch1 chX..chY chZ  ...>] [-wdmsa] [-p <num_threads>] 
[-model <model_file_key> [-data <data_file_key>]
-bi                           　　　　 solve bidirectional route
-d <dst>                     　　　destination
-ero <ero1 ero2 ero3 ...>      ERO Port names
-s <src>                                source
-ch <ch1 chX..chY chZ  ...>  use channel names (chX..chY means {chX,
                                chX+1, ..., chY})
-wdmsa                                 use one WDM channel in round robin order 
-p                                           number of concurrent threads
-model <model_file_key>     key of GLPK model file name 
-data <data_file_key>           key of skeleton data file name

usage: reserve [-bi] -d <dst> [-ero <ero1 ero2 ero3..>] -s <src> 
[-ch <ch1 chX..chY chZ  ...>] [-wdmsa] [-p <num_threads>] 
[-model <model_file_key> [-data <data_file_key>]
-bi                           　　　　 solve bidirectional route
-d <dst>                     　　　destination
-ero <ero1 ero2 ero3 ...>      ERO Port names
-s <src>                                source
-ch <ch1 chX..chY chZ  ...>  use channel names (chX..chY means {chX,
                                chX+1, ..., chY})
-wdmsa                                 use one WDM channel in round robin order 
-p                                           number of concurrent threads
-model <model_file_key>     key of GLPK model file name 
-data <data_file_key>           key of skeleton data file name
                              
usage: writeDB

usage: terminate -g <globalid | id> [-db]
-g <globalid | id>                       index of globalid, or real UUID
-db                                       delete from DB file

usage: TERMINATEALL [-db]
-db                                       delete from DB file

usage: query -g <globalid | id> [-q] [-db]
  -g <globalid | id>                        index of globalid, or real UUID
-q                                           do not output the route
-db                                         read from DB file
usage: deltmp [true|false]
usage: dumpglpsol [true|false]

```

 
## ６．ライブラリ仕様 
プログラムをライブラリとして使用する場合のモジュールの仕様について記述します。 
 
- `make_available_connections()`: MakeAvailableConnections.pyのメイン処理。 
- `make_pathfinder_GLPK()`: MakePathFinderGLPK.pyのメイン処理。 
- `NRM_server()`: NRMServer.pyのメイン処理。 
- `NRM_client()`: NRMClient.pyのメイン処理。 

### `make_available_connections()`

- `MakeAvailableConnections.py` のメイン処理です。
- すべての引数は省略可能です。
- `topo_xml`、`glpk_dir` の指定方法や、省略時の動作はコマンド実行時と同じです。

### `make_pathfinder_GLPK()`

- `MakePathfinderGLPK.py` のメイン処理です。
- すべての引数は省略可能です。
- `topo_xml`、`glpk_dir`、`pf_modelbase_file`、`solvec_modelbase_file`、`model_file`、`data_file` の指定方法や、省略時の動作はコマンド実行時と同じです。
- `solvec` 引数には `True` または `False` を指定します。省略された場合は `False` となり、`--solvec` オプションを省略した場合と同じ動作になります。

### `NRM_server()`

- `NRMServer.py` のメイン処理です。
- `db` 引数には `True` または `False` を指定します。省略された場合は `False` となり、`--db` オプションを省略した場合と同じ動作になります。

### `NRM_client()`

- `NRM_client.py` のメイン処理です。
- `command` 引数にはサブコマンドの文字列を指定します。省略された場合は、サブコマンドの入力を受け付けるインタラクティブモードとなります。


## ７．作成されるファイル一覧

一連の処理で作成されるファイルは以下の通りです。

| ファイルパス | 内容 | 作成・追記タイミング |
|--------------|------|----------------------|
| `history.nrm` | `NRMClient.py` のインタラクティブモードでのコマンド履歴を保持します。削除しても経路計算の実行には影響ありません。 | `NRMClient.py` |
| `"glpk_dir"/ac` 配下のファイル | 利用可能な接続情報を書き出した `*.conn.txt`、GLPKモデルファイル `.model`、`channels.data` など。削除すると `MakePathFinderGLPK.py` や `NRMClient.py` による経路計算が実行できなくなります。 | `MakeAvailableConnections.py` |
| `"glpk_dir"/glpk` 配下のファイル | 経路計算に必要なスケルトンファイル。削除すると `NRMClient.py` の経路計算（`pathfind` / `reserve`）が実行できなくなります。 | `MakePathFinderGLPK.py` |
| `db` 配下のファイル | 予約情報を保持するデータベースです。削除すると `NRMServer.py` の `--db` オプション実行時に予約情報が読み込まれなくなりますが、`NRMClient.py:writeDB` により新規予約が書き出されると自動で再作成されます。 | `NRMClient.py` `writeDB` サブコマンド |
| `logs` 配下のファイル | 実行ログです。削除しても経路計算の実行には影響ありません。 | すべてのコマンド |
| `tmp` ディレクトリ / `"glpk_dir"` / 予約UUID 配下の `.data`, `.sol` ファイル | 経路計算に使用する一時データファイルです。`deltmp` を `False` にすると削除されずに残ります。経路計算毎に作成されるため、削除しても問題ありません。 | `NRMClient.py` `reserve`, `pathfind` サブコマンド |



## ８．トポロジファイルの参照箇所一覧
プログラム内ではトポロジーファイル.xmlのデータを読み込み、各項目についてオブジェクトに保持している。いあkにどの項目をどのように参照して使用しているかを記す。
| 要素 | 属性 | 使用目的 |
|------|------|----------|
| `channelTable` | `type` | `"optical"` でない場合はワーニングメッセージを出力し、そのチャンネルテーブルは無視されます。 |
|  | `id` | `ChannelTable` オブジェクトの ID として使用されます。 |
| `channel` | `no` | `Channel` オブジェクトの `no` として使用され、`{channelTableのid}_{no}` でチャンネル名を構築します。 |
| `comp` | `ref` | `Component` オブジェクトの名前として使用されます。 |
|  | `Model` | `.data` ファイルや `.model` ファイルの GLPK 制約式の作成などに使用されます。 |
|  | `GLPK` | `Model` オブジェクトの制約式として使用されます。 |
|  | `Controller` | `"Socket"` 属性と一緒に、中間コントローラを保持するかどうかの判定に使用されます。保持しないものは `solvec` の経路計算の対象となりません。 |
|  | `Socket` | `"Controller"` 属性と一緒に、中間コントローラを保持するかどうかの判定に使用されます。 |
|  | `GLPKchannelTableId` | GLPK 制約式の `"Channels"` の文字列を `"Channels_<GLPKchannelTableId>"` に置換するために使用されます。置換後の内容は `ac` 配下の `.model` ファイルに書き込まれます。 |
|  | `Cost` | `Component` のコストとして、スケルトンデータの `cost` 値や `OUT_OF_SERVICES` 値の作成に使用されます。 |
| `Port` | `number` | `Port` オブジェクトの `no` として使用され、`{Component名}_{no}` で `Port` 名を構築します。 |
|  | `supPortChannel` | `Port` がサポートするチャンネルテーブルを判別するために使用されます。 |
|  | `name` | `Port` オブジェクト名として `"query"` サブコマンドでの出力に使用されます。 |
|  | （IN/OUT） | `"IN"` または `"OUT"` の部分を抽出し、`pathfind` / `query` の出力に使用されます。`io` 要素が取得できなかった場合の `io` タイプの識別や、反対 `Port` の識別にも使用されます。 |
|  | `io` | `Port` が `input` / `output` / `bidi` かを識別するために使用されます。 |
| `net` | `code` | `PortPair` 登録時のエラーメッセージに使用されます。 |
|  | `pair` | `PortPair` オブジェクトのキーとして、`-` より前の値を使用します。 |
| `node` | `ref` | `component` 名として使用されます。 |
|  | `pin` | `{ref}_{pin}` で `Port` 名として使用されます。 |
|  | `cost` | `PortPair` オブジェクトのコストとして、スケルトンデータの `cost` 値や `OUT_OF_SERVICES` 値の作成に使用されます。 |

なお、トポロジファイルの生成については、下記を参照してください。下記は古いKiCADに対応している点にご注意ください。最新Ver.のKiCADへの対応については現在検討中です。
https://unit.aist.go.jp/riaep/cppc/en/TDG_Download/index.html

 
## ９．ライセンス 
このプロジェクトはApache 2.0ライセンスの下で公開されています。詳細はLICENSEファイルを参照してください。 
https://www.apache.org/licenses/LICENSE-2.0.html 
 

## １０．Acknowledgement 
 This work is partly based on results obtained from a project, JPNP16007, commissioned by the New Energy and Industrial Technology Development Organization (NEDO). 
