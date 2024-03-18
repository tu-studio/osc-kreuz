conf_data = configuration_data()
conf_data.set('bin_dir', get_option('prefix') / get_option('bindir'))

configure_file(input : 'osc-kreuz.service.in',
                output : 'osc-kreuz.service',
                configuration: conf_data,
                install_dir: '/etc/systemd/user'
)
