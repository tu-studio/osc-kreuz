# OSCRouter
The OSC-Router written in python serves as central interface for OSC-messages in a multiclient spatial rendering environment. It automatically translates incoming OSC-messages to match the expected formats of the rendering-engines and distributes it to all connected clients including UI-Clients and Data-clients for automation data.

# Development
For Development it is recommended to install the python package in a virtual environment.
``` bash
python -m venv venv
source venv/bin/activate
pip install -e .
```
then it can be run using 
```bash
seamless-oscrouter
# To Check Command line options use
seamless-oscrouter --help
``` 

# Installation
```bash
meson setup build_dir
cd build_dir
sudo meson install
```
The default configuration does not work at the moment

# Configuration
TODO


# About
The OSC-Router was originally developed as part of the SeamLess Suite