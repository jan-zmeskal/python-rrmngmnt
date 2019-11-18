# -*- coding: utf-8 -*-
import types

import pytest
import netaddr
from rrmngmnt import common, Host, User
from .common import FakeExecutorFactory


def test_fqdn2ip_positive():
    ip = common.fqdn2ip('github.com')
    assert netaddr.valid_ipv4(ip)


def test_fqdn2ip_negative():
    with pytest.raises(Exception) as ex_info:
        common.fqdn2ip('github.or')
    assert 'github.or' in str(ex_info.value)


class TestCommandReader(object):

    data = {
        'cat shopping_list.txt': (0, 'bananas\nmilk\nhuge blender', ''),
        'cat milk_shake_recipe.txt': (
            1, '', 'cat: milk_shake_recipe.txt: No such file or directory'
        ),
    }
    files = {}

    @classmethod
    @pytest.fixture(scope='class')
    def fake_host(cls):
        fh = Host('1.1.1.1')
        fh.add_user(User('root', '11111'))
        fh.executor_factory = FakeExecutorFactory(cls.data, cls.files)
        return fh

    def test_return_type(self, fake_host):
        """ Test that CommandReader returns generator type """
        cmd = 'cat shopping_list.txt'
        cmd_reader = common.CommandReader(fake_host.executor(), cmd.split())
        ret = cmd_reader.read_lines()

        assert isinstance(ret, types.GeneratorType)

        expected_output = self.data[cmd][1].split('\n')
        for i in range(len(expected_output)):
            assert next(ret) == expected_output[i]

        with pytest.raises(StopIteration):
            next(ret)

    def test_iterate_over_output(self, fake_host):
        """
        Test that we can iterate over CommandReader's output using for loop
        """
        cmd = 'cat shopping_list.txt'
        cmd_reader = common.CommandReader(fake_host.executor(), cmd.split())
        expected_output = self.data[cmd][1].split('\n')
        cmd_reader_output = []

        for line in cmd_reader.read_lines():
            cmd_reader_output.append(line)

        assert cmd_reader_output == expected_output

    def test_return_code(self, fake_host):
        """ Test that rc of command is captured by CommandReader """
        cmd = 'cat shopping_list.txt'
        cmd_reader = common.CommandReader(fake_host.executor(), cmd.split())

        assert cmd_reader.rc is None

        for line in cmd_reader.read_lines():
            pass

        assert not cmd_reader.rc

    def test_stderr(self, fake_host):
        """ Test that error output is captured by CommandReader """
        cmd = 'cat milk_shake_recipe.txt'
        cmd_reader = common.CommandReader(fake_host.executor(), cmd.split())

        assert not cmd_reader.err

        for line in cmd_reader.read_lines():
            pass

        assert cmd_reader.rc
        assert cmd_reader.err
