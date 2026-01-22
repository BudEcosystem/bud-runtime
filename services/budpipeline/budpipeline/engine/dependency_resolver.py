"""Dependency Resolver - handles DAG dependency resolution and execution ordering.

Provides:
- Topological sorting of DAG steps
- Cycle detection
- Execution batching for parallel steps
- Dependency queries
- Step readiness checking
"""

from collections import defaultdict, deque

from budpipeline.commons.exceptions import CyclicDependencyError
from budpipeline.engine.schemas import WorkflowDAG, WorkflowStep


class DependencyResolver:
    """Resolves dependencies in a workflow DAG.

    Uses Kahn's algorithm for topological sorting, which also detects cycles.
    Groups steps into batches for parallel execution where possible.
    """

    def __init__(self, dag: WorkflowDAG) -> None:
        """Initialize resolver with a DAG.

        Args:
            dag: The workflow DAG to resolve
        """
        self.dag = dag
        self._step_index: dict[str, WorkflowStep] = {step.id: step for step in dag.steps}

        # Build adjacency lists for graph operations
        self._adjacency: dict[str, set[str]] = defaultdict(set)  # step -> dependents
        self._reverse_adjacency: dict[str, set[str]] = defaultdict(set)  # step -> dependencies
        self._in_degree: dict[str, int] = {}

        self._build_graph()

    def _build_graph(self) -> None:
        """Build graph representation from DAG."""
        for step in self.dag.steps:
            self._in_degree[step.id] = len(step.depends_on)

            for dep_id in step.depends_on:
                self._adjacency[dep_id].add(step.id)
                self._reverse_adjacency[step.id].add(dep_id)

    def get_execution_order(self) -> list[list[WorkflowStep]]:
        """Get execution order as batches of parallel steps.

        Returns topologically sorted steps grouped into batches.
        Steps in the same batch can be executed in parallel.

        Returns:
            List of batches, where each batch is a list of steps

        Raises:
            CyclicDependencyError: If the DAG contains a cycle
        """
        # Use modified Kahn's algorithm for batched topological sort
        in_degree = self._in_degree.copy()
        batches: list[list[WorkflowStep]] = []

        # Find initial batch (all nodes with in_degree 0)
        current_batch_ids = [step_id for step_id, degree in in_degree.items() if degree == 0]

        processed_count = 0

        while current_batch_ids:
            # Create batch with actual step objects
            current_batch = [self._step_index[step_id] for step_id in current_batch_ids]
            batches.append(current_batch)
            processed_count += len(current_batch)

            # Find next batch
            next_batch_ids: list[str] = []

            for step_id in current_batch_ids:
                for dependent_id in self._adjacency[step_id]:
                    in_degree[dependent_id] -= 1
                    if in_degree[dependent_id] == 0:
                        next_batch_ids.append(dependent_id)

            current_batch_ids = next_batch_ids

        # Check for cycles (if not all nodes were processed)
        if processed_count != len(self.dag.steps):
            cycle_path = self._find_cycle()
            raise CyclicDependencyError(cycle_path)

        return batches

    def _find_cycle(self) -> list[str]:
        """Find a cycle in the graph for error reporting.

        Returns:
            List of step IDs forming a cycle
        """
        # Use DFS to find cycle
        visited: set[str] = set()
        rec_stack: set[str] = set()
        path: list[str] = []

        def dfs(node: str) -> bool:
            visited.add(node)
            rec_stack.add(node)
            path.append(node)

            for neighbor in self._reverse_adjacency[node]:
                if neighbor not in visited:
                    if dfs(neighbor):
                        return True
                elif neighbor in rec_stack:
                    # Found cycle - extract it from path
                    path.index(neighbor)
                    path.append(neighbor)
                    return True

            path.pop()
            rec_stack.remove(node)
            return False

        for step_id in self._step_index:
            if step_id not in visited and dfs(step_id):
                # Extract the cycle portion
                for i, node in enumerate(path):
                    if node == path[-1] and i != len(path) - 1:
                        return path[i:]
                return path

        return []

    def get_root_steps(self) -> list[WorkflowStep]:
        """Get steps with no dependencies.

        Returns:
            List of root steps
        """
        return [step for step in self.dag.steps if len(step.depends_on) == 0]

    def get_leaf_steps(self) -> list[WorkflowStep]:
        """Get steps that no other step depends on.

        Returns:
            List of leaf steps
        """
        return [step for step in self.dag.steps if len(self._adjacency[step.id]) == 0]

    def get_dependencies(self, step_id: str) -> list[WorkflowStep]:
        """Get direct dependencies of a step.

        Args:
            step_id: The step ID

        Returns:
            List of steps this step directly depends on
        """
        step = self._step_index.get(step_id)
        if not step:
            return []

        return [
            self._step_index[dep_id] for dep_id in step.depends_on if dep_id in self._step_index
        ]

    def get_all_dependencies(self, step_id: str) -> list[WorkflowStep]:
        """Get all transitive dependencies of a step.

        Args:
            step_id: The step ID

        Returns:
            List of all steps this step depends on (directly or transitively)
        """
        if step_id not in self._step_index:
            return []

        all_deps: set[str] = set()
        queue = deque(self._reverse_adjacency[step_id])

        while queue:
            dep_id = queue.popleft()
            if dep_id not in all_deps:
                all_deps.add(dep_id)
                queue.extend(self._reverse_adjacency[dep_id])

        return [self._step_index[dep_id] for dep_id in all_deps]

    def get_dependents(self, step_id: str) -> list[WorkflowStep]:
        """Get direct dependents of a step.

        Args:
            step_id: The step ID

        Returns:
            List of steps that directly depend on this step
        """
        return [
            self._step_index[dep_id]
            for dep_id in self._adjacency[step_id]
            if dep_id in self._step_index
        ]

    def get_all_dependents(self, step_id: str) -> list[WorkflowStep]:
        """Get all transitive dependents of a step.

        Args:
            step_id: The step ID

        Returns:
            List of all steps that depend on this step (directly or transitively)
        """
        if step_id not in self._step_index:
            return []

        all_dependents: set[str] = set()
        queue = deque(self._adjacency[step_id])

        while queue:
            dep_id = queue.popleft()
            if dep_id not in all_dependents:
                all_dependents.add(dep_id)
                queue.extend(self._adjacency[dep_id])

        return [self._step_index[dep_id] for dep_id in all_dependents]

    def is_dependency_of(self, step_id: str, target_id: str) -> bool:
        """Check if step_id is a dependency of target_id.

        Args:
            step_id: The potential dependency
            target_id: The step that might depend on step_id

        Returns:
            True if step_id is a (possibly transitive) dependency of target_id
        """
        if step_id not in self._step_index or target_id not in self._step_index:
            return False

        # BFS to find if we can reach step_id from target_id's dependencies
        visited: set[str] = set()
        queue = deque([target_id])

        while queue:
            current = queue.popleft()
            if current == step_id:
                return True

            if current in visited:
                continue

            visited.add(current)
            queue.extend(self._reverse_adjacency[current])

        return False

    def can_run_parallel(self, step_a: str, step_b: str) -> bool:
        """Check if two steps can run in parallel.

        Steps can run in parallel if neither depends on the other
        (directly or transitively).

        Args:
            step_a: First step ID
            step_b: Second step ID

        Returns:
            True if the steps can run in parallel
        """
        # Steps cannot run in parallel if one is an ancestor of the other
        return not self.is_dependency_of(step_a, step_b) and not self.is_dependency_of(
            step_b, step_a
        )

    def get_ready_steps(self, completed: set[str]) -> list[WorkflowStep]:
        """Get steps that are ready to execute.

        A step is ready if all its dependencies have completed.

        Args:
            completed: Set of completed step IDs

        Returns:
            List of steps ready to execute
        """
        ready: list[WorkflowStep] = []

        for step in self.dag.steps:
            if step.id in completed:
                continue

            # Check if all dependencies are completed
            deps_met = all(dep_id in completed for dep_id in step.depends_on)
            if deps_met:
                ready.append(step)

        return ready

    def is_step_ready(self, step_id: str, completed: set[str]) -> bool:
        """Check if a specific step is ready to execute.

        Args:
            step_id: The step ID to check
            completed: Set of completed step IDs

        Returns:
            True if the step is ready to execute
        """
        step = self._step_index.get(step_id)
        if not step:
            return False

        return all(dep_id in completed for dep_id in step.depends_on)

    def get_step_level(self, step_id: str) -> int:
        """Get the level (depth) of a step in the DAG.

        The level is the longest path from any root to this step.

        Args:
            step_id: The step ID

        Returns:
            The level (0 for roots)
        """
        if step_id not in self._step_index:
            return -1

        step = self._step_index[step_id]
        if not step.depends_on:
            return 0

        return 1 + max(self.get_step_level(dep_id) for dep_id in step.depends_on)

    def validate(self) -> list[str]:
        """Validate the DAG structure.

        Returns:
            List of validation errors (empty if valid)
        """
        errors: list[str] = []

        # Check for cycles
        try:
            self.get_execution_order()
        except CyclicDependencyError as e:
            errors.append(str(e))

        # Check for missing dependencies (should be caught by parser, but double-check)
        for step in self.dag.steps:
            for dep_id in step.depends_on:
                if dep_id not in self._step_index:
                    errors.append(f"Step '{step.id}' depends on non-existent step '{dep_id}'")

        return errors
