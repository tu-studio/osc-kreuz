# osc_kreuz
The osc_kreuz serves as a central interface for OSC-messages in a multiclient spatial rendering environment. It automatically translates incoming OSC messages to match the expected formats of the rendering engines and distributes it to all connected clients including UI Clients and Data clients for automation data.

# Development
For Development it is recommended to install the python package in a virtual environment.
``` bash
python -m venv venv
source venv/bin/activate
pip install -e .
```
then it can be run using 
```bash
osc_kreuz
# To Check Command line options use
osc_kreuz --help
``` 

# Installation
Install with pip:
```bash
pip install osc_kreuz
```

# Configuration
TODO

# Releasing

Releases are published automatically when a tag is pushed to GitHub.

``` bash

   # Set next version number
   export RELEASE=x.x.x

   git tag -a $RELEASE -m "Version $RELEASE"

   # Push
   git push --tags
```
# About
The osc_kreuz was originally developed as part of the SeamLess Suite, then named OSC-Router.