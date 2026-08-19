"""Tracing for the Battery Utility Calculator step.

The BUC step is the one place in the pipeline that can appear to "just stop":

  - ``EnergyCostCalculator.optimize()`` throws away the solver's results object
    and only reads ``model.objective()``. When HiGHS reports anything other than
    "optimal" — infeasible, unbounded, iteration limit — the APPSI interface
    raises `RuntimeError: A feasible solution was not found`, with no hint as to
    which of those it was.
  - It rebuilds a fresh model and a fresh SolverFactory for every candidate
    storage, so a per-solve slowdown multiplies by (locations x volumes).

Turning this on wraps ``optimize()`` to report the size and duration of every
solve and, when one fails, to re-solve it with ``load_solution=False`` purely to
read the real termination condition and put it in the error message.

    BUC_DEBUG=1 python launch.py --agents B_01     size, timing, status
    BUC_DEBUG=2 python launch.py --agents B_01     the above plus the HiGHS log

``optimize()`` takes no solver options, so this wrapper accepts them instead:

    BUC_SOLVER_OPTIONS="time_limit=60"     turn an apparent hang into a status
    BUC_SOLVER_OPTIONS="presolve=off"      skip presolve (and its dependent-
                                           equations search, which carries its
                                           own 1000 s limit)

Level 2 passes ``tee=True`` into the solve and lifts the log level on pyomo's own
loggers, which logging_setup.py keeps quiet by default. That is the only way to
tell a solver that is grinding (simplex iterations scrolling past) from one that
never starts — the two look identical from outside, and ``optimize()`` hard-codes
``tee=False``.

Level 1 also screens the input series once per solve for NaN, inf and duplicate
index entries. A NaN price does not raise: HiGHS returns ``objective = nan``,
that nan flows into ``worth``, and the bid silently disappears from the curve.
Note which variables each price series multiplies — with ``volume=0`` every
storage flow is pinned to ``bounds=(0, 0)``, so a broken ``wholesale_market_prices``
(which multiplies only ``storage_to_wholesale``, ``wholesale_to_storage`` and the
by-default-disabled ``pv_to_wholesale``) cannot affect the baseline at all and
shows up for the first time on the first real storage.

It is off unless BUC_DEBUG is set, and it never changes what the pipeline
computes — only what it tells you about it.
"""
import logging
import os
import time

_ENABLED = False


def _level() -> int:
    raw = os.environ.get("BUC_DEBUG", "").strip().lower()
    if raw in ("2", "tee", "verbose"):
        return 2
    if raw in ("1", "true", "yes", "on"):
        return 1
    return 0


def _screen_inputs(ecc) -> list[str]:
    """Report anything in the input series that would poison the coefficients."""
    import numpy as np

    problems = []
    series_by_name = {
        "demand": getattr(ecc, "demand", None),
        "solar_generation": getattr(ecc, "solar_generation", None),
        "supplier_prices": getattr(ecc, "supplier_prices", None),
        "eeg_prices": getattr(ecc, "eeg_prices", None),
        "wholesale_market_prices": getattr(ecc, "wholesale_market_prices", None),
    }
    community = getattr(ecc, "community_market_prices", None)
    if isinstance(community, dict):
        for location, series in community.items():
            series_by_name[f"community_market_prices[{location}]"] = series

    expected = len(ecc.timesteps)
    for name, series in series_by_name.items():
        if series is None:
            continue
        values = np.asarray(getattr(series, "values", series), dtype=float)
        if np.isnan(values).any():
            problems.append(f"{name}: {int(np.isnan(values).sum())} NaN")
        if np.isinf(values).any():
            problems.append(f"{name}: {int(np.isinf(values).sum())} inf")
        if len(values) != expected:
            problems.append(f"{name}: {len(values)} values but {expected} timesteps")
        index = getattr(series, "index", None)
        if index is not None and getattr(index, "has_duplicates", False):
            # .loc[timestep] then returns a Series instead of a scalar, and the
            # objective expression blows up instead of staying linear.
            problems.append(f"{name}: duplicate index entries")
    return problems


def _model_size(model) -> str:
    """Variables and constraints in a built pyomo model."""
    import pyomo.environ as pyo

    variables = sum(len(v) for v in model.component_objects(pyo.Var, active=True))
    constraints = sum(len(c) for c in model.component_objects(pyo.Constraint, active=True))
    return f"{variables} vars, {constraints} constraints"


def _termination_condition(model, solver: str) -> str:
    """Re-solve without loading a solution, just to read the status."""
    import pyomo.environ as pyo

    # APPSI raises instead of returning when it cannot load a solution, so the
    # only way to see the real condition is to ask it not to load one.
    # SolverFactory("appsi_highs") hands back a LegacySolver wrapper, so the
    # load_solutions kwarg is the path that actually works; the config attribute
    # is the fallback for a raw APPSI object.
    try:
        results = pyo.SolverFactory(solver).solve(model, load_solutions=False)
        return str(results.solver.termination_condition)
    except Exception:                                # noqa: BLE001 - diagnostics only
        pass
    try:
        optimizer = pyo.SolverFactory(solver)
        optimizer.config.load_solution = False
        return str(optimizer.solve(model).termination_condition)
    except Exception as error:                       # noqa: BLE001 - diagnostics only
        return f"could not determine ({type(error).__name__}: {error})"


def _solver_options() -> dict:
    """BUC_SOLVER_OPTIONS="time_limit=60,presolve=off" -> {"time_limit": 60.0, ...}"""
    raw = os.environ.get("BUC_SOLVER_OPTIONS", "").strip()
    options = {}
    for pair in raw.split(","):
        if "=" not in pair:
            continue
        key, _, value = pair.partition("=")
        value = value.strip()
        try:
            options[key.strip()] = float(value) if value.replace(".", "", 1).isdigit() else value
        except ValueError:
            options[key.strip()] = value
    return options


def _solve(ecc, solver: str, tee: bool, options: dict):
    """optimize(), but with the solver log and solver options exposed."""
    import pyomo.environ as pyo

    optimizer = pyo.SolverFactory(solver)
    for key, value in options.items():
        optimizer.options[key] = value
    optimizer.solve(ecc.model, tee=tee)
    ecc.is_optimized = True
    return ecc.model.objective()


def enable() -> None:
    """Wrap EnergyCostCalculator.optimize with size/timing/status tracing."""
    global _ENABLED
    if _ENABLED:
        return
    _ENABLED = True

    from battery_utility_calculator.energy_costs_calculator import EnergyCostCalculator

    original = EnergyCostCalculator.optimize
    counter = {"n": 0}
    level = _level() or 1
    tee = level >= 2
    options = _solver_options()

    if tee:
        # logging_setup.py silences these; at level 2 the solver output is the
        # whole point.
        logging.getLogger("pyomo").setLevel(logging.INFO)

    def traced(self, solver: str = "gurobi"):
        counter["n"] += 1
        index = counter["n"]
        volume = getattr(self.storage, "volume", "?")
        location = getattr(self, "storage_location", None) or getattr(self, "my_location", "?")
        size = _model_size(self.model)
        print(f"BUC #{index}: solving volume={volume} location={location} "
              f"timesteps={len(self.timesteps)} ({size}) solver={solver}", flush=True)

        for problem in _screen_inputs(self):
            print(f"BUC #{index}: INPUT PROBLEM — {problem}", flush=True)

        started = time.perf_counter()
        try:
            if tee or options:
                value = _solve(self, solver, tee, options)
            else:
                value = original(self, solver=solver)
        except Exception as error:
            elapsed = time.perf_counter() - started
            condition = _termination_condition(self.model, solver)
            print(f"BUC #{index}: FAILED after {elapsed:.1f}s — termination={condition}", flush=True)
            raise RuntimeError(
                f"BUC solve failed for volume={volume} at location={location} "
                f"({len(self.timesteps)} timesteps, {size}): termination={condition}. "
                f"Original error: {error}"
            ) from error

        elapsed = time.perf_counter() - started
        note = "  <-- nan objective, this bid will vanish from the curve" if value != value else ""
        print(f"BUC #{index}: ok in {elapsed:.1f}s — objective={value}{note}", flush=True)
        return value

    EnergyCostCalculator.optimize = traced
    print(f"BUC_DEBUG: tracing EnergyCostCalculator.optimize (level {level}, "
          f"solver log {'on' if tee else 'off'}, options {options or 'none'})", flush=True)


def enable_if_requested() -> None:
    if _level():
        enable()
