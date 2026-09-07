# Dual-Zone Feasible Domain Evidence

Controlled Synthetic Engineering Demo

Development-only evidence set

Not field data and not a real industrial incident

## Evidence status

- Source type: `engineering_analysis`
- Approval status: approved for this controlled development demonstration
- Scope: synthetic dual-zone thermal fixture model only

## Joint operating-envelope premise

Zone A and Zone B are independently controllable in this controlled synthetic
model. The approved joint operating envelope is the Cartesian product

```text
[20, 30] x [20, 30] degC
```

This means every ordered pair `(T_A, T_B)` satisfying both component bounds is
admissible in the development model. The evidence is intentionally a joint
envelope statement; it is not an inference from unrelated marginal
observations.

## F-T_A

```text
20 <= T_A <= 30 degC
```

This component bound is valid only as part of the approved joint Cartesian
product stated above.

## F-T_B

```text
20 <= T_B <= 30 degC
```

This component bound is valid only as part of the approved joint Cartesian
product stated above.

## Evidence boundary

These values are controlled synthetic premises for demonstrating the existing
workflow. They are not measurements, manufacturing records, field data, or
claims about a real product or incident.
