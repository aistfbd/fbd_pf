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

Main processes of NRNServer.py
"""

import socket
import struct
from fbd.util import logutil, param
from fbd.topo import topology
from fbd.pathfinder import GLPK_constant, request_handler, pathfinder_util

log = logutil.getLogger()

BUFSIZE = 4096


def create_socket():
    """
    Create a socket
    """
    # AF_INET: IPv4 TCP socket communication
    # SOCK_STREAM: Socket type for TCP
    server_socket: socket.socket = socket.socket(
        socket.AF_INET, socket.SOCK_STREAM
    )
    server_socket.bind((param.NRM_HOST, param.NRM_PORT))

    server_socket.listen()
    log.info("NRM Server is listening")
    return server_socket


def receive_requests(
    client_socket: socket.socket, handler: request_handler.RequestHandler
):
    """
    Receive the client's request, execute the operation, and return the result
    """
    while True:
        try:
            # receive message from client
            data = client_socket.recv(BUFSIZE).decode()
            if len(data) == 0:
                return
            log.info("Received message: {}".format(data))
            reply: str = handler.handle_req(data)
            reply_data: bytes = reply.encode()
            # Send the size of reply_data first
            client_socket.sendall(struct.pack(">I", len(reply_data)))
            # print(f"send reply size={len(reply_data)}")
            client_socket.sendall(reply_data)
        except (ConnectionAbortedError, ConnectionResetError, BrokenPipeError):
            print("close client")
            return


def _check_args(
    topo_xml: str = param.TOPO_XML,
    glpk_dir: str = param.GLPK_DIR,
    db: bool = False,
):
    """
    Check the types of the arguments
    """
    pathfinder_util.check_arg_str(topo_xml)
    pathfinder_util.check_arg_str(glpk_dir)
    pathfinder_util.check_arg_bool(db)


def NRM_server(
    topo_xml: str = param.TOPO_XML,
    glpk_dir: str = param.GLPK_DIR,
    db: bool = False,
):
    """
    Main processing of NRMServer.py
    Launch the server to accept NRM requests
    """
    _check_args(topo_xml, glpk_dir, db)
    server_socket: socket.socket = create_socket()

    topo: topology.Topology = topology.Topology(
        topology.topology_filename(topo_xml),
        GLPK_constant.get_available_connectionsdir(glpk_dir),
        True,
    )

    handler: request_handler.RequestHandler = request_handler.RequestHandler(
        topo, topo_xml, glpk_dir, db
    )
    while True:
        try:
            print("Waiting for connection...")
            # Receive a connect request
            (client_socket, address) = server_socket.accept()
            print("Connection from cli{}".format(address))

            receive_requests(client_socket, handler)
        except (KeyboardInterrupt, EOFError):
            print("close server")
            break
    handler.close_DB()
    server_socket.close()


if __name__ == "__main__":
    NRM_server(db=True)
