import os
import yaml

class Error(Exception):
    pass

class MissingEnvironment(Error):
    pass

class UndefinedKeyError(Error, AttributeError, KeyError):
    pass

class LockedError(Error):
    pass

class ConfigFileError(Error):
    pass

class ConfigTree(object):
    def __init__(self):
        self.locked = False

class ConfigStore(object):
    def __init__(self, config_tree=None, name='config', path=[]):
        if config_tree is None:
            config_tree = ConfigTree()
        self._config_tree = config_tree
        self._name = name
        self._path = path
        self._attributes = {}

    def __getitem__(self, key):
        try:
            return self._attributes[key]
        except KeyError:
            if self.locked:
                raise UndefinedKeyError("Configuration key not found: {}.{}".format(self, key))
            self._attributes[key] = ConfigStore(self._config_tree, '{}.{}'.format(self._name, key), self._path + [key])
            return self._attributes[key]

    def __setitem__(self, key, value):
        if self.locked:
            raise LockedError("Cannot set key {} for locked {}".format(key, self))
        self._attributes[key] = value

    def __getattr__(self, key):
        if key.startswith('_') or hasattr(ConfigStore, key):
            return super(ConfigStore, self).__getattr__(key)
        else:
            return self[key]

    def __setattr__(self, key, value):
        # Need to look at the class for locked
        if key.startswith('_') or hasattr(ConfigStore, key):
            super(ConfigStore, self).__setattr__(key, value)
        else:
            self[key] = value

    @property
    def locked(self):
        return self._config_tree.locked

    @locked.setter
    def locked(self, value):
        self._config_tree.locked = value

    def clear(self):
        self.attributes.clear()

    def update_dict(self, d):
        for key, value in d.iteritems():
            if isinstance(value, dict):
                self[key].update_dict(value)
            else:
                self[key] = value

    def __str__(self):
        return self._name

    def __repr__(self):
        out = []
        for key, value in sorted(self._attributes.iteritems()):
            if isinstance(value, ConfigStore):
                rendered = repr(value)
                if rendered:
                    out.append(rendered)
            else:
                out.append("{}.{} = {!r}".format(self._name, key, value))
        return '\n'.join(out)

    def to_dict(self):
        output = {}
        for key, value in self.iteritems():
            if isinstance(value, ConfigStore):
                value = value.to_dict()
            output[key] = value
        return output

    # Add dict-like methods here
    def __iter__(self):
        return self._attributes.__iter__()

    def iteritems(self):
        return self._attributes.iteritems()

    def items(self):
        return self._attributes.items()

class Configuration(object):
    def __init__(self):
        self.directives = []
        self.env = self.discover_env()
        self.configatron = ConfigStore()
        self.configatron.locked = True

    def set_env(self, env):
        self.env = env
        self.reapply_config()

    def discover_env(self):
        env_file = '/etc/flags/env'
        if os.path.exists(env_file):
            with open(env_file) as f:
                env = f.read().strip()
        else:
            env = 'local'
        return env

    def register(self, filepath, raw=False, optional=False, nested=None):
        if not filepath.startswith('/'):
            # Borrowed from chalk-config
            raise Error('Register only accepts absolute paths, not {}. (This ensures that config is always correctly loaded rather than depending on your current directory. To avoid this error in the future, you may want to use a wrapper that expands paths based on a base directory.)', filepath)
        elif optional and not os.path.exists(filepath):
            config = None
        else:
            with open(filepath) as f:
                try:
                    config = yaml.load(f)
                except Exception as e:
                    _, _, tb = sys.exc_info()
                    raise ConfigFileError, '{} (while loading {})'.format(e, filepath), tb

        self.register_parsed(config, filepath, raw=raw, optional=optional, nested=nested)

    def register_parsed(self, config, filepath, raw=False, optional=False, nested=None):
        directive = {
            'config': config,
            'filepath': filepath,
            'raw': raw,
            'optional': optional,
            'nested': nested,
        }
        self.directives.append(directive)
        self.mixin_config(directive)

    def reapply_config(self):
        self.configatron.clear()
        for directive in self.directives:
            self.mixin_config(directive)

    def mixin_config(self, directive):
        raw = directive['raw']
        config = directive['config']
        filepath = directive['filepath']

        if directive['optional'] and config is None:
            return

        if not raw and filepath and config is not None and self.env not in config:
            raise MissingEnvironment("Current environment {env} not defined in config file {filepath}. (HINT: you should have a YAML key of {env}. You may want to inherit a default via YAML's `<<` operator.)".format(env=self.env, filepath=filepath))

        if raw:
            choice = config
        elif filepath and config:
            choice = config[self.env]
        elif filepath:
            choice = {}
        else:
            choice = config

        self.configatron.locked = False
        base_config = self.configatron
        # Evaluate any interesting nesting
        if directive['nested'] is not None:
            for key in directive['nested'].split('.'):
                base_config = base_config[key]
        base_config.update_dict(choice)
        self.configatron.locked = True

_config = Configuration()
register = _config.register
set_env = _config.set_env
configatron = _config.configatron
