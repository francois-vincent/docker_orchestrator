# encoding: utf-8

import time

from . import *
import utils


def get_images(filter=None):
    """ Get images names, with optional filter on name.
    :param filter: if string, get images names containing it, if python container, get images in this set.
    :return: a list of images names
    """
    docker_images = utils.Command('docker images').stdout_column(0, 1)
    if filter:
        if isinstance(filter, basestring):
            return [x for x in docker_images if filter in x]
        else:
            return [x for x in docker_images if x in filter]
    return docker_images


def get_containers(filter=None, image=None, all=True):
    """ Get containers names, with optional filter on name.
    :param filter: if string, get containers names containing it, if python container (list, set, ...),
           get containers in this set.
    :param image: if string, get containers from this image (ignore filter).
    :param all: if False, get only running containers, else get all containers.
    :return: a list of containers names
    """
    docker_cmd = 'docker ps -a' if all else 'docker ps'
    if image:
        return utils.extract_column(utils.filter_column(utils.Command(docker_cmd).stdout, 1, eq=image), -1)
    else:
        containers = utils.Command(docker_cmd).stdout_column(-1, 1)
        if filter:
            if isinstance(filter, basestring):
                return [x for x in containers if filter in x]
            else:
                return [x for x in containers if x in filter]
        return containers


def container_stop(*container):
    ret = True
    for cont in container:
        ret &= not utils.command('docker stop ' + cont)
    return ret


def container_delete(*container):
    ret = True
    for cont in container:
        ret &= not utils.command('docker rm ' + cont)
    return ret


def image_delete(image):
    return not utils.command('docker rmi ' + image)


def image_delete_and_containers(image):
    """ WARNING: This will remove an image and all its dependant containers
    """
    for container in get_containers(image=image):
        container_stop(container)
    for container in get_containers(image=image, all=True):
        container_delete(container)
    return image_delete(image)


def docker_build(image, tag=None, context=None):
    cmd = 'docker build -f {}/Dockerfile -t {} .'.format(image, tag or image)
    print(utils.yellow(cmd))
    with utils.cd(context or os.path.join(ROOTDIR, 'images')):
        return not utils.Command(cmd, show='Build: ').returncode


def docker_run(image, container, host=None, parameters=None):
    cmd = 'docker run -d '
    cmd += '--name {} '.format(container)
    cmd += '-h {} '.format(host or container)
    if parameters:
        cmd += parameters + ' '
    cmd += image
    print(utils.yellow(cmd))
    return not utils.command(cmd)


def docker_commit(container, image):
    return not utils.command('docker commit {} {}'.format(container, image))


def get_container_ip(container, raises=False):
    docker_cmd = utils.Command("docker inspect --format '{{ .NetworkSettings.IPAddress }}' %s" % container)
    if raises and docker_cmd.stderr:
        raise RuntimeError("Container {} is not running".format(container))
    return docker_cmd.stdout.strip()


def docker_exec(cmd, container, user=None, stdout_only=True, status_only=False, raises=False, strip=True):
    docker_cmd = 'docker exec -i {} {} {}'.format('-u {}'.format(user) if user else '', container, cmd)
    if status_only:
        return not utils.command(docker_cmd)
    dock = utils.Command(docker_cmd)
    if raises and dock.returncode:
        raise RuntimeError(
            "Error while executing <{}> on {}: [{}]".
                format(docker_cmd, container, dock.stderr.strip() or dock.returncode))
    if stdout_only:
        return dock.stdout[:-1] if strip else dock.stdout
    return dock


def path_exists(path, container):
    return docker_exec('test -e {}'.format(path), container, status_only=True)


def put_data(data, dest, container, append=False, user=None, perms=None):
    if append and not path_exists(dest, container):
        docker_exec('touch {}'.format(dest), container)
    docker_cmd = 'docker exec -i {} /bin/bash -c "cat {} {}"'.format(container, '>>' if append else '>', dest)
    utils.command_input(docker_cmd, data)
    if user:
        set_user(dest, user, container)
    if perms:
        set_permissions(dest, perms, container)
    return True


def get_data(source, container):
    return docker_exec('cat {}'.format(source), container, raises=True, strip=False)


def put_file(source, dest, container, user=None, perms=None):
    docker_cmd = 'docker cp {} {}:{}'.format(source, container, dest)
    ret = utils.command(docker_cmd)
    if ret:
        raise RuntimeError("Error while executing<{}> on {}".format(docker_cmd, container))
    if user:
        set_user(dest, user, container)
    if perms:
        set_permissions(dest, perms, container)
    return True


def set_user(path, user, container):
    cmd = 'chown {} {}'.format(user, path)
    return docker_exec(cmd, container, status_only=True, raises=True)


def set_permissions(path, perms, container):
    cmd = 'chmod {} {}'.format(perms, path)
    return docker_exec(cmd, container, status_only=True, raises=True)


def get_version(app, container):
    text = docker_exec('apt-cache policy {}'.format(app), container, user='root')
    try:
        return utils.extract_column(utils.filter_column(text, 0, startswith='Install'), 1, sep=':')[0]
    except IndexError:
        return None


def wait_running_command(cmd, container, timeout=1):
    count, step = timeout, 0.2
    while count > 0:
        if cmd in docker_exec('ps ax', container):
            return True
        time.sleep(step)
        count -= step
    return False
