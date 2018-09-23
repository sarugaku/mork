- Added ``VirtualEnv.resolve_dist(dist, working_set)`` to find the resolution set for a distribution on the specified working set.
- Added ``VirtualEnv.initial_working_set`` which finds the working set based on the prefix according to ``sysconfig``.
- Added the ability to pass ``extra_dists=[]`` to ``VirtualEnv.activated()`` in order to add dists to the activation scope for import in code.
