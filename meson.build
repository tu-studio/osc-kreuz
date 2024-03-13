project('OscRouter')

data_path = get_option('datadir') / 'seamless-core' / 'oscrouter'
config_path = get_option('sysconfdir') / 'seamless-core' / 'oscrouter'
venv_path = get_option('prefix') / data_path / 'venv'
install_data('example_configs/oscRouterConfig.yml', install_dir: config_path) # install_data is nessary otherwise meson will not ask for su permission

# creating virtual environment
meson.add_install_script(
	'sh', '-c',
	'python3 -m venv @0@; '.format(venv_path)
)

# installing oscrouter with pip
# uses pip of the created virtual environment
meson.add_install_script(
	'sh', '-c',
	'@0@/bin/pip install @1@; '.format(
		venv_path, meson.current_source_dir())
)

# linking oscrouter binary to bindir
meson.add_install_script(
	'sh', '-c',
	'ln -s -f @0@ @1@'.format(
        venv_path / 'bin' / 'seamless-oscrouter',
        get_option('prefix') / get_option('bindir') / 'seamless-oscrouter')
)