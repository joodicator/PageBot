# PageBot

A general-purpose, modular, extensible IRC robot written in Python 2. Includes numerous plugins for various different purposes.

## Contents
1. [Dependencies](#dependencies)
2. [Contributing](#contributing)
3. [License](#license)
4. [Installation and Usage](#installation-and-usage)
5. [Overview of Files](#overview-of-files)
6. [Main Configuration File](#main-configuration-file)
7. [Core Modules](#core-modules)
8. [Support Modules](#support-modules)
9. [Available Plugins](#available-plugins)
    1. [Admin Tools](#admin-tools)
        - [`aop`](#aop) - give channel op status to users.
        - [`chanserv`](#chanserv) - keep ChanServ out of channels.
        - [`debug`](#debug) - print debugging information to the console.
        - [`flood`](#flood) - defend against flooding attacks.
        - [`invite`](#invite) - join channels when invited.
    2. [User Tools](#user-tools)
        - [`convert`](#convert) - convert between units of measurement.
        - [`dice`](#dice) - simulate dice rolling, etc.
        - [`kakasi`](#kakasi) - transliterate Japanese characters.
        - [`mirror`](#mirror) - copy impermanent URLs for posterity.
        - [`qdbs`](#qdbs) - show updates from *QdbS* quote databases.
        - [`seen`](#seen) - tell when users were last seen.
        - [`tell`](#tell) - leave public messages for users.
        - [`url`](#url) - show information about URLs.
    3. [Game Tools](#game-tools)
        - [`dominions`](#dominions) - show updates from *Dominions 4: Thrones of Ascension*.
        - [`dungeonworld`](#dungeonworld) - assist with running *Dungeon World* sessions.
        - [`minecraft`](#minecraft) - connect channels to *Minecraft* servers.
        - [`terraria`](#terraria) - connect channels to *Terraria* servers.
    4. [Other Plugins](#other-plugins)

## Dependencies

### Required
* [Python](https://python.org) 2.7.
* A POSIX shell, such as [Bash](https://www.gnu.org/software/bash).

### Optional
* [BeautifulSoup 4](https://pypi.python.org/pypi/beautifulsoup4), for [`dominions`](#dominions), [`qdbs`](#qdbs) and [`url`](#url).
* [html5lib](https://pypi.python.org/pypi/html5lib), for [`dominions`](#dominions), [`qdbs`](#qdbs) and [`url`](#url).
* [google-api-python-client](//github.com/google/google-api-python-client), for some features of [`url`](#url).
* [KAKASI](http://kakasi.namazu.org), for [`kakasi`](#kakasi).
* [joodicator/pipeserve](//github.com/joodicator/pipeserve), for [`minecraft`](#minecraft) and [`chess`](#chess).
* [joodicator/mcchat2](//github.com/joodicator/mcchat2), for [`minecraft`](#minecraft).
* [joodicator/chess](//github.com/joodicator/chess), for [`chess`](#chess).

## Contributing
Bug reports and feature requests may be submitted to this repository using the issue tracker, and are more than welcome. Pull requests fixing bugs are welcome, and pull requests adding or changing features will be duly considered.

## License

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
5. Run `main`, and the bot will connect to the configured IRC server and print a log of sent and received IRC messages to `stdout`. The bot currently has no built-in daemon mode, but it can be left running in the background using a terminal multiplexer such as GNU `screen`. To restart the bot, issue `Ctrl+C` once and wait or twice to terminate it. It may also be caused to restart using the admin command [`!restart`](#control), or with a particular quit message using [`!quit MESSAGE`](#control).
6. There are at least three ways to cause the bot to join IRC channels:
    1. Configure the channels statically in [`conf/bot.py`](#main-configuration-file), and they will be automatically joined.
    2. If the [`invite`](#invite) plugin is loaded: configure the channels dynamically (while the bot is running) using the IRC `INVITE` and `KICK` commands to cause it to join or leave channels. You must usually be a channel operator to do this. This will be remembered when the bot is restarted.
    3. If you are a bot administrator, use the [`!join` and `!part`](#control) commands in a channel or by private message. These settings will *not* be remembered when the bot is restarted.
7. While the bot is running, if you are an administrator, modules can be dynamically installed, uninstalled and reloaded from disk using the [`!load`, `!unload`, `!reload` and `!hard-reload`](#control) commands.

## Overview of Files
* **`main`** - The POSIX shell script used to run PageBot.
* **`conf/`** - User configuration files.
* **`conf/templates/`** - Templates for files in `conf/`.
* **`state/`** - Data saved dynamically by PageBot to persist when it is restarted.
* **`static/`** - Static data files which are not program code.
* **`page/`** - Plugins and support modules that extend ameliabot to implement most of PageBot's functionality.
* **`tools/`** - Auxiliary programs, mostly used for testing and development.
* **`ameliabot/`** - A heavily modified version of http://sourceforge.net/projects/ameliabot/.
* **`lib/untwisted/`** - A modified version of http://sourceforge.net/p/untwisted/.
* **`lib/xirclib.py`** - A lightweight implementation of IRC for untwisted.

## Main Configuration File
This file is located at `conf/bot.py` and configures the core features of the bot. It is a Python 2.7 source file which may bind the following names at the top level:

| Name          | Type                      | Description                                                                            |
|---------------|---------------------------|----------------------------------------------------------------------------------------|
|`server`       |`str`                      | The hostname of the IRC server to which to connect. |
|`port`         |`int`                      | The port number to which to connect. Usually 6667. Plain IRC connections must be accepted on this port, as PageBot does not (currently) support SSL. |
|`nick`         |`str`                      | The nickname for the bot to use on IRC. |
|`user`         |`str`                      | The username for the bot to use on IRC. |
|`name`         |`str`                      | The "real name" for the bot to use on IRC. |
|`host`         |`str`                      | The bot's own hostname reported to the IRC server. In practice, this is usually ignored by the server, and can be anything. |
|`channels`     |`list` of `str`            | The channels to join automatically after connecting. |
|`plugins`      |`list` of `str`            | The plugins to load automatically. |
|`timeout`      |`Number`                   | The number of seconds of latency after which the connection will time out and restart. |
|`bang_cmd`     |`True` or `False`          | If False, bot commands must be prefixed by `NICK: `, where `NICK` is the bot's nick. This is useful if there are multiple bots present which may respond to commands of the form `!COMMAND`. |
|`flood_limits` |`list` of `(Number,Number)`| Each list item `(lines, seconds)` enforces a serverbound flood protection rule preventing the bot from sending more than `lines` IRC messages in any period of `seconds` seconds. This is useful to prevent the bot from being disconnected by an IRC server's flood protection mechanisms. In practice, IRC servers often have multiple such mechanisms, hence the need for multiple rules. |

If any of these are not specified, the default values in [`main.py`](main.py) or [`ameliabot/amelia.py`](ameliabot/amelia.py) (in that order) are used.

## Core Modules
These plugins implement the basic functionality of PageBot beyond that provided by the code of *ameliabot*, and should usually be present in the `plugins` section of [`conf/bot.py`](#main-configuration-file) and loaded at all times, in order for the bot to work properly. Additionally, the user may wish to edit some of the configuration files listed here to use certain features.

#### `runtime`
Actively performs miscellaneous tasks essential to the bot and other modules.

#### `message`
Manages basic IRC message events from `xirclib` and provides the `!help` command.
* **`!help`** - shows information about (most) user commands.

#### `nickserv`
Communicates with the network service known as NickServ on most IRC networks.
* **`conf/nickserv.py`** - contains network-specific information used to identify NickServ, and the bot's own password used to identify to NickServ, if it has one.

#### `auth`
Provides authentication of bot administrators. Requires [`identity`](#identity) to be separately installed for certain features.
* **`!id PASS`**, **`!identify PASS`** - cause the bot to recognise the user issuing this command as an administrator. 
* **`conf/admins.txt`** - one `nick!user@host` wildcard expression, or, if `identity` is installed, one access name from `conf/identity.py`, which is allowed to use admin commands.
* **`conf/auth_password.txt`** - the password, if any, accepted by `!identify`.

#### `control`
Provides admin commands for control of the bot's basic functions.
* **`!echo MSG`** - [admin] repeat `MSG` in the same channel or back by PM to the sender.
* **`!raw CMD`** - [admin] send `CMD` to the server as a [raw IRC message](https://tools.ietf.org/html/rfc2812).
* **`!msg TARGET MSG`** - [admin] say `MSG` to the nick or channel given by `TARGET`.
* **`!act TARGET MSG`** - [admin] send `MSG` as a [CTCP `ACTION` message](http://www.mirc.org/mishbox/reference/ctcpref.htm) (as generated by `/me` in most IRC clients).
* **`!j CHAN`**, **`!join CHAN`** - [admin] join the given channel.
* **`!part [CHAN]`** - [admin] leave the given channel, or the current channel if none is given.
* **`!quit [MSG]`** - [admin] quit the network, with the given quit message, if any. If the bot's process is not manually terminated within a few seconds of issuing this command, it will automatically reconnect.
* **`!restart`** - [admin] quit the network with a quit message indicating that the bot is restarting.
* **`!eval EXPR`** - [admin] show the value of the Python expression `EXPR` (with `bot` and all loaded modules in scope).
* **`!exec STMT`** - [admin] execute the Python statement `STMT` (with `bot` and all loaded modules in scope).
* **`!yield ACTION`** - [admin] perform the given asynchronous untwisted action and show the return value when (and if) it completes.
* **`!load MOD`** - [admin] install the plugin module named `MOD`, usually from a Python file in `page/`.
* **`!unload MOD`** - [admin] uninstall the plugin module named `MOD`.
* **`!reload`** - [admin] reload the code of all reloadable modules (those in `page/` and certain others) from their source files, and reinstall all installed plugin modules, possibly retaining the state of the old instances.
* **`!hard-reload`** - [admin] as `!reload`, but discard as much old state information as possible, thus resetting the state of most modules.

#### `channel`
Manages state information relating to IRC channels. Also defines the concept of a *quiet* channel: a channel is quiet if it is listed in the corresponding configuration file, or if it has mode `+m` active. Several plugins modify their behaviour to suppress frivolous messages to quiet channels.
* **`conf/quiet_channels.txt`** - a list of channels, one per line, which are always considered to be *quiet*.

## Support Modules
These plugins do not by themselves implement functionality useful to the user, but are required by some other plugins. Unless otherwise noted, they do not need to be explicitly installed, as they will be automatically loaded by the plugins that depend on them. However, many of them do have configuration files that may need to be edited by the user.

### Infrastructure

#### `bridge`
Allows groups of channels - each of which is either an IRC channel or a special type of channel external to the IRC network, provided by a module such as [`minecraft`](`#minecraft`) - to be *bridged* together, such that any message sent to one will also be relayed to the others by the bot. Also causes certain commands to work in the aforementioned non-IRC channels.
* **`conf/bridge.py`** - one tuple (comma-separated list) of strings (which start or end with `'` or `"`) per line, each of which represents a group of channels bridged together. Each string is either an IRC channel name starting with `#` or the identifier of a non-IRC channel.
* **`conf/substitute.py`** - a newline-separated list of tuples of strings `'CONTEXT', 'OLD_NAME', 'NEW_NAME'` representing substitutions to be made to messages from non-IRC channels before they are broadcast to other bridged channels. When `CONTEXT` is the name of a compatible non-IRC channel, any occurrence of the word `OLD_NAME` will be replaced with `NEW_NAME`. This can be useful to prevent IRC users from being unnecessarily highlighted by messages originating elsewhere containing their IRC nicks - for example, a message that the user wrote under the same name on a Minecraft server. Whether this is supported, and the exact manner of replacement, depends on the type of channel.
* **`!online`** - lists the names of users present in any channels bridged to this channel, including the channel itself if it is not an IRC channel.
* **`!time`**, **`!date`** - tells the current time and date in UTC. Only available in non-IRC channels.

#### `chan_link`
Allows pairs of channels to be linked together, so that messages from one channel are relayed to the other. This is the same functionality provided by [`bridge`](#bridge), except that: it only affects IRC channels, and as such uses a somewhat different format for displaying messages; it allows finer control over the nature of the channel links; and it allows links to be created dynamically by admin commands or programmatically by other plugins. A channel link is *mutual* if messages are relayed in both directions; otherwise, they are only relayed from one channel to another. A channel link is *persistent* if it is saved in the state file so that it is re-established when the bot is restarted.
* **`!add-chan-link CHAN`** - [admin] creates a mutual, persistent link between this channel and `CHAN`.
* **`!add-chan-link-from CHAN`** [admin] creates a non-mutual, persistent link from `CHAN` to this channel.
* **`!del-chan-link CHAN`** - [admin] permanently removes any link involving `CHAN` and this channel.
* **`!online`** - lists the users in any channels linked to this channel.
* **`state/chan_link_persistent.txt`** - a newline-separated list of Python tuples of strings `(CHAN1, CHAN2)` representing a persistent link from `CHAN1` to `CHAN2`. The link is mutual if and only if `(CHAN2, CHAN1)` is also present in the list.

#### `limit`
Implements per-user flood protection for user commands and other actions causing processor or network usage, to curtail denial-of-service attacks against the bot. When a user exceeds the limits defined in [`flood.py`](page/flood.py), they are ignored for a period of time and given a notification of this.

#### `modal`
Allows different plugins to share access to limited resources associated with IRC channels, such as the right to respond to a command whose name is the same for two different plugins. Access is mediated based on a centrally managed *mode* determining which plugin has access at any given time. See comments in [`modal.py`](page/modal.py) for more information.

### External API Access

#### `imgur`
Provides programmatic access to [`Imgur`](http://imgur.com)'s API.
* **`conf/imgur_client_id.txt`** - the `client_id` associated with the account used to access Imgur's API. According to Imgur's instructions, a different `client_id` should be used for each separate instance of the bot. See https://api.imgur.com/ for more information.

#### `pastebin`
Provides programmatic access to [Pastebin](http://pastebin.com)'s API.
* **`conf/pastebin_dev_key.txt`** - the Developer API Key associated with the account used to access Pastebin's API. See http://pastebin.com/api/ for more information.

#### `youtube`
Provides programmatic access to [YouTube](http://youtube.com)'s API. Requires [google-api-python-client](//github.com/google/google-api-python-client) to be separately installed in the same Python distribution used to run the bot.
* **`conf/youtube_api_key`** - the developer key used to access YouTube's Data API version 3. See https://developers.google.com/youtube/v3/getting-started for more information.

### Other Modules

#### `identity`
Manages sets of credentials used to recognise particular IRC users.
* **`conf/identity.py`** - a Python 2.7 source file whose top-level bindings of the form `NAME = [CRED1, CRED2, ...]` each define an *access name* `NAME` referring to a particular person, and the *credentials* `CRED1, CRED2, ...` used to authenticate them. An IRC user may be successfully recognised as belonging to an access name if the user satisfies *any* one of the credentials, which may take any of the following forms:

    Format                          | Criteria
    --------------------------------|----------
    `('hostmask', 'NICK!USER@HOST')`| The user's IRC nick, user and hostnames must match the given hostmask, which may include wildcard characters `*` and `?`. This must be used with care, as there are a number of subtleties involved in the assignment of IRC usernames and hostnames; however, a combination of `*!USER@HOST` with no additional wildcards is *usually* safe.
    `('nickserv', 'ACCOUNT')`       | The user must be identified to NickServ using the given account name. Currently, it is assumed that the user's nick is always equal to their account name, as is the case on some but not all IRC networks.
    `('prev_hosts', COUNT)`         | The user's `USER@HOST` equals one of the `COUNT` most recent recorded values which successfully identified to this access name by *any* method. This can be useful, in combination with a `'nickserv'` credential, to allow a user to still be recognised when NickServ is absent from the network or the user has not yet manually identified. A reasonable value for `COUNT` is `3`.
    `('access', 'NAME')`            | The user is identified as belonging to another access name, which validates this access name by proxy.

* **`state/identity_hosts.json`** - records needed to implement the `'prev_hosts'` credential. A JSON object `{'NAME1': ['USER11@HOST11', 'USER12@HOST12', ...], 'NAME2': ['USER21@HOST21', 'USER22@HOST22', ...], ...}` giving the most recent identified hosts, in chronological order and starting with the least recent, for each access name on record.

#### `util`
Provides various miscellaneous classes and functions shared by many different modules.

## Available Plugins

### Admin Tools

#### `aop`
Automatically ops other users. When the bot has mode `+o` in a channel, this module allows the bot to automatically give `+o` to other users when they join the channel, when they issue `!update`, and when the bot joins the channel. This plugin automatically loads [`identity`](#identity).
* **`conf/aop.txt`** - a sequence of *channel sections*, where a *channel section* starts with a single line containing one or more channel names (each starting with `#`) separated by spaces, and is followed by a list of *user specifications*, each on a separate line. A *user specification* is a hostmask of the form `NICK!USER@HOST`, possibly including wildcard characters `*` and `?`, or an *access name* from the [`identity`](#identity) module. Each *user specification* causes the corresponding user to be automatically opped in each channel named in the corresponding *channel section*. Additional whitespace and empty lines are ignored. *Comments* start with `--` and cause the remainder of the line to be ignored.
* **`!update`** - give `+o` to the user issuing this command, if they do not have it and are subject to automatic op.

#### `chanserv`
Communicates with the network services known as ChanServ on most IRC networks. Currently, this is only useful for automatically evicting ChanServ from desired channels, but more features may be added in the future.
* **`conf/chanserv_password.py`** - a CSV-style newline-separated list of tuples under the header `'channel', 'password'`, specifying the password (a string) to be used to gain founder-level access to each channel (a string).
* **`conf/chanserv_evict.txt`** - a whitespace-separated list of channels in which the bot will attempt to cause ChanServ to leave whenever it is encountered there. This can be useful on IRC networks with misconfigured services. Each channel should also have its password listed in `chanserv_password.py`.

#### `debug`
Displays on the console extended information about the internals of the bot's operation. When loaded, shows most *untwisted* events passing through the bot's primary `Mode` instance, and possibly also those passing through auxiliary `Mode` instances created by plugins. Events which occur so frequently as to make the console unreadable are suppressed.

#### `flood`
Employs heuristic measurements to detect when a user is maliciously flooding a channel with repetitive messages, either alone or in concert with other users. This is especially useful against automated spam-bot attacks. When such behaviour is detected, the bot will ban and kick the offending user or perform some other action according to its configuration.
* **`conf/flood_channels.py`** - A CSV-style newline-separated list of tuples under the header `'channel', 'punish_commands'`, whose columns have the following meanings:

    Field             | Type                          | Description
    ------------------|-------------------------------|-------------
    `channel`         | `str`                         | The name of a channel, which should start with `#`, in which the bot will actively defend against flooding attacks.
    `punish_commands` | `list` of `str`, or `DEFAULT` | The sequence of commands that the bot shall issue when a flooding user is detected. Each item is a raw IRC command, possibly including format specifiers as defined below. `DEFAULT` is equivalent to `['MODE %(chan)s +b %(hostmask)s', 'KICK %(chan)s %(nick)s :%(reason)s']`.

    The following format specifiers may occur in `punish_commands`:

    Specifier      | Description
    ---------------|-------------
    `%(nick)s`     | The nickname of the flooding user.
    `%(user)s`     | The username of the flooding user.
    `%(host)s`     | The hostname of the flooding user.
    `%(hostmask)s` | `*!%(user)s@%(host)s` if the username does not start with `~`, or otherwise `*!*@%(host)s`.
    `%(chan)s`     | The channel in which the flooding occurred.
    `%(reason)s`   | A message describing why the user was targeted. Currently, this is always `Flooding detected.`

* **`tools/test_flood.py`** - a console program which reads from standard input an [irssi](https://irssi.org)-formatted IRC log and simulates the behaviour of the `flood` module on messages from the log. The *score* of each message, which is a measure of how close it is being considered part of a flood, is shown next to each message, and any message whose score exceeds the threshold is separated from its score by an exclamation mark and highlighted in red. This is useful for tuning the parameters in [`flood.py`](page/flood.py) to eliminate false positives and false negatives.

#### `invite`
Causes the bot to join channels when invited, and indefinitely remembers `INVITE`d and `KICK`ed channels.
* **`INVITE`** messages, issued in most clients by `/invite NICK [CHANNEL]`, cause the bot to join the corresponding channel and save this channel in a dynamic auto-join list that persists when the bot is restarted.
* **`KICK`** messages, issued in most clients by `/kick [CHANNEL] NICK [MESSAGE]`, remove the corresponding channel from the auto-join list if it is present.
* **`state/channel_invite.txt`** - a newline-separated list of channels which the bot has been invited to and will automatically join.

### User Tools

#### `convert`
Converts quantities between different measurement units.
* **`!cv`**, **`!convert QUANTITY UNIT1 [to] UNIT2`** - converts `QUANTITY` from `UNIT1` to `UNIT2`, and displays the result. `QUANTITY` is a decimal number, possibly including a decimal point, and possibly including an exponent in scientific E-notation - for example, `!convert 3.232e-35 m to Planck lengths`. The word `to` is optional. See `!help convert` for the available units.

#### `dice`
Simulates dice rolls and other random choices. Uses Python 2's standard random number generator, which in turn uses either an internal pseduo-random number generation algorithm or a source of entropy provided by the operating system.
* **`!r`**, **`!roll MdN+K`**, **`!roll MdN-K`** - Simulate rolling `M` dice, each with `N` sides, and add or subtract `K` to the result.
* **`!r`**, **`!roll {WEIGHT1: CHOICE1, WEIGHT2: CHOICE2, ...}`** - Return one of the given `CHOICE`s, each of which has probability proportional to its associated `WEIGHT` of being chosen. The `WEIGHT: ` prefix may be omitted, in which case the weight defaults to 1.

Multiple dice rolls or choices may be made in the same `!roll` invocation by writing them one after the other, possibly separated by other text, which will be repeated in the result. Moreover, the two types of random sampling may be mixed together, and lists of choices may be nested within each other. See `!help roll` for more information and additional features.

#### `kakasi`
Shows the Hepburn romanisation of Japanese text. Where there is more than one possible reading of a sequence of kanji, the alternatives are shown within braces. Any messages detected to contain a majority of Japanese text will be automatically transliterated. Requires [KAKASI](http://kakasi.namazu.org/) and in particular the shared library `libkakasi.so` to be present on the system.
* **`!rj`**, **`!romaji TEXT`** - explicitly transliterate `TEXT` from Japanese characters to romaji.
* **`page/kakasi_lib.py`** - support module implementing the reusable library component of `kakasi`.

#### `mirror`
Automatically copies resources from URLs known to expire after a short time, for posterity. When such a URL is posted in a channel, the bot will copy it to a permanent location and provide a link to the copy. Currently, this consists of copying PNG, GIF or JPEG images hosted on [4chan](http://4chan.org) to [Imgur](http://imgur.com), but more schemes may be added in future. This plugin requires the [`imgur`](#imgur) module to be configured with a valid `client_id`.

#### `qdbs`
Notifies channels and users of new entries posted to a [QdbS](http://www.qdbs.org) quote database. This plugin automatically loads the [`identity`](#identity) module. Requires [BeautifulSoup 4](https://pypi.python.org/pypi/beautifulsoup4) and [html5lib](https://pypi.python.org/pypi/html5lib).
* **`conf/qdbs_public.py`** - Allows channels to be notified when a new quote has been approved and is publically visible. A CSV-style newline-separated list of Python tuples, under the header `'channel', 'index_url', 'remote_index_url'`, whose columns have the following meanings:

    Field               | Type  | Description
    --------------------|-------|-------------
    `channel`           | `str` | The IRC channel to be notified of public updates.
    `index_url`         | `str` | The URL of the index page of the quote database, to be accessed by the bot. This may refer to a host on a private network local to the machine on which the bot is running.
    `remote_index_url`  | `str` | The URL of the index page of the quote database, to be posted in the channel. This should usually be a URL accessible from the public Internet, and must refer to the same quote database as `index_url`.

* **`conf/qdbs_private.py`** - Allows certain IRC users, who are authenticated by [`identity`](#identity), to be notified by private message when a new quote has been submitted for approval. A CSV-style newline-separated list of Python tuples under the header `'access_name', 'qdb_username', 'qdb_password', 'admin_url', 'remote_admin_url'`, whose columns have the following meanings:

    Field               | Type  | Description
    --------------------|-------|-------------
    `access_name`       | `str` | The *access name* configured in `conf/identity.py` of the user who is to receive notifications.
    `qdb_username`      | `str` | The username of the QdbS admin account of this user.
    `qdb_password`      | `str` | The password hash cookie, set by QdbS upon logging in, of the admin account of this user.
    `admin_url`         | `str` | The URL of the admin page of the quote database, to be accessed by the bot. This may refer to a host on a private network local to the machine on which the bot is running.
    `remote_admin_url`  | `str` | The URL of the admin page of the quote database, to be sent by PM to the user. This should usually be a URL accessible from the public Internet, and must refer to the same quote database as `admin_url`.

* **`state/qdbs.json`** - records state information for this plugin, including the last quote that each channel or user has been notified of.

#### `seen`
Tells when users were last seen by the bot in a channel.
* **`!seen NICK[!USER@HOST]`** - shows information about the most recently observed activity in this channel of any user matching the given nickname or full hostmask, which may include wildcard characters `*` and `?`.
* **`state/seen.json`** - the database recording the last activity of every user in every channel.

#### `tell`
Allows users to leave public messages for each other in channels. This is similar to the service provided by *MemoServ* on many IRC networks, but can be useful when MemoServ is not available, or when the recipient may not be logged in to a NickServ account or may not notice that they have a memo.

* User commands:
    * **`!tell USER MSG`** - leave a message to be delivered to `USER` when they are next seen in this channel. If `USER` contains `!` or `@`, it must match the recipient's `NICK!USER@HOST`; otherwise, it must only match their `NICK`; in either case, it may contain wildcard characters `*` and `?`. Additionally, `USER` may consist of multiple alternatives separated by `/` (with no spaces) - the message will be delivered to the first one of these which is seen.
    * **`!tell USER1[, USER2, ...]: MSG`** - leave multiple copies of the same message, each for one of several recipients. A comma-separated list of recipients, each accepting the same syntax as above, terminated by a colon, is used to address the message.
    * **`!untell [USER1, USER2, ...]`** - if a list of recipients is given, delete the last message sent in this channel, to each of them, by the user issuing this command. Otherwise, delete the last such message sent to any recipient. If given, a recipient specification must equal exactly that used with `!tell` to send the message.
    * **`!dismiss [NICK[!USER@HOST]]`** - delete the least recent pending message in this channel addressed to the user issuing this command which is from the given `NICK` or `NICK!USER@HOST` if specified, or from any sender. This can be useful when the recipient of a message has observed the message being sent, is already aware of its contents, and wishes to avoid it being repeated. Up to 3 additional `!dismiss` commands may be included on the same line as this command.
    * **`!undismiss [NICK[!USER@HOST]]`** - restore the message which was most recently deleted using `!dismiss`, is from the given `NICK` or `NICK!USER@HOST` if specified, or from any sender. This can be useful to reverse an accidental usage of `!dismiss`.
    * **`!read`** - if used in a channel, delivers any messages addressed to the user issuing this command. If used by PM, delivers any messages which have been designated to be read privately. This only happens when a user has too many messages to comfortably display in a channel, and after the user is explicitly notified of this in-channel.

* Admin commands:
    * **`!tell? [QUERY]`** - list all pending messages in the current channel (or in all channels if used by PM) where the sender's `NICK!USER@HOST`, the recipient specification, or the message content itself contains the text of the given `QUERY` (or all such messages if none is given).
    * **`!tell+ FROM_NICK!USER@HOST, RECIPIENT, #CHAN, YYYY-MM-DD HH:MM, MESSAGE`** - insert an artifical pending message into the record, with the given sender, recipient specification, channel of delivery, sent time, and message content.
    * **`!tell- INDEX1 INDEX2 ...`** - delete some messages according to the index numbers displayed with them in the output from `!tell?`. Note that the assignment of index numbers to messages changes in different channels, when sending commands by PM, and after messages are created or deleted.
    * **`!tell-clear`** - delete all pending messages and other state information (except for the states accessible via `!tell-undo` and `!tell-redo`).
    * **`!tell-undo`** - restore the plugin's state to how it was before the most recent change (which was not caused by `!tell-undo` or `!tell-redo`).
    * **`!tell-redo`** - restore the plugin's state to how it was before the most recent use of `!tell-undo`.

* Files:
    * **`state/tell.pickle`** - the database of pending messages and other information, in the form of a [pickled](https://docs.python.org/2/library/pickle.html) Python 2.7 object.

If the user issuing `!tell` or `!untell` is a bot administrator, the arguments of the command may be prefixed with the name of a channel so that it affects that channel rather than any current channel. Additionally, the commands `!tell`, `!untell`, `!tell?`, `!tell+`, `!tell-`, `!tell-clear`, `!tell-undo` and `!tell-redo` may equivalently be written as `!page`, `!unpage`, `!page?`, `!page+`, `!page-`, `!page-clear`, `!page-undo` and `!page-redo`, respectively.

#### `url`
Shows information about URLs mentioned in the channel. The title, file size and MIME type are shown, if available. For links to images, the "best guess" provided by [Google](http://google.com)'s reverse image search is also shown. If the [`imgur`](#imgur) module is configured with a valid client ID, additional information is shown for Imgur URLs. If the [`youtube`](#youtube) module is configured with a valid API key, additional information is shown for YouTube videos. Requires [BeautifulSoup 4](https://pypi.python.org/pypi/beautifulsoup4) and [html5lib](https://pypi.python.org/pypi/html5lib).
* **`!title`**, **`!url`** - show information about each URL in the most recent channel message containing URLs. The message in question is then removed from the record, such that `!url` issued again will show information about the second most recent such message, and so forth.
* **`!title`** **`!url TEXT`** - show information about each URL occurring in the given `TEXT`.
* **`page/url_collect.py`** - a support module implementing the component of `url` responsible for maintaining a public list of recently-mentioned URLs in each channel, accessible to other modules and independent of the main functionality of `!url`.

Up to 5 additional `!url` invocations, introduced by `!` as usual, may be included on the same line as the first `!url` command. This can be useful to view the titles of several recently mentioned URLs at once.

### Game Tools

#### `dominions`
Displays updates from [Dominions 4: Thrones of Ascension](http://www.illwinter.com/dom4) multiplayer servers. The game must be hosted using Dominion's TCP server, with the `--statuspage` option used to generate an HTML document accessible to the bot by HTTP or in the local file system. The bot will periodically read this document to discover updates in the game's status. See [this document](http://www.illwinter.com/dom4/startoptions.pdf) for more information about the command-line options of Dominions 4. Requires [BeautifulSoup 4](https://pypi.python.org/pypi/beautifulsoup4) and [html5lib](https://pypi.python.org/pypi/html5lib).
* **`!dom+ URL1 URL2 ...`** - [admin] add games to be monitored in this channel. Each `URL` must give the location of a corresponding status page; supported URL schemes include `http://`, `https://`, and `file://`. Whenever the current turn advances, the bot will send a message to the channel. Moreover, if the bot can change the channel's topic, it will add a section showing the turn number and which non-AI players have taken their turns.
* **`!dom?`** - [admin] show the number, URL and (if known) name of each game being monitored in this channel.
* **`!dom- SPEC1 SPEC2 ...`** - [admin] remove monitored games from this channel. Each `SPEC` is either a URL as in `!dom+` or a game number as displayed by `!dom?`.
* **`!turn`** - display the turn number, and which non-AI players have taken their turns, in each game monitored in this channel.
* **`state/dominions.json`** - the dynamic configuration, cache, and other information saved by the bot.

The commands `!dom+`, `!dom-` and `!dom?` have the special property that they may be followed by a new command (introduced with the `!` character as usual) on the same line, for convenience when issuing multiple commands at once.

#### `dungeonworld`
Assists with running games of [Dungeon World](http://www.dungeon-world.com) on IRC. Supplements the functionality of the [`dice`](#dice) plugin, which should be separately installed. Requires the [`pastebin`](#pastebin) module to be configured with a valid developer key.
* **`!missed-rolls`** - shows a tally of the *move rolls* which were *missed* in this channel, grouped by nick, since the last time this command was issued. In Dungeon World and related games, a *move roll* is a roll involving a number of 6-sided dice such that exactly 2 dice are used in the result - for example: `2d6`, `2d6+1`, `b2[3d6]` or `w2[3d6-1]`; and such a roll is *missed* if its result is less than 7. This is useful for recording the XP that characters gain for failed moves at the end of a session.
* **`!insert-missed-roll [NICK [LABEL]]`** - insert an artificial missed roll into the record. If specified, the roll is attributed to `NICK`, or otherwise it is attributed to the user issuing this command. If a `LABEL` is given, this will be used later to describe the roll when listing missed rolls.
* **`!delete-missed-roll [NICK]`** - delete from the record the most recent *matching* group of missed rolls. A group of rolls consists of all the rolls made on the same line, i.e. in a single IRC message. If `NICK` is specified, a roll is *matching* if it was made by `NICK`; otherwise, every roll is *matching*.
* **`state/dungeonworld_rolls.txt`** - a newline-separated list of Python tuples `(MISSES, ROLLS, CHAN, (NICK,USER,HOST), LABEL)` each representing a group of *move rolls*:

    Index   | Field                 | Type              | Description   |
    --------|-----------------------|-------------------|---------------|
    0       | `MISSES`              | `int`             | Number of *move rolls* in group which *missed*. |
    1       | `ROLLS`               | `int`             | Total number of *move rolls* in group. |
    2       | `CHAN`                | `str`             | Channel where rolls were made. |
    3       | `(NICK,USER,HOST)`    | `tuple` of `str`  | The user who made the rolls. |
    4       | `LABEL`               | `str`             | Usually the result message from `!roll`. |

#### `minecraft`
Relays messages between [Minecraft](https://minecraft.net/) servers and other channels. The plugin connects to Minecraft servers via [`pipeserve`](//github.com/joodicator/pipeserve) and [`mcchat2`](//github.com/joodicator/mcchat2), both of which must be installed and run separately. The [`bridge`](#bridge) plugin must also be separately installed, and configured to connect Minecraft servers to other channels.
* **`conf/minecraft.py`** - a list of Minecraft server connections specified by a CSV-style newline-separated list of tuples under the header `'name', 'address', 'family', 'display'`, whose columns have the following meanings:

    Field       | Type                              | Description
    ------------|-----------------------------------|------------
    `name`      | `str`                             | The name of the special channel representing this server, to be used with `bridge`. Must begin with an alphanumeric character.
    `address`   | `str` or `(str,int)`              | The address of the socket created by [`pipeserve`](//github.com/joodicator/pipeserve) giving access to the instance of [`mcchat2`](//github.com/joodicator/mcchat2) for this server. This should usually be a UNIX domain socket, in which case it is a string giving the filename of the socket; but it may also be the hostname and port number of a TCP/IP socket.
    `family`    | `AF_UNIX`, `AF_INET` or `AF_INET6`| The address family of the socket address given in `address`. This must be `AF_UNIX` if it is the path of a UNIX domain socket, or `AF_INET` or `AF_INET6` if it gives a TCP/IPv4 or TCP/IPv6 address. Note that these are the names of constants and not strings, e.g. `AF_UNIX` and not `'AF_UNIX'`.
    `display`   | `str` or `None`                   | A user-readable name to be used to refer to this server in case a name cannot be retrieved from the server's query interface. The server name and the availability of the query interface can both be set in [server.properties](http://minecraft.gamepedia.com/Server.properties). If not specified, the identifier from `name` will be used as a default.

#### `terraria`
Relays messages between [Terraria](https://terraria.org/) servers and other channels. The [`bridge`](#bridge) plugin must also be separately installed, and configured to connect Terraria servers to other channels.
* **`conf/terraria.py`** - a CSV-style newline-separated list of Python tuples representing Terraria servers to which the bot will connect, under the header `'name', 'address', 'user', 'password', 'display'`, whose columns have the following meanings:

    Field       | Type                  | Description
    ------------|-----------------------|-------------
    `name`      | `str`                 | The name of the special channel used to identify this server when configuring [`bridge`](#bridge). Must start with an alphanumeric character.
    `address`   | `tuple` of `str`,`int`| A tuple `(HOST, PORT)` giving the hostname and port number of the server.
    `user`      | `str`                 | The name that the bot shall use to connect to the server. This should be distinct from the name of any other character. A good choice is the bot's own IRC nick.
    `password`  | `str`                 | The password required to connect to the server. If no password is required, this may be left as the empty string, `''`.
    `display`   | `str`                 | A user-readable name to be used to refer to the server in case the world name cannot be retrieved from it.
* **`state/terraria.json`** - cached information about Terraria servers, including the last known protocol version used by each server. 

### Other Plugins

#### `chess`
Allows two-player games of chess to be played on IRC using a textual interface. This is done by connecting to [this chess engine](//github.com/joodicator/chess) through a socket created by [pipeserve](//github.com/joodicator/pipeserve), both of which must be installed and run separately.
* **`!chess SUBCOMMAND`** - issues `SUBCOMMAND` to the chess engine. See the output of `!help chess` for available subcommands.
* **`state/chess`** - the UNIX domain socket allowing communication with an instance of the chess engine. This must be created before the plugin is loaded.

#### `bum`
Occasionally repeats people's messages, with one word replaced with "bum". Suppressed in [quiet](#channel) channels. Inspired by https://github.com/ollien/buttbot.
* **`static/bum_ignore.txt`** - words which will *not* be replaced; generated by [PageBot-words](//github.com/joodicator/PageBot-words).

#### `hue`
Whenever onamatapoeic laughter is detected in the channel, the bot joins in. Suppressed in [quiet](#channel) channels.

#### `upoopia`
Allows two-player games of [Upoopia](http://www.unicorn7.org/games/game/553) to be played on IRC using a textual interface. Because of the imperfect information each player is supposed to receive, this is implemented with each player residing in separate IRC channel where private information is sent by the bot, with any other public messages being relayed between the two channels (using the [`chan_link`](#chan-link) module). The bot must be present in both channels, as may spectators, but a player should never join their opponent's channel while a game is being played.
* **`!upoopia #OTHER_CHAN [COLOUR]`** - initiate a game of Upoopia against an opponent residing in `#OTHER_CHAN`. To start a game, both players must have `+o` in their respective channels, and both must issue this command against the other channel. Each player may indicate their preferred `COLOUR`, either `b`/`blue` or `r`/`red`, with the convention that *blue* has the first move. If the preferences cannot be resolved, the colours will be assigned randomly.
* **`!r[ed]`**, **`! r[ed]`**, **`!move r[ed] DIR NUM`** - make a move by using a red die of value `NUM` to move the red worm `NUM` units in direction `DIR`: one of `l`/`left`, `r`/`right`, `u`/`up` or `d`/`down`.
* **`!b[lue]`**, **`! b[lue]`**, **`!move b[lue] DIR NUM`** - make a move by using a blue die of value `NUM` to move the blue worm `NUM` units in direction `DIR`: one of `l`/`left`, `r`/`right`, `u`/`up` or `d`/`down`.
* **`!xray NUM`** - make a move by sacrificing a die of the opponent's colour, of value `NUM`, in order to see their dice for the remainder of the round.
* **`!resign`** - concede defeat, ending the game in victory for the opponent.
* **`!cancel`** - end a pending or ongoing game without any result.
* **`!board`** - display the current state of the game board.
* **`page/upoopia_lib.py`** - a support module implementing the reusable library component of `upoopia`.
