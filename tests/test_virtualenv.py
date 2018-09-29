# -*- coding=utf-8 -*-

from __future__ import absolute_import, print_function

import mork
import os
import pytest
import sys
import vistir


def test_workon_home(tmpdir):
    workon_home = tmpdir.mkdir("virtualenvs")
    with vistir.contextmanagers.temp_environ():
        os.environ["WORKON_HOME"] = workon_home.strpath
        workon_home_str = vistir.compat.Path(workon_home.strpath).as_posix()
        assert mork.virtualenv.VirtualEnv.get_workon_home().as_posix() == workon_home_str


@pytest.mark.parametrize('input_path, normalized', [
        ('/home/user/path/Some\ Path', u'/home/user/path/Some\ Path'),
        ('\\\\networkpath\\some\\share\\drive', u'\\\\networkpath\\some\\share\\drive'),
        ('c:\\some.user\\path\\To\something', u'C:\\some.user\\path\\To\something'),
        ('C:\\some.user\\path\\To\something', u'C:\\some.user\\path\\To\something'),
    ]
)
def test_normpath(input_path, normalized, monkeypatch):
    with monkeypatch.context() as m:
        m.setattr(vistir.compat.Path, "is_absolute", lambda x: True)
        if os.name == "nt":
            normalized = normalized.replace("/", "\\")
        m.setattr(os, "name", "nt")
        import importlib
        pathlib = importlib.import_module(vistir.compat.Path.__module__)
        if not pathlib.WindowsPath._flavour.is_supported:
            # hack for linux to still run the same test suite
            m.setattr(pathlib, "WindowsPath", pathlib.PosixPath)
            if input_path[0].isalnum():
                new_path = input_path[0].capitalize() + input_path[1:]
                input_path = new_path
        assert mork.virtualenv.VirtualEnv.normalize_path(input_path) == normalized


def test_get_dists(tmpvenv):
    dists = tmpvenv.get_distributions()
    dist_names = [dist.project_name for dist in dists]
    assert all(pkg in dist_names for pkg in ['setuptools', 'pip', 'wheel']), dist_names


def test_get_sys_path():
    python_path = sys.executable
    mork_path = [p for p in mork.virtualenv.VirtualEnv.get_sys_path(python_path) if p]
    assert all(p in sys.path for p in mork_path), set(mork_path) - set(sys.path)


def test_dist_resolution():
    import pkg_resources
    requests = pkg_resources.get_distribution(pkg_resources.Requirement('requests'))
    dists = mork.virtualenv.VirtualEnv.resolve_dist(requests, pkg_resources.working_set)
    dist_names = [dist.project_name for dist in dists]
    expected = ['certifi', 'urllib3', 'requests', 'chardet', 'idna']
    assert all([pkg in dist_names for pkg in expected]), set(expected) ^ set(dist_names)


def test_properties(tmpvenv):
    script_basedir = "Scripts" if os.name == "nt" else "bin"
    assert script_basedir == tmpvenv.script_basedir
    scripts_dir = tmpvenv.venv_dir.joinpath(script_basedir).as_posix()
    assert scripts_dir == vistir.compat.Path(tmpvenv.scripts_dir).as_posix()
    python = "{0}/python".format(tmpvenv.venv_dir.joinpath(script_basedir).as_posix())
    assert python == tmpvenv.python
    libdir = "Lib" if os.name == "nt" else "lib"
    libdir = tmpvenv.venv_dir.joinpath(libdir).as_posix().lower()
    assert any(
        vistir.compat.Path(pth).as_posix().lower().startswith(libdir)
        for pth in tmpvenv.sys_path
    ),  list(tmpvenv.sys_path)
    assert tmpvenv.sys_prefix == tmpvenv.venv_dir.as_posix()


def test_install(tmpvenv):
    import requirementslib
    requests = requirementslib.Requirement.from_line("requests")
    pytz = requirementslib.Requirement.from_line("pytz")
    retcode = tmpvenv.install(requests)
    assert retcode == 0
    retcode = tmpvenv.install(pytz)
    assert retcode == 0
    assert tmpvenv.is_installed("requests")
    assert tmpvenv.is_installed("pytz")
    venv_dists = [dist for dist in tmpvenv.get_distributions()]
    venv_workingset = [dist for dist in tmpvenv.get_working_set()]
    expected = ["requests", "pytz"]
    assert all(pkg in [dist.project_name for dist in venv_dists] for pkg in expected)
    assert all(pkg in [dist.project_name for dist in venv_workingset] for pkg in expected)
    with tmpvenv.activated():
        tmp_pytz = tmpvenv.safe_import("pytz")
        pytz_path = vistir.compat.Path(tmp_pytz.__path__[0]).as_posix()
        assert pytz_path.startswith(tmpvenv.venv_dir.as_posix()), pytz_path


def test_uninstall(tmpvenv):
    def uninstall(pkg):
        results = []
        with tmpvenv.uninstall(pkg, auto_confirm=True, verbose=False) as uninstaller:
            if uninstaller:
                results.append(pkg)
        return results

    import requirementslib
    requests = requirementslib.Requirement.from_line("requests")
    retcode = tmpvenv.install(requests)
    assert retcode == 0
    assert tmpvenv.is_installed("requests")
    requests_dist = next(iter(
        dist for dist in tmpvenv.get_distributions()
        if dist.project_name == "requests"), None
    )
    requests_deps = [
        dist for dist in tmpvenv.resolve_dist(requests_dist, tmpvenv.get_working_set())
        if dist is not None
    ]
    uninstalled_packages = []
    for dep in requests_deps:
        uninstalled = uninstall(dep.project_name)
        uninstalled_packages.extend(uninstalled)
    assert uninstalled_packages
    assert all(pkg.project_name in uninstalled_packages for pkg in requests_deps)
