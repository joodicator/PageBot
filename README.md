# PageBot

A general-purpose, modular, extensible IRC robot written in Python 2, based on the *untwisted* network framework.

It includes plugins for a [public messaging system](#tell), [URL scanning](#url), [dice rolling](#dice), [channel operator management](#aop), [telling when a user was last seen](#seen), [connecting channels to Minecraft servers](#minecraft), and numerous others.

## Contents
1. [Requirements](#requirements)
2. [Contributing](#contributing)
3. [Copying](#copying)
4. [Installation and Usage](#installation-and-usage)
5. [Overview of Files](#overview-of-files)
6. [Main Configuration File](#main-configuration-file)
7. [Core Modules](#core-modules)
8. [Support Modules](#support-modules)
9. [Available Plugins](#available-plugins)

## Requirements
* [Python](https://python.org) 2.7
* A POSIX-compliant shell interpreter such as `bash`. This dependency may be removed in the future.
* Further requirements of individual plugins used. See [Available Plugins](#available-plugins) for details.

## Contributing
Bug reports and feature requests may be submitted to this repository using the issue tracker, and are more than welcome. Pull requests fixing bugs are welcome, and pull requests adding or changing features will be duly considered.

## Copying

This program is free software: you can redistribute it and/or modify it under the terms of the GNU Lesser General Public License as published by the 
Free Software Foundation, either version 3 of the License, or (at your option) any later version.

This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the implied warranty of 
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the [GNU Lesser General Public License](COPYING.LESSER) for more details.

You should have received a copy of the GNU Lesser General Public License along with this program. If not, see http://www.gnu.org/licenses/.

## Installation and Usage
1. Clone this repository, or download an archive of the code and extract it, into an empty directory.
2. Copy `conf/templates/bot.py` to `conf/bot.py` and edit it to configure the basic parameters of the bot. See [Main Configuration File](#main-configuration-file).
3. As needed for any plugins loaded, copy additional files from `conf/templates/` into `conf/` and edit them. The plugins listed in [Core Modules](#core-modules) should usually be present at the beginning of this list, in the same order.
4. If the bot should identify to NickServ, create [`conf/nickserv.py`](#nickserv) with the relevant information. If you wish to be able to issue admin-only commands to the bot, add yourself to `conf/admins.txt` and/or set a password in `conf/auth_password.txt` and then use the [`!identify`](#auth) command.
5. Run `main`, and the bot will connect to the configured IRC server and print a log of sent and received IRC messages to `stdout`. The bot currently has no built-in daemon mode, but it can be left running in the background using a terminal multiplexer such as GNU `screen`. To restart the bot, issue `Ctrl+C` once and wait or twice to terminate it. It may also be caused to restart with a particular quit message using the admin command [`!raw QUIT :message`](#control).
6. There are at least three ways to cause the bot to join IRC channels:
    1. Configure the channels statically in [`conf/bot.py`](#main-configuration-file), and they will be automatically joined.
    2. If the [`invite`](#invite) plugin is loaded: configure the channels dynamically (while the bot is running) using the IRC `INVITE` and `KICK` commands to cause it to join or leave channels. You must usually be a channel operator to do this. This will be remembered when the bot is restarted.
    3. If you are a bot administrator, use the [`!join` and `!part`](#control) commands in a channel or by private message. These settings will *not* be remembered when the bot is restarted.
7. While the bot is running, if you are an administrator, modules can be dynamically installed, uninstalled and reloaded from disk using the [`!load`, `!unload`, `!reload` and `hard-reload`](#control) commands.

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
These plugins implement the basic functionality of PageBot beyond that provided by the code of *ameliabot*, and should usually be present in the `plugins` section of [`conf/bot.py`](#main-configuration-file) and loaded at all times, in order for the bot to work properly.

### `runtime`
Actively performs miscellaneous tasks essential to the bot and other modules.

### `message`
Manages basic IRC message events from `xirclib` and provides the `!help` command.
* `!help` - shows information about (most) user commands.
* `conf/ignore.txt` - one `nick!user@host` wildcard expression per line to ignore all messages from.

### `nickserv`
Communicates with the network service known as NickServ on most IRC networks.
* `conf/nickserv.py` - contains network-specific information used to identify NickServ, and the bot's own password used to identify to NickServ, if it has one.

### `auth`
Provides authentication of bot administrators.
* `!id PASS`, `!identify PASS` - cause the bot to recognise the user issuing this command as an administrator. 
* `conf/admins.txt` - one `nick!user@host` wildcard expression, or, if `identity` is installed, one access name from `conf/identity.py`, which is allowed to use admin commands.
* `conf/auth_password.txt` - the password, if any, accepted by `!identify`.

### `control`
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

### `channel`
Manages state information relating to IRC channels. Also defines the concept of a *quiet* channel: a channel is quiet if it is listed in the corresponding configuration file, or if it has mode `+m` active. Several plugins modify their behaviour to suppress frivolous messages to quiet channels.
* `conf/quiet_channels.txt` - a list of channels, one per line, which are always considered to be *quiet*.

## Support Modules
These plugins do not by themselves implement functionality useful to the user, but are required by some other plugins. Unless otherwise noted, they do not need to be explicitly installed, as they will be automatically loaded by the plugins that depend on them.

### `bridge`
Allows groups of channels - each of which is either an IRC channel or a special type of channel external to the IRC network, provided by a module such as [`minecraft`](`#minecraft`) - to be *bridged* together, such that any message sent to one will also be relayed to the others by the bot. Also causes certain commands to work in the aforementioned non-IRC channels.
* `conf/bridge.py` - one tuple (comma-separated list) of strings (which start or end with `'` or `"`) per line, each of which represents a group of channels bridged together. Each string is either an IRC channel name starting with `#` or the identifier of a non-IRC channel.
* `!online` - lists the names of users present in any channels bridged to this channel, including the channel itself if it is not an IRC channel.
* `!time`, `!date` - tells the current time and date in UTC. Only available in non-IRC channels.

### `chan_link`
Allows pairs of channels to be linked together, so that messages from one channel are relayed to the other. This is the same functionality provided by [`bridge`](#bridge), except that: it only affects IRC channels, and as such uses a somewhat different format for displaying messages; it allows finer control over the nature of the channel links; and it allows links to be created dynamically by admin commands or programmatically by other plugins. A channel link is *mutual* if messages are relayed in both directions; otherwise, they are only relayed from one channel to another. A channel link is *persistent* if it is saved in the state file so that it is re-established when the bot is restarted.
* `!add-chan-link CHAN` - [admin] creates a mutual, persistent link between this channel and `CHAN`.
* `!add-chan-link-from CHAN` [admin] creates a non-mutual, persistent link from `CHAN` to this channel.
* `!del-chan-link CHAN` - [admin] permanently removes any link involving `CHAN` and this channel.
* `!online` - lists the users in any channels linked to this channel.
* `state/chan_link_persistent.txt` - a newline-separated list of Python tuples of strings `(CHAN1, CHAN2)` representing a persistent link from `CHAN1` to `CHAN2`. The link is mutual if and only if `(CHAN2, CHAN1)` is also present in the list.

*To be completed...*

## Available Plugins

### `aop`
Automatically ops other users. When the bot has mode `+o` in a channel, this module allows the bot to automatically give `+o` to other users when they join the channel, when they issue `!update`, and when the bot joins the channel. This plugin automatically loads [`identity`](#identity).
* `conf/aop.txt` - a sequence of *channel sections*, where a *channel section* starts with a single line containing one or more channel names (each starting with `#`) separated by spaces, and is followed by a list of *user specifications*, each on a separate line. A *user specification* is a hostmask of the form `NICK!USER@HOST`, possibly including wildcard characters `*` and `?`, or an *access name* from the [`identity`](#identity) module. Each *user specification* causes the corresponding user to be automatically opped in each channel named in the corresponding *channel section*. Additional whitespace and empty lines are ignored. *Comments* start with `--` and cause the remainder of the line to be ignored.
* `!update` - give `+o` to the user issuing this command, if they do not have it and are subject to automatic op.

### `bum`
Occasionally repeats people's messages, with one word replaced with "bum". Suppressed in [*quiet*](#channel) channels. Inspired by https://github.com/ollien/buttbot.
* `static/bum_ignore.txt` - words which will *not* be replaced; generated by [PageBot-words](//github.com/joodicator/PageBot-words).

### `chanserv`
Communicates with the network services known as ChanServ on most IRC networks. Currently, this is only useful for automatically evicting ChanServ from desired channels, but more features may be added in the future.
* `conf/chanserv_password.py` - a CSV-style newline-separated list of tuples under the header `'channel', 'password'`, specifying the password (a string) to be used to gain founder-level access to each channel (a string).
* `conf/chanserv_evict.txt` - a whitespace-separated list of channels in which the bot will attempt to cause ChanServ to leave whenever it is encountered there. This can be useful on IRC networks with misconfigured services. Each channel should also have its password listed in `chanserv_password.py`.

### `chess`
Allows two-player games of chess to be played on IRC using a textual interface. This is done by connecting to [this chess engine](//github.com/joodicator/chess) through a UNIX domain socket created by [pipeserv](//github.com/joodicator/pipeserv), both of which must be installed and run separately.
* `!chess SUBCOMMAND` - issues `SUBCOMMAND` to the chess engine. See the output of `!help chess` for available subcommands.
* `state/chess` - the UNIX domain socket allowing communication with an instance of the chess engine. This must be created before the plugin is loaded.

### `convert`
Converts quantities between different measurement units.
* `!cv`, `!convert QUANTITY UNIT1 [to] UNIT2` - converts `QUANTITY` from `UNIT1` to `UNIT2`, and displays the result. `QUANTITY` is a decimal number, possibly including a decimal point, and possibly including an exponent in scientific E-notation - for example, `!convert 3.232e-35 m to Planck lengths`. The word `to` is optional. See `!help convert` for the available units.

### `debug`
Displays on the console extended information about the internals of the bot's operation. When loaded, shows most *untwisted* events passing through the bot's primary `Mode` instance, and possibly also those passing through auxiliary `Mode` instances created by plugins. Events which occur so frequently as to make the console unreadable are suppressed.

### `dice`
Simulates dice rolls and other random choices. Uses Python 2's standard random number generator, which in turn uses either an internal pseduo-random number generation algorithm or a source of entropy provided by the operating system.
* `!r`, `!roll MdN+K`, `!roll MdN-K` - Simulate rolling `M` dice, each with `N` sides, and add or subtract `K` to the result.
* `!r`, `!roll {WEIGHT1: CHOICE1, WEIGHT2: CHOICE2, ...}` - Return one of the given `CHOICE`s, each of which has probability proportional to its associated `WEIGHT` of being chosen. The `WEIGHT: ` prefix may be omitted, in which case the weight defaults to 1.

Multiple dice rolls or choices may be made in the same `!roll` invocation by writing them one after the other, possibly separated by other text, which will be repeated in the result. Moreover, the two types of random sampling may be mixed together, and lists of choices may be nested within each other. See `!help roll` for more information.

*To be completed...*
