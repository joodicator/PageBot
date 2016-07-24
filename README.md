# PageBot

A general-purpose, modular, extensible IRC robot written in Python 2, based on the *untwisted* network framework.

It includes plugins for a [public messaging system](#tell), [URL scanning](#url), [dice rolling](#dice), [channel operator management](#aop), [telling when a user was last seen](#seen), [connecting channels to Minecraft servers](#minecraft), and numerous others.

## Contents
1. [Requirements](#requirements)
2. [Contributing](#contributing)
3. [License](#license)
4. [Installation and Usage](#installation-and-usage)
5. [Overview of Files](#overview-of-files)
6. [Main Configuration File](#main-configuration-file)
7. [Core Modules](#core-modules)
8. [Available Plugins](#available-plugins)

## Requirements
* [Python](https://python.org) 2.7
* A POSIX-compliant shell interpreter such as `bash`. This dependency may be removed in the future.
* Further requirements of individual plugins used. See [Available Plugins](#available-plugins) for details.

## Contributing
Bug reports and feature requests may be submitted to this repository using the issue tracker, and are more than welcome. Pull requests fixing bugs are welcome, and pull requests adding or changing features will be duly considered.

## License

This program is free software: you can redistribute it and/or modify it under the terms of the GNU Lesser General Public License as published by the 
Free Software Foundation, either version 3 of the License, or (at your option) any later version.

This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the implied warranty of 
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU Lesser General Public License for more details.

You should have received a copy of the GNU Lesser General Public License along with this program. If not, see http://www.gnu.org/licenses/.

## Installation and Usage
* Clone this repository, or download an archive of the code and extract it, into an empty directory.
* Copy `conf/templates/bot.py` to `conf/bot.py` and edit it to configure the basic parameters of the bot. See [Main Configuration File](#main-configuration-file).
* As needed for any plugins loaded, copy additional files from `conf/templates/` into `conf/` and edit them. The plugins listed in [Core Modules](#core-modules) should usually be present at the beginning of this list, in the same order.
* If the bot should identify to NickServ, create [`conf/nickserv.py`](#nickserv) with the relevant information. If you wish to be able to issue admin-only commands to the bot, add yourself to `conf/admins.txt` and/or set a password in `conf/auth_password.txt` and then use the [`!identify`](#auth) command.
* Run `main`, and the bot will connect to the configured IRC server and print a log of sent and received IRC messages to `stdout`. The bot currently has no built-in daemon mode, but it can be left running in the background using a terminal multiplexer such as GNU `screen`. To restart the bot, issue `Ctrl+C` once and wait or twice to terminate it. It may also be caused to restart with a particular quit message using the admin command [`!raw QUIT :message`](#control).
* There are at least three ways to cause the bot to join IRC channels:
    1. Configure the channels statically in [`conf/bot.py`](#main-configuration-file), and they will be automatically joined.
    2. If the [`invite`](#invite) plugin is loaded: configure the channels dynamically (while the bot is running) using the IRC `INVITE` and `KICK` commands to cause it to join or leave channels. You must usually be a channel operator to do this. This will be remembered when the bot is restarted.
    3. If you are a bot administrator, use the [`!join` and `!part`](#control) commands in a channel or by private message. These settings will *not* be remembered when the bot is restarted.
* While the bot is running, if you are an administrator, modules can be dynamically installed, uninstalled and reloaded from disk using the [`!load`, `!unload`, `!reload` and `hard-reload`](#control) commands.

## Overview of Files
* `main` - The POSIX shell script used to run PageBot.
* `conf/` - User configuration files.
* `conf/templates/` - Templates for files in `conf/`.
* `state/` - Data saved dynamically by PageBot to persist when it is restarted.
* `static/` - Static data files which are not program code.
* `page/` - Plugins and support modules that extend ameliabot to implement most of PageBot's functionality.
* `ameliabot/` - A heavily modified version of http://sourceforge.net/projects/ameliabot/.
* `lib/untwisted/` - A modified version of http://sourceforge.net/p/untwisted/.
* `lib/xirclib.py` - A lightweight implementation of IRC for untwisted.

## Main Configuration File
This file is located at `conf/bot.py` and configures the core features of the bot. It is a Python 2.7 source file which may bind the following names at the top level:

| Name          | Type                      | Description                                                                            |
|---------------|---------------------------|----------------------------------------------------------------------------------------|
|`server`       |`string`                   | The hostname of the IRC server to which to connect. |
|`port`         |`int`                      | The port number to which to connect. Usually 6667. Plain IRC connections must be accepted on this port, as PageBot does not (currently) support SSL. |
|`nick`         |`string`                   | The nickname for the bot to use on IRC. |
|`user`         |`string`                   | The username for the bot to use on IRC. |
|`name`         |`string`                   | The "real name" for the bot to use on IRC. |
|`host`         |`string`                   | The bot's own hostname reported to the IRC server. In practice, this is usually ignored by the server, and can be anything. |
|`channels`     |`list` of `string`         | The channels to join automatically after connecting. |
|`plugins`      |`list` of `string`         | The plugins to load automatically. |
|`timeout`      |`Number`                   | The number of seconds of latency after which the connection will time out and restart. |
|`bang_cmd`     |`True` or `False`          | If False, bot commands must be prefixed by `NICK: `, where `NICK` is the bot's nick. This is useful if there are multiple bots present which may respond to commands of the form `!COMMAND`. |
|`flood_limits` |`list` of `(Number,Number)`| Each list item `(lines, seconds)` enforces a serverbound flood protection rule preventing the bot from sending more than `lines` IRC messages in any period of `seconds` seconds. This is useful to prevent the bot from being disconnected by an IRC server's flood protection mechanisms. In practice, IRC servers often have multiple such mechanisms, hence the need for multiple rules. |

If any of these are not specified, the default values in [`main.py`](main.py) or [`ameliabot/amelia.py`](ameliabot/amelia.py) (in that order) are used.

## Core Modules
### runtime
Actively performs miscellaneous tasks essential to the bot and other modules.

### message
Manages basic IRC message events from `xirclib` and provides the `!help` command.
* `!help` - shows information about (most) user commands.
* `conf/ignore.txt` - one `nick!user@host` wildcard expression per line to ignore all messages from.

### nickserv
Communicates with the network service known as NickServ on most IRC networks.
* `conf/nickserv.py` - contains network-specific information used to identify NickServ, and the bot's own password used to identify to NickServ, if it has one.

### auth
Provides authentication of bot administrators.
* `!id PASS`, `!identify PASS` - cause the bot to recognise the user issuing this command as an administrator. 
* `conf/admins.txt` - one `nick!user@host` wildcard expression, or, if `identity` is installed, one access name from `conf/identity.py`, which is allowed to use admin commands.
* `conf/auth_password.txt` - the password, if any, accepted by `!identify`.

### control
Provides admin commands for control of the bot's basic functions.
* `!echo MSG` - [admin] repeat `MSG` in the same channel or back by PM to the sender.
* `!raw CMD` - [admin] send `CMD` to the server as a [raw IRC message](https://tools.ietf.org/html/rfc2812).
* `!msg TARGET MSG` - [admin] say `MSG` to the nick or channel given by `TARGET`.
* `!act TARGET MSG` - [admin] send `MSG` as a [CTCP `ACTION` message](http://www.mirc.org/mishbox/reference/ctcpref.htm) (as generated by `/me` in most IRC clients).
* `!j CHAN`, `!join CHAN` - [admin] join the given channel.
* `!part [CHAN]` - [admin] leave the given channel, or the current channel if none is given.
* `!eval EXPR` - [admin] show the value of the Python expression `EXPR` (with `bot` and all loaded modules in scope).
* `!exec STMT` - [admin] execute the Python statement `STMT` (with `bot` and all loaded modules in scope).
* `!yield ACTION` - [admin] perform the given asynchronous untwisted action and show the return value when (and if) it completes.
* `!load MOD` - [admin] install the plugin module named `MOD`, usually from a Python file in `page/`.
* `!unload MOD` - [admin] uninstall the plugin module named `MOD`.
* `!reload` - [admin] reload the code of all reloadable modules (those in `page/` and certain others) from their source files, and reinstall all installed plugin modules, possibly retaining the state of the old instances.
* `!hard-reload` - [admin] as `!reload`, but discard as much old state information as possible, thus resetting the state of most modules.

### channel
Manages state information relating to IRC channels.
* `conf/quiet_channels.txt` - one channel name per line in which certain automatic messages from the bot, such as those from `bum`, will be suppressed.

## Available Plugins
*To be completed...*
