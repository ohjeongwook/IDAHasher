import os
import thread  
import functools
import threading
import traceback
import time
import json

import idaapi
import idc

import rpyc
from rpyc.utils.server import ThreadedServer
from viewer import *

def execute_sync(function, sync_type):
    """
    Synchronize with the disassembler for safe database access.

    Modified from https://github.com/vrtadmin/FIRST-plugin-ida
    """

    @functools.wraps(function)
    def wrapper(*args, **kwargs):
        output = [None]
        def thunk():
            output[0] = function(*args, **kwargs)
            return 1

        if threading.current_thread().name == 'MainThread':
            thunk()
        else:
            idaapi.execute_sync(thunk, sync_type)
        return output[0]
    return wrapper

class ExecuteSyncDefs:
    @staticmethod
    def execute_read(function):
        return execute_sync(function, idaapi.MFF_READ)

    @staticmethod
    def execute_write(function):
        return execute_sync(function, idaapi.MFF_WRITE)

    @staticmethod
    def execute_ui(function):
        return execute_sync(function, idaapi.MFF_FAST)

class IDA:
    @ExecuteSyncDefs.execute_read
    def get_current_address(self):
        return idaapi.get_screen_ea()

    @ExecuteSyncDefs.execute_read
    def get_database_directory():
        return idautils.GetIdbDir()

    @ExecuteSyncDefs.execute_read
    def get_function_addresses(self):
        return list(idautils.Functions())

    @ExecuteSyncDefs.execute_read
    def get_function_name_at(self, address):
        return idaapi.get_short_name(address)

    @ExecuteSyncDefs.execute_read
    def get_function_raw_name_at(self, function_address):
        return idaapi.get_name(function_address)

    @ExecuteSyncDefs.execute_read
    def get_imagebase(self):
        return idaapi.get_imagebase()

    @ExecuteSyncDefs.execute_read
    def get_item_size(self, address):
        return ida_bytes.get_item_size(address)

    @ExecuteSyncDefs.execute_read
    def get_root_filename(self):
        return idaapi.get_root_filename()

    @ExecuteSyncDefs.execute_ui
    def jumpto(self, address):
        return idaapi.jumpto(idaapi.get_imagebase() + address)

    @ExecuteSyncDefs.execute_ui
    def set_item_color(self, address, color):
        return idaapi.set_item_color(address, color)

    @ExecuteSyncDefs.execute_ui
    def color_lines(self, start, end, color):
        address = idaapi.get_imagebase() + start
        while address < idaapi.get_imagebase() + end:
            idaapi.set_item_color(address, color)
            address += ida_bytes.get_item_size(address)

    @ExecuteSyncDefs.execute_ui
    def color_node(self, addresses, bg_color, frame_color):
        if len(addresses) <= 0:
            return

        func = idaapi.get_func(idaapi.get_imagebase() + addresses[0])
        flowchart_ = idaapi.FlowChart(func)

        address_map = {}
        for address in addresses:
            address_map[idaapi.get_imagebase() + address] = 1

        for code_block in flowchart_:
            if not code_block.start_ea in address_map:
                continue
            node_info = idaapi.node_info_t()
            node_info.bg_color = bg_color
            node_info.frame_color = frame_color
            idaapi.set_node_info(func.start_ea, code_block.id, node_info, idaapi.NIF_BG_COLOR | idaapi.NIF_FRAME_COLOR)

    @ExecuteSyncDefs.execute_read
    def navigate_to_function(self, function_address, address):
        return self.navigate(address)

    @ExecuteSyncDefs.execute_read
    def set_function_name_at(self, function_address, new_name):
        idaapi.set_name(function_address, new_name, idaapi.SN_NOWARN)

    @ExecuteSyncDefs.execute_read
    def get_md5(self):
        return idc.GetInputMD5().lower()

    @ExecuteSyncDefs.execute_read
    def export(self, filename):
        print('export %s' % filename)
        try:
            binkit = idaapi.load_plugin('BinKit')
            if binkit:
                idc_command = ("SaveBinKitAnalysis(\"%s\");" % (filename)).replace("\\", "\\\\")
                print(idc_command)
                idc.eval_idc(str(idc_command))
        except:
            traceback.print_exc()
            pass

    @ExecuteSyncDefs.execute_read
    def show_diff(self, filename):
        viewer = Viewer(filename)
        viewer.show_functions_match_viewer()
        viewer.set_basic_blocks_color(0xCCFFFF, 0xCC00CC)
        idaapi.set_dock_pos("Function Matches", "Functions window", idaapi.DP_TAB)      

def export_thread(filename):
    ida = IDA()
    ida.export(filename)

def show_diff_thread(filename):
    ida = IDA()
    ida.show_diff(filename)

class BinKitService(rpyc.Service):
    def on_connect(self, conn):
        self.ida = IDA()

    def get_pid(self):
        return os.getpid()

    def jumpto(self, address):
        self.ida.jumpto(address)
        
    def set_item_color(self, address, color):
        self.ida.set_item_color(address, color)

    def get_md5(self):
        return self.ida.get_md5()

    def get_root_filename(self):
        return self.ida.get_root_filename()

    def export(self, filename):
        thread.start_new_thread(export_thread, (filename,))

    def show_diff(self, filename):
        thread.start_new_thread(show_diff_thread, (filename,))

    def run_commands(self, command_list):
        for command in command_list:
            if command['name'] == 'jumpto':
                self.jumpto(command['address'])

            elif command['name'] == 'color_lines':
                self.ida.color_lines(command['start'], command['end'], command['color'])

            elif command['name'] == 'color_node':
                if 'frame_color' in command:
                    frame_color = command['frame_color']
                else:
                    frame_color = 0x000000
                self.ida.color_node(command['addresses'], command['bg_color'], frame_color)

def start_binkit_server(connection_filename):
    port = 18861
    while 1:
        try:
            t = ThreadedServer(BinKitService(), port = port, protocol_config = {
                'allow_public_attrs': True,
            })
            print('Listening on %d\n' % port)
            md5 = idc.GetInputMD5().lower()
            try:
                with open(connection_filename, "w") as fd:
                    json.dump({'port': port, 'md5': md5, 'root_fileanem': idaapi.get_root_filename(), 'input_filename': idaapi.get_input_file_path()}, fd)
            except:
                traceback.print_exc()

            t.start()
            break
        except:
            port += 1
            traceback.print_exc()

if __name__ == '__main__':
    def run():  
        ida = IDA()
        while 1:
            print('get_current_address: %x' % ida.get_current_address())
            time.sleep(1)

    print(threading.current_thread().name)
    thread.start_new_thread(run, ())  
