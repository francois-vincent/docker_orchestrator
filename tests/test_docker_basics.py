# encoding: utf-8

import glob

from ..docker_basics import *

image = 'testimage'
data = \
"""ligne 1
ligne 2
ça cé ben vrê ù à ö

"""


def basic_setup():
    container_stop('toto')
    container_delete('toto')
    docker_build(image)
    docker_run(image, 'toto')


def test_docker_build():
    image_delete_and_containers(image)
    assert docker_build(image)
    assert len(get_images(image)) == 1
    assert docker_build(image)


def test_get_images():
    docker_build(image)
    assert image in get_images()
    assert get_images(image) == [image]
    assert get_images((image, )) == [image]


def test_get_containers():
    docker_build(image)
    container_stop('toto', 'titi')
    container_delete('toto', 'titi')
    docker_run(image, 'toto')
    docker_run(image, 'titi')
    assert get_containers('toto') == ['toto']
    assert get_containers('toto', all=False) == ['toto']
    assert get_containers(('toto', )) == ['toto']
    assert set(get_containers(image=image)).issuperset(('toto', 'titi'))
    container_stop('toto', 'titi')
    assert get_containers('toto', all=False) == []
    assert get_containers('toto') == ['toto']
    container_delete('toto', 'titi')
    assert get_containers('toto') == []


def test_docker_exec():
    basic_setup()
    assert docker_exec('pwd', 'toto') == '/\n'
    assert docker_exec('pwd', 'toto', status_only=True)
    assert docker_exec('wtf', 'toto', status_only=True) is False
    result = docker_exec('pwd', 'toto', stdout_only=False)
    assert result.returncode == 0
    assert result.stdout.strip() == '/'
    assert result.stderr.strip() == ''


def test_docker_exec_user():
    basic_setup()
    assert docker_exec('touch /root/toto', 'toto', status_only=True)
    assert docker_exec('ls -al /root | grep toto', 'toto').startswith(('-rw-r--r--  1 root root'))
    assert docker_exec('mkdir -p /var/www', 'toto', status_only=True)
    assert path_set_user('/var/www', 'www-data', 'toto', 'www-data')
    assert docker_exec('touch /var/www/titi', 'toto', user='www-data', status_only=True)
    assert docker_exec('ls -al /var/www | grep titi', 'toto').startswith(('-rw-r--r--  1 www-data www-data'))


def test_path_exists():
    basic_setup()
    assert not path_exists('/root/a/b', 'toto')
    docker_exec('mkdir -p /root/a/b', 'toto')
    assert path_exists('/root/a/b', 'toto')


def test_put_data():
    basic_setup()
    put_data(data, '/root/data.txt', 'toto')
    assert get_data('/root/data.txt', 'toto') == data
    put_data(data, '/root/data.txt', 'toto', append=True)
    assert get_data('/root/data.txt', 'toto') == data + data


def test_put_file():
    basic_setup()
    file = os.path.join(ROOTDIR, 'tests/dummy1.txt')
    with open(file, 'r') as f:
        data = f.read()
    # check full file path
    put_file(file, '/root/dummy.txt', 'toto')
    assert data == get_data('/root/dummy.txt', 'toto')
    # check directory path
    put_file(file, '/root', 'toto')
    assert data == get_data('/root/dummy1.txt', 'toto')


def test_create_user():
    basic_setup()
    create_user('toto', 'toto')
    assert docker_exec('groups toto', 'toto') == 'toto : toto\n'
    create_user('titi', 'toto', ('group1', 'group2'))
    assert docker_exec('groups titi', 'toto') == 'titi : titi group1 group2\n'


def test_set_user_permissions():
    basic_setup()
    file = os.path.join(ROOTDIR, 'tests/dummy1.txt')
    put_file(file, '/root/dummy.txt', 'toto')
    assert docker_exec('ls -al /root | grep dummy', 'toto').startswith(('-rw-rw-r--  1 root root'))
    assert path_set_user('/root/dummy.txt', 'www-data', 'toto')
    assert docker_exec('ls -al /root | grep dummy', 'toto').startswith(('-rw-rw-r--  1 www-data root'))
    assert path_set_user('/root/dummy.txt', 'www-data', 'toto', group='www-data')
    assert docker_exec('ls -al /root | grep dummy', 'toto').startswith(('-rw-rw-r--  1 www-data www-data'))
    assert set_permissions('/root/dummy.txt', '0744', 'toto')
    assert docker_exec('ls -al /root | grep dummy', 'toto').startswith(('-rwxr--r--  1 www-data www-data'))


def test_put_directory():
    basic_setup()
    put_directory('.', '/root/subdir', 'toto')
    for file in glob.glob('*'):
        assert path_exists(os.path.join('/root/subdir', file), 'toto')


def test_get_processes():
    basic_setup()
    assert get_processes('toto')
    assert get_processes('toto', 'sshd')
