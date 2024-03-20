# OSC-kreuz
The osc-kreuz serves as a central interface for OSC messages in a multiclient spatial rendering environment. It automatically translates incoming OSC messages to match the expected formats of the rendering engines and distributes it to all connected clients including UI Clients and Data clients for automation data.

# Development
For Development it is recommended to install the python package in a virtual environment.
``` bash
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

# Installation
Install with pip:
```bash
pip install osc-kreuz
```

On our machines osc-kreuz is installed systemwide using:
``` bash
meson setup -Dversioned_install=true --wipe builddir
meson install -C builddir
```

when using the `versioned_install` flag the installation of multiple different versions of the osc-kreuz is possible, see [here](versioned_install.md)

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
The osc-kreuz was originally developed as part of the SeamLess Suite, then named OSC-Router.