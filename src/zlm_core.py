from collections import OrderedDict
from enum import IntEnum
import copy
import subprocess
import os
import sys
import json
import re

from zlm_settings import ZBRUSH_PATH, SCRIPT_PATH, ZLM_PATH

ZLM_OP_RENAME = 0
ZLM_OP_MODE = 1
ZLM_OP_CREATE = 2


class ZlmLayerMode(IntEnum):
    off = 0
    record = 1
    active = 2


class ZlmSubTool(object):
    def __init__(self, name, index):
        self.name = name
        self.index = index

    @staticmethod
    def from_line(line):
        line = line.strip()
        start = line.find("\"")
        end = line.find("\"", start+1)
        splitted = line[end+1:].strip()
        name = line[start+1: end]
        if name.endswith('.'):
            name = name[:-1]
        return ZlmSubTool(name, int(splitted))


class ZlmLayer(object):
    def __init__(self, name, intensity, mode, index, master=None):
        super(ZlmLayer, self).__init__()
        self.master = master
        self._mode = 0
        self.name = name
        self.intensity = intensity
        self.mode = mode
        self.index = index

    @property
    def mode(self):
        return int(self._mode)

    @mode.setter
    def mode(self, value):
        if value == ZlmLayerMode.record:
            if self.master:
                if self.master.recording_layer:
                    self.master.recording_layer._mode = ZlmLayerMode.active
                self.master.recording_layer = self
        self._mode = value

    @staticmethod
    def from_line(line, line_index):
        line = line.strip()
        start = line.find("\"")
        end = line.find("\"", start+1)

        splitted = line[end+1:].strip().split(' ')
        return ZlmLayer(line[start+1: end], float(splitted[0]), int(splitted[1]), line_index)

    def zbrush_index(self):
        if self.master:
            return len(self.master.instances_list) - self.index
        return 0

    def __repr__(self):
        return f"ZlmLayer({self.name}, {self.intensity}, {self._mode}, {self.index})"


class ZlmLayers(object):
    cb_layer_created = 0
    cb_layer_removed = 1
    cb_layer_updated = 2
    cb_layer_renamed = 3

    def __init__(self):
        self.instances = {}
        self.instances_list = []

        self.subtool = None

        self.recording_layer = None

        self._cb_on_layer_created = []
        self._cb_on_layer_removed = []
        self._cb_on_layer_updated = []
        self._cb_on_layer_renamed = []

    def add_callback(self, cb_type, callback):
        if cb_type == 0:
            self._cb_on_layer_created.append(callback)
        elif cb_type == 1:
            self._cb_on_layer_removed.append(callback)
        elif cb_type == 2:
            self._cb_on_layer_updated.append(callback)
        elif cb_type == 3:
            self._cb_on_layer_renamed.append(callback)

    def _add_layer(self, layer):
        l = self.instances.get(layer.name, [])
        l.append(layer)
        self.instances[layer.name] = l
        self.instances_list.append(layer)

        layer.master = self

    def set_subtool(self, subtool):
        self.subtool = subtool

    def clear(self):
        self.instances.clear()
        self.instances_list.clear()

    def layers_it(self, exclude_record=True, backward=False):
        layers = self.instances_list
        if backward:
            layers = reversed(layers)

        for l in layers:
            if exclude_record and l.mode == ZlmLayerMode.record:
                continue
            yield l

    def get_first_layer_by_name(self, name):
        try:
            return self.instances[name][0]
        except:
            pass
        return None

    def create_layer(self, name, mode=ZlmLayerMode.off, intensity=1.0):
        layer = ZlmLayer(name, intensity, mode, len(self.instances_list) + 1, self)
        self._add_layer(layer)
        for cb in self._cb_on_layer_created:
            cb(layer)
        return layer

    def remove_layer(self, layer):
        if self.recording_layer == layer:
            self.recording_layer = None

        self.instances[layer.name].remove(layer)

        self.instances_list.remove(layer)

        for l in self.instances_list[layer.index-1:]:
            l.index -= 1

        for cb in self._cb_on_layer_removed:
            cb(layer)
        return layer

    def rename_layer(self, layer, new_name):
        if new_name and new_name != layer.name:
            old_name = layer.name
            self.instances[layer.name].remove(layer)
            new_name = self.validate_layer_name(new_name)
            layer.name = new_name
            l = self.instances.get(new_name, [])
            l.append(layer)
            self.instances[new_name] = l

            for cb in self._cb_on_layer_renamed:
                cb(layer, old_name)
            return True
        return False

    def load_from_file(self, file_path):
        self.clear()
        subTool = None

        with open(file_path, mode='r') as f:
            lines = f.readlines()
            # last line is for subtools
            for x, line in enumerate(lines[:-1]):
                layer = ZlmLayer.from_line(line, x+1)
                self._add_layer(layer)
            subTool = ZlmSubTool.from_line(lines[-1])
            self.set_subtool(subTool)
        for cb in self._cb_on_layer_updated:
            cb()

    def validate_layer_name(self, name):
        name = name.replace(' ', '_')
        if name not in self.instances:
            return name

        # add number at the end
        highest_number = 0
        for layer in self.instances[name]:
            match = re.search('(\d+)$', layer.name)
            if match:
                number = int(match.group(0))
                if number > highest_number:
                    highest_number = number
        highest_number += 1
        # replace number with new number
        match = re.search('(\d+)$', name)
        if match:
            name = name[:match.span()[0]]
        name = f'{name}{highest_number:02d}'
        return self.validate_layer_name(name)

    def remove_name_duplicate(self):
        modified_layers = []
        dup_names = []
        for key, layers in self.instances.items():
            if len(layers) > 1:
                dup_names.append(key)

        for dup_name in dup_names:
            for layer in list(self.instances[dup_name]):
                new_name = self.validate_layer_name(layer.name)
                self.rename_layer(layer, new_name)
                modified_layers.append(layer)
        return modified_layers


main_layers = ZlmLayers()


def get_preset_folders():
    """ Look for preset folder
    1. With the executable
    2. In the user
    """

    out = {
        'app': None,
        'user': None
    }

    if getattr(sys, 'frozen', False):
        root = sys.executable
    else:
        root = __file__

    directory = os.path.join(os.path.dirname(root), 'presets')
    if not os.path.isdir(directory):
        os.makedirs(directory)
    out['app'] = directory

    directory = os.path.expanduser(os.path.join('~', 'zLayerManager', 'presets'))
    if not os.path.isdir(directory):
        os.makedirs(directory)
    out['user'] = directory

    return out


def get_preset_file():
    folders = get_preset_folders()
    out = {}
    for key, value in folders.items():
        if value:
            out[key] = tuple(os.path.join(value, f) for f in os.listdir(value) if '.json' in f)
        else:
            out[key] = ()
    return out


def validate_new_preset_file(preset_name):
    if not preset_name:
        return False

    folders = get_preset_folders()
    user_folder = folders['user']
    full_path = os.path.join(user_folder, preset_name + '.json')
    return not os.path.exists(full_path)


def create_new_preset_file(preset_name):
    folders = get_preset_folders()
    user_folder = folders['user']
    full_path = os.path.join(user_folder, preset_name + '.json')

    f = open(full_path, mode='w')
    f.write('{}')
    f.close()


def remove_preset_file(preset_name):
    folders = get_preset_folders()
    user_folder = folders['user']
    full_path = os.path.join(user_folder, preset_name + '.json')

    try:
        os.remove(full_path)
    except:
        pass


def load_presets():
    preset_files = get_preset_file()
    out = {}
    for key, value in preset_files.items():
        out[key] = {}
        for f in value:
            filename = os.path.basename(f).split('.')[0]
            with open(f, mode='r') as filobj:
                out[key][filename] = json.load(filobj)
    return out


def get_layers_as_preset():
    out = {
        'active': [],
        'record': None
    }

    for layer in main_layers.instances_list:
        if layer.mode == 1:  # or layer.intensity != 1.0:
            out['record'] = {
                'name': layer.name,
                'index': layer.index
            }
        elif layer.mode == 2:
            curLayer = {
                'name': layer.name,
                'index': layer.index,
                'intensity': layer.intensity,
            }
            out['active'].append(curLayer)

    return out


def apply_preset(preset):
    # loop through all layers and apply default value

    for layer in main_layers.instances_list:
        layer.intensity = 1.0
        layer.mode = 0

    for layer in preset['active']:
        layers = main_layers.instances.get(layer['name'], None)
        if layers:
            if len(layers) > 1:
                # check for index in the array of layer with the same name
                for l in layers:
                    if l.index == layer['index']:
                        cl = l
                        break
                else:
                    # Maybe just skip ?
                    # cl = layers[0]
                    continue
            else:
                cl = layers[0]

            cl.mode = 2
            cl.intensity = layer['intensity']

    if preset['record']:
        layers = main_layers.instances.get(preset['record']['name'], None)
        if layers:
            if len(layers) > 1:
                # check for index in the array of layer with the same name
                for l in layers:
                    if l.index == layer['index']:
                        cl = l
                        break
                else:
                    # Maybe just skip ?
                    # cl = layers[0]
                    return
            else:
                cl = layers[0]

            cl.mode = 1


def save_layers_preset(name, data):
    folder = get_preset_folders()
    filepath = os.path.join(folder['user'], name + '.json')

    with open(filepath, mode='w') as f:
        json.dump(data, f, indent=4)


startupinfo = None
if os.name == 'nt':
    startupinfo = subprocess.STARTUPINFO()
    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
