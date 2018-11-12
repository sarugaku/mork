# -*- coding=utf-8 -*-

import base64
import contextlib
import hashlib
import importlib
import json
import os
import re
import site
import sys

from distutils.sysconfig import get_python_lib
from sysconfig import get_paths

import pkg_resources
import six

from cached_property import cached_property

import distlib.scripts
import distlib.wheel
import vistir


class VirtualEnv(object):
    def __init__(self, prefix=None, base_working_set=None, is_venv=True):
        pkgresources = self.safe_import("pkg_resources")
        sys_module = self.safe_import("sys")
        own_dist = pkgresources.get_distribution(pkgresources.Requirement("mork"))
        _working_set = pkgresources.WorkingSet(sys_module.path)
        if base_working_set is None:
            base_working_set = _working_set
        self.own_dist = own_dist
        self.base_working_set = base_working_set
        self.is_venv = is_venv
        self.system_python = sys.executable
        self.real_prefix = getattr(sys, "real_prefix", sys.prefix)
        self._modules = {'pkg_resources': pkgresources, 'mork': own_dist}
        self.extra_dists = []
        prefix = prefix if prefix else sys_module.prefix
        self.prefix = vistir.compat.Path(prefix)
        super(VirtualEnv, self).__init__()

    @classmethod
    def from_project_path(cls, path):
        """Utility for finding a virtualenv location based on a project path"""
        path = vistir.compat.Path(path)
        if path.name == 'Pipfile':
            pipfile_path = path
            path = path.parent
        else:
            pipfile_path = path / 'Pipfile'
        pipfile_location = cls.normalize_path(pipfile_path)
        venv_path = path / '.venv'
        if venv_path.exists():
            if not venv_path.is_dir():
                possible_path = vistir.compat.Path(venv_path.read_text().strip())
                if possible_path.exists():
                    return cls(possible_path.as_posix())
            else:
                if venv_path.joinpath('lib').exists():
                    return cls(venv_path.as_posix())
        sanitized = re.sub(r'[ $`!*@"\\\r\n\t]', "_", path.name)[0:42]
        hash_ = hashlib.sha256(pipfile_location.encode()).digest()[:6]
        encoded_hash = base64.urlsafe_b64encode(hash_).decode()
        hash_fragment = encoded_hash[:8]
        venv_name = "{0}-{1}".format(sanitized, hash_fragment)
        return cls(cls.get_workon_home().joinpath(venv_name).as_posix())

    @classmethod
    def normalize_path(cls, path):
        if not path:
            return
        if isinstance(path, six.string_types):
            path = vistir.compat.Path(path)
        if not path.is_absolute():
            try:
                path = path.resolve()
            except OSError:
                path = path.absolute()
        path = vistir.path.unicode_path("{0}".format(path))
        if os.name != "nt":
            return path

        drive, tail = os.path.splitdrive(path)
        # Only match (lower cased) local drives (e.g. 'c:'), not UNC mounts.
        if drive.islower() and len(drive) == 2 and drive[1] == ":":
            path = "{}{}".format(drive.upper(), tail)

        return vistir.path.unicode_path(path)

    @classmethod
    def get_workon_home(cls):
        workon_home = os.environ.get("WORKON_HOME")
        if not workon_home:
            if os.name == "nt":
                workon_home = "~/.virtualenvs"
            else:
                workon_home = os.path.join(
                    os.environ.get("XDG_DATA_HOME", "~/.local/share"), "virtualenvs"
                )
        return vistir.compat.Path(os.path.expandvars(workon_home)).expanduser()

    @classmethod
    def filter_sources(cls, requirement, sources):
        if not sources or not requirement.index:
            return sources
        filtered_sources = [
            source for source in sources
            if source.get("name") == requirement.index
        ]
        return filtered_sources or sources

    def safe_import(self, name):
        """Helper utility for reimporting previously imported modules while inside the venv"""
        module = None
        if name not in self._modules:
            self._modules[name] = importlib.import_module(name)
        module = self._modules[name]
        if not module:
            dist = next(iter(
                dist for dist in self.base_working_set if dist.project_name == name
            ), None)
            if dist:
                dist.activate()
            module = importlib.import_module(name)
        if name in sys.modules:
            try:
                six.moves.reload_module(module)
                six.moves.reload_module(sys.modules[name])
            except TypeError:
                del sys.modules[name]
                sys.modules[name] = self._modules[name]
        return module

    @classmethod
    def get_sys_path(cls, python_path):
        """Get the :data:`sys.path` data for a given python executable.

        :param str python_path: Path to a specific python executable.
        :return: The system path information for that python runtime.
        :rtype: list
        """

        command = [python_path, "-c", "import json, sys; print(json.dumps(sys.path))"]
        c = vistir.misc.run(command, return_object=True, block=True, nospin=True)
        assert c.returncode == 0, "failed loading virtualenv path"
        sys_path = json.loads(c.out.strip())
        return sys_path

    @classmethod
    def resolve_dist(cls, dist, working_set):
        """Given a local distribution and a working set, returns all dependencies from the set.

        :param dist: A single distribution to find the dependencies of
        :type dist: :class:`pkg_resources.Distribution`
        :param working_set: A working set to search for all packages
        :type working_set: :class:`pkg_resources.WorkingSet`
        :return: A set of distributions which the package depends on, including the package
        :rtype: set(:class:`pkg_resources.Distribution`)
        """

        deps = set()
        deps.add(dist)
        try:
            reqs = dist.requires()
        except AttributeError:
            return deps
        for req in reqs:
            dist = working_set.find(req)
            deps |= cls.resolve_dist(dist, working_set)
        return deps

    def add_dist(self, dist_name):
        pkg_resources = self.safe_import("pkg_resources")
        dist = pkg_resources.get_distribution(pkg_resources.Requirement(dist_name))
        extras = self.resolve_dist(dist, self.base_working_set)
        if extras:
            self.extra_dists.extend(extras)

    @property
    def pyversion(self):
        include_dir = self.prefix / "include"
        python_path = next(iter(list(include_dir.iterdir())), None)
        if python_path and python_path.name.startswith("python"):
            python_version = python_path.name.replace("python", "")
            py_version_short, abiflags = python_version[:3], python_version[3:]
            return {"py_version_short": py_version_short, "abiflags": abiflags}
        return {}

    @cached_property
    def base_paths(self):
        """
        Returns the context appropriate paths for the environment.

        :return: A dictionary of environment specific paths to be used for installation operations
        :rtype: dict

        .. note:: The implementation of this is borrowed from a combination of pip and
           virtualenv and is likely to change at some point in the future.

        >>> from pipenv.core import project
        >>> from pipenv.environment import Environment
        >>> env = Environment(prefix=project.virtualenv_location, is_venv=True, sources=project.sources)
        >>> import pprint
        >>> pprint.pprint(env.base_paths)
        {'PATH': '/home/hawk/.virtualenvs/pipenv-MfOPs1lW/bin::/bin:/usr/bin',
        'PYTHONPATH': '/home/hawk/.virtualenvs/pipenv-MfOPs1lW/lib/python3.7/site-packages',
        'data': '/home/hawk/.virtualenvs/pipenv-MfOPs1lW',
        'include': '/home/hawk/.pyenv/versions/3.7.1/include/python3.7m',
        'libdir': '/home/hawk/.virtualenvs/pipenv-MfOPs1lW/lib/python3.7/site-packages',
        'platinclude': '/home/hawk/.pyenv/versions/3.7.1/include/python3.7m',
        'platlib': '/home/hawk/.virtualenvs/pipenv-MfOPs1lW/lib/python3.7/site-packages',
        'platstdlib': '/home/hawk/.virtualenvs/pipenv-MfOPs1lW/lib/python3.7',
        'prefix': '/home/hawk/.virtualenvs/pipenv-MfOPs1lW',
        'purelib': '/home/hawk/.virtualenvs/pipenv-MfOPs1lW/lib/python3.7/site-packages',
        'scripts': '/home/hawk/.virtualenvs/pipenv-MfOPs1lW/bin',
        'stdlib': '/home/hawk/.pyenv/versions/3.7.1/lib/python3.7'}
        """

        prefix = self.prefix.as_posix()
        install_scheme = 'nt' if (os.name == 'nt') else 'posix_prefix'
        paths = get_paths(install_scheme, vars={
            'base': prefix,
            'platbase': prefix,
        })
        paths["PATH"] = paths["scripts"] + os.pathsep + os.defpath
        if "prefix" not in paths:
            paths["prefix"] = prefix
        purelib = get_python_lib(plat_specific=0, prefix=prefix)
        platlib = get_python_lib(plat_specific=1, prefix=prefix)
        if purelib == platlib:
            lib_dirs = purelib
        else:
            lib_dirs = purelib + os.pathsep + platlib
        paths["libdir"] = purelib
        paths["purelib"] = purelib
        paths["platlib"] = platlib
        paths['PYTHONPATH'] = lib_dirs
        paths["libdirs"] = lib_dirs
        return paths

    @cached_property
    def script_basedir(self):
        """Path to the environment scripts dir"""
        script_dir = self.base_paths["scripts"]
        return script_dir

    @property
    def python(self):
        """Path to the environment python"""
        py = vistir.compat.Path(self.base_paths["scripts"]).joinpath("python").as_posix()
        if not py:
            return vistir.compat.Path(sys.executable).as_posix()
        return py

    @cached_property
    def sys_path(self):
        """The system path inside the environment

        :return: The :data:`sys.path` from the environment
        :rtype: list
        """

        current_executable = vistir.compat.Path(sys.executable).as_posix()
        if not self.python or self.python == current_executable:
            return sys.path
        elif any([sys.prefix == self.prefix, not self.is_venv]):
            return sys.path
        cmd_args = [self.python, "-c", "import json, sys; print(json.dumps(sys.path))"]
        path, _ = vistir.misc.run(cmd_args, return_object=False, nospin=True, block=True, combine_stderr=False)
        path = json.loads(path.strip())
        return path

    @cached_property
    def system_paths(self):
        paths = {}
        paths = get_paths()
        return paths

    @cached_property
    def sys_prefix(self):
        """The prefix run inside the context of the environment

        :return: The python prefix inside the environment
        :rtype: :data:`sys.prefix`
        """

        command = [self.python, "-c" "import sys; print(sys.prefix)"]
        c = vistir.misc.run(command, return_object=True, block=True, nospin=True)
        sys_prefix = vistir.compat.Path(vistir.misc.to_text(c.out).strip()).as_posix()
        return sys_prefix

    @cached_property
    def paths(self):
        paths = {}
        with vistir.contextmanagers.temp_environ(), vistir.contextmanagers.temp_path():
            os.environ["PYTHONIOENCODING"] = vistir.compat.fs_str("utf-8")
            os.environ["PYTHONDONTWRITEBYTECODE"] = vistir.compat.fs_str("1")
            paths = self.base_paths
            os.environ["PATH"] = paths["PATH"]
            os.environ["PYTHONPATH"] = paths["PYTHONPATH"]
            if "headers" not in paths:
                paths["headers"] = paths["include"]
        return paths

    @property
    def libdir(self):
        purelib = self.paths.get("purelib", None)
        if purelib and os.path.exists(purelib):
            return "purelib", purelib
        return "platlib", self.paths["platlib"]

    def find_egg(self, egg_dist):
        site_packages = get_python_lib()
        search_filename = "{0}.egg-link".format(egg_dist.project_name)
        try:
            user_site = site.getusersitepackages()
        except AttributeError:
            user_site = site.USER_SITE
        search_locations = [site_packages, user_site]
        for site_directory in search_locations:
            egg = os.path.join(site_directory, search_filename)
            if os.path.isfile(egg):
                return egg

    def locate_dist(self, dist):
        location = self.find_egg(dist)
        if not location:
            return dist.location

    def dist_is_in_project(self, dist):
        from .project import _normalized
        prefix = _normalized(self.base_paths["prefix"])
        location = self.locate_dist(dist)
        if not location:
            return False
        return _normalized(location).startswith(prefix)

    def get_installed_packages(self):
        workingset = self.get_working_set()
        packages = [pkg for pkg in workingset if self.dist_is_in_project(pkg)]
        return packages

    def get_finder(self):
        from .vendor.pip_shims import Command, cmdoptions, index_group, PackageFinder
        from .environments import PIPENV_CACHE_DIR
        index_urls = [source.get("url") for source in self.sources]

        class PipCommand(Command):
            name = "PipCommand"

        pip_command = PipCommand()
        index_opts = cmdoptions.make_option_group(
            index_group, pip_command.parser
        )
        cmd_opts = pip_command.cmd_opts
        pip_command.parser.insert_option_group(0, index_opts)
        pip_command.parser.insert_option_group(0, cmd_opts)
        pip_args = self._modules["pipenv"].utils.prepare_pip_source_args(self.sources, [])
        pip_options, _ = pip_command.parser.parse_args(pip_args)
        pip_options.cache_dir = PIPENV_CACHE_DIR
        pip_options.pre = self.pipfile.get("pre", False)
        with pip_command._build_session(pip_options) as session:
            finder = PackageFinder(
                find_links=pip_options.find_links,
                index_urls=index_urls, allow_all_prereleases=pip_options.pre,
                trusted_hosts=pip_options.trusted_hosts,
                process_dependency_links=pip_options.process_dependency_links,
                session=session
            )
            yield finder

    def get_package_info(self):
        dependency_links = []
        packages = self.get_installed_packages()
        # This code is borrowed from pip's current implementation
        for dist in packages:
            if dist.has_metadata('dependency_links.txt'):
                dependency_links.extend(dist.get_metadata_lines('dependency_links.txt'))

        with self.get_finder() as finder:
            finder.add_dependency_links(dependency_links)

            for dist in packages:
                typ = 'unknown'
                all_candidates = finder.find_all_candidates(dist.key)
                if not finder.pip_options.pre:
                    # Remove prereleases
                    all_candidates = [
                        candidate for candidate in all_candidates
                        if not candidate.version.is_prerelease
                    ]

                if not all_candidates:
                    continue
                best_candidate = max(all_candidates, key=finder._candidate_sort_key)
                remote_version = best_candidate.version
                if best_candidate.location.is_wheel:
                    typ = 'wheel'
                else:
                    typ = 'sdist'
                # This is dirty but makes the rest of the code much cleaner
                dist.latest_version = remote_version
                dist.latest_filetype = typ
                yield dist

    def get_outdated_packages(self):
        return [
            pkg for pkg in self.get_package_info()
            if pkg.latest_version._version > pkg.parsed_version._version
        ]

    @property
    def scripts_dir(self):
        return self.base_paths["scripts"]

    @cached_property
    def initial_working_set(self):
        system_path = self.get_sys_path(self.system_python)
        working_set = self._modules["pkg_resources"].WorkingSet(system_path)
        return working_set

    def get_distributions(self):
        """Retrives the distributions installed on the library path of the virtualenv

        :return: A set of distributions found on the library path
        :rtype: iterator
        """

        return self._modules["pkg_resources"].find_distributions(
            self.paths["PYTHONPATH"], only=True
        )

    def get_working_set(self):
        """Retrieve the working set of installed packages for the virtualenv.

        :return: The working set for the virtualenv
        :rtype: :class:`pkg_resources.WorkingSet`
        """

        working_set = self._modules["pkg_resources"].WorkingSet(self.sys_path)
        return working_set

    @cached_property
    def python_version(self):
        with self.activated():
            sysconfig = self.safe_import("sysconfig")
            py_version = sysconfig.get_python_version()
            return py_version

    def get_setup_install_args(self, pkgname, setup_py, develop=False):
        """Get setup.py install args for installing the supplied package in the virtualenv

        :param str pkgname: The name of the package to install
        :param str setup_py: The path to the setup file of the package
        :param bool develop: Whether the package is in development mode
        :return: The installation arguments to pass to the interpreter when installing
        :rtype: list
        """

        headers = self.base_paths["headers"]
        headers = headers / "python{0}".format(self.python_version) / pkgname
        install_arg = "install" if not develop else "develop"
        return [
            self.python, "-u", "-c", SETUPTOOLS_SHIM % setup_py, install_arg,
            "--single-version-externally-managed",
            "--install-headers={0}".format(self.base_paths["headers"]),
            "--install-purelib={0}".format(self.base_paths["purelib"]),
            "--install-platlib={0}".format(self.base_paths["platlib"]),
            "--install-scripts={0}".format(self.base_paths["scripts"]),
            "--install-data={0}".format(self.base_paths["data"]),
        ]

    def setuptools_install(self, chdir_to, pkg_name, setup_py_path=None, editable=False):
        """Install an sdist or an editable package into the virtualenv

        :param str chdir_to: The location to change to
        :param str setup_py_path: The path to the setup.py, if applicable defaults to None
        :param  bool editable: Whether the package is editable, defaults to False
        """

        install_options = ["--prefix={0}".format(self.prefix.as_posix()),]
        with vistir.contextmanagers.cd(chdir_to):
            c = self.run(
                self.get_setup_install_args(pkg_name, setup_py_path, develop=editable) +
                install_options, cwd=chdir_to
            )
            return c.returncode

    def install(self, req, editable=False, sources=[]):
        """Install a package into the virtualenv

        :param req: A requirement to install
        :type req: :class:`requirementslib.models.requirement.Requirement`
        :param bool editable: Whether the requirement is editable, defaults to False
        :param list sources: A list of pip sources to consult, defaults to []
        :return: A return code, 0 if successful
        :rtype: int
        """

        try:
            packagebuilder = self.safe_import("packagebuilder")
        except ImportError:
            packagebuilder = None
        with self.activated(include_extras=False):
            if not packagebuilder:
                return 2
            ireq = req.as_ireq()
            sources = self.filter_sources(req, sources)
            cache_dir = os.environ.get('PASSA_CACHE_DIR',
                os.environ.get(
                    'PIPENV_CACHE_DIR',
                    vistir.path.create_tracked_tempdir(prefix="passabuild")
                )
            )
            built = packagebuilder.build.build(ireq, sources, cache_dir)
            if isinstance(built, distlib.wheel.Wheel):
                maker = distlib.scripts.ScriptMaker(None, None)
                built.install(self.paths, maker)
            else:
                path = vistir.compat.Path(built.path)
                cd_path = path.parent
                setup_py = cd_path.joinpath("setup.py")
                return self.setuptools_install(
                    cd_path.as_posix(), req.name, setup_py.as_posix(),
                    editable=req.editable
                )
            return 0

    @contextlib.contextmanager
    def activated(self, include_extras=True, extra_dists=[]):
        """A context manager which activates the virtualenv.

        :param list extra_dists: Paths added to the context after the virtualenv is activated.

        This context manager sets the following environment variables:
            * `PYTHONUSERBASE`
            * `VIRTUAL_ENV`
            * `PYTHONIOENCODING`
            * `PYTHONDONTWRITEBYTECODE`

        In addition, it activates the virtualenv inline by calling `activate_this.py`.
        """

        original_path = sys.path
        original_prefix = sys.prefix
        original_user_base = os.environ.get("PYTHONUSERBASE", None)
        original_venv = os.environ.get("VIRTUAL_ENV", None)
        parent_path = vistir.compat.Path(__file__).absolute().parent.parent.as_posix()
        prefix = self.prefix.as_posix()
        with vistir.contextmanagers.temp_environ(), vistir.contextmanagers.temp_path():
            os.environ["PATH"] = os.pathsep.join([
                vistir.compat.fs_str(self.scripts_dir),
                vistir.compat.fs_str(self.prefix.as_posix()),
                os.environ.get("PATH", "")
            ])
            os.environ["PYTHONIOENCODING"] = vistir.compat.fs_str("utf-8")
            os.environ["PYTHONDONTWRITEBYTECODE"] = vistir.compat.fs_str("1")
            os.environ["PATH"] = self.base_paths["PATH"]
            os.environ["PYTHONPATH"] = self.base_paths["PYTHONPATH"]
            if self.is_venv:
                os.environ["VIRTUAL_ENV"] = vistir.compat.fs_str(prefix)
            sys.path = self.sys_path
            sys.prefix = self.sys_prefix
            site.addsitedir(self.base_paths["purelib"])
            if include_extras:
                site.addsitedir(parent_path)
                extra_dists = list(self.extra_dists) + extra_dists
                for extra_dist in extra_dists:
                    if extra_dist not in self.get_working_set():
                        extra_dist.activate(self.sys_path)
                sys.modules["recursive_monkey_patch"] = self.recursive_monkey_patch
            try:
                yield
            finally:
                del os.environ["VIRTUAL_ENV"]
                if original_user_base:
                    os.environ["PYTHONUSERBASE"] = original_user_base
                if original_venv:
                    os.environ["VIRTUAL_ENV"] = original_venv
                sys.path = original_path
                sys.prefix = original_prefix
                six.moves.reload_module(pkg_resources)

    def run(self, cmd, cwd=os.curdir):
        """Run a command with :class:`~subprocess.Popen` in the context of the virtualenv

        :param cmd: A command to run in the virtual environment
        :type cmd: str or list
        :param str cwd: The working directory in which to execute the command, defaults to :data:`os.curdir`
        :return: A finished command object
        :rtype: :class:`~subprocess.Popen`
        """

        c = None
        with self.activated():
            script = vistir.cmdparse.Script.parse(cmd)
            c = vistir.misc.run(script._parts, return_object=True, nospin=True, cwd=cwd)
        return c

    def run_py(self, cmd, cwd=os.curdir):
        """Run a python command in the virtualenv context.

        :param cmd: A command to run in the virtual environment - runs with `python -c`
        :type cmd: str or list
        :param str cwd: The working directory in which to execute the command, defaults to :data:`os.curdir`
        :return: A finished command object
        :rtype: :class:`~subprocess.Popen`
        """

        c = None
        if isinstance(cmd, six.string_types):
            script = vistir.cmdparse.Script.parse("{0} -c {1}".format(self.python, cmd))
        else:
            script = vistir.cmdparse.Script.parse([self.python, "-c"] + list(cmd))
        with self.activated():
            c = vistir.misc.run(script._parts, return_object=True, nospin=True, cwd=cwd)
        return c

    def is_installed(self, pkgname):
        """Given a package name, returns whether it is installed in the virtual environment

        :param str pkgname: The name of a package
        :return: Whether the supplied package is installed in the environment
        :rtype: bool
        """

        return any(d for d in self.get_distributions() if d.project_name == pkgname)

    def get_monkeypatched_pathset(self):
        """Returns a monkeypatched `UninstallPathset` for using to uninstall packages from the virtualenv

        :return: A patched `UninstallPathset` which enables uninstallation of venv packages
        :rtype: :class:`pip._internal.req.req_uninstall.UninstallPathset`
        """

        from pip_shims.shims import InstallRequirement
        # Determine the path to the uninstall module name based on the install module name
        uninstall_path = InstallRequirement.__module__.replace(
            "req_install", "req_uninstall"
        )
        req_uninstall = self.safe_import(uninstall_path)
        self.recursive_monkey_patch.monkey_patch(
            PatchedUninstaller, req_uninstall.UninstallPathSet
        )
        return req_uninstall.UninstallPathSet

    @contextlib.contextmanager
    def uninstall(self, pkgname, *args, **kwargs):
        """A context manager which allows uninstallation of packages from the virtualenv

        :param str pkgname: The name of a package to uninstall

        >>> venv = VirtualEnv("/path/to/venv/root")
        >>> with venv.uninstall("pytz", auto_confirm=True, verbose=False) as uninstaller:
                cleaned = uninstaller.paths
        >>> if cleaned:
                print("uninstalled packages: %s" % cleaned)
        """

        auto_confirm = kwargs.pop("auto_confirm", True)
        verbose = kwargs.pop("verbose", False)
        with self.activated():
            pathset_base = self.get_monkeypatched_pathset()
            dist = next(
                iter(filter(lambda d: d.project_name == pkgname, self.get_working_set())),
                None
            )
            pathset = pathset_base.from_dist(dist)
            if pathset is not None:
                pathset.remove(auto_confirm=auto_confirm, verbose=verbose)
            try:
                yield pathset
            except Exception as e:
                if pathset is not None:
                    pathset.rollback()
            else:
                if pathset is not None:
                    pathset.commit()
            if pathset is None:
                return


SETUPTOOLS_SHIM = (
    "import setuptools, tokenize;__file__=%r;"
    "f=getattr(tokenize, 'open', open)(__file__);"
    "code=f.read().replace('\\r\\n', '\\n');"
    "f.close();"
    "exec(compile(code, __file__, 'exec'))"
)


class PatchedUninstaller(object):
    def _permitted(self, path):
        return True
