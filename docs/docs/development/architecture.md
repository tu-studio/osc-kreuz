# System-Architecture

## Source

A source describes a virtual sound object that has a position and gains for different systems.

## Render Units vs Receiver

A **render unit** abstractly describes an abstract spatial audio system (e.g. wfs, ambisonics or lfe), that is in itself composed of different receivers (twonder, audio-matrix, encoders etc). The render unit handles the incoming gain for this spatialization system.
**Receiver**s are represent devices that will receive positional or gain information from the OSC-kreuz.

Render units are specified as a list of strings in the config. Some special render unit names will cause an alias to be created for use in OSC paths, but functionally the names are arbitrary.

Receivers are specified in the config in a list of receivers. For each Receiver the type has to be specified, for more info see [here.](../configuration.md). A receiver can have multiple hostnames and ports, that are also called receivers in the code.

## SoundObject

The current state of the OSC-kreuz is kept in an array of `SoundObject`s, that most classes have access to.
Each Soundobject corresponds to a source and knows its own index, the number of render units, the room scaling factor and the globalconfig.
It stores the following variable information:

- its own position in all available base coordinate formats
- the gain for each render unit
- the gain for direct speaker sends (not implemented in the seamless system, but they exist)
- its WFS-attributes (`planewave`, `doppler` and `angle`)
- a dictionary for keeping state of updates from the ui to enable blocking updates from "automation clients"

Whenever the position is changed in one coordinate format all other formats are updated. The SoundObject is only used for keeping the state, it does not handle the sending to receivers.

## OSC-Communication

Incoming OSC-communication is handled in the file `osccomcenter.py` by the class OSCComCenter.

All OSC paths are setup in this class in the `setupOscBindings()` function. It also contains the osc message handlers.
The most important handlers are the position handler `osc_handler_position()` and `osc_handler_gain()`. They are passed to different osc paths with different preset arguments using the creation of `partial` functions.

The OSC-Listeners run as `BlockingOSCUDPServers` in seperate Threads

### OSC-Message Signalflow

When an OSC data message is received the following happens:

The `BlockingOSCUDPServers` running on this port calls the OSC handler function of this OSC path using the osc_data_dispatcher.

Lets assume we received positional data, then `osc_handler_position` is called. After validation of the source id, the SoundObject with this source_index is updated using the setPosition() function. If the position was actually changed afterwards the osc_handler calls the function `OSCComCenter.notifyRenderClientsForUpdate` with the name of the update-function used by the BaseReceiver, `"sourcePositionChanged"` and the source index.

The `OSCComCenter` then iterates over all receivers, gets the update-function by name using `getattr()` and calls it. If a receiver does not overwrite this function, nothing happens. We'll assume the receiver is a basic `SpatialReceiver`, other Receivers do and should follow the same logic.

From `sourcePositionChanged()`, a PositionUpdate is added to this receivers update queue with correct the source index.
Notably, the update does not contain the actual positional data, just the information that this receiver should get an update on the specified OSC path.
The update queue is a `Set`, making sure each individual PositionUpdate can only exist once per Queue.

After adding the update to the queue, `update_source(source_idx)` is called. a semaphore is used to ensure only on source update is performed at a time, and the next update will only be performed after `update_interval` seconds.

The update procedure looks as follows:

1. lock the semaphore for this source index
2. swap the active update queue with the reserve `update_queue_swap`, so updates received during the update procedure are not lost
3. pop all updates from the queue, convert them to OSCMessages and add them to a list of messages
4. send all messages to all hostnames related to this receiver
5. schedule the unlocking of the queue using the `update_interval`
6. after the timeout has passed: release the semaphore, call `update_source` again if any updates arrived in the meantime
