# OSC-Paths

On port 4455 (default value) the osc-kreuz listens on a number of paths for [position changes](#positional-data), [gain changes](#gains) and [special properties](#special-properties) for the wfs system. For most paths there exists a version of the path, where the index of the source that is changed is included in the path, and one where the index is sent as the first OSC argument.

Additionally there is the config port (4999) for the [subscription protocol](#subscription-protocol) and full copying of all outputs with the [debug mode](#debug-functions)

## Positional Data

Positional Data can be sent to the following paths, where `[position_format]` is a placeholder for a string describing the positional format, see [Supported position formats](./position-formats.md):

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
`wfs` or `wavefieldsynthesis` for the rendering system `wfs`).

There exists also a special path, where gains for the different rendering systems can be set by the index of the rendering system, starting from 0, in the order the rendering systems are declared in the config, these are the first three in the table.

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

A client can subscribe to all position and gain messages e.g. a viewer-client during production process. Subcriptions and pong messages should be sent to port 4999.

The connection is initialised via:
`/osckreuz/subscribe s i [s i i]` where the parameters are client_name (string), client_port (int), coordinate_format (string), source_index_in_osc_path (int, allowed values are 0 and 1), min_update_intervall (int, in ms)
The last three arguments are optional and are set to '"xyz" 0 10' by default.
e.g. `/osckreuz/subscribe my_cool_viewer 55123 xyz 1 10`
will send source-position messages to the subscribing client as follows:

- For Position
  `/source/1/xyz fff` with a max. rate of 100Hz (every 10 ms).
- For gains e.g.
  `/source/1/ambi f`

for now, direct sends and attributes always send the source index as a parameter.

If `sourceIndexInOscPath` is set to zero, the following paths are used:

- Positional Data: `/source/[coordinateFormat] i[f...]`
- Renderer Gains: `/source/send iif (source_index renderer_index gain)`
- Direct Send Gains: `/source/direct iif (source_index send_index gain)`
- Attribute: `/source/attribute isf (source_index attribute_name value)`

The ip-Address of the client is retrieved automatically from the udp-packet by the OSC-Router.

### ping-pong

The osc-router regularly sends the message
`/osckreuz/ping 4999` to all subscribed clients
which should be answered (to port 4999) with
`/osckreuz/pong uniqueClientName`
The uniqueClientName has to be the same as in the subcription message.
If the client does not answer to the ping message it will be erased after a certain time.

## Debug functions

Port: 4999

A copy of all outgoing osc-messages from the osc-kreuz can requested by sending:
`/osckreuz/debug/osccopy ipAddress:port` with ipAddress and listening port of the receiving machine e.g. `/osckreuz/debug/osccopy 192.168.3.2:55112`
The debug-osc messages contain the name of the target as well as ip-address and port.
To deactivate this send a message without target address: `/osckreuz/debug/osccopy`

With the message `/osckreuz/debug/verbose i` a verbosity level can be set which activates console printing of incoming and outcoming messages as well as further information.
Set verbosity to 0 when to stop console output which can significantly slow down the system.
