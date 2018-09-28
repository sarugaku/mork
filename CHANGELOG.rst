0.1.3 (2018-09-28)
==================

Features
--------

- ``VirtualEnv`` instances will now create a reference to the outer ``pkg_resources.WorkingSet`` at instantiation and store it in ``VirtualEnv.base_working_set``.  `#8 <https://github.com/sarugaku/mork/issues/8>`_
  

Bug Fixes
---------

- Removed references to and attempted imports of ``passa`` builder and installer functionality from ``VirtualEnv`` implementation in favor of ``packagebuilder`` and ``installer``.  `#7 <https://github.com/sarugaku/mork/issues/7>`_
  
- Fixed an issue which caused errors on python versions 2.7-3.6 when attempting to uninstall packages in the virtualenv due to failed import attempts when using ``pip-shims.req_install``.  `#9 <https://github.com/sarugaku/mork/issues/9>`_


0.1.2 (2018-09-23)
==================

Bug Fixes
---------

- Fixed an issue which caused failures when generating ``VirtualEnv.sys_path`` due to passing of ``posixpath`` instances to normalization methods expecting strings.  `#5 <https://github.com/sarugaku/mork/issues/5>`_


0.1.1 (2018-09-23)
==================

Features
--------

- - Added ``VirtualEnv.resolve_dist(dist, working_set)`` to find the resolution set for a distribution on the specified working set.
  - Added ``VirtualEnv.initial_working_set`` which finds the working set based on the prefix according to ``sysconfig``.
  - Added the ability to pass ``extra_dists=[]`` to ``VirtualEnv.activated()`` in order to add dists to the activation scope for import in code.  `#2 <https://github.com/sarugaku/mork/issues/2>`_
  

Bug Fixes
---------

- Fixed a bug which caused ``VirtualEnv.sys_path`` to fail to populate correctly.  `#1 <https://github.com/sarugaku/mork/issues/1>`_


0.1.0 (2018-09-21)
==================

No significant changes.
