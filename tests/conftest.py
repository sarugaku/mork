# -*- coding=utf-8 -*-

import pytest
import mork
import os
import sys
import vistir


@pytest.fixture(scope="function")
def virtualenv(tmpdir_factory):
    venv_dir = tmpdir_factory.mktemp("passa-testenv")
    print("Creating virtualenv {0!r}".format(venv_dir.strpath))
    venv_path = vistir.compat.Path(venv_dir.strpath).as_posix()
    c = vistir.misc.run([sys.executable, "-m", "virtualenv", venv_path],
                            return_object=True, block=True, nospin=True)
    if c.returncode == 0:
        print("Virtualenv created...")
        return venv_dir
    raise RuntimeError("Failed creating virtualenv for testing...{0!r}".format(c.err.strip()))


@pytest.fixture
def tmpvenv(virtualenv, tmpdir):
    venv_path = vistir.compat.Path(virtualenv.strpath).as_posix()
    with vistir.contextmanagers.temp_environ():
        os.environ["PACKAGEBUILDER_CACHE_DIR"] = tmpdir.strpath
        yield mork.virtualenv.VirtualEnv(venv_path)
    if "PACKAGEBUILDER_CACHE_DIR" in os.environ:
        del os.environ["PACKAGEBUILDER_CACHE_DIR"]
