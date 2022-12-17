from configparser import ConfigParser


class Config:
    def __init__(self):
        self.config = ConfigParser()
        self.__load_config()

    def __load_config(self):
        self.config.read('config.ini')
        to_save = False

        if not self.config.has_section('server'):
            self.config.add_section('server')
            to_save = True

        if not self.config.has_option('server', 'url'):
            url = input('Podaj adres serwera: ')
            self.config.set('server', 'url', url)
            to_save = True

        if not self.config.has_section('devices'):
            self.config.add_section('devices')
            to_save = True

        if to_save:
            self.__save_config()

    def __save_config(self):
        with open('config.ini', 'w') as configfile:
            self.config.write(configfile)

    def get_server_url(self):
        return self.config.get('server', 'url')

    def get_device_config(self, device_name: str):
        if not self.config.has_option('devices', device_name):
            connection_string = input(f'Podaj connection_string urządzenia {device_name}: ')
            self.config.set('devices', device_name, connection_string)
            self.__save_config()
        return self.config.get('devices', device_name)
