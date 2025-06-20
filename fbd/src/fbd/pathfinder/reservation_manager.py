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

Module that manages route reservation information.
"""

from __future__ import annotations
import os
import uuid
import json
import sqlite3
from fbd.util import logutil, param
from fbd.topo import topology, channel_table, port
from fbd.pathfinder import GLPK_util, GLPK_route


log = logutil.getLogger()


class GlobalIdManager:
    """
    Class that manages reservation IDs and global IDs.

    Attributes:
        self.id2global: dictionary {id: globalid}
        self.global2id: dictionary {globalid: id}
    """

    UNKNOWN_ID = -1
    next_ID = 1

    def __init__(
        self,
    ):
        self.id2global: dict[str:str] = {}
        self.global2id: dict[str:str] = {}

    def add_globalid(self, globalid: str):
        """
        Assign an ID and link it with a global ID.
        """
        id: str = str(GlobalIdManager.next_ID)
        self.id2global[id] = globalid
        self.global2id[globalid] = id
        GlobalIdManager.next_ID += 1
        return id

    def get_globalid_by_id(self, id: str):
        """
        Get the globalid from the id specified by the -g option.  
        If an id is specified, return the globalid corresponding to that id.  
        If a globalid is specified, return it as is.  
        If the globalid cannot be found, return None.
        """
        globalid: str | None = self.id2global.get(id)
        if globalid is not None:
            """
            Since the globalid was obtained from the id, return it.
            """
            return globalid
        else:
            """
            Since the globalid could not be obtained from the id,  
            treat it as a globalid and search if it exists as a key in self.global2id.
            """
            globalid = id
            if globalid in self.global2id.keys():
                return globalid
            else:
                None

    def del_globalid(self, globalid: str):
        """
        Delete the id corresponding to the globalid.
        """
        id: str = self.global2id.pop(globalid)
        del self.id2global[id]

    def clear(self):
        """
        Delete all ids and globalids.
        """
        self.id2global.clear()
        self.global2id.clear()
        GlobalIdManager.next_ID = 1


class Reservation:
    """
    Class that holds reservation information.

    Attributes:
        self.used_conn: used_conn
    """

    DEFAULT_NRM_ID = 1
    DEFAULT_USER_NAME = "demo"

    def __init__(
        self,
        globalid: str,
        src: GLPK_route.PortChannel,
        dst: GLPK_route.PortChannel,
        glpk_route: GLPK_route.GLPKRoute,
    ):
        self.globalid: str = globalid
        self.src: GLPK_route.PortChannel = src
        self.dst: GLPK_route.PortChannel = dst
        self.glpk_route: GLPK_route.GLPKRoute = glpk_route
        self.written_db: bool = False

    def _dump_port_channel(self, pc: GLPK_route.PortChannel, buf: list[str]):
        """
        Append PortChannel information into buf
        """
        buf.append(f"{' name':33}{pc.port.name}")
        buf.append(f"{' name':33}{pc.port.full_name}")
        buf.append(f"{' chNo':33}{pc.ch.full_no}")

    def dump(self, buf: list[str]):
        """
        Append Reservation information into buf
        TextDump:toString() L155
        """
        buf.append(f"{'globalId':33}{self.globalid}")
        buf.append("src")
        self._dump_port_channel(self.src, buf)
        buf.append("dst")
        self._dump_port_channel(self.dst, buf)


class ReservationDBManager:
    """
    Class that manages the database of Reservation objects.

    Attributes:
        self.topo: Topology object
        self.connection: Object for database connection information
        self.cursor: Cursor object to operate the database
    """

    TABLE_NAME_RSV = "reservation"

    def __init__(
        self,
        topo: topology.Topology,
        topo_xml: str,
    ):
        self.topo: topology.Topology = topo
        db_dir = param.DB_DIR
        os.makedirs(db_dir, exist_ok=True)
        db_file = os.path.join(db_dir, f"{topo_xml}.db")

        self.connection: sqlite3.Connection = sqlite3.connect(db_file)

        # Create a cursor object to operate sqLite
        self.cursor: sqlite3.Cursor = self.connection.cursor()
        # Create table. Set globalid to be unique (no duplicates allowed)
        self.cursor.execute(
            f"CREATE TABLE IF NOT EXISTS {self.TABLE_NAME_RSV}(globalid STRING UNIQUE, reserve STRING)"
        )
        self.connection.commit()

    def add_record(self, rsv: Reservation):
        """
        Write the Reservation information to the DB and return True.  
        If it has already been written (written_db=True), do not write again and return False.
        """
        if rsv.written_db:
            return False
        try:
            reserve_txt = self._dump_json(rsv)
            self.cursor.execute(
                f"INSERT INTO {self.TABLE_NAME_RSV}(globalid, reserve) values('{rsv.globalid}','{reserve_txt}')"
            )
            self.connection.commit()
        except Exception as e:
            msg = f"failed to write DB globalid={rsv.globalid} : {e}"
            log.error(msg)
            raise Exception(msg) from e
        rsv.written_db = True
        log.info(f"add DB globalId={rsv.globalid}")
        return True

    def del_record(self, globalid: str):
        """
        Delete Reservation information from the DB.  
        Return False if the specified globalid does not exist.  
        Return True when deletion is complete.
        """
        try:
            self.cursor.execute(
                f"SELECT globalid FROM {self.TABLE_NAME_RSV} WHERE globalid='{globalid}'"
            )
            if self.cursor.fetchone() is None:
                return False
            self.cursor.execute(
                f"DELETE FROM {self.TABLE_NAME_RSV} WHERE globalid='{globalid}'"
            )
            self.connection.commit()
        except Exception as e:
            msg = f"failed to delete DB globalid={globalid} : {e}"
            log.error(msg)
            raise Exception(msg) from e
        return True

    def del_all_record(self):
        """
        Delete all Reservation information from the database.
        """
        try:
            self.cursor.execute(f"DELETE FROM {self.TABLE_NAME_RSV}")
            self.connection.commit()
        except Exception as e:
            msg = f"failed to delete all record from DB : {e}"
            log.error(msg)
            raise Exception(msg) from e
        return True

    def get_all_record(self):
        """
        Read all data from the DB and return it as a dictionary {globalid: Reservation, ...}.
        """
        self.cursor.execute(f"SELECT * FROM {self.TABLE_NAME_RSV}")
        record_list: list[tuple[str]] = self.cursor.fetchall()
        # tuple: record = (globalid, reserve)
        rsv_dict: dict[str:Reservation] = {}
        for record in record_list:
            try:
                rsv: Reservation = self._load_json(record[1])
                rsv_dict[record[0]] = rsv
            except Exception as e:
                msg = f"failed to get DB globalid={record[0]} : {e}"
                log.error(msg)
                raise Exception(msg) from e
        return rsv_dict

    def get_record(self, globalid: str):
        """
        Read Reservation information from the DB.  
        Return None if not found.
        """
        try:
            self.cursor.execute(
                f"SELECT * FROM {self.TABLE_NAME_RSV} WHERE globalid='{globalid}'"
            )
            if (record := self.cursor.fetchone()) is None:
                return None


            assert (
                len(record) == 2
            ), f"ASSERT! invalid DB record {[val for val in record]}"

            rsv: Reservation = self._load_json(record[1])
        except Exception as e:
            msg = f"failed to get DB globalid={globalid} : {e}"
            log.error(msg)
            raise Exception(msg) from e
        return rsv

    def _dump_json(self, rsv: Reservation):
        """
        Convert Reservation to JSON formatted text.
        """
        r_entry_list: list[dict[str : str | bool | int]] = []
        for entry in rsv.glpk_route.entry_list:
            r_entry_dic = {
                "src": entry.src.make_key(),
                "dst": entry.dst.make_key(),
                "x": entry.x,
                "c": entry.c,
                "is_go": entry.is_go,
            }
            r_entry_list.append(r_entry_dic)

        json_reserve = {
            "globalid": rsv.globalid,
            "src": rsv.src.make_key(),
            "dst": rsv.dst.make_key(),
            "route": r_entry_list,
        }
        return json.dumps(json_reserve)

    def _make_portchannel(self, key: str):
        """
        Restore a PortChannel object from a key in the format
         "{port.full_name}@{ch.full_no}".
        """
        names: list[str] = key.split("@")
        if len(names) != 2:
            msg = f"invalid PortChannel data :{key}"
            log.error(msg)
            raise RuntimeError(msg)
        p: port.Port | None = self.topo.get_port_by_name(names[0])
        ch: channel_table.Channel | None = self.topo.get_channel_by_fullno(
            names[1]
        )
        if (p is None) or (ch is None):
            msg = f"invalid PortChannel data :{key}"
            log.error(msg)
            raise RuntimeError(msg)
        return GLPK_route.PortChannel(p, ch)

    def _make_glpk_route(
        self, r_entry_json_list: list[dict[str : str | bool | int]]
    ):
        """
        Restore a GLPKRoute object from a GLPKRoute object in JSON format.
        """
        entry_list: list[GLPK_route.GLPKRouteEntry] = []
        for entry in r_entry_json_list:
            route_entry: GLPK_route.GLPKRouteEntry = GLPK_route.GLPKRouteEntry(
                self._make_portchannel(entry["src"]),
                self._make_portchannel(entry["dst"]),
                entry["x"],
                entry["c"],
                entry["is_go"],
            )
            assert (
                route_entry.c is True
            ), f"ASSERT! c is False: {route_entry.dump()}"
            entry_list.append(route_entry)

        return GLPK_route.GLPKRoute(entry_list)

    def _load_json(self, json_str: str):
        """
        Load JSON data and restore the Reservation object.
        """
        try:
            json_reserve = json.loads(json_str)

            rsv = Reservation(
                json_reserve["globalid"],
                self._make_portchannel(json_reserve["src"]),
                self._make_portchannel(json_reserve["dst"]),
                self._make_glpk_route(json_reserve["route"]),
            )
            rsv.written_db = True
            return rsv
        except Exception as e:
            log.error(e)
            raise Exception(e) from e

    def close(self):
        self.cursor.close()
        self.connection.close()


class ReservationManager:
    """
    Class that manages all Reservations.

    Attributes:
        self.id_mgr: GlobalIdManager object that manages reservation IDs and global IDs
        self.rsv_DB_mgr: ReservationDBManager object that manages reservation information in the database
        self.reserve_map: Dictionary {globalid : Reservation} holding reservation information in memory

    """

    def __init__(
        self,
        topo: topology.Topology,
        topo_xml: str,
        db: bool,
    ):
        self.id_mgr: GlobalIdManager = GlobalIdManager()
        self.rsv_DB_mgr: ReservationDBManager = ReservationDBManager(
            topo, topo_xml
        )
        if db:
            """
            Load information from the DB and store it in reserve_map.
            """
            self.reserve_map: dict[str:Reservation] = (
                self.rsv_DB_mgr.get_all_record()
            )
            for globalid in self.reserve_map.keys():
                id = self.id_mgr.add_globalid(globalid)
                print(f"id={id}, globalId={globalid}")
        else:
            self.reserve_map: dict[str:Reservation] = {}

    @staticmethod
    def get_new_reservationID():
        """
        Issue a new globalid.
        """
        return f"urn:uuid:{uuid.uuid4()}"

    def find_used_path(self):
        """
        Return a GLPKRoute that holds a list of GLPKRouteEntry for useX.
        """
        entry_list: GLPK_route.GLPKRouteEntry = [
            entry
            for r in self.reserve_map.values()
            for entry in r.glpk_route.entry_list
            if entry.x
        ]
        #        log.info("ReservationManager:find_used_path =")
        #        for entry in entry_list:
        #            log.info(entry.dump())
        return GLPK_route.GLPKRoute(entry_list)

    def make_use_connection_list(self):
        """
        Returns a GLPKRoute that holds a list of GLPKRouteEntry objects for useC.
        Since entry.c is True for all entries, no check is performed.
        Entries with isC set to False are filtered out in make_route_entry_list() and make_conn_entry_list().
        """
        entry_list: GLPK_route.GLPKRouteEntry = [
            entry
            for r in self.reserve_map.values()
            for entry in r.glpk_route.entry_list
        ]
        #        log.info("ReservationManager:make_use_connection_list =")
        #        for entry in entry_list:
        #            log.info(entry.dump())
        return GLPK_route.GLPKRoute(entry_list)

    def add(self, rsv: Reservation):
        """       
        Stores the Reservation in memory
        """
        self.reserve_map[rsv.globalid] = rsv

    def delete(self, globalid: str):
        """
        Delete the Reservation in memory.  
        Return True if deletion is successful, or False if the entry is not found.
        """
        rsv: Reservation | None = self.reserve_map.pop(globalid, None)
        if rsv is not None:
            self.id_mgr.del_globalid(globalid)
            return True
        return False

    def delete_all(self):
        """
        Delete all the Reservation on memory
        """
        self.reserve_map.clear()
        self.id_mgr.clear()

    def delete_DB(self, globalid: str):
        """
        Delete the Reservation from the database.  
        Return True if deletion is successful, or False if the entry is not found.
        """
        return self.rsv_DB_mgr.del_record(globalid)

    def delete_DB_all(self):
        """
        Delete all Reservations from DB.
        """
        return self.rsv_DB_mgr.del_all_record()

    def get(self, globalid: str, db: bool):
        """
        Retrieve Reservation information.  
        If db=True, also retrieve information that exists only in the database and not in memory.
        """
        rsv: Reservation = self.reserve_map.get(globalid)
        if rsv is not None:
            return rsv
        if db:
            return self.rsv_DB_mgr.get_record(globalid)

    def get_all(self, db: bool):
        """
        Retrieve all Reservation information.  
        If db=True, also include information that exists only in the database and not in memory.
        """
        rsv_list: list[Reservation] = self.reserve_map.values()
        if db is False:
            return rsv_list

        # Retrieve reservation information from the database
        db_list = list(self.rsv_DB_mgr.get_all_record().values())

        # Retrieve reservation information in memory that has not been written to the DB
        only_mem_list: list[Reservation] = [
            rsv for rsv in rsv_list if (rsv.written_db is False)
        ]

        return db_list + only_mem_list

    def write_DB(self):
        """
        Write all Reservations in memory to the database,  
        and return a message with the number of entries successfully written.  
        If there are entries that failed during the write process, return an error message  
        and only write the entries that succeeded.
        
        Entries that have already been written have written_db=True and will not be written again.  
        Since all entries are searched regardless of write status,  
        if performance becomes a concern, consider storing already-written entries in a separate dictionary.
        """
        msg: list[str] = []
        written_num: int = 0
        for rsv in self.reserve_map.values():
            try:
                written = self.rsv_DB_mgr.add_record(rsv)
            except Exception as e:
                msg.append(f"{e}")
            else:
                if written:
                    written_num += 1

        msg.append(f"{written_num} entries written to the DB")
        return GLPK_util.RET.join(msg)
