# Info on symlink structure for versioned install flag

## Binaries

```path
/usr/local/bin/
├── osc-kreuz -> /usr/local/bin/osc-kreuz-<version>
└── osc-kreuz-<version> -> /usr/local/share/osc-kreuz-<version>/venv/bin/osc-kreuz
```

## Venvs

```path
/usr/local/share/
└── osc-kreuz-<version>/
    └── venv/
```

The systemd service files are not versioned.
