===============================================================================
mork: A project for installing packages across the virtualenv boundary.
===============================================================================

.. image:: https://img.shields.io/pypi/v/mork.svg
    :target: https://pypi.org/project/mork

.. image:: https://img.shields.io/pypi/l/mork.svg
    :target: https://pypi.org/project/mork

.. image:: https://api.travis-ci.com/sarugaku/mork.svg?branch=master
    :target: https://travis-ci.com/sarugaku/mork

.. image:: https://ci.appveyor.com/api/projects/status/y9kpdaqy4di5nhyk/branch/master?svg=true
    :target: https://ci.appveyor.com/project/sarugaku/mork

.. image:: https://img.shields.io/pypi/pyversions/mork.svg
    :target: https://pypi.org/project/mork

.. image:: https://img.shields.io/badge/Say%20Thanks-!-1EAEDB.svg
    :target: https://saythanks.io/to/techalchemy

.. image:: https://readthedocs.org/projects/mork/badge/?version=latest
    :target: https://mork.readthedocs.io/en/latest/?badge=latest
    :alt: Documentation Status

Summary
=======

Mork_ is a library designed for installing and querying python packages inside virtual
environments.

.. _Mork: https://mork.readthedocs.io/en/latest/


🐉 See What's Installed
-----------------------

  ::

    >>> import mork
    >>> venv = mork.VirtualEnv.from_project_path('/home/user/git/pipenv')
    >>> dists = venv.get_distributions()
    >>> [dist for dist in dists][:3]
    [wheel 0.31.1 (/home/user/.virtualenvs/pipenv-MfOPs1lW/lib/python3.7/site-packages), Werkzeug 0.14.1 (/home/user/.virtualenvs/pipenv-MfOPs1lW/lib/python3.7/site-packages), vistir 0.1.4 (/home/user/.virtualenvs/pipenv-MfOPs1lW/lib/python3.7/site-packages)]


🐉 Install A Package
--------------------

  ::

    >>> from requirementslib.models.requirements import Requirement
    >>> r = Requirement.from_line("requests")
    >>> venv.install(r, editable=False)


🐉 Uninstall a Package
----------------------

  ::

    >>> pkg = "pytz"
    >>> with venv.uninstall(pkg, auto_confirm=True) as uninstall:
            if uninstall.paths:
                cleaned = pkg
    >>> print("Removed package: %s" % cleaned)


🐉 Display Information about Python
-----------------------------------

  ::

    >>> venv.python
    '/home/user/.virtualenvs/pipenv-MfOPs1lW/bin/python'
    >>> venv.python_version
    '3.7'


🐉 Run Commands Inside the Virtualenv
-------------------------------------

  ::

    >>> cmd = venv.run("env")
    >>> [line for line in cmd.out.splitlines() if line.startswith("VIRTUAL_ENV")]
    ['VIRTUAL_ENV=/user/hawk/.virtualenvs/pipenv-MfOPs1lW']
    >>> cmd = venv.run_py(["import os; print(os.environ.get('VIRTUAL_ENV'))"])
    Deactivating virtualenv...
    >>> cmd.out
    '/home/user/.virtualenvs/pipenv-MfOPs1lW\n'
    >>> with venv.activated():
            print(os.environ["VIRTUAL_ENV"])
    /home/hawk/.virtualenvs/pipenv-MfOPs1lW


`Read the documentation <https://mork.readthedocs.io/>`__.
