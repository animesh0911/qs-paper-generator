"""The three eval scenarios, one module per paid workflow.

Each module implements the same four functions consumed by ``evals.run``:

- ``build_units(args)``   — expand the CLI matrix into :class:`EvalUnit`s.
- ``estimate(unit)``      — rough token forecast for the budget gate.
- ``run_unit(unit)``      — the paid phase: production call via the metered
                            seam; returns a RunRecord + writes raw artifacts.
- ``score_unit(record)`` — deterministic scoring over stored artifacts;
                            deterministic metrics + judge verdicts.

Wiring to production entry points is real; bodies that need datasets, judge
tuning, or fixtures raise :class:`~evals.scenarios.base.EvalNotImplemented`
naming the implementation issue that will land them.
"""
