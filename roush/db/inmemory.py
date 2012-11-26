#!/usr/bin/env python

from functools import partial


class DataType(object):
    Integer, String, JsonEntry, JsonBlob = range(0, 4)

    def __init__(self, data_type, data_size=0):
        self.data_type = data_type
        self.data_size = data_size

    def sqlalchemy_format(self):
        if self.data_type == self.Integer:
            return "INTEGER"
        elif self.data_type == self.JsonEntry:
            return "JSON_ENTRY"
        elif self.data_type == self.JsonBlob:
            return "JSON"
        elif self.data_type == self.String:
            return "VARCHAR(%s)" % self.data_size


# Make column types similar to sqlalchemy
Integer = DataType(DataType.Integer)
JsonEntry = DataType(DataType.JsonEntry)
JsonBlob = DataType(DataType.JsonBlob)
String = partial(DataType, DataType.String)


class Column(object):
    def __init__(self, column_type, *args, **kwargs):
        self.schema = {'primary_key': False,
                       'unique': False,
                       'updatable': True,
                       'required': False,
                       'read_only': False}
        self.schema.update(kwargs)
        self.schema['type'] = column_type.sqlalchemy_format()


class InMemoryBase(object):
    def __new__(cls, *args, **kwargs):
        obj = super(InMemoryBase, cls).__new__(cls, *args, **kwargs)

        if not '__cols__' in obj.__dict__:
            obj.__dict__['__cols__'] = {}

        for k, v in obj.__class__.__dict__.iteritems():
            print 'found %s' % k
            if isinstance(v, Column):
                print 'moving %s' % k
                obj.__dict__['__cols__'][k] = v

        return obj

    def _coerce(self, what, towhat):
        if what is not None:
            return towhat(what)

        return what

    def __setattr__(self, name, value):
        if name in self.__dict__['__cols__']:
            wanted_type = None
            new_value = value

            type_name = self.__dict__['__cols__'][name].schema['type']

            if type_name == 'INTEGER' or type_name == 'NUMBER':
                wanted_type = int

            if 'VARCHAR' in type_name:
                wanted_type = str

            if wanted_type is not None:
                new_value = self._coerce(value, wanted_type)

            self.__dict__[name] = new_value
        else:
            self.__dict__[name] = value
