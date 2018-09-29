# -*- coding=utf-8 -*-

import base64
import contextlib
import hashlib
import importlib
import json
import os
import posixpath
import re
import sys
import sysconfig

import distlib.scripts
import distlib.wheel
import six

from cached_property import cached_property

import vistir


class VirtualEnv(object):
    def __init__(self, venv_dir):
        pkg_resources = self.safe_import("pkg_resources")
        sys_module = self.safe_import("sys")
        self.base_working_set = pkg_resources.WorkingSet(sys_module.path)
        own_dist = pkg_resources.get_distribution(pkg_resources.Requirement("mork"))
        self.extra_dists = self.resolve_dist(own_dist, self.base_working_set)
        self._modules = {'pkg_resources': pkg_resources}
        try:
            self.recursive_monkey_patch = self.safe_import("recursive_monkey_patch")
        except ImportError:
            self.recursive_monkey_patch = None
        self.venv_dir = vistir.compat.Path(venv_dir)

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

    @classmethod
    def safe_import(cls, name):
        """Helper utility for reimporting previously imported modules while inside the venv"""
        module = None
        if name not in sys.modules:
            module = importlib.import_module(name)
        else:
            module = sys.modules[name]
        six.moves.reload_module(module)
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

    @property
    def pyversion(self):
        include_dir = self.venv_dir / "include"
        python_path = next(iter(list(include_dir.iterdir())), None)
        if python_path and python_path.name.startswith("python"):
            python_version = python_path.name.replace("python", "")
            py_version_short, abiflags = python_version[:3], python_version[3:]
            return {"py_version_short": py_version_short, "abiflags": abiflags}
        return {}

    @cached_property
    def base_paths(self):
        if "sysconfig" not in self._modules:
            self._modules["sysconfig"] = self.safe_import("sysconfig")
        sysconfig = self._modules["sysconfig"]
        prefix = self.venv_dir.as_posix()
        scheme = sysconfig._get_default_scheme()
        config = {
            "base": prefix,
            "installed_base": prefix,
            "platbase": prefix,
            "installed_platbase": prefix
        }
        config.update(self.pyversion)
        paths = {
            k: v.format(**config)
            for k, v in sysconfig._INSTALL_SCHEMES[scheme].items()
        }
        if "prefix" not in paths:
            paths["prefix"] = prefix
        return paths

    @cached_property
    def script_basedir(self):
        """Path to the virtualenv scripts dir"""
        script_dir = os.path.basename(sysconfig.get_paths()["scripts"])
        return script_dir

    @property
    def python(self):
        """Path to the virtualenv python"""
        return self.venv_dir.joinpath(self.script_basedir).joinpath("python").as_posix()

    @cached_property
    def sys_path(self):
        """The system path inside the virtualenv

        :return: The :data:`sys.path` from the virtualenv
        :rtype: list
        """

        path = [
            p for p in self.get_sys_path(self.python)
            if posixpath.normpath(p).startswith(posixpath.normpath(str(self.venv_dir)))
        ]
        return path

    @cached_property
    def system_paths(self):
        paths = {}
        sysconfig = self.safe_import("sysconfig")
        paths = sysconfig.get_paths()
        return paths

    @cached_property
    def sys_prefix(self):
        """The prefix run inside the context of the virtualenv

        :return: The python prefix inside the virtualenv
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
            os.environ["PYTHONUSERBASE"] = vistir.compat.fs_str(self.venv_dir.as_posix())
            os.environ["PYTHONIOENCODING"] = vistir.compat.fs_str("utf-8")
            os.environ["PYTHONDONTWRITEBYTECODE"] = vistir.compat.fs_str("1")
            sysconfig = self.safe_import("sysconfig")
            self._modules["sysconfig"] = sysconfig
            paths = self.base_paths
            if "headers" not in paths:
                paths["headers"] = paths["include"]
        return paths

    @property
    def scripts_dir(self):
        return self.paths["scripts"]

    @property
    def libdir(self):
        purelib = self.paths.get("purelib", None)
        if purelib and os.path.exists(purelib):
            return "purelib", purelib
        return "platlib", self.paths["platlib"]

    @cached_property
    def initial_working_set(self):
        sysconfig = self.safe_import("sysconfig")
        pkg_resources = self.safe_import("pkg_resources")
        base = sysconfig.get_config_var("prefix")
        base_path = sysconfig._INSTALL_SCHEMES[sysconfig._get_default_scheme()]["scripts"]
        system_python = posixpath.join(
            base_path.format(base=base), "python"
        )
        system_path = self.get_sys_path(system_python)
        working_set = pkg_resources.WorkingSet(system_path)
        return working_set

    def get_distributions(self):
        """Retrives the distributions installed on the library path of the virtualenv

        :return: A set of distributions found on the library path
        :rtype: iterator
        """

        pkg_resources = self.safe_import("pkg_resources")
        return pkg_resources.find_distributions(self.paths["purelib"], only=True)

    def get_working_set(self):
        """Retrieve the working set of installed packages for the virtualenv.

        :return: The working set for the virtualenv
        :rtype: :class:`pkg_resources.WorkingSet`
        """

        working_set = None
        import pkg_resources
        working_set = pkg_resources.WorkingSet(self.sys_path)
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

        headers = self.paths["headers"]
        headers = headers / "python{0}".format(self.python_version) / pkgname
        install_arg = "install" if not develop else "develop"
        return [
            self.python, "-u", "-c", SETUPTOOLS_SHIM % setup_py, install_arg,
            "--single-version-externally-managed",
            "--install-headers={0}".format(self.paths["headers"]),
            "--install-purelib={0}".format(self.paths["purelib"]),
            "--install-platlib={0}".format(self.paths["platlib"]),
            "--install-scripts={0}".format(self.scripts_dir),
            "--install-data={0}".format(self.paths["data"]),
        ]

    def setuptools_install(self, chdir_to, pkg_name, setup_py_path=None, editable=False):
        """Install an sdist or an editable package into the virtualenv

        :param str chdir_to: The location to change to
        :param str setup_py_path: The path to the setup.py, if applicable defaults to None
        :param  bool editable: Whether the package is editable, defaults to False
        """

        install_options = ["--prefix={0}".format(self.venv_dir.as_posix()),]
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
        with vistir.contextmanagers.temp_environ(), vistir.contextmanagers.temp_path():
            os.environ["PYTHONIOENCODING"] = vistir.compat.fs_str("utf-8")
            os.environ["PYTHONDONTWRITEBYTECODE"] = vistir.compat.fs_str("1")
            activate_this = os.path.join(self.scripts_dir, "activate_this.py")
            with open(activate_this, "r") as f:
                code = compile(f.read(), activate_this, "exec")
                exec(code, dict(__file__=activate_this))
            os.environ["PYTHONUSERBASE"] = vistir.compat.fs_str(self.venv_dir.as_posix())
            os.environ["VIRTUAL_ENV"] = vistir.compat.fs_str(self.venv_dir.as_posix())
            sys.path = self.sys_path
            sys.prefix = self.sys_prefix
            pkg_resources = self.safe_import("pkg_resources")
            if include_extras:
                site = self.safe_import("site")
                site.addsitedir(parent_path)
                extra_dists = list(self.extra_dists) + extra_dists
                for extra_dist in extra_dists:
                    if extra_dist not in self.get_working_set():
                        extra_dist.activate(self.sys_path)
                sys.modules["recursive_monkey_patch"] = self.recursive_monkey_patch
            try:
                yield
            finally:
                print("Deactivating virtualenv...")
                del os.environ["VIRTUAL_ENV"]
                del os.environ["PYTHONUSERBASE"]
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
