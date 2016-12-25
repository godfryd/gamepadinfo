#!/usr/bin/python3
"""Detect gamepads and show their state on Linux."""
import os
import datetime
import queue
import struct
import glob
import ctypes
import fcntl
import traceback
import array
import asyncio
import select

import urwid
import pyudev
import evdev
import sdl2

JS_EVENT_BUTTON = 0x01  # button pressed/released
JS_EVENT_AXIS = 0x02  # joystick moved
JS_EVENT_INIT = 0x80  # initial state of device


# pylint: disable=no-member
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

BUTTON_NAMES = {v: k[4:] for k, v in evdev.ecodes.ecodes.items()}

INPUT_DEVICES = {}


def scan_evdev_gamepads():
    """Scan for evdev gamepads."""
    # remove old evdev devices
    global INPUT_DEVICES  # pylint: disable=global-statement
    INPUT_DEVICES = {fn: INPUT_DEVICES[fn] for fn in INPUT_DEVICES if not fn.startswith('/dev/input/event')}

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
                # print 'EVDEV', d.name, fn
                if fn not in INPUT_DEVICES:
                    INPUT_DEVICES[fn] = {}
                INPUT_DEVICES[fn]['evdev'] = d


def present_evdev_gamepad(dev):
    """Generate description of evdev gamepads for urwid."""
    text = [('emph', "EVDEV:",)]
    caps = dev.capabilities()
    text.append("   name: '%s'" % dev.name)
    text.append('   file: %s' % dev.fn)
    text.append('   phys: %s' % dev.phys)
    if evdev.ecodes.EV_ABS in caps:
        axes_text = '   axes: '
        axes = caps[evdev.ecodes.EV_ABS]
        axes_text += ", ".join([evdev.ecodes.ABS[a[0]][4:] for a in axes])
        text.append(axes_text)
    if evdev.ecodes.EV_KEY in caps:
        keys_text = []
        keys_text.append('   buttons: ')
        keys = caps[evdev.ecodes.EV_KEY]
        for k in keys:
            if k in GAMEPAD_BUTTONS:
                keys_text.append(('key', BUTTON_NAMES[k]))
            else:
                keys_text.append(BUTTON_NAMES[k])
            keys_text.append(', ')
        text.append(keys_text[:-1])
    text.append('   %s' % str(dev.info))
    # caps = dev.capabilities(verbose=True)
    # text.append(str(caps))
    # caps = dev.capabilities()
    # text.append(str(caps))

    # TODO: add SDL2 id
    return text


def scan_jsio_gamepads():
    """Scan for jsio gamepads."""
    # remove old js devices
    global INPUT_DEVICES  # pylint: disable=global-statement
    INPUT_DEVICES = {fn: INPUT_DEVICES[fn] for fn in INPUT_DEVICES if not fn.startswith('/dev/input/js')}

    syspaths = glob.glob("/dev/input/js*")

    # ioctls, pylint: disable=invalid-name
    JSIOCGVERSION = 0x80046a01
    JSIOCGAXES = 0x80016a11
    JSIOCGBUTTONS = 0x80016a12
    JSIOCGNAME = 0x81006a13

    for fn in syspaths:
        data = dict(path=fn)
        try:
            with open(fn, "r") as jsfile:
                fcntl.fcntl(jsfile.fileno(), fcntl.F_SETFL, os.O_NONBLOCK)

                val = ctypes.c_int()

                if fcntl.ioctl(jsfile.fileno(), JSIOCGAXES, val) != 0:
                    print("Failed to read number of axes")
                else:
                    data['axes'] = val.value

                if fcntl.ioctl(jsfile.fileno(), JSIOCGBUTTONS, val) != 0:
                    print("Failed to read number of axes")
                else:
                    data['buttons'] = val.value

                if fcntl.ioctl(jsfile.fileno(), JSIOCGVERSION, val) != 0:
                    print("Failed to read version")
                else:
                    data['version'] = '0x%x' % val.value

                buf = array.array('b', [0] * 64)
                fcntl.ioctl(jsfile.fileno(), JSIOCGNAME + (0x10000 * len(buf)), buf)
                data['name'] = str(buf.tobytes(), 'utf-8').rstrip("\x00")

            if fn not in INPUT_DEVICES:
                INPUT_DEVICES[fn] = {}
            INPUT_DEVICES[fn]['jsio'] = data
        except PermissionError:
            pass  # TODO: show errors on some status bar or logs panel
        except:
            print(traceback.format_exc())


def present_jsio_gamepad(data):
    """Generate description of jsio gamepads for urwid."""
    text = [('emph', "JSIO:",)]
    for k, v in data.items():
        if k.lower() == 'name':
            v = "'%s'" % v
        text.append('   %s: %s' % (k.lower(), v))
    return text


def scan_pygame_gamepads():
    """Scan for pygame gamepads."""
    import pygame  # pylint: disable=import-error
    pygame.init()
    pygame.joystick.init()
    for i in range(pygame.joystick.get_count()):
        j = pygame.joystick.Joystick(i)
        j.init()
        name = j.get_name().strip()

        for d in INPUT_DEVICES.values():
            if 'jsio' not in d:
                continue
            n = d['jsio']['name'].strip()
            if n.startswith(name):
                d['pygame'] = j


def present_pygame_gamepad(data):
    """Generate description of pygame gamepads for urwid."""
    text = [('emph', "PyGame:",)]
    text.append('   name: %s' % data.get_name())
    text.append('   id: %s' % data.get_id())
    text.append('   numaxes: %s' % data.get_numaxes())
    text.append('   numballs: %s' % data.get_numballs())
    text.append('   numbuttons: %s' % data.get_numbuttons())
    # print '\tnumhats: %s' % data.get_numhats()
    return text


def scan_sdl2_gamepads():
    """Scan for sdl2 gamepads."""
    sdl2.SDL_Init(sdl2.SDL_INIT_JOYSTICK | sdl2.SDL_INIT_GAMECONTROLLER)
    num = sdl2.joystick.SDL_NumJoysticks()
    for i in range(num):
        j = sdl2.joystick.SDL_JoystickOpen(i)
        name = str(sdl2.SDL_JoystickName(j).strip(), 'utf-8')
        for d in INPUT_DEVICES.values():
            if 'evdev' not in d:
                continue
            n = d['evdev'].name
            if n.startswith(name):
                d['sdl2'] = j

        # guid = sdl2.joystick.SDL_JoystickGetGUID(js)
        # my_guid = SDL_JoystickGetGUIDString(guid)


def sdl_joystickgetguidstring(guid):
    """Get SDL2 GUID from low level data."""
    s = ''
    for g in guid.data:
        s += "{:x}".format(g >> 4)
        s += "{:x}".format(g & 0x0F)
    return s


def present_sdl2_gamepad(j):
    """Generate description of sdl2 gamepads for urwid."""
    text = [('emph', "SDL2:",)]
    text.append('   guid: %s' % sdl_joystickgetguidstring(sdl2.joystick.SDL_JoystickGetGUID(j)))
    text.append('   id: %s' % sdl2.joystick.SDL_JoystickInstanceID(j))
    text.append('   NumAxes: %s' % sdl2.joystick.SDL_JoystickNumAxes(j))
    text.append('   NumBalls: %s' % sdl2.joystick.SDL_JoystickNumBalls(j))
    text.append('   NumButtons: %s' % sdl2.joystick.SDL_JoystickNumButtons(j))
    text.append('   NumHats: %s' % sdl2.joystick.SDL_JoystickNumHats(j))
    return text


class DeviceTreeWidget(urwid.TreeWidget):
    """ Display widget for leaf nodes """
    def get_display_text(self):
        return self.get_node().get_value()['name']


class DeviceNode(urwid.TreeNode):
    """ Data storage object for leaf nodes """
    def load_widget(self):
        return DeviceTreeWidget(self)


class DeviceParentNode(urwid.ParentNode):
    """ Data storage object for interior/parent nodes """
    def load_widget(self):
        return DeviceTreeWidget(self)

    def load_child_keys(self):
        data = self.get_value()
        return list(range(len(data['children'])))

    def load_child_node(self, key):
        """Return either an DeviceNode or DeviceParentNode"""
        childdata = self.get_value()['children'][key]
        childdepth = self.get_depth() + 1
        if 'children' in childdata:
            childclass = DeviceParentNode
        else:
            childclass = DeviceNode
        return childclass(childdata, parent=self, key=key, depth=childdepth)


class DevicesTree(urwid.TreeListBox):
    def __init__(self, *args, **kwargs):
        self.node_visited_cb = kwargs.pop('node_visited_cb')
        super(DevicesTree, self).__init__(*args, **kwargs)

    def change_focus(self, *args, **kwargs):
        super(DevicesTree, self).change_focus(*args, **kwargs)
        _, node = self.get_focus()
        data = node.get_value()
        self.node_visited_cb(data['dev'])


class DeviceBox(urwid.LineBox):
    def __init__(self):
        self.lines = urwid.SimpleFocusListWalker([])
        self.lines_box = urwid.ListBox(self.lines)
        super(DeviceBox, self).__init__(self.lines_box, 'Dev Box: [select device]')
        self.device = None

    def show_device(self, device):
        self.device = device
        text = []

        if device:
            if 'DEVNAME' in device and device['DEVNAME'] in INPUT_DEVICES:
                data = INPUT_DEVICES[device['DEVNAME']]
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

            self.set_title('Dev Box: ' + device.sys_path)
        else:
            self.set_title('Dev Box: [select device]')

        elems = [urwid.Text(t) for t in text]
        self.lines[:] = elems
        if elems:
            self.lines_box.focus_position = 0


class Udev(object):
    def __init__(self, ui_queue):
        self.ui_queue = ui_queue
        self.ctx = pyudev.Context()

        self.ui_wakeup_fd = None
        self.monitor = None
        self.observer = None

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
            if ('ID_INPUT_JOYSTICK' in device and device['ID_INPUT_JOYSTICK']) or ('DEVNAME' in device and device['DEVNAME'] in INPUT_DEVICES):
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
        _, roots, in_joystick_chain = self.get_devs()
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


class GamePadStateBox(urwid.Text):
    def __init__(self, *args, **kwargs):
        super(GamePadStateBox, self).__init__(*args, **kwargs)
        self.buttons = {}
        self.axes = {}

    def update_state(self, source, device, event):
        if source == 'evdev':
            self._update_evdev_state(device, event)
        elif source == 'jsio':
            self._update_jsio_state(device, event)

    def _update_evdev_state(self, device, event):
        buttons = [BUTTON_NAMES[k[1]] if k[0] == '?' else k[0] for k in device.active_keys(verbose=True)]
        text = "Buttons: %s\n" % ", ".join(buttons)

        if event.type == evdev.ecodes.EV_ABS:
            self.axes[event.code] = event.value

        caps = device.capabilities()
        axes_caps = {}
        for a, info in caps[evdev.ecodes.EV_ABS]:
            axes_caps[a] = info

        text += "Axes:\n"
        for c, val in self.axes.items():
            text += "  %s: %d/%d\n" % (evdev.ecodes.ABS[c][4:], val, axes_caps[c].max)

        self.set_text(text)

    def _update_jsio_state(self, device, event):
        # pylint: disable=unused-argument
        if event['type'] == JS_EVENT_BUTTON:
            if event['value'] == 1:
                self.buttons[event['number']] = event['value']
            else:
                if event['number'] in self.buttons:
                    del self.buttons[event['number']]
        elif event['type'] == JS_EVENT_AXIS:
            self.axes[event['number']] = event['value']

        buttons = [str(b) for b in self.buttons.keys()]
        text = "Buttons: %s\n" % ", ".join(buttons)

        text += "Axes:\n"
        for a, v in self.axes.items():
            text += "  %s: %d\n" % (a, v)

        self.set_text(text)


class MyAsyncioEventLoop(urwid.AsyncioEventLoop):
    def run(self):
        """
        Start the event loop.  Exit the loop when any callback raises
        an exception.  If ExitMainLoop is raised, exit cleanly.
        """
        self._loop.set_exception_handler(self._exception_handler)
        self._loop.run_forever()
        if self._exc_info:
            e = self._exc_info
            self._exc_info = None
            open('a.log', 'a').write(str(e)+'\n')
            if e[1]:
                raise e[1]


class ConsoleUI(object):
    # pylint: disable=too-many-instance-attributes
    palette = [
        ('body', 'black', 'light gray'),
        ('normal', 'light gray', ''),
        ('focus', 'white', 'black'),
        ('head', 'yellow', 'black', 'standout'),
        ('foot', 'light gray', 'black'),
        ('key', 'light cyan', 'black', 'underline'),
        ('title', 'white', 'black', 'bold'),
        ('flag', 'dark gray', 'light gray'),
        ('error', 'dark red', 'light gray'),
        ('emph', 'yellow', ''),
        ('dim', 'light gray', 'black'),
        ]

    footer_texts = [[
        # focused devs tree
        ('key', "TAB"), ":Change focused pane  ",
        ('key', "DOWN"), ",",
        ('key', "UP"), ",",
        ('key', "PAGE UP"), ",",
        ('key', "PAGE DOWN"), ",",
        ('key', "+"), ",",
        ('key', "-"), ",",
        ('key', "LEFT"), ",",
        ('key', "HOME"), ",",
        ('key', "END"), ":Navigate Devices Tree and select device  ",
        ('key', "F1"), ":Help  ",
        ('key', "F2"), ":Switch Log Box/GamePad State  ",
        ('key', "ESC"), ",",
        ('key', "Q"), ":Quit"
    ], [
        # focused dev box
        ('key', "TAB"), ":Change focused pane  ",
        ('key', "DOWN"), ",",
        ('key', "UP"), ",",
        ('key', "PAGE UP"), ",",
        ('key', "PAGE DOWN"), ":Scroll Dev Box content  ",
        ('key', "F1"), ":Help  ",
        ('key', "F2"), ":Switch Log Box/GamePad State  ",
        ('key', "ESC"), ",",
        ('key', "Q"), ":Quit"
    ], [
        # focused log box
        ('key', "TAB"), ":Change focused pane  ",
        ('key', "DOWN"), ",",
        ('key', "UP"), ",",
        ('key', "PAGE UP"), ",",
        ('key', "PAGE DOWN"), ":Scroll Log Box content  ",
        ('key', "F1"), ":Help  ",
        ('key', "F2"), ":Switch Log Box/GamePad State  ",
        ('key', "ESC"), ",",
        ('key', "Q"), ":Quit"
    ]]

    def __init__(self):
        self.udev_queue = queue.Queue()
        self.udev = Udev(self.udev_queue)

        # log box
        self.log_list = urwid.SimpleFocusListWalker([])
        self.log_list.append(urwid.Text(('dim', '%s: event monitoring started' % datetime.datetime.now())))
        self.log_box = urwid.ListBox(self.log_list)
        self.log_box_wrap = urwid.AttrMap(urwid.LineBox(self.log_box, 'Log Box'), 'normal', 'focus')

        # gampad state box
        self.gamepad_state_box = GamePadStateBox("-")
        self.gamepad_state_box_wrap = urwid.AttrMap(urwid.LineBox(urwid.Filler(self.gamepad_state_box, valign='top'), 'GamePad State Box'), 'normal', 'focus')

        # dev box
        self.dev_box = DeviceBox()
        self.dev_box_wrap = urwid.AttrMap(self.dev_box, 'normal', 'focus')

        self.cols = urwid.Columns([urwid.Filler(urwid.Text('placeholder')),
                                   self.dev_box_wrap])

        # dev tree
        self.refresh_devs_tree()  # invoke after creating cols

        self.bottom_elems = [self.log_box_wrap, self.gamepad_state_box_wrap]
        self.bottom_elem_idx = 0
        self.pile = urwid.Pile([self.cols,
                                self.bottom_elems[self.bottom_elem_idx]])
        self.view = urwid.Frame(
            self.pile,
            header=urwid.AttrWrap(urwid.Text(" -= GamePad Info =-"), 'head'),
            footer=urwid.AttrWrap(urwid.Text(self.footer_texts[0]), 'foot'))

        self.aloop = asyncio.get_event_loop()
        evl = MyAsyncioEventLoop(loop=self.aloop)
        self.loop = urwid.MainLoop(self.view, self.palette, event_loop=evl,
                                   unhandled_input=self.unhandled_input)

        self.focus_pane = 0
        self.pile.focus_position = 0
        self.cols.focus_position = 0

        self.ui_wakeup_fd = self.loop.watch_pipe(self.handle_udev_event)
        self.udev.setup_monitor(self.ui_wakeup_fd)

        self.evdev_events_handler_task = None
        self.selected_evdev_device = None
        self.jsio_events_handler_task = None
        self.selected_jsio_device = None

    def main(self):
        """Run the program."""

        self.loop.run()

    def switch_bottom_elem(self):
        self.bottom_elem_idx = 1 - self.bottom_elem_idx
        self.pile.contents[1] = (self.bottom_elems[self.bottom_elem_idx], ('weight', 1))

    def unhandled_input(self, k):
        if k in ('q', 'Q', 'esc'):
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
            self.view.footer = urwid.AttrWrap(urwid.Text(self.footer_texts[self.focus_pane]), 'foot')
        elif k == 'f2':
            self.switch_bottom_elem()
        # else:
        #     self.log(k)

    def log(self, text):
        entry = '%s: %s' % (datetime.datetime.now(), text)
        self.log_list.append(urwid.Text(entry))
        self.log_box.focus_position = len(self.log_list) - 1

    def handle_udev_event(self, data):
        for _ in data:
            (action, device) = self.udev_queue.get(block=False)
            entry = '%8s - %s' % (action, device.sys_path)
            self.log(entry)

        self.refresh_devs_tree()

    def refresh_devs_tree(self):
        devtree = self.udev.get_dev_tree()

        self.topnode = DeviceParentNode(devtree)
        self.listbox = DevicesTree(urwid.TreeWalker(self.topnode), node_visited_cb=self.node_visited)
        self.listbox.offset_rows = 1
        self.devs_tree = urwid.LineBox(self.listbox, 'Devices Tree')
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
                self.log(str(event))
                self.gamepad_state_box.update_state('evdev', device, event)
            if not self.evdev_events_handler_task:
                break

    def async_jsio_read(self, device):
        future = asyncio.Future()
        data_format = 'LhBB'

        def ready():
            self.aloop.remove_reader(device['file'].fileno())
            events = []
            while select.select([device['file'].fileno()], [], [], 0.0)[0]:
                data = device['file'].read(struct.calcsize(data_format))
                data = struct.unpack(data_format, data)
                event = dict(time=data[0], value=data[1], type=data[2] & ~JS_EVENT_INIT, number=data[3])
                events.append(event)
            future.set_result(events)

        self.aloop.add_reader(device['file'].fileno(), ready)
        return future

    async def handle_jsio_events(self, device):
        device['file'] = open(device['path'], 'rb', os.O_RDONLY | os.O_NDELAY)
        while True:
            events = await self.async_jsio_read(device)
            for event in events:
                self.log('%s: %s ' % (device['path'], str(event)))
                self.gamepad_state_box.update_state('jsio', device, event)
            if not self.jsio_events_handler_task:
                break

    def node_visited(self, device):
        self.dev_box.show_device(device)

        if self.evdev_events_handler_task:
            self.log('stopped monitorig evdev %s' % self.selected_evdev_device)
            self.evdev_events_handler_task.cancel()
            self.aloop.remove_reader(self.selected_evdev_device.fileno())
            self.evdev_events_handler_task = None

        if self.jsio_events_handler_task:
            self.log('stopped monitorig jsio %s' % self.selected_jsio_device)
            self.jsio_events_handler_task.cancel()
            self.aloop.remove_reader(self.selected_jsio_device['file'].fileno())
            self.jsio_events_handler_task = None

        if device and 'DEVNAME' in device and device['DEVNAME'] in INPUT_DEVICES:
            data = INPUT_DEVICES[device['DEVNAME']]
            if 'evdev' in data:
                self.selected_evdev_device = data['evdev']
                self.log('started monitorig evdev %s' % self.selected_evdev_device)
                self.evdev_events_handler_task = asyncio.ensure_future(self.handle_evdev_events(data['evdev']), loop=self.aloop)
            elif 'jsio' in data:
                self.selected_jsio_device = data['jsio']
                self.log('started monitorig jsio %s' % self.selected_jsio_device['path'])
                self.jsio_events_handler_task = asyncio.ensure_future(self.handle_jsio_events(data['jsio']), loop=self.aloop)


def main():
    ui = ConsoleUI()
    ui.main()


if __name__ == "__main__":
    main()
