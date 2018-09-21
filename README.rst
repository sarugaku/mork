===============================================================================
mork: A project for installing packages across the virtualenv boundary.
===============================================================================

.. image:: https://img.shields.io/pypi/v/passa.svg
    :target: https://pypi.org/project/passa

.. image:: https://img.shields.io/pypi/l/passa.svg
    :target: https://pypi.org/project/passa

.. image:: https://api.travis-ci.com/sarugaku/passa.svg?branch=master
    :target: https://travis-ci.com/sarugaku/passa

.. image:: https://ci.appveyor.com/api/projects/status/y9kpdaqy4di5nhyk/branch/master?svg=true
    :target: https://ci.appveyor.com/project/sarugaku/passa

.. image:: https://img.shields.io/pypi/pyversions/passa.svg
    :target: https://pypi.org/project/passa

.. image:: https://img.shields.io/badge/Say%20Thanks-!-1EAEDB.svg
    :target: https://saythanks.io/to/techalchemy

.. image:: https://readthedocs.org/projects/passa/badge/?version=latest
    :target: https://passa.readthedocs.io/en/latest/?badge=latest
    :alt: Documentation Status

Summary
=======

Mork_ is a library designed for installing and querying python packages inside virtual
environments.

  ::

    >>> import mork
    >>> venv = mork.virtualenv.VirtualEnv.from_project('/home/hawk/git/pipenv')
    >>> installed_packages = venv.get_distributions()
    >>> python_version = venv.python_version
    >>> with venv.activated():
            do_stuff()
    >>> venv.run(["some", "code"])
    >>> venv.run_py("some code")

`Read the documentation <https://mork.readthedocs.io/>`__.
