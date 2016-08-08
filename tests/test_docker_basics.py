# encoding: utf-8

from ..docker_basics import *

image = 'testimage'
data = \
"""ligne 1
ligne 2
ça cé ben vrê ù à ö

"""


def basic_setup():
    docker_build(image)
    container_stop('toto')
    container_delete('toto')
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
    assert set(get_containers(image=image)) == {'toto', 'titi'}
    container_stop('toto', 'titi')
    assert get_containers('toto', all=False) == []
    assert get_containers('toto') == ['toto']
    container_delete('toto', 'titi')
    assert get_containers('toto') == []


def test_docker_exec():
    basic_setup()
    assert docker_exec('pwd', 'toto') == '/'
    assert docker_exec('pwd', 'toto', status_only=True)
    assert docker_exec('wtf', 'toto', status_only=True) is False
    result = docker_exec('pwd', 'toto', stdout_only=False)
    assert result.returncode == 0
    assert result.stdout.strip() == '/'
    assert result.stderr.strip() == ''


def test_path_exists():
    basic_setup()
    docker_exec('mkdir -p /root/a/b', 'toto')
    assert path_exists('/root/a/b', 'toto')


def test_put_data():
    basic_setup()
    assert put_data(data, '/root/data.txt', 'toto')
    assert get_data('/root/data.txt', 'toto') == data
    assert put_data(data, '/root/data.txt', 'toto', append=True)
    assert get_data('/root/data.txt', 'toto') == data + data


def test_put_file():
    basic_setup()
    file = os.path.join(ROOTDIR, 'tests/dummy.txt')
    assert put_file(file, '/root/dummy.txt', 'toto')
    with open(file, 'r') as f:
        assert f.read() == get_data('/root/dummy.txt', 'toto')


def test_set_user_permissions():
    basic_setup()
    file = os.path.join(ROOTDIR, 'tests/dummy.txt')
    assert put_file(file, '/root/dummy.txt', 'toto')
    assert docker_exec('ls -al /root | grep dummy', 'toto').startswith(('-rw-rw-r--  1 root root'))
    assert set_user('/root/dummy.txt', 'www-data', 'toto')
    assert docker_exec('ls -al /root | grep dummy', 'toto').startswith(('-rw-rw-r--  1 www-data root'))
    assert set_permissions('/root/dummy.txt', '0744', 'toto')
    assert docker_exec('ls -al /root | grep dummy', 'toto').startswith(('-rwxr--r--  1 www-data root'))
