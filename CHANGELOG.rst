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
