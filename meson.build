data_path = get_option('datadir') / 'seamless-core' / 'oscrouter'
config_path = get_option('sysconfdir') / 'seamless-core' / 'oscrouter'

install_data('oscRouterConfig.txt', install_dir: config_path) # install_data is nessary otherwise meson will not ask for su permission

meson.add_install_script(
	'sh', '-c',
	'python3 -m venv @0@; '.format(get_option('prefix') / data_path / 'venv')
)

meson.add_install_script(
	'sh', '-c',
	'@0@/bin/pip install @1@; '.format(
		get_option('prefix') / data_path / 'venv', meson.current_source_dir())
)

meson.add_install_script(
	'sh', '-c',
	'ln -s -f @0@ @1@'.format(
        get_option('prefix') / data_path / 'venv' / 'bin' / 'seamless-oscrouter',
        get_option('prefix') / get_option('bindir') / 'seamless-oscrouter')
)

meson.add_install_script(
	'sh', '-c',
	'echo @0@'.format(
		config_path)
)