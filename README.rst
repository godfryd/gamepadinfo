.. image:: https://api.travis-ci.org/godfryd/gamepadinfo.svg?branch=master
   :target: https://travis-ci.org/godfryd/gamepadinfo

.. image:: http://img.shields.io/pypi/v/gamepadinfo.svg
    :target: https://pypi.python.org/pypi/gamepadinfo

.. image:: http://img.shields.io/pypi/dm/gamepadinfo.svg
    :target: https://pypi.python.org/pypi/gamepadinfo

.. image:: http://img.shields.io/pypi/l/gamepadinfo.svg
    :target: https://pypi.python.org/pypi/gamepadinfo

.. image:: http://img.shields.io/pypi/pyversions/gamepadinfo.svg
    :target: https://pypi.python.org/pypi/gamepadinfo

gamepadinfo
===========

This is a Python script that detects gamepads and shows their state on
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

Let's install and run.

*From source repository*

Installing and running from source code repository goes as follows::

   $ git clone https://github.com/godfryd/gamepadinfo
   $ cd gamepadinfo/
   $ ./gamepadinfo.py

*Via pip*

Installing and running using pip goes as follows::

   $ pip install gamepadinfo
   $ gamepadinfo

Video & Screenshot
------------------

Short video presentation:

   https://asciinema.org/a/5b5h1d850xk8wflv7v9db9qgb

Screenshot:

.. figure:: /screenshot.png
   :alt: Screenshot
