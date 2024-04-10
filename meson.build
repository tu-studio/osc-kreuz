project('osc-kreuz',
  version: run_command('python3', '-c' , 'from src.osc_kreuz._version import get_versions;print(get_versions()["version"])', check: true).stdout().strip())


if get_option('versioned_install')
  	install_postfix = '-' + meson.project_version()
else
	install_postfix = ''
endif

install_venv_path = get_option('prefix') / get_option('datadir') / ('osc-kreuz' + install_postfix) / 'venv'
build_venv_path = meson.current_source_dir() / 'venv'
wheel_name = 'osc_kreuz-' + meson.project_version() + '-py3-none-any.whl'

# --- build python wheel
# create venv (does nothing if it already exists)
run_command('python3',  '-m',  'venv', build_venv_path, check: true)

# install build
run_command('@0@/bin/pip'.format(build_venv_path),  'install', 'build', check: true)

# build wheel
custom_target('wheel_target', command: ['@0@/bin/python3'.format(build_venv_path), '-m', 'build', '--wheel', '@CURRENT_SOURCE_DIR@', '--outdir',  '@BUILD_ROOT@'], output: wheel_name, build_by_default: true, build_always_stale: true)
# build_target('wheel', wheel_target, target_type: 'executable')

# --- install osc-kreuz with pip

# create virtual environment
meson.add_install_script(
	'sh', '-c',
	'sudo python3 -m venv @0@; '.format(install_venv_path)
)
# use pip of the created virtual environment to install the wheel
meson.add_install_script(
	'sh', '-c',
	'sudo @0@/bin/pip install @1@; '.format(
		install_venv_path, meson.build_root() / wheel_name)
)

# symlink osc-kreuz binary to bindir
meson.add_install_script(
	'sh', '-c',
	'sudo ln -s -f @0@ @1@'.format(
        install_venv_path / 'bin' / 'osc-kreuz',
        get_option('prefix') / get_option('bindir') / 'osc-kreuz' + install_postfix)
)

if get_option('versioned_install')
	# symlink version specific osc-kreuz binary to bindir
	meson.add_install_script(
		'sh', '-c',
		'sudo ln -s -f @0@ @1@'.format(
			get_option('prefix') / get_option('bindir') / 'osc-kreuz' + install_postfix,
			get_option('prefix') / get_option('bindir') / 'osc-kreuz')
)
endif

subdir('systemd')