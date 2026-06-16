# TODO

- Simplify broker mode so the implementer role does not know the Spec-Driven TDD stage order. The implementer should only know how to initialize brokered work, ask the broker for the next task, perform the assigned task, and ask the broker to review/verify completion. Move all workflow ordering and stage-selection policy into the broker/orchestrator role. Consider reducing the broker MCP contract to two operations: `getNextTask` and `reviewTask`, where `getNextTask` returns either the first/next task, `complete` when the workflow is done, or a blocker when progress is impossible.
