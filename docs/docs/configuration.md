# Configuration

The configuration is done using a YAML-Config file, an example config file can be found in `example_configs`.

## global config

the `global`-Section of the Config contains general settings:

| Setting               | Description                                                                                                                                                                                                                      | Default                   |
| --------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------- |
| `ip`                  | ip address the osc-kreuz listens on                                                                                                                                                                                              | 127.0.0.1                 |
| `port_ui`             | Highest Priority listen-port intended for GUI applications                                                                                                                                                                       | 4455                      |
| `port_data`           | lower priority port for listening to automated clients. pauses listening when data is received on `inputport_ui`                                                                                                                 | 4007                      |
| `port_settings`       | used for connection requests and debug functions                                                                                                                                                                                 | 4999                      |
| `number_sources`      | number of source audio channels                                                                                                                                                                                                  | 64                        |
| `max_gain`            | max gain for the audiorouter                                                                                                                                                                                                     | 2                         |
| `number_direct_sends` | number of direct send channels                                                                                                                                                                                                   | 46                        |
| `send_changes_only`   | only send when source data has changed,                                                                                                                                                                                          | true                      |
| `data_port_timeout`   | when data is received on the ui port, the data port is paused for this timeout, in seconds, set to 0 to deactivate                                                                                                               | 2                         |
| `render_units`        | available render units in this system                                                                                                                                                                                            | ["ambi", "wfs", "reverb"] |
| `room_scaling_factor` | All incoming position changes are multiplied by this factor. this allows using the same control panel in differently sized rooms                                                                                                 | 1                         |
| `room_name`           | only used for CWonder emulation, name of the current room                                                                                                                                                                        | "default_room"            |
| `room_polygon`        | only needed for CWonder emulation. List of points describing the WFS-System layout. each point is represented by a list containing its x, y and z coordinates as floats. for example `room_polygon: [[0,0,0], [1,0,0], [0,1,0]]` | []                        |

## Receivers

This Section of the config contains a list of clients that receive updates from osc-kreuz.
common settings are:
| Setting | Description | Default |
| ----------------- | -------------------------------------------------------------------------------------------------------- | ------- |
| `type` | Type of the receiver, you should probably use `audiomatrix` | |
| `hostname` | target host, can be a hostname or an ip address, used in conjunction with `port` | |
| `port` | Port of the target host | |
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
