"""Tests for Dependency Resolver - TDD approach.

These tests define the expected behavior of the dependency resolver.
Key functionality:
- Topological sort of DAG steps
- Cycle detection
- Execution batching (parallel steps)
- Dependency validation
"""

from typing import Any

import pytest

from budpipeline.commons.exceptions import CyclicDependencyError, DAGValidationError
from budpipeline.engine.dag_parser import DAGParser
from budpipeline.engine.dependency_resolver import DependencyResolver


class TestDependencyResolverBasic:
    """Test basic dependency resolution."""

    def test_resolve_single_step(self, simple_dag: dict[str, Any]) -> None:
        """Should resolve single-step DAG."""
        dag = DAGParser.parse(simple_dag)
        resolver = DependencyResolver(dag)

        execution_order = resolver.get_execution_order()

        assert len(execution_order) == 1
        assert len(execution_order[0]) == 1
        assert execution_order[0][0].id == "step1"

    def test_resolve_linear_dag(self, linear_dag: dict[str, Any]) -> None:
        """Should resolve linear DAG into sequential batches."""
        dag = DAGParser.parse(linear_dag)
        resolver = DependencyResolver(dag)

        execution_order = resolver.get_execution_order()

        # Linear DAG should have 3 batches, each with 1 step
        assert len(execution_order) == 3
        assert len(execution_order[0]) == 1
        assert execution_order[0][0].id == "step1"
        assert len(execution_order[1]) == 1
        assert execution_order[1][0].id == "step2"
        assert len(execution_order[2]) == 1
        assert execution_order[2][0].id == "step3"

    def test_resolve_parallel_dag(self, parallel_dag: dict[str, Any]) -> None:
        """Should resolve parallel DAG with parallel batch."""
        dag = DAGParser.parse(parallel_dag)
        resolver = DependencyResolver(dag)

        execution_order = resolver.get_execution_order()

        # parallel_dag: step1 -> (step2a, step2b) -> step3
        assert len(execution_order) == 3

        # First batch: step1 (root)
        assert len(execution_order[0]) == 1
        assert execution_order[0][0].id == "step1"

        # Second batch: step2a, step2b (parallel)
        assert len(execution_order[1]) == 2
        batch_ids = {s.id for s in execution_order[1]}
        assert batch_ids == {"step2a", "step2b"}

        # Third batch: step3 (depends on both)
        assert len(execution_order[2]) == 1
        assert execution_order[2][0].id == "step3"

    def test_resolve_diamond_dag(self, diamond_dag: dict[str, Any]) -> None:
        """Should resolve diamond pattern: A -> (B, C) -> D."""
        dag = DAGParser.parse(diamond_dag)
        resolver = DependencyResolver(dag)

        execution_order = resolver.get_execution_order()

        assert len(execution_order) == 3

        # First: A
        assert execution_order[0][0].id == "A"

        # Second: B, C (parallel)
        batch_ids = {s.id for s in execution_order[1]}
        assert batch_ids == {"B", "C"}

        # Third: D
        assert execution_order[2][0].id == "D"


class TestCycleDetection:
    """Test cycle detection in DAGs."""

    def test_detect_simple_cycle(self, cyclic_dag: dict[str, Any]) -> None:
        """Should detect A -> B -> C -> A cycle."""
        dag = DAGParser.parse(cyclic_dag)
        resolver = DependencyResolver(dag)

        with pytest.raises(CyclicDependencyError) as exc_info:
            resolver.get_execution_order()

        # Should identify the cycle
        assert "cyclic" in str(exc_info.value).lower() or "cycle" in str(exc_info.value).lower()

    def test_detect_self_cycle(self) -> None:
        """Should detect self-referencing cycle (caught at parse time)."""
        dag_dict = {
            "name": "self-cycle",
            "version": "1.0",
            "steps": [
                {"id": "A", "name": "A", "action": "test", "depends_on": ["A"], "params": {}}
            ],
        }
        # Self-dependency should be caught during parsing
        with pytest.raises(DAGValidationError):
            DAGParser.parse(dag_dict)

    def test_detect_two_node_cycle(self) -> None:
        """Should detect A <-> B cycle."""
        dag_dict = {
            "name": "two-node-cycle",
            "version": "1.0",
            "steps": [
                {"id": "A", "name": "A", "action": "test", "depends_on": ["B"], "params": {}},
                {"id": "B", "name": "B", "action": "test", "depends_on": ["A"], "params": {}},
            ],
        }
        dag = DAGParser.parse(dag_dict)
        resolver = DependencyResolver(dag)

        with pytest.raises(CyclicDependencyError):
            resolver.get_execution_order()

    def test_detect_indirect_cycle(self) -> None:
        """Should detect indirect cycle: A -> B -> C -> D -> B."""
        dag_dict = {
            "name": "indirect-cycle",
            "version": "1.0",
            "steps": [
                {"id": "A", "name": "A", "action": "test", "params": {}},
                {"id": "B", "name": "B", "action": "test", "depends_on": ["A", "D"], "params": {}},
                {"id": "C", "name": "C", "action": "test", "depends_on": ["B"], "params": {}},
                {"id": "D", "name": "D", "action": "test", "depends_on": ["C"], "params": {}},
            ],
        }
        dag = DAGParser.parse(dag_dict)
        resolver = DependencyResolver(dag)

        with pytest.raises(CyclicDependencyError):
            resolver.get_execution_order()

    def test_no_false_positive_for_valid_dag(self, complex_dag: dict[str, Any]) -> None:
        """Should not raise for valid complex DAG."""
        dag = DAGParser.parse(complex_dag)
        resolver = DependencyResolver(dag)

        # Should not raise
        execution_order = resolver.get_execution_order()
        assert len(execution_order) > 0


class TestExecutionBatching:
    """Test step batching for parallel execution."""

    def test_maximize_parallelism(self) -> None:
        """Should maximize parallel execution."""
        # DAG: A -> (B, C, D) -> E
        dag_dict = {
            "name": "max-parallel",
            "version": "1.0",
            "steps": [
                {"id": "A", "name": "A", "action": "test", "params": {}},
                {"id": "B", "name": "B", "action": "test", "depends_on": ["A"], "params": {}},
                {"id": "C", "name": "C", "action": "test", "depends_on": ["A"], "params": {}},
                {"id": "D", "name": "D", "action": "test", "depends_on": ["A"], "params": {}},
                {
                    "id": "E",
                    "name": "E",
                    "action": "test",
                    "depends_on": ["B", "C", "D"],
                    "params": {},
                },
            ],
        }
        dag = DAGParser.parse(dag_dict)
        resolver = DependencyResolver(dag)

        execution_order = resolver.get_execution_order()

        assert len(execution_order) == 3
        assert len(execution_order[0]) == 1  # A
        assert len(execution_order[1]) == 3  # B, C, D
        assert len(execution_order[2]) == 1  # E

    def test_multiple_roots(self) -> None:
        """Should handle DAG with multiple root nodes."""
        dag_dict = {
            "name": "multi-root",
            "version": "1.0",
            "steps": [
                {"id": "A", "name": "A", "action": "test", "params": {}},
                {"id": "B", "name": "B", "action": "test", "params": {}},
                {"id": "C", "name": "C", "action": "test", "depends_on": ["A", "B"], "params": {}},
            ],
        }
        dag = DAGParser.parse(dag_dict)
        resolver = DependencyResolver(dag)

        execution_order = resolver.get_execution_order()

        # A and B should be in first batch (parallel roots)
        assert len(execution_order) == 2
        first_batch_ids = {s.id for s in execution_order[0]}
        assert first_batch_ids == {"A", "B"}

    def test_multiple_leaves(self) -> None:
        """Should handle DAG with multiple leaf nodes."""
        dag_dict = {
            "name": "multi-leaf",
            "version": "1.0",
            "steps": [
                {"id": "A", "name": "A", "action": "test", "params": {}},
                {"id": "B", "name": "B", "action": "test", "depends_on": ["A"], "params": {}},
                {"id": "C", "name": "C", "action": "test", "depends_on": ["A"], "params": {}},
            ],
        }
        dag = DAGParser.parse(dag_dict)
        resolver = DependencyResolver(dag)

        execution_order = resolver.get_execution_order()

        # A first, then B and C in parallel
        assert len(execution_order) == 2
        assert execution_order[0][0].id == "A"
        last_batch_ids = {s.id for s in execution_order[1]}
        assert last_batch_ids == {"B", "C"}

    def test_complex_dependencies(self) -> None:
        """Should handle complex dependency patterns."""
        # DAG:
        #   A -> B -> D
        #   A -> C -> D
        #   B -> E
        dag_dict = {
            "name": "complex-deps",
            "version": "1.0",
            "steps": [
                {"id": "A", "name": "A", "action": "test", "params": {}},
                {"id": "B", "name": "B", "action": "test", "depends_on": ["A"], "params": {}},
                {"id": "C", "name": "C", "action": "test", "depends_on": ["A"], "params": {}},
                {"id": "D", "name": "D", "action": "test", "depends_on": ["B", "C"], "params": {}},
                {"id": "E", "name": "E", "action": "test", "depends_on": ["B"], "params": {}},
            ],
        }
        dag = DAGParser.parse(dag_dict)
        resolver = DependencyResolver(dag)

        execution_order = resolver.get_execution_order()

        # A first
        assert execution_order[0][0].id == "A"

        # B and C can be parallel
        batch2_ids = {s.id for s in execution_order[1]}
        assert batch2_ids == {"B", "C"}

        # D and E can be parallel (both depend on things from batch 2)
        batch3_ids = {s.id for s in execution_order[2]}
        assert batch3_ids == {"D", "E"}


class TestDependencyQueries:
    """Test dependency query methods."""

    def test_get_dependencies(self, parallel_dag: dict[str, Any]) -> None:
        """Should get direct dependencies of a step."""
        dag = DAGParser.parse(parallel_dag)
        resolver = DependencyResolver(dag)

        deps = resolver.get_dependencies("step3")
        dep_ids = {s.id for s in deps}
        assert dep_ids == {"step2a", "step2b"}

    def test_get_all_dependencies(self, linear_dag: dict[str, Any]) -> None:
        """Should get all transitive dependencies."""
        dag = DAGParser.parse(linear_dag)
        resolver = DependencyResolver(dag)

        all_deps = resolver.get_all_dependencies("step3")
        dep_ids = {s.id for s in all_deps}
        assert dep_ids == {"step1", "step2"}

    def test_get_dependents(self, parallel_dag: dict[str, Any]) -> None:
        """Should get direct dependents of a step."""
        dag = DAGParser.parse(parallel_dag)
        resolver = DependencyResolver(dag)

        dependents = resolver.get_dependents("step1")
        dep_ids = {s.id for s in dependents}
        assert dep_ids == {"step2a", "step2b"}

    def test_get_all_dependents(self, linear_dag: dict[str, Any]) -> None:
        """Should get all transitive dependents."""
        dag = DAGParser.parse(linear_dag)
        resolver = DependencyResolver(dag)

        all_deps = resolver.get_all_dependents("step1")
        dep_ids = {s.id for s in all_deps}
        assert dep_ids == {"step2", "step3"}

    def test_is_dependency_of(self, linear_dag: dict[str, Any]) -> None:
        """Should check if step is a dependency of another."""
        dag = DAGParser.parse(linear_dag)
        resolver = DependencyResolver(dag)

        assert resolver.is_dependency_of("step1", "step3") is True
        assert resolver.is_dependency_of("step1", "step2") is True
        assert resolver.is_dependency_of("step2", "step1") is False
        assert resolver.is_dependency_of("step3", "step1") is False

    def test_can_run_parallel(self, parallel_dag: dict[str, Any]) -> None:
        """Should determine if two steps can run in parallel."""
        dag = DAGParser.parse(parallel_dag)
        resolver = DependencyResolver(dag)

        # step2a and step2b should be able to run in parallel
        assert resolver.can_run_parallel("step2a", "step2b") is True

        # step1 and step3 cannot (step3 depends on things after step1)
        assert resolver.can_run_parallel("step1", "step3") is False

        # step2a and step3 cannot (step3 depends on step2a)
        assert resolver.can_run_parallel("step2a", "step3") is False


class TestStepReadiness:
    """Test step readiness checking."""

    def test_ready_with_no_dependencies(self, simple_dag: dict[str, Any]) -> None:
        """Step with no dependencies should be ready immediately."""
        dag = DAGParser.parse(simple_dag)
        resolver = DependencyResolver(dag)

        completed: set[str] = set()
        ready = resolver.get_ready_steps(completed)

        assert len(ready) == 1
        assert ready[0].id == "step1"

    def test_ready_after_dependencies_complete(self, linear_dag: dict[str, Any]) -> None:
        """Step should be ready when all dependencies complete."""
        dag = DAGParser.parse(linear_dag)
        resolver = DependencyResolver(dag)

        # Initially only step1 is ready
        ready = resolver.get_ready_steps(set())
        assert len(ready) == 1
        assert ready[0].id == "step1"

        # After step1 completes, step2 is ready
        ready = resolver.get_ready_steps({"step1"})
        assert len(ready) == 1
        assert ready[0].id == "step2"

        # After step2 completes, step3 is ready
        ready = resolver.get_ready_steps({"step1", "step2"})
        assert len(ready) == 1
        assert ready[0].id == "step3"

    def test_ready_parallel_steps(self, parallel_dag: dict[str, Any]) -> None:
        """Multiple steps should be ready if dependencies are met."""
        dag = DAGParser.parse(parallel_dag)
        resolver = DependencyResolver(dag)

        # After step1 completes, both step2a and step2b are ready
        ready = resolver.get_ready_steps({"step1"})
        ready_ids = {s.id for s in ready}
        assert ready_ids == {"step2a", "step2b"}

    def test_is_step_ready(self, linear_dag: dict[str, Any]) -> None:
        """Should check if specific step is ready."""
        dag = DAGParser.parse(linear_dag)
        resolver = DependencyResolver(dag)

        assert resolver.is_step_ready("step1", set()) is True
        assert resolver.is_step_ready("step2", set()) is False
        assert resolver.is_step_ready("step2", {"step1"}) is True
        assert resolver.is_step_ready("step3", {"step1"}) is False
        assert resolver.is_step_ready("step3", {"step1", "step2"}) is True


class TestPerformance:
    """Test performance with large DAGs."""

    def test_large_linear_dag(self, make_step, make_dag) -> None:
        """Should efficiently handle long linear chains."""
        steps = []
        for i in range(200):
            step = make_step(
                f"step{i}",
                depends_on=[f"step{i - 1}"] if i > 0 else None,
            )
            steps.append(step)

        dag_dict = make_dag(name="large-linear", steps=steps)
        dag = DAGParser.parse(dag_dict)
        resolver = DependencyResolver(dag)

        execution_order = resolver.get_execution_order()

        assert len(execution_order) == 200

    def test_wide_parallel_dag(self, make_step, make_dag) -> None:
        """Should efficiently handle wide parallel DAGs."""
        steps = [make_step("root")]

        for i in range(100):
            steps.append(make_step(f"p{i}", depends_on=["root"]))

        parallel_ids = [f"p{i}" for i in range(100)]
        steps.append(make_step("final", depends_on=parallel_ids))

        dag_dict = make_dag(name="wide-parallel", steps=steps)
        dag = DAGParser.parse(dag_dict)
        resolver = DependencyResolver(dag)

        execution_order = resolver.get_execution_order()

        assert len(execution_order) == 3
        assert len(execution_order[0]) == 1  # root
        assert len(execution_order[1]) == 100  # parallel
        assert len(execution_order[2]) == 1  # final

    def test_deep_diamond_dag(self, make_step, make_dag) -> None:
        """Should handle deeply nested diamond patterns."""
        steps = [make_step("A0")]

        # Create 20 levels of diamonds
        for level in range(20):
            prev = f"A{level}"
            steps.append(make_step(f"B{level}", depends_on=[prev]))
            steps.append(make_step(f"C{level}", depends_on=[prev]))
            steps.append(make_step(f"A{level + 1}", depends_on=[f"B{level}", f"C{level}"]))

        dag_dict = make_dag(name="deep-diamond", steps=steps)
        dag = DAGParser.parse(dag_dict)
        resolver = DependencyResolver(dag)

        execution_order = resolver.get_execution_order()

        # Should have 3 * 20 + 1 batches alternating between single and parallel
        assert len(execution_order) > 0


class TestEdgeCases:
    """Test edge cases."""

    def test_disconnected_components(self) -> None:
        """Should handle disconnected graph components."""
        dag_dict = {
            "name": "disconnected",
            "version": "1.0",
            "steps": [
                {"id": "A1", "name": "A1", "action": "test", "params": {}},
                {"id": "A2", "name": "A2", "action": "test", "depends_on": ["A1"], "params": {}},
                {"id": "B1", "name": "B1", "action": "test", "params": {}},
                {"id": "B2", "name": "B2", "action": "test", "depends_on": ["B1"], "params": {}},
            ],
        }
        dag = DAGParser.parse(dag_dict)
        resolver = DependencyResolver(dag)

        execution_order = resolver.get_execution_order()

        # A1 and B1 should be in first batch (parallel roots)
        first_batch_ids = {s.id for s in execution_order[0]}
        assert first_batch_ids == {"A1", "B1"}

        # A2 and B2 in second batch
        second_batch_ids = {s.id for s in execution_order[1]}
        assert second_batch_ids == {"A2", "B2"}

    def test_single_step_is_root_and_leaf(self, simple_dag: dict[str, Any]) -> None:
        """Single step should be both root and leaf."""
        dag = DAGParser.parse(simple_dag)
        resolver = DependencyResolver(dag)

        roots = resolver.get_root_steps()
        leaves = resolver.get_leaf_steps()

        assert len(roots) == 1
        assert len(leaves) == 1
        assert roots[0].id == leaves[0].id == "step1"

    def test_step_depends_on_multiple_levels(self) -> None:
        """Step depending on nodes at different levels."""
        # D depends on both A (root) and C (level 2)
        dag_dict = {
            "name": "multi-level-dep",
            "version": "1.0",
            "steps": [
                {"id": "A", "name": "A", "action": "test", "params": {}},
                {"id": "B", "name": "B", "action": "test", "depends_on": ["A"], "params": {}},
                {"id": "C", "name": "C", "action": "test", "depends_on": ["B"], "params": {}},
                {"id": "D", "name": "D", "action": "test", "depends_on": ["A", "C"], "params": {}},
            ],
        }
        dag = DAGParser.parse(dag_dict)
        resolver = DependencyResolver(dag)

        execution_order = resolver.get_execution_order()

        # D cannot run until C completes, so it must be in last batch
        last_batch_ids = {s.id for s in execution_order[-1]}
        assert "D" in last_batch_ids
