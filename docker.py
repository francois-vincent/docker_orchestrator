# encoding: utf-8

from docker_basics import *
import utils


class PlatformManager(utils.Sequencer):
    """
    Class in charge of bringing up a running platform and performing other docker magic
    Check existence or creates the images,
    then check existence or runs the containers.
    Optionally, stops and commits the containers.
    """

    def __init__(self, platform, images, common_parameters='', parameters={},
                 network=None, user='root', timeout=1):
        """
        :param platform: string
        :param images: dictionary/pair iterable of container-name:image
        :param parameters: dictionary/pair iterable of container-name:iterable of strings
        """
        self.images_rootdir = ROOTDIR
        self.platform_name = platform
        self.platform = self
        self.network = network or platform
        self.images = images
        common_parameters += ' '
        self.parameters = {k: common_parameters for k in images}
        for k in images:
            if k in parameters:
                self.parameters[k] += parameters[k]
        self.user = user
        self.timeout = timeout
        self.containers = {k: '-'.join((v, self.platform_name, k)) for k, v in images.iteritems()}
        self.images_names = set(images.values())
        self.containers_names = self.containers.values()
        self.managers = {}

    def register_manager(self, name, manager):
        self.managers[name] = manager
        return self

    def get_manager(self, name):
        return self.managers.get(name)

    def host_from_container(self, container):
        for k, v in self.containers.iteritems():
            if v == container:
                return k
        raise LookupError("container {} not found".format(container))

    def pre_setup(self, *args):
        return self.run_sequence(args)

    def post_teardown(self, *args):
        self.post = args
        return self

    def standard_setup(self):
        self.build_images()
        self.setup_network()
        self.run_containers('rm_container')
        return self.connect_network()

    def reset(self, reset='rm_image'):
        """ Resets a platform
        :param reset: 'uproot': remove platform images and any dependant container
                      'rm_image': remove platform images and containers
                      'rm_container': remove and stop platform containers
                      'stop': stop platform containers
        """
        if not reset:
            return self
        if reset == 'uproot':
            self.images_delete(uproot=True)
            return self
        if reset in ('stop', 'rm_container', 'rm_image'):
            self.containers_stop()
        if reset in ('rm_container', 'rm_image'):
            self.containers_delete()
        if reset == 'rm_image':
            self.images_delete()
        return self

    def build_images(self, reset=None):
        self.reset(reset)
        existing = self.get_real_images()
        for image in self.images_names:
            if image not in existing:
                print(utils.yellow("Build image {}".format(image)))
                docker_build(image)
        return self

    def images_exist(self):
        return self.images_names == set(self.get_real_images())

    def run_containers(self, reset=None):
        self.reset(reset)
        running = self.get_real_containers()
        existing = self.get_real_containers(True)
        for k, v in self.images.iteritems():
            container = self.containers[k]
            if container in running:
                continue
            if container in existing:
                docker_start(container)
            else:
                docker_run(v, container, container, self.parameters[k])
        return self

    def get_real_images(self):
        return get_images(self.images_names)

    def get_real_containers(self, all=False):
        return get_containers(self.containers_names, all=all)

    def images_delete(self, uproot=False):
        func = image_delete_and_containers if uproot else image_delete
        for image in self.get_real_images():
            print(utils.red("Delete image {}".format(image)))
            func(image)
        return self

    def containers_stop(self):
        for container in self.get_real_containers():
            print(utils.yellow("Stop container {}".format(container)))
            container_stop(container)
        return self

    def containers_delete(self):
        for container in self.get_real_containers(True):
            print(utils.yellow("Delete container {}".format(container)))
            container_delete(container)
        return self

    def setup_network(self):
        if not self.network in get_networks(self.network):
            docker_network(self.network)
        return self

    def connect_network(self):
        for cont in self.containers_names:
            network_connect(self.network, cont)
        return self

    def teardown_network(self):
        if self.network in get_networks(self.network):
            docker_network(self.network, 'remove')
        return self

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.run_sequence(getattr(self, 'post', ()))

    def get_hosts(self, raises=False):
        """ Returns the dict(host, ip) of containers actually running, or raises
           an exception if the number of running containers differs from the number
           of defined containers.
        """
        self.hosts_ips = {k: get_container_ip(v) for k, v in self.containers.iteritems()}
        if raises:
            if not all(self.hosts_ips.values()):
                expected = len(self.containers)
                found = len([x for x in self.hosts_ips.itervalues() if x])
                raise RuntimeError("Expecting {} running containers, found {}".format(expected, found))
        return self.hosts_ips

    def wait_process(self, proc, raises=True):
        for container in self.containers.itervalues():
            if not wait_running_command(proc, container, timeout=self.timeout):
                if raises:
                    raise RuntimeError("Container {} has no running '{}'".format(container, proc))
                return
        return True

    def ssh(self, cmd, host=None):
        """ this method requires that an ssh daemon is running on the target
            and that an authorized_keys file is set with a rsa plubilc key,
            all conditions met by images provided in this project.
        """
        if host:
            return utils.ssh(cmd, get_container_ip(self.containers[host]), self.user)
        return {k: utils.ssh(cmd, get_container_ip(v), self.user) for k, v in self.containers.iteritems()}

    def scp(self, source, dest, host=None):
        """ this method requires that an ssh daemon is running on the target
            and that an authorized_keys file is set with a rsa plubilc key,
            all conditions met by images provided in this project.
        """
        containers = [self.containers[host]] if host else self.containers.itervalues()
        for container in containers:
            utils.scp(source, dest, get_container_ip(container), self.user)
        return self

    def ssh_put_data(self, data, dest, host=None, append=False):
        if not append:
            self.ssh('touch {}'.format(dest), host)
        cmd = ''.join(('echo "', data, '" >>' if append else '" >', dest))
        self.ssh(cmd, host)
        return self

    def ssh_get_data(self, source, host=None):
        return self.ssh('cat {}'.format(source), host)

    def docker_exec(self, cmd, host=None, status_only=False):
        if host:
            return docker_exec(cmd, self.containers[host], status_only=status_only)
        return {k: docker_exec(cmd, v, status_only=status_only) for k, v in self.containers.iteritems()}

    def put_data(self, data, dest, host=None, append=False):
        containers = [self.containers[host]] if host else self.containers.itervalues()
        for container in containers:
            put_data(data, dest, container, append=append)
        return self

    def put_file(self, data, dest, host=None, append=False):
        containers = [self.containers[host]] if host else self.containers.itervalues()
        for container in containers:
            put_data(data, dest, container, append=append)
        return self

    def get_data(self, source, host=None):
        if host:
            return get_data(source, self.containers[host])
        return {k: get_data(source, v) for k, v in self.containers.iteritems()}

    def path_exists(self, path, host=None, negate=False):
        containers = [self.containers[host]] if host else self.containers.itervalues()
        for container in containers:
            if negate:
                if not path_exists(path, container):
                    continue
                print(utils.red("Found path <{}> on host <{}>".format(path, self.host_from_container(container))))
            else:
                if path_exists(path, container):
                    continue
                print(utils.red("Path <{}> not found on host <{}>".format(path, self.host_from_container(container))))
            return False
        return True

    def get_version(self, app, host=None):
        if host:
            return get_version(app, self.containers[host])
        return {k: get_version(app, v) for k, v in self.containers.iteritems()}

    def commit_containers(self, images, stop=True):
        if stop:
            self.containers_stop()
        for k, v in self.containers.iteritems():
            print(utils.yellow("commit {} to {}".format(v, images[k])))
            docker_commit(v, images[k])
        return self

    def start_services(self, *args, **kwargs):
        """ start services on the platform
        :param args: sequence of services to start on all hosts.
        :param kwargs: key=host, value=sequence of services, or
                       key=service, value=sequence of hosts.
        """
        wait_process = kwargs.pop('wait_process', None)
        for service in args:
            self.docker_exec('service {} start'.format(service))
        hosts_keys = set(kwargs).issubset(set(self.images.keys()))
        for k, v in kwargs.iteritems():
            for x in v:
                if hosts_keys:
                    self.docker_exec('service {} start'.format(x), k)
                else:
                    self.docker_exec('service {} start'.format(k), x)
        if wait_process:
            if isinstance(wait_process, basestring):
                self.wait_process(wait_process)
            else:
                for w in wait_process:
                    self.wait_process(w)


class DeployedPlatformManager(PlatformManager):
    """ Class that manages the deployed platform, essentially through specific images and
        containers names, plus a setup function constructing these images and containers.
        Here the subclass PlatformManager is used as a mixin (constructor not called).
    """

    def __init__(self, platform, distri):
        self.platform = platform
        self.platform_name = platform.platform_name
        self.parameters = platform.parameters
        self.user = platform.user
        self.timeout = platform.timeout
        self.distri = distri
        self.images = {k: '-'.join((v, self.platform_name, k)) for k, v in platform.images.iteritems()}
        self.containers = {k: '-'.join((v, 'deployed')) for k, v in self.images.iteritems()}
        self.images_names = set(self.images.values())
        self.containers_names = self.containers.values()
        self.managers = {}

    def setup(self, reset=None):
        fabric = self.platform.get_manager('fabric')
        self.reset(reset)
        if not self.images_exist():
            self.platform.setup('rm_container')
            fabric.set_platform(distrib=self.distri)
            fabric.deploy_from_scratch(True)
            self.platform.commit_containers(self.images)
        self.run_containers('rm_container')
        fabric.register_platform(self)
        fabric.set_platform(distrib=self.distri)
        return self
