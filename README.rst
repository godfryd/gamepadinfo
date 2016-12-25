gamepadinfo
===========

This is a Python script that detects gamepads and show their state on
Linux.

Dependencies
------------

-  python3
-  urwid
-  pyudev
-  evdev
-  sdl2

Dependencies can be installed on Ubuntu manually:

$ sudo apt-get install python-urwid python-pyudev python-evdev
python-sdl2

If `gamepadinfo` is being installed via pip then dependencies will be installed automatically.

Installing and Running
----------------------

From source repository
~~~~~~~~~~~~~~~~~~~~~~

Installing and running from source code repository goes as follows::

   $ git clone https://github.com/godfryd/gamepadinfo
   $ cd gamepadinfo/
   $ ./gamepadinfo.py

Via pip
~~~~~~~

Installing and running using pip goes as follows::

   $ pip install gamepadinfo
   $ gamepadinfo

Screenshot
----------

.. figure:: /screenshot.png
   :alt: Screenshot

   Screenshot
