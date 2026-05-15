# Development

For Development it is recommended to install the python package in a virtual environment.

```bash
python -m venv venv
source venv/bin/activate
pip install -e .

# to also install dev dependencies for documentation and testing do the following:
pip install -e ".[dev]"
```

then it can be run using

```bash
osc-kreuz
# To Check Command line options use
osc-kreuz --help
```
# Testing

tests are automatically run using github actions, to locally run the full test suite ru
```bash
pytest
```
in the project root.

since some of these tests involve complex setups with multiple threads for black box testing they might take a while to exit, even after all tests have finished.

# Releasing

Releases are published automatically when a tag is pushed to GitHub.

```bash

# Set next version number
export RELEASE=x.x.x

git tag -a $RELEASE -m "Version $RELEASE"

# Push
git push --tags
```
