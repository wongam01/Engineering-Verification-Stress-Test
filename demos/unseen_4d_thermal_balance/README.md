# Phase 4D — Dual-Zone Thermal Balance

Controlled Synthetic Engineering Demo

Development-only evidence set

Not field data and not a real industrial incident

## Purpose

This demonstration checks whether the existing product workflow can apply a
supported two-variable relationship constraint to a new engineering case
without changing the validated Core, AI parser, adapter, or application
execution semantics.

This is not an official Test #4 and is not independent validation evidence.

## Controlled documents

- `requirement.txt` defines the engineering temperature-balance requirement.
- `verification.txt` defines the looser acceptance criterion.
- `feasible_domain_evidence.md` defines the approved development-only joint
  operating envelope.
- `expected_case.json` freezes the expected canonical formal case before the
  live workflow is exercised.

## Formal case

Variables:

- `T_A [degC]`
- `T_B [degC]`

Feasible Domain:

```text
20 <= T_A <= 30
20 <= T_B <= 30
```

The two zones are independently controllable in this controlled synthetic
model. The approved joint operating envelope is the Cartesian product
`[20, 30] x [20, 30] degC`.

Requirement:

```text
R_BALANCE: |T_A - T_B| <= 2 degC
```

Verification criterion:

```text
V_BALANCE: |T_A - T_B| <= 5 degC
```

Formal escape target:

```text
exists T_A, T_B:
    (20 <= T_A <= 30)
    and (20 <= T_B <= 30)
    and (|T_A - T_B| <= 5)
    and (|T_A - T_B| > 2)
```

## Expected result

The expected witness is a class, not one fixed solver coordinate:

```text
|T_A - T_B| = 5 degC
```

Expected formal result:

```text
F PASS
V PASS
R FAIL
VERIFICATION_GAP_FOUND
Worst violation = 3 degC
```

Any concrete state returned by the solver is acceptable when both variables
are inside the approved joint envelope and the conditions above hold.

## Claim boundary

This demo shows reuse of the existing Evidence, Review, Assurance Gate, and
Formal Stress Test workflow for one supported `abs_difference_max` schema. It
does not show that arbitrary engineering documents, unsupported mathematical
relationships, or real industrial systems can be formalized automatically.
