PageBot
=======

An IRC robot written in Python 2, based on the untwisted framework.

Be warned that this program is not a good example of software engineering:
although it mostly works, it is the product of innumerable dirty hacks applied
in order to keep it working without the expense of changing the outdated and
buggy software it is based on.

The author has given up on maintaining any kind of useful documentation, so
the code will probably be incomprehensible.

Files
-----
<dl>
    <dt>lib/untwisted</dt>
    <dd>A modified version of http://sourceforge.net/p/untwisted/.</dd>

    <dt>lib/xirclib.py</dt>
    <dd>A lightweight implementation of IRC for untwisted.</dd>

    <dt>ameliabot/</dt>
    <dd>A heavily modified version of
        http://sourceforge.net/projects/ameliabot/.</dd>

    <dt>conf/</dt>
    <dd>User configuration files.</dd>

    <dt>state/</dt>
    <dd>Persistent data and runtime files.</dd>

    <dt>page/</dt>
    <dd>Plugins and support modules that are original components of
        PageBot.</dd>

    <dt>page/tell.py</dt>
    <dd>The "tell" plugin for which PageBot was originally created.</dd>

    <dt>main</dt>
    <dd>The bash script used to start PageBot.</dd>

    <dt>main.py</dt>
    <dd>The main program; called from main.</dd>
</dl>
