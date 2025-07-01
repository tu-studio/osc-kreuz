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
## versioned install
when using the `versioned_install` flag the installation of multiple different versions of the osc-kreuz is possible, the binaries and venv are installed and symlinked as follows:


### Binaries

```path
/usr/local/bin/
├── osc-kreuz -> /usr/local/bin/osc-kreuz-<version>
└── osc-kreuz-<version> -> /usr/local/share/osc-kreuz-<version>/venv/bin/osc-kreuz
```

### Venvs

```path
/usr/local/share/
└── osc-kreuz-<version>/
    └── venv/
```

The systemd service files are not versioned.
