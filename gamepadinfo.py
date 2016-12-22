#!/usr/bin/python3

import os
import datetime
import queue
import struct
import glob
import os
import ctypes
import fcntl
import traceback
import array
import sys
import asyncio

import urwid
import pyudev
import evdev
#import pygame
import sdl2


GAMEPAD_BUTTONS = (evdev.ecodes.BTN_A,
                   evdev.ecodes.BTN_B,
                   evdev.ecodes.BTN_X,
                   evdev.ecodes.BTN_Y,
                   evdev.ecodes.BTN_Z,
                   evdev.ecodes.BTN_BACK,
                   evdev.ecodes.BTN_SELECT,
                   evdev.ecodes.BTN_START,
                   evdev.ecodes.BTN_DPAD_DOWN,
                   evdev.ecodes.BTN_DPAD_LEFT,
                   evdev.ecodes.BTN_DPAD_RIGHT,
                   evdev.ecodes.BTN_DPAD_UP,
                   evdev.ecodes.BTN_GAMEPAD,
                   evdev.ecodes.BTN_JOYSTICK,
                   evdev.ecodes.BTN_NORTH,
                   evdev.ecodes.BTN_SOUTH,
                   evdev.ecodes.BTN_EAST,
                   evdev.ecodes.BTN_WEST,
                   evdev.ecodes.BTN_THUMB,
                   evdev.ecodes.BTN_THUMB2,
                   evdev.ecodes.BTN_THUMBL,
                   evdev.ecodes.BTN_THUMBR)

BUTTON_NAMES = {v: k[4:].lower() for k, v in evdev.ecodes.ecodes.items()}

input_devices = {}


def scan_evdev_gamepads():
    # remove old evdev devices
    global input_devices
    input_devices = {fn: input_devices[fn] for fn in input_devices if not fn.startswith('/dev/input/event')}

    devs = []
    for fn in evdev.list_devices():
        try:
            d = evdev.InputDevice(fn)
        except:
            # TODO trace here what happened
            continue
        same = False
        for dd in devs:
            if dd.fn == d.fn:
                same = True
        if same:
            continue
        caps = d.capabilities()
        if evdev.ecodes.EV_ABS in caps and evdev.ecodes.EV_KEY in caps:
            keys = caps[evdev.ecodes.EV_KEY]
            if any(k in keys for k in GAMEPAD_BUTTONS):
                devs.append(d)
                fn = d.fn
                #print 'EVDEV', d.name, fn
                if fn not in input_devices:
                    input_devices[fn] = {}
                input_devices[fn]['evdev'] = d

def present_evdev_gamepad(d):
    text = [('emph', "EVDEV:",)]
    caps = d.capabilities()
    text.append('   name: %s' % d.name)
    text.append('   file: %s' % d.fn)
    text.append('   phys: %s' % d.phys)
    if evdev.ecodes.EV_ABS in caps:
        text.append('   abs')
    if evdev.ecodes.EV_KEY in caps:
        keys_text = '   buttons: '
        keys = caps[evdev.ecodes.EV_KEY]
        for k in GAMEPAD_BUTTONS:
            if k in keys:
                keys_text += BUTTON_NAMES[k] + ' '
        text.append(keys_text)
    text.append('   %s' % str(d.info))
    # TODO: add SDL2 id
    return text


def scan_jsio_gamepads():
    # remove old js devices
    global input_devices
    input_devices = {fn: input_devices[fn] for fn in input_devices if not fn.startswith('/dev/input/js')}

    syspaths = glob.glob("/dev/input/js*")

    #ioctls
    JSIOCGVERSION = 0x80046a01
    JSIOCGAXES = 0x80016a11
    JSIOCGBUTTONS = 0x80016a12
    JSIOCGNAME = 0x81006a13

    for fn in syspaths:
        #print path
        data = dict(path=fn)
        try:
            with open(fn, "r") as jsfile:
                fcntl.fcntl(jsfile.fileno(), fcntl.F_SETFL, os.O_NONBLOCK)

                val = ctypes.c_int()

                if fcntl.ioctl(jsfile.fileno(), JSIOCGAXES, val) != 0:
                    print("Failed to read number of axes")
                else:
                    data['axes'] = val.value
                    #print 'axes', data['axes']

                if fcntl.ioctl(jsfile.fileno(), JSIOCGBUTTONS, val) != 0:
                    print("Failed to read number of axes")
                else:
                    data['buttons'] = val.value
                    #print 'buttons', data['buttons']

                if fcntl.ioctl(jsfile.fileno(), JSIOCGVERSION, val) != 0:
                    print("Failed to read version")
                else:
                    data['version'] = '0x%x' % val.value
                    #print 'version', data['version']

                buf = array.array('b', [0] * 64)
                fcntl.ioctl(jsfile.fileno(), JSIOCGNAME + (0x10000 * len(buf)), buf)
                data['name'] = buf.tostring() # .replace('\0', '')
                #print 'name', data['name']

            if fn not in input_devices:
                input_devices[fn] = {}
            input_devices[fn]['jsio'] = data
        except PermissionError:
            pass  # TODO: show errors on some status bar or logs panel
        except:
            print(traceback.format_exc())
            #pass

def present_jsio_gamepad(data):
    text = [('emph', "JSIO:",)]
    for k, v in data.items():
        text.append('   %s: %s' % (k.lower(), v))
    return text


def scan_pygame_gamepads():
    pygame.init()
    pygame.joystick.init()
    for i in range(pygame.joystick.get_count()):
        j = pygame.joystick.Joystick(i)
        j.init()
        name = j.get_name().strip()

        for fn, d in input_devices.items():
            if 'jsio' not in d:
                continue
            n = d['jsio']['name'].strip()
            if n.startswith(name):
                d['pygame'] = j

def present_pygame_gamepad(data):
    text = [('emph', "PyGame:",)]
    text.append('   name: %s' % data.get_name())
    text.append('   id: %s' % data.get_id())
    text.append('   numaxes: %s' % data.get_numaxes())
    text.append('   numballs: %s' % data.get_numballs())
    text.append('   numbuttons: %s' % data.get_numbuttons())
    #print '\tnumhats: %s' % data.get_numhats()
    return text


def scan_sdl2_gamepads():
    sdl2.SDL_Init(sdl2.SDL_INIT_JOYSTICK | sdl2.SDL_INIT_GAMECONTROLLER)
    num = sdl2.joystick.SDL_NumJoysticks()
    #print num
    for i in range(num):
        j = sdl2.joystick.SDL_JoystickOpen(i)
        name = str(sdl2.SDL_JoystickName(j).strip())
        for fn, d in input_devices.items():
            if 'evdev' not in d:
                continue
            n = d['evdev'].name
            if n.startswith(name):
                d['sdl2'] = j

        #guid = sdl2.joystick.SDL_JoystickGetGUID(js)
        #my_guid = SDL_JoystickGetGUIDString(guid)

def SDL_JoystickGetGUIDString(guid):
    s = ''
    for g in guid.data:
        s += "{:x}".format(g >> 4)
        s += "{:x}".format(g & 0x0F)
    return s

def present_sdl2_gamepad(j):
    text = [('emph', "SDL2:",)]
    text.append('   guid: %s' % SDL_JoystickGetGUIDString(sdl2.joystick.SDL_JoystickGetGUID(j)))
    text.append('   id: %s' % sdl2.joystick.SDL_JoystickInstanceID(j))
    text.append('   NumAxes: %s' % sdl2.joystick.SDL_JoystickNumAxes(j))
    text.append('   NumBalls: %s' % sdl2.joystick.SDL_JoystickNumBalls(j))
    text.append('   NumButtons: %s' % sdl2.joystick.SDL_JoystickNumButtons(j))
    text.append('   NumHats: %s' % sdl2.joystick.SDL_JoystickNumHats(j))
    return text




class ExampleTreeWidget(urwid.TreeWidget):
    """ Display widget for leaf nodes """
    def get_display_text(self):
        return self.get_node().get_value()['name']


class ExampleNode(urwid.TreeNode):
    """ Data storage object for leaf nodes """
    def load_widget(self):
        return ExampleTreeWidget(self)


class ExampleParentNode(urwid.ParentNode):
    """ Data storage object for interior/parent nodes """
    def load_widget(self):
        return ExampleTreeWidget(self)

    def load_child_keys(self):
        data = self.get_value()
        return list(range(len(data['children'])))

    def load_child_node(self, key):
        """Return either an ExampleNode or ExampleParentNode"""
        open('a.log', 'a').write('node\n')
        childdata = self.get_value()['children'][key]
        childdepth = self.get_depth() + 1
        if 'children' in childdata:
            childclass = ExampleParentNode
        else:
            childclass = ExampleNode
        return childclass(childdata, parent=self, key=key, depth=childdepth)

class MyTree(urwid.TreeListBox):
    def __init__(self, *args, **kwargs):
        self.node_visited_cb = kwargs.pop('node_visited_cb')
        super(MyTree, self).__init__(*args, **kwargs)

    def change_focus(self, *args, **kwargs):
        super(MyTree, self).change_focus(*args, **kwargs)
        _, node = self.get_focus()
        data = node.get_value()
        #print data
        self.node_visited_cb(data['dev'])


class DeviceBox(urwid.LineBox):
    def __init__(self):
        self.lines = urwid.SimpleFocusListWalker([])
        self.lines.append(urwid.Text(('dim', '<select device>')))
        self.lines_box = urwid.ListBox(self.lines)
        super(DeviceBox, self).__init__(self.lines_box, '-')
        self.device = None

    def show_device(self, device):
        self.device = device
        text = []
        if 'DEVNAME' in device and device['DEVNAME'] in input_devices:
            data = input_devices[device['DEVNAME']]
            if 'sdl2' in data:
                text += present_sdl2_gamepad(data['sdl2'])
            if 'evdev' in data:
                text += present_evdev_gamepad(data['evdev'])
            if 'pygame' in data:
                text += present_pygame_gamepad(data['pygame'])
            if 'jsio' in data:
                text += present_jsio_gamepad(data['jsio'])

        text.append(('emph', "UDEV:"))
        for k in list(device.keys()):
            text.append("   %s: %s" % (k, device[k]))

        self.lines[:] = [urwid.Text(t) for t in text]

        self.set_title(device.sys_path)

    def make_focus(self):
        self.set_title(device.sys_path)


class Udev(object):
    def __init__(self, ui_queue):
        self.ui_queue = ui_queue
        self.ctx = pyudev.Context()

    def send_event_to_ui_thread(self, action, device):
        self.ui_queue.put((action, device))
        os.write(self.ui_wakeup_fd, b'a')

    def _find_parents(self, dev):
        if dev.parent is None:
            return [dev]
        else:
            return [dev] + self._find_parents(dev.parent)

    def get_devs(self):
        devs = {}
        roots = set()
        in_joystick_chain = []

        for device in self.ctx.list_devices():
            devs[device.sys_path] = device
            if ('ID_INPUT_JOYSTICK' in device and device['ID_INPUT_JOYSTICK']) or ('DEVNAME' in device and device['DEVNAME'] in input_devices):
                #print device
                #for k, v in device.iteritems():
                #    print '    ', k, v
                in_joystick_chain.append(device.sys_path)
                for anc in self._find_parents(device.parent):
                    in_joystick_chain.append(anc.sys_path)
                    if anc.parent is None:
                        roots.add(anc)
        return devs, roots, in_joystick_chain

    def get_subtree(self, dev, in_joystick_chain, parent):
        if dev.sys_path in in_joystick_chain:
            if parent:
                name = dev.sys_path.replace(parent.sys_path, '')
            else:
                name = dev.sys_path
            result = {"name": name, "dev": dev, "children": []}
            for d in dev.children:
                if d.parent.sys_path != dev.sys_path:
                    continue
                st = self.get_subtree(d, in_joystick_chain, dev)
                if st:
                    result['children'].append(st)
            return result
        else:
            return None

    def get_dev_tree(self):
        scan_evdev_gamepads()
        scan_jsio_gamepads()
        # scan_pygame_gamepads() # TODO: missing pygame for python3
        scan_sdl2_gamepads()
        devs, roots, in_joystick_chain = self.get_devs()
        result = {"name": "root", "dev": None, "children": []}
        for r in roots:
            st = self.get_subtree(r, in_joystick_chain, None)
            if st:
                result['children'].append(st)
        return result

    def setup_monitor(self, ui_wakeup_fd):
        self.ui_wakeup_fd = ui_wakeup_fd

        self.monitor = pyudev.Monitor.from_netlink(self.ctx)
        self.observer = pyudev.MonitorObserver(self.monitor, self.send_event_to_ui_thread)
        self.observer.start()


class ConsoleUI(object):
    palette = [
        ('body', 'black', 'light gray'),
        ('normal', 'light gray', ''),
        ('focus', 'white', 'black'),
        ('head', 'yellow', 'black', 'standout'),
        ('foot', 'light gray', 'black'),
        ('key', 'light cyan', 'black','underline'),
        ('title', 'white', 'black', 'bold'),
        ('flag', 'dark gray', 'light gray'),
        ('error', 'dark red', 'light gray'),
        ('emph', 'yellow', ''),
        ('dim', 'light gray', 'black'),
        ]

    footer_text = [
        ('title', "Example Data Browser"), "    ",
        ('key', "UP"), ",", ('key', "DOWN"), ",",
        ('key', "PAGE UP"), ",", ('key', "PAGE DOWN"),
        "  ",
        ('key', "+"), ",",
        ('key', "-"), "  ",
        ('key', "LEFT"), "  ",
        ('key', "HOME"), "  ",
        ('key', "END"), "  ",
        ('key', "Q"),
        ]

    def __init__(self):
        self.udev_queue = queue.Queue()
        self.udev = Udev(self.udev_queue)

        self.focus_pane = 0

        self.header = urwid.Text( " -= GamePad Info =-" )
        self.footer = urwid.AttrWrap( urwid.Text( self.footer_text ),
            'foot')
        self.log = urwid.SimpleFocusListWalker([])
        self.log.append(urwid.Text(('dim', '%s: monitoring udev started' % datetime.datetime.now())))
        self.log_box = urwid.ListBox(self.log)
        self.log_box_wrap = urwid.AttrMap(urwid.LineBox(self.log_box, 'udev events'), 'normal', 'focus')

        self.dev_box = DeviceBox()
        self.dev_box_wrap = urwid.AttrMap(self.dev_box, 'normal', 'focus')

        self.cols = urwid.Columns([urwid.Filler(urwid.Text('placeholder')),
                                   self.dev_box_wrap])
        self.refresh_devs_tree()  # invoke after creating cols
        self.pile = urwid.Pile([self.cols,
                                self.log_box_wrap])
        self.view = urwid.Frame(
            self.pile,
            header=urwid.AttrWrap(self.header, 'head' ),
            footer=self.footer )

        self.aloop = asyncio.get_event_loop()
        evl = urwid.AsyncioEventLoop(loop=self.aloop)
        self.loop = urwid.MainLoop(self.view, self.palette, event_loop=evl,
                                   unhandled_input=self.unhandled_input)

        self.ui_wakeup_fd = self.loop.watch_pipe(self.handle_udev_event)
        self.udev.setup_monitor(self.ui_wakeup_fd)

    def main(self):
        """Run the program."""

        self.loop.run()

    def unhandled_input(self, k):
        if k in ('q','Q'):
            raise urwid.ExitMainLoop()
        elif k == 'tab':
            if self.focus_pane == 0:
                # devs tree -> dev box
                self.cols.focus_position = 1
                self.focus_pane = 1
            elif self.focus_pane == 1:
                # dev box -> logs
                self.pile.focus_position = 1
                self.focus_pane = 2
            else:
                # logs -> devs tree
                self.pile.focus_position = 0
                self.cols.focus_position = 0
                self.focus_pane = 0

    def handle_udev_event(self, data):
        for _ in data:
            (action, device) = self.udev_queue.get(block=False)
            entry = '%s: %8s - %s' % (datetime.datetime.now(), action, device.sys_path)
            self.log.append(urwid.Text(entry))
            self.log_box.focus_position = len(self.log) - 1

        self.refresh_devs_tree()

    def refresh_devs_tree(self):
        devtree = self.udev.get_dev_tree()

        self.topnode = ExampleParentNode(devtree)
        self.listbox = MyTree(urwid.TreeWalker(self.topnode), node_visited_cb=self.node_visited)
        self.listbox.offset_rows = 1
        self.devs_tree = urwid.LineBox(self.listbox, 'devices tree')
        self.devs_tree_wrap = urwid.AttrMap(self.devs_tree, 'normal', 'focus')

        self.cols.contents[0] = (self.devs_tree_wrap, ('weight', 1, False))

    def async_evdev_read(self, device):
        future = asyncio.Future()
        def ready():
            self.aloop.remove_reader(device.fileno())
            future.set_result(device.read())
        self.aloop.add_reader(device.fileno(), ready)
        return future

    async def handle_evdev_events(self, device):
        while True:
            events = await self.async_evdev_read(device)
            for event in events:
                entry = '%s: %s' % (datetime.datetime.now(), str(event))
                self.log.append(urwid.Text(entry))
                self.log_box.focus_position = len(self.log) - 1

    def node_visited(self, device):
        if not device:
            return
        self.dev_box.show_device(device)

        if 'DEVNAME' in device and device['DEVNAME'] in input_devices:
            data = input_devices[device['DEVNAME']]
            if 'evdev' in data:
                asyncio.ensure_future(self.handle_evdev_events(data['evdev']), loop=self.aloop)


def main():
    ui = ConsoleUI()
    ui.main()

if __name__=="__main__":
    main()
