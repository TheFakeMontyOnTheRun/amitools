"""config value classes that define the config entries"""

import os
import sys

if sys.version_info >= (3, 0, 0):
    str_type = str
else:
    str_type = basestring


class ConfigBaseValue(object):

    def __init__(self, default=None, val_type=None):
        self.val_type = val_type
        self.default = self.parse_value(default)

    def __repr__(self):
        return "ConfigValue(default={}, val_type={})" \
            .format(self.default, self.val_type)

    def get_default(self):
        return self.default

    def parse_value(self, v, old_val=None):
        v = self._conv_value(v)
        self._check_value(v)
        return v

    def _conv_value(self, v):
        if v is None:
            raise ValueError("value must not be None! {}".format(v))
        return self.val_type(v)

    def _check_value(self, v):
        if not type(v) is self.val_type:
            raise ValueError("invalid type: {} of {}".format(type(v), v))


class ConfigBoolValue(ConfigBaseValue):

    def __init__(self, default=False):
        super(ConfigBoolValue, self).__init__(default, bool)

    def _conv_value(self, v):
        if isinstance(v, str_type):
            s = v.lower()
            if s in ('yes', 'on'):
                return True
            elif s in ('no', 'off'):
                return False
        return v


class ConfigIntValue(ConfigBaseValue):

    def __init__(self, default=0, int_range=None):
        self.int_range = int_range
        super(ConfigIntValue, self).__init__(default, int)

    def _conv_value(self, v):
        if isinstance(v, str_type):
            # hex string
            if v.startswith('0x'):
                return int(v[2:], 16)
            # classic hex
            elif v[0] == '$':
                return int(v[1:], 16)
            elif v.isdigit():
                return int(v)
            else:
                raise ValueError("invalid integer string: {}".format(v))
        elif type(v) is int:
            return v
        elif type(v) is bool:
            raise ValueError("integer required, not bool: {}".format(v))
        else:
            super(ConfigIntValue, self)._conv_value(v)

    def _check_value(self, v):
        ir = self.int_range
        if ir is not None:
            if v < ir[0] or v > ir[1]:
                raise ValueError("invalid int parameter given! {} not in {}"
                                 .format(v, ir))
        return super(ConfigIntValue, self)._check_value(v)


class ConfigSizeValue(ConfigIntValue):

    def __init__(self, default=0, int_range=None, units=1024):
        self.units = units
        super(ConfigSizeValue, self).__init__(default, int_range)

    def _conv_value(self, v):
        scale = 1
        if isinstance(v, str_type):
            v = v.lower()
            # skip byte endinng
            if v.endswith('b'):
                v = v[:-1]
            # KiB units: scale = 1024
            if v.endswith('i'):
                units = 1024
                v = v[:-1]
            else:
                units = self.units
            # Kilo
            if v.endswith('k'):
                scale = units
                v = v[:-1]
            elif v.endswith('m'):
                scale = units * units
                v = v[:-1]
            elif v.endswith('g'):
                scale = units * units * units
                v = v[:-1]
        return super(ConfigSizeValue, self)._conv_value(v) * scale


class ConfigStringValue(ConfigBaseValue):

    def __init__(self, default=None, allow_none=False):
        self.allow_none = allow_none
        super(ConfigStringValue, self).__init__(default, str)

    def _conv_value(self, v):
        if self.allow_none and v is None:
            return None
        if not isinstance(v, str_type):
            raise ValueError("expected string value: {}".format(v))
        return super(ConfigStringValue, self)._conv_value(v)

    def _check_value(self, v):
        if self.allow_none and v is None:
            return
        super(ConfigStringValue, self)._check_value(v)


class ConfigPathValue(ConfigStringValue):

    def __init__(self, default=None, is_dir=False, must_exist=False):
        self.is_dir = is_dir
        self.must_exist = must_exist
        super(ConfigPathValue, self).__init__(default)

    def _check_value(self, v):
        if self.must_exist:
            if self.is_dir:
                if not os.path.isdir(v):
                    raise ValueError("directory does not exist: {}".format(v))
            else:
                if not os.path.isfile(v):
                    raise ValueError("file does not exist: {}".format(v))
        else:
            if os.path.exists(v):
                if self.is_dir:
                    if not os.path.isdir(v):
                        raise ValueError("not a directory: {}".format(v))
                else:
                    if not os.path.isfile(v):
                        raise ValueError("not a file: {}".format(v))
        return v


class ConfigEnumValue(ConfigStringValue):

    def __init__(self, val_map, default):
        # convert list
        if type(val_map) in (list, tuple):
            d = {}
            for a in val_map:
                d[a] = a
            self.val_map = d
        else:
            self.val_map = val_map
        super(ConfigEnumValue, self).__init__(default)

    def _conv_value(self, v):
        if v in self.val_map:
            return self.val_map[v]
        else:
            return v

    def _check_value(self, v):
        if v not in self.val_map.values():
            raise ValueError("invalid enum value: {}".format(v))


class ConfigValueList(ConfigBaseValue):

    def __init__(self, entry_cfg, default=None,
                 entry_sep=None, append_prefix=None):
        self.entry_cfg = entry_cfg
        if entry_sep is None:
            entry_sep = ','
        if append_prefix is None:
            append_prefix = '+'
        if default is None:
            default = []
        self.entry_sep = entry_sep
        self.append_prefix = append_prefix
        super(ConfigValueList, self).__init__(default, list)

    def parse_value(self, v, old_val=None):
        """parse a list entry.

        Either give an empty list with None, a list or tuple to parse the
        values stored there or a string.

        The string will be split with ``entry_sep`` and then parsed.

        Args:
            v (any): value to be parsed as a list. either list or str
            old_val (list, optional): old list (may be appended) or None
        Returns:
            list    a list of parsed values
        Raises:
            ValueError  is parsing went wrong
        """
        if v is None:
            return []
        elif type(v) in (tuple, list):
            return list(map(self.entry_cfg.parse_value, v))
        else:
            s = str(v)
            append = False
            # append prefix?
            if len(s) > 0 and s.startswith(self.append_prefix):
                s = s[len(self.append_prefix):]
                append = True
            entries = s.split(self.entry_sep)
            res = list(map(self.entry_cfg.parse_value, entries))
            # append to old list
            if append and old_val is not None:
                return old_val + res
            else:
                return res
