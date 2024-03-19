project('osc-kreuz',
  version: run_command('python', '-c' , 'from src.osc_kreuz._version import get_versions;print(get_versions()["version"])', check: true).stdout().strip())

# py = import('python')
# python = py.find_installation(meson.current_source_dir() / 'venv/bin/python')




if get_option('versioned_install')
  	install_postfix = '-' + meson.project_version()
else
	install_postfix = ''
endif

venv_path = get_option('prefix') / get_option('datadir') / ('osc-kreuz' + install_postfix) / 'venv'

# creating virtual environment
meson.add_install_script(
	'sh', '-c',
	'sudo python3 -m venv @0@; '.format(venv_path)
)

# installing osc-kreuz with pip
# uses pip of the created virtual environment
meson.add_install_script(
	'sh', '-c',
	'sudo @0@/bin/pip install @1@; '.format(
		venv_path, meson.current_source_dir())
)

# linking osc-kreuz binary to bindir
meson.add_install_script(
	'sh', '-c',
	'sudo ln -s -f @0@ @1@'.format(
        venv_path / 'bin' / 'osc-kreuz',
        get_option('prefix') / get_option('bindir') / 'osc-kreuz')
)

subdir('systemd')