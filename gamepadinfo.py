import evdev
import struct
import glob
import os
import ctypes
import fcntl
import traceback
import array
from colorama import init, Style, Fore

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

BUTTON_NAMES = {v: k[4:].lower() for k, v in evdev.ecodes.ecodes.iteritems()}

all_devices = {}


def add_evdev_gamepads():
    devs = []
    for fn in evdev.list_devices():
        try:
            d = evdev.InputDevice(fn)
        except:
            pass
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
                phys = d.phys
                #print 'EVDEV', d.name, phys
                if phys not in all_devices:
                    all_devices[phys] = {}
                all_devices[phys]['evdev'] = d


def present_evdev_gamepad(d):
    print Fore.YELLOW + "\tEVDEV:"
    caps = d.capabilities()
    print '\tname:', d.name
    print '\tfile:', d.fn
    #print '\tphys:', d.phys
    if evdev.ecodes.EV_ABS in caps:
        print '\tabs'
    if evdev.ecodes.EV_KEY in caps:
        print '\tbuttons:',
        keys = caps[evdev.ecodes.EV_KEY]
        for k in GAMEPAD_BUTTONS:
            if k in keys:
                print BUTTON_NAMES[k],
        print ''
    print '\t', d.info
    #0500000049190000020400001b010000


def add_jsio_gamepads():
    devices = {}
    syspaths = glob.glob("/dev/input/js*")

    #ioctls
    JSIOCGVERSION = 0x80046a01
    JSIOCGAXES = 0x80016a11
    JSIOCGBUTTONS = 0x80016a12
    JSIOCGNAME = 0x81006a13

    for path in syspaths:
        #print path
        data = dict(path=path)
        try:
            with open(path, "r") as jsfile:
                fcntl.fcntl(jsfile.fileno(), fcntl.F_SETFL, os.O_NONBLOCK)

                val = ctypes.c_int()

                if fcntl.ioctl(jsfile.fileno(), JSIOCGAXES, val) != 0:
                    print "Failed to read number of axes"
                else:
                    data['axes'] = val.value
                    #print 'axes', data['axes']

                if fcntl.ioctl(jsfile.fileno(), JSIOCGBUTTONS, val) != 0:
                    print "Failed to read number of axes"
                else:
                    data['buttons'] = val.value
                    #print 'buttons', data['buttons']

                if fcntl.ioctl(jsfile.fileno(), JSIOCGVERSION, val) != 0:
                    print "Failed to read version"
                else:
                    data['version'] = '0x%x' % val.value
                    #print 'version', data['version']

                buf = array.array('c', ['\0'] * 64)
                fcntl.ioctl(jsfile.fileno(), JSIOCGNAME + (0x10000 * len(buf)), buf)
                data['name'] = buf.tostring()
                #print 'name', data['name']

            p = os.path.join('/sys/class/input', path.rsplit('/', 1)[1])
            for phys, d in all_devices.iteritems():
                paths = d['sysfs']['paths']
                if p in paths:
                    d['jsio'] = data
        except:
            #print traceback.format_exc()
            pass




def present_jsio_gamepad(data):
    print Fore.YELLOW + "\tJSIO:"
    for k, v in data.iteritems():
#        if k in ['paths', 'PRODUCT', 'PHYS']:
        print '\t%s: %s' % (k.lower(), v)


def add_sysfs_input_devs():
    syspaths = glob.glob("/sys/class/input/event*") + glob.glob("/sys/class/input/js*")

    for path in syspaths:
        dev_uevent_file = os.path.join(path, 'device/uevent')
        if not os.path.exists(dev_uevent_file):
            continue
        #print dev_uevent_file
        with open(dev_uevent_file) as f:
            data = dict(paths=[path])
            for l in  f.readlines():
                l = l.strip()
                k, v = l.split('=', 1)
                data[k] = v.strip('"')
            #if 'PHYS' not in data:
            #    print 'NO PHYS', data
            #    continue
            phys = data['PHYS']
            #print 'SYSFS', data['NAME'], phys
            if phys not in all_devices:
                all_devices[phys] = {}
            if 'sysfs' not in all_devices[phys]:
                all_devices[phys]['sysfs'] = data
            else:
                d = all_devices[phys]['sysfs']
                d['paths'].append(path)
                if 'extra' not in d:
                    d['extra'] = []
                d['extra'].append(data)

def present_sysfs_data(data):
    print Fore.YELLOW + "\tSYSFS:"
    for k, v in data.iteritems():
        if k in ['paths', 'PRODUCT', 'PHYS']:
            print '\t%s: %s' % (k.lower(), v)


def add_pygame_gamepads():
    import pygame
    pygame.init()
    pygame.joystick.init()
    for i in range(pygame.joystick.get_count()):
        j = pygame.joystick.Joystick(i)
        j.init()
        name = j.get_name().strip()
        #print j.get_id()
        for phys, d in all_devices.iteritems():
            n = d['sysfs']['NAME'].strip()
            if name == n:
                d['pygame'] = j

def present_pygame_gamepad(data):
    print Fore.YELLOW + "\tPyGame:"
    #print '\tname: %s' % data.get_name()
    print '\tid: %s' % data.get_id()
    print '\tnumaxes: %s' % data.get_numaxes()
    print '\tnumballs: %s' % data.get_numballs()
    print '\tnumbuttons: %s' % data.get_numbuttons()
    #print '\tnumhats: %s' % data.get_numhats()


def add_sdl2_gamepads():
    import sdl2
    sdl2.SDL_Init(sdl2.SDL_INIT_JOYSTICK | sdl2.SDL_INIT_GAMECONTROLLER)
    num = sdl2.joystick.SDL_NumJoysticks()
    print num
    for i in range(num):
        j = sdl2.joystick.SDL_JoystickOpen(i)
        name = sdl2.SDL_JoystickName(j).strip()
        for phys, d in all_devices.iteritems():
            n = d['sysfs']['NAME'].strip()
            if name == n:
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
    print Fore.YELLOW + "\tSDL2:"
    import sdl2
    print '\tguid: %s' % SDL_JoystickGetGUIDString(sdl2.joystick.SDL_JoystickGetGUID(j))
    print '\tid: %s' % sdl2.joystick.SDL_JoystickInstanceID(j)
    print '\tNumAxes: %s' % sdl2.joystick.SDL_JoystickNumAxes(j)
    print '\tNumBalls: %s' % sdl2.joystick.SDL_JoystickNumBalls(j)
    print '\tNumButtons: %s' % sdl2.joystick.SDL_JoystickNumButtons(j)
    print '\tNumHats: %s' % sdl2.joystick.SDL_JoystickNumHats(j)


def main():
    init(autoreset=True)
    add_sysfs_input_devs()
    add_evdev_gamepads()
    add_jsio_gamepads()
    add_pygame_gamepads()
    add_sdl2_gamepads()

    for phys, data in all_devices.iteritems():
        if 'sysfs' in data and ('evdev' in data or 'jsio' in data):
            print Style.BRIGHT + data['sysfs']['NAME']
            present_sysfs_data(data['sysfs'])
        if 'evdev' in data:
            present_evdev_gamepad(data['evdev'])
        if 'jsio' in data:
            present_jsio_gamepad(data['jsio'])
        if 'pygame' in data:
            present_pygame_gamepad(data['pygame'])
        if 'sdl2' in data:
            present_sdl2_gamepad(data['sdl2'])


if __name__ == '__main__':
    main()
