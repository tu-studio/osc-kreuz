project('osc-kreuz',
  version: run_command('python3', '-c' , 'from src.osc_kreuz._version import get_versions;print(get_versions()["version"])', check: true).stdout().strip())


if get_option('versioned_install')
  	install_postfix = '-' + meson.project_version()
else
	install_postfix = ''
endif

venv_path = get_option('prefix') / get_option('datadir') / ('osc-kreuz' + install_postfix) / 'venv'
build_venv_path = meson.current_source_dir() / 'venv'
wheel_name = 'osc_kreuz-' + meson.project_version() + '-py3-none-any.whl'

# creating virtual environments
meson.add_install_script(
	'sh', '-c',
	'sudo python3 -m venv @0@; '.format(venv_path)
)

meson.add_install_script(
	'sh', '-c',
	'python3 -m venv @0@; '.format(build_venv_path)
)

# build python wheel
meson.add_install_script(
	'sh', '-c',
	'@0@/bin/pip install build;'.format(build_venv_path)
)

meson.add_install_script(
	'sh', '-c',
	'@0@/bin/python3 -m build --wheel @1@'.format(build_venv_path, meson.current_source_dir())
)

# installing osc-kreuz with pip
# uses pip of the created virtual environment
meson.add_install_script(
	'sh', '-c',
	'sudo @0@/bin/pip install @1@; '.format(
		venv_path, meson.current_source_dir() / 'dist' / wheel_name)
)

# linking osc-kreuz binary to bindir
meson.add_install_script(
	'sh', '-c',
	'sudo ln -s -f @0@ @1@'.format(
        venv_path / 'bin' / 'osc-kreuz',
        get_option('prefix') / get_option('bindir') / 'osc-kreuz' + install_postfix)
)

if get_option('versioned_install')
	# linking osc-kreuz binary to bindir
	meson.add_install_script(
		'sh', '-c',
		'sudo ln -s -f @0@ @1@'.format(
			get_option('prefix') / get_option('bindir') / 'osc-kreuz' + install_postfix,
			get_option('prefix') / get_option('bindir') / 'osc-kreuz')
)
endif

subdir('systemd')