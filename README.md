# OSC-kreuz

The osc-kreuz serves as a central interface for OSC messages in a multiclient spatial rendering environment. It automatically translates incoming OSC messages to match the expected formats of the rendering engines and distributes it to all connected clients including UI Clients and Data clients for automation data.

# Installation

Install with pip:

```bash
pip install osc-kreuz
```

On our machines osc-kreuz is installed systemwide using:

```bash
meson setup -Dversioned_install=true --wipe build
meson install -C build
```

when using the `versioned_install` flag the installation of multiple different versions of the osc-kreuz is possible, see [here](versioned_install.md)

# OSC-Paths

On port 4455 (default value) the osc-kreuz listens on a number of paths for [position changes](#positional-data), [gain changes](#gains) and [special properties](#special-properties) for the wfs system. For most paths there exists a version of the path, where the index of the source that is changed is included in the path, and one where the index is sent as the first OSC argument.

Additionally there is the config port (4999) for the [subscription protocol](#subscription-protocol) and full copying of all outputs with the [debug mode](#debug-functions)

## Positional Data

Positional Data can be sent to the following paths, where `[position_format]` is a placeholder for a string describing the positional format, see [Supported position formats](#supported-position-formats):

| OSC-Path                                            | Argument Types |
| --------------------------------------------------- | -------------- |
| `/source/[position_format]`                         | `i[f...]`      |
| `/source/pos/[position_format]`                     | `i[f...]`      |
| `/source/position/[position_format]`                | `i[f...]`      |
| `/source/[source_index]/[position_format]`          | `[f...]`       |
| `/source/pos/[source_index]/[position_format]`      | `[f...]`       |
| `/source/position/[source_index]/[position_format]` | `[f...]`       |

## Special Properties

These Properties for the WFS system can be set using the following paths, where `[property]` is one of the currently supported properties, `doppler`, `planewave`, `angle`:

| OSC-Path                            | Argument Types |
| ----------------------------------- | -------------- |
| `/source/[property]`                | `if`           |
| `/source/[source_index]/[property]` | `f`            |

## Gains

Gains can be set individually for each rendering system, `[rendering_system]` can be either the name of the rendering system, or for some special rendering systems also an alias (`ambi` or `ambisonics` for the rendering system `ambi`,
`wfs` or `wavefieldsynthesis` for the rendering system `wfs`). There exists also a special path, where gains for the different rendering systems can be set by the index of the rendering system, starting from 0, in the order the rendering systems are declared in the config, these are the first three in the table.

| OSC-Path                                              | Argument Types |
| ----------------------------------------------------- | -------------- |
| `/source/send/spatial`                                | `iif`          |
| `/send/gain`                                          | `iif`          |
| `/source/send`                                        | `iif`          |
| `/source/send/[rendering_system]`                     | `if`           |
| `/source/send/[rendering_system]/gain`                | `if`           |
| `/send/[rendering_system]`                            | `if`           |
| `/send/[rendering_system]/gain`                       | `if`           |
| `/source/[rendering_system]`                          | `if`           |
| `/source/[rendering_system]/gain`                     | `if`           |
| `/source/[source_index]/send/[rendering_system]`      | `f`            |
| `/source/[source_index]/send/[rendering_system]/gain` | `f`            |
| `/send/[source_index]/[rendering_system]`             | `f`            |
| `/send/[source_index]/[rendering_system]/gain`        | `f`            |
| `/source/[source_index]/[rendering_system]`           | `f`            |
| `/source/[source_index]/[rendering_system]/gain`      | `f`            |

Direct Sends also have an endpoint `/source/send/direct`, but it is not really used at the moment.

## Subscription Protocol

Subcription-Port: 4999

The Subscription Protocol enables Applications to subscribe to the osc-kreuz.

The connection is initialised by a subscricption request from the client which is followed by a regular ping-message from the osc-kreuz that must by answered by a pong-message in order to keep the subscription alive. Source-Position and gain messages should be sent to port 4455 and the subcription-messages to port 4999.

### Subscribe

A client can subscribe to all position and gain messages e.g. a viewer-client during production process. Subcriptions and pong messages should be send to port 4999.
The connection is initialised via:
`/oscrouer/subscribe s i s (i i)` with s = uniqueClientName, i=listeningPort, s=coordinateFormat, i=sourceIndexInOsc(0/1), i=minUpdateIntervall
The last three arguments are optional and are set to '1 10' by default.
e.g. `/oscrouter/subscribe maxViewer 55123 xyz 1 10`
will send source-position messages to the subscribing client as follows:

- For Position
  `/source/1/xyz fff` with a max. rate of 100Hz (every 10 ms).
- For gains e.g.
  `/source/1/ambi f`

The ip-Address of the client is retrieved automatically from the udp-packet by the OSC-Router.

### ping-pong

The osc-router regularly sends the message
`/oscrouter/ping 4999` to all subscribed clients
which should be answered (to port 4999) with
`/oscrouter/pong uniqueClientName`
The uniqueClientName has to be the same as in the subcription message.
If the client does not answer to the ping message it will be erased after a certain time.

## Debug functions

Port: 4999

A copy of all outgoing osc-messages from the osc-kreuz can requested by sending:
`/oscrouter/debug/osccopy ipAddress:port` with ipAddress and listening port of the receiving machine e.g. `/oscrouter/debug/osccopy 192.168.3.2:55112`
The debug-osc messages contain the name of the target as well as ip-address and port.
To deactivate this send a message without target address: `/oscrouter/debug/osccopy`

With the message `/oscrouter/debug/verbose i` a verbosity level can be set which activates console printing of incoming and outcoming messages as well as further informations.
Set verbosity to 0 when to stop console output which can significantly slow down the system.

# Configuration

The configuration is done using a YAML-Config file, an example config file can be found in `example_configs`.

## global config

the `globalconfig`-Section of the Config contains general settings:

| Setting               | Description                                                                                                                      | Default                   |
| --------------------- | -------------------------------------------------------------------------------------------------------------------------------- | ------------------------- |
| `ip`                  | ip address the osc-kreuz listens on                                                                                              | 127.0.0.1                 |
| `port_ui`             | Highest Priority listen-port intended for GUI applications                                                                       | 4455                      |
| `port_data`           | lower priority port for listening to automated clients. pauses listening when data is received on `inputport_ui`                 | 4007                      |
| `port_settings`       | global configs can be changed on this port                                                                                       | 4999                      |
| `number_sources`      | number of source audio channels                                                                                                  | 64                        |
| `max_gain`            | max gain for the audiorouter                                                                                                     | 2                         |
| `number_direct_sends` | number of direct send channels                                                                                                   | 46                        |
| `send_changes_only`   | only send when source data has changed,                                                                                          | true                      |
| `data_port_timeout`   | when data is received on the ui port, the data port is paused for this timeout, in seconds, set to 0 to deactivate               | 2                         |
| `render_units`        | available render units in this system                                                                                            | ["ambi", "wfs", "reverb"] |
| `room_scaling_factor` | All incoming position changes are multiplied by this factor. this allows using the same control panel in differently sized rooms | 1                         |

## Receivers

This Section of the config contains a list of clients that receive updates from osc-kreuz.
common settings are:
| Setting | Description | Default |
| ----------------- | -------------------------------------------------------------------------------------------------------- | ------- |
| `type` | Type of the receiver, you should probably use `audiomatrix` | |
| `hostname` | target host, can be a hostname or an ip address, ignored when `hosts` is set | |
| `port` | Port the target listens on, ignored when `hosts` is set | |
| `hosts` | can contain a list of hostnames and ports, allows sending updates to multiple receivers of the same type | |
| `updateintervall` | time (in ms) to wait between subsequent update bundles | |
| `dataformat` | format the positional data is sent in. supports a lot of different formats | xyz |

### Audiomatrix

This Receiver type is intended for use with the [Audio Matrix](https://github.com/tu-studio/audio-matrix), but can be configured in a flexible way in order to be used for many different receivers.
what makes it powerful is an additional option, `paths`, for configuring the osc paths the target listens on.
`paths` contains a list of osc paths with the following configuration options:
| Setting | Description |
| ---------- | ----------------------------------------------------------------------------------------------- |
| `path` | OSC-Path |
| `type` | type of data that is sent to this path, options are `gain` and `position` |
| `renderer` | only used when `type`=`gain`, choose renderer whose gain is sent to this path |
| `format` | only used when `type`=`position`, chooses the datatype of the positional data sent to this path |

Data is sent to clients with the index of the source as the first parameter, followed by the positional or gain data.

# Supported position formats

Currently, 2 different coordinate systems are supported: **cartesian** and **spherical** coordinates.

For cartesian coordinates, the format string can contain any of the letters `x`, `y` and `z`. For spherical coordinates, the letters `a`, `e`, `d` are allowed. A suffix of `rad` tells the osc-kreuz that azimuth or elevation should be in radians, otherwise they are in degrees. If only one of the spherical coordinates is required, `azim`, `azimuth`, `elev`, `elevation`, `dist`, `distance` are also valid position formats.

Some examples of valid position format strings are listed in the following table:

| Position Format String | Datatypes of Data | Comment |
| ---------------------- | ----------------- | ------- |
| `xyz`                  | `fff`             |         |
| `xz`                   | `ff`              |         |
| `y`                    | `f`               |         |
| `aed`                  | `fff`             |         |
| `aedrad`               | `fff`             |         |
| `distance`             | `f`               |         |
| `elevrad`              | `f`               |         |
| `azimuth`              | `f`               |         |

# Development

For Development it is recommended to install the python package in a virtual environment.

```bash
python -m venv venv
source venv/bin/activate
pip install -e .
```

then it can be run using

```bash
osc-kreuz
# To Check Command line options use
osc-kreuz --help
```

# Releasing

Releases are published automatically when a tag is pushed to GitHub.

```bash

# Set next version number
export RELEASE=x.x.x

git tag -a $RELEASE -m "Version $RELEASE"

# Push
git push --tags
```

# About

The osc-kreuz was originally developed as part of the SeamLess Suite, then named OSC-Router.
