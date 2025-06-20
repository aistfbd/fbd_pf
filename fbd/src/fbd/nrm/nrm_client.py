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

Main Processes of NRNClient.py
"""

import readline
import os
import socket
import struct
from fbd.util import logutil, param
from fbd.pathfinder import pathfinder_util

log = logutil.getLogger()


def receive_request(client_socket):
    """
    Output the reply message received from the server
    """
    stream = client_socket.makefile("rb")
    assert struct.calcsize(">I") == 4
    bytes_data: bytes = stream.read(4)
    if len(bytes_data) != 4:
        raise ConnectionAbortedError(
            "The server returned an empty response and is probably down"
        )
    reply_len: int = struct.unpack(">I", bytes_data)[0]
    reply_data = stream.read(reply_len)
    print(reply_data.decode())


def create_socket():
    """
    Start socket communication with the server
    """
    client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    client_socket.connect((param.NRM_HOST, param.NRM_PORT))
    log.info("NRM Client Connected to server")
    return client_socket


def NRM_client(command: str | None = None):
    """
    Main processing of NRMClient.py
    If a command is specified, send the command to the server.
    If no command is specified, enter interactive mode and send the entered command to the server.
    """
    if command is not None:
        pathfinder_util.check_arg_str(command)

    client_socket = create_socket()

    if command is not None:
        if len(command) > 0:
            client_socket.send(command.encode())
            receive_request(client_socket)
        client_socket.shutdown(socket.SHUT_RDWR)
        client_socket.close()
        print("close")
        return

    if os.path.exists("history.nrm"):
        readline.read_history_file("history.nrm")
    while True:
        try:
            line = input("> ")
            if len(line) > 0:
                client_socket.send(line.encode())
                readline.write_history_file("history.nrm")
                receive_request(client_socket)
        except (KeyboardInterrupt, EOFError):
            break
        except Exception as e:
            raise Exception(e) from e
    client_socket.shutdown(socket.SHUT_RDWR)
    client_socket.close()
    return


if __name__ == "__main__":
    # NRM_client("pathfind -s P1201_2 -d P204_1 -m 20 -o 1    -wdmfull")
    # NRM_client("")
    NRM_client()
