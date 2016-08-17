# encoding: utf-8

import os.path

from ..docker import PlatformManager, container_stop

ROOTDIR = os.path.dirname(os.path.abspath(__file__))


def test_build_delete_images():
    platform = PlatformManager('test', {'host': 'testimage'})
    platform.build_images(reset='uproot')
    assert platform.get_real_images() == ['testimage']
    platform.reset('rm_image')
    assert platform.get_real_images() == []


def test_run_stop_delete_containers():
    platform = PlatformManager('test', {'host': 'testimage'}).build_images()
    platform.run_containers(reset='rm_container')
    assert platform.get_real_containers() == ['testimage-test-host']
    platform.containers_stop()
    assert platform.get_real_containers() == []
    assert platform.get_real_containers(True) == ['testimage-test-host']
    platform.containers_delete()
    assert platform.get_real_containers(True) == []


def test_get_hosts():
    with PlatformManager('test', {'host1': 'testimage', 'host2': 'testimage'}).standard_setup() as platform:
        assert set(platform.get_real_containers()) == {'testimage-test-host1', 'testimage-test-host2'}
        hosts = platform.get_hosts()
        assert set(hosts.keys()) == {'host1', 'host2'}
        assert '172.17.' in hosts['host1']
        assert '172.17.' in hosts['host2']
        container_stop('testimage-test-host2')
        hosts = platform.get_hosts()
        assert set(hosts.keys()) == {'host1', 'host2'}
        assert '172.17.' in hosts['host1']
        assert '' == hosts['host2']
        try:
            platform.get_hosts(raises=True)
            assert 0, "Should raise a RuntimeError"
        except RuntimeError as e:
            assert e.args == ('Expecting 2 running containers, found 1', )
        except Exception as e:
            assert 0, "Should raise a RuntimeError, raised {}".format(e)


def test_network():
    with PlatformManager('test', {'host1': 'testimage', 'host2': 'testimage'}).standard_setup() as platform:
        assert platform.docker_exec('ping -c 1 {}'.format(platform.containers['host2']), 'host1', True)
        assert platform.docker_exec('ping -c 1 {}'.format(platform.containers['host1']), 'host2', True)


def test_docker_exec():
    with PlatformManager('test', {'host1': 'testimage', 'host2': 'testimage'}).standard_setup() as platform:
        assert platform.docker_exec('pwd') == {'host1': '/\n', 'host2': '/\n'}
        assert platform.docker_exec('pwd', host='host1') == '/\n'


def test_create_user():
    with PlatformManager('test', {'host1': 'testimage', 'host2': 'testimage'}).standard_setup() as platform:
        platform.create_user('toto')
        assert platform.docker_exec('groups toto') == {'host1': 'toto : toto\n', 'host2': 'toto : toto\n'}


def test_put_get_data():
    with PlatformManager('test', {'host1': 'testimage', 'host2': 'testimage'}).standard_setup() as platform:
        platform.docker_exec('mkdir /root/testdir')
        platform.put_data('fluctuat nec mergitur', '/root/testdir/bob.txt')
        assert platform.get_data('/root/testdir/bob.txt') == {'host1': 'fluctuat nec mergitur', 'host2': 'fluctuat nec mergitur'}


def test_put_file():
    with PlatformManager('test', {'host1': 'testimage', 'host2': 'testimage'}).standard_setup() as platform:
        platform.docker_exec('mkdir /root/testdir')
        platform.put_file(os.path.join(ROOTDIR, 'dummy2.txt'), '/root/testdir')
        assert platform.path_exists('/root/testdir/dummy2.txt')
        assert platform.get_data('/root/testdir/dummy2.txt') == {'host1': 'hello world', 'host2': 'hello world'}
        platform.put_file(os.path.join(ROOTDIR, 'dummy2.txt'), '/root/testdir/dummy.txt')
        assert platform.path_exists('/root/testdir/dummy.txt')


def test_get_processes():
    with PlatformManager('test', {'host1': 'testimage', 'host2': 'testimage'}).standard_setup() as platform:
        processes = platform.get_processes()
        assert processes['host1'] == platform.get_processes('host1')
        assert processes['host2'] == platform.get_processes('host2')


def test_ssh():
    with PlatformManager('test', {'host1': 'testimage', 'host2': 'testimage'}).standard_setup() as platform:
        assert platform.ssh('pwd') == {'host1': '/root\n', 'host2': '/root\n'}
        assert platform.ssh('pwd', host='host1') == '/root\n'


def test_ssh_put_file_exists():
    with PlatformManager('test', {'host1': 'testimage', 'host2': 'testimage'}).standard_setup() as platform:
        platform.ssh('mkdir /root/testdir')
        platform.scp(os.path.join(ROOTDIR, 'dummy2.txt'), '/root/testdir')
        assert platform.path_exists('/root/testdir/dummy2.txt')
        assert platform.ssh('cat /root/testdir/dummy2.txt') == {'host1': 'hello world', 'host2': 'hello world'}
        platform.ssh('rm -f /root/testdir/dummy2.txt', 'host1')
        assert platform.path_exists('/root/testdir/dummy2.txt', 'host2')
        assert not platform.path_exists('/root/testdir/dummy2.txt', 'host1')


def test_put_file_exists():
    with PlatformManager('test', {'host1': 'testimage', 'host2': 'testimage'}).standard_setup() as platform:
        platform.docker_exec('mkdir /root/testdir')
        platform.scp(os.path.join(ROOTDIR, 'dummy2.txt'), '/root/testdir')
        assert platform.docker_exec('cat /root/testdir/dummy2.txt') == {'host1': 'hello world', 'host2': 'hello world'}
        assert platform.path_exists('/root/testdir/dummy2.txt')
        platform.docker_exec('rm -f /root/testdir/dummy2.txt', 'host1')
        assert platform.path_exists('/root/testdir/dummy2.txt', 'host2')
        assert not platform.path_exists('/root/testdir/dummy2.txt', 'host1')
