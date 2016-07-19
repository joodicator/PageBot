PageBot
=======

A general-purpose, modular, extensible IRC robot written in Python 2, based on the *untwisted* network framework.

Requirements
------------
* [Python](https://python.org) 2.7
* A POSIX-compliant shell interpreter such as `bash`. This dependency may be removed in the future.
* Further requirements of individual plugins used. See below for details.

Installation and Usage
----------------------
* Clone this repository, or download an archive of the code and extract it, into an empty directory.
* Copy `conf/templates/bot.py` to `conf/bot.py` and edit it to configure the basic parameters of the bot, such as what IRC server it shall connect to, and which plugins from `page/` should be loaded.
* As needed for any plugins loaded, copy additional files from `conf/templates/` into `conf/` and edit them. The following modules, which implement core functionality, should usually be present in the list, in this order: `runtime`, `message`, `nickserv`, `auth`, `control`, `channel`.
* If the bot should identify to `NickServ`, create `conf/nickserv.py` with the relevant information. If you wish to be able to issue admin-only commands to the bot, add yourself to `conf/admins.txt` and/or set a password in `conf/auth_password.txt` and then use the `!identify` (`!id`) command.
* Run `main`, and the bot will connect to the configured IRC server and print a log of sent and received IRC messages to `stdout`. The bot currently has no built-in daemon mode, but it can be left running in the background using a terminal multiplexer such as GNU `screen`. To restart the bot, issue `Ctrl+C` once and wait or twice to terminate it. It may also be caused to restart with a particular quit message using the admin command `!raw QUIT :message`.
* There are at least three ways to cause the bot to join IRC channels:
    1. Configure the channels statically in `conf/bot.py`, and they will be automatically joined.
    2. If the `invite` plugin is loaded: configure the channels dynamically (while the bot is running) using the IRC `INVITE` and `KICK` commands to cause it to join or leave channels. You must usually be a channel operator to do this. This will be remembered when the bot is restarted.
    3. If you are a bot administrator, use the `!join` (or `!j`) and `!part` commands in a channel or by private message. These settings will *not* be remembered when the bot is restarted.
* While the bot is running, if you are an administrator, modules can be dynamically installed using `!load` and uninstalled using `!unload`. The code of every module may be dynamically reloaded using `!reload` while allowing the newly loaded modules to restore the in-memory state of the previous version, if supported; or using `!hard-reload` to make modules reload as if the bot were restarted, with a small number of exceptions for data that would cause errors if it were lost.

Overview of Files
-----------------
* `main` - The POSIX shell script used to run PageBot.
* `conf/` - User configuration files.
* `conf/templates/` - Templates for files in `conf/`.
* `state/` - Data saved dynamically by PageBot to persist when it is restarted.
* `static/` - Static data files which are not program code.
* `page/` - Plugins and support modules that extend ameliabot to implement most of PageBot's functionality.
* `ameliabot/` - A heavily modified version of http://sourceforge.net/projects/ameliabot/.
* `lib/untwisted/` - A modified version of http://sourceforge.net/p/untwisted/.
* `lib/xirclib.py` - A lightweight implementation of IRC for untwisted.

Available Plugins
-----------------
*To be completed...*
