# -*- coding=utf-8 -*-

import pytest
import mork
import sys
import vistir


@pytest.fixture(scope="function")
def virtualenv(tmpdir_factory):
    venv_dir = tmpdir_factory.mktemp("passa-testenv")
    print("Creating virtualenv {0!r}".format(venv_dir.strpath))
    c = vistir.misc.run([sys.executable, "-m", "virtualenv", venv_dir.strpath],
                            return_object=True, block=True, nospin=True)
    if c.returncode == 0:
        print("Virtualenv created...")
        return venv_dir
    raise RuntimeError("Failed creating virtualenv for testing...{0!r}".format(c.err.strip()))


@pytest.fixture
def tmpvenv(virtualenv):
    return mork.virtualenv.VirtualEnv(virtualenv.strpath)
