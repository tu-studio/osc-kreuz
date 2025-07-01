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
