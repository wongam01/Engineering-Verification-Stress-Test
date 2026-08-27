# Engineering-Verification-Stress-Test

<p align="center">
  <strong>AI-Assisted Adversarial Stress Testing for Engineering Verification Plans</strong>
</p>

<p align="center">
검사·시험·검증계획을 실제 적용 전에 가상으로 공격하여,<br>
검증을 통과할 수 있는 부적합 상태와 최악의 미검출 상태를 탐색하는 엔지니어링 검증 시스템
</p>

<p align="center">

![Python](https://img.shields.io/badge/Python-3.13-3776AB?logo=python&logoColor=white)
![Z3](https://img.shields.io/badge/Solver-Z3-5C2D91)
![Status](https://img.shields.io/badge/Status-Proof_of_Concept-orange)
![Project](https://img.shields.io/badge/HIMEC-AI_Contest-0A7EA4)

</p>

---

## 📌 Overview

엔지니어링에서는 제품이나 시스템이 요구사항을 만족하는지 확인하기 위해  
Inspection Plan, Test Plan, Verification Plan 등을 사용합니다.

하지만 **현재 검증계획을 모두 통과하더라도 실제 Engineering Requirement를 위반하는 상태가 존재할 수 있습니다.**

본 프로젝트는 이러한 검증계획을 생산·시험·시공 전에 **가상으로 Stress Test**합니다.

```text
Engineering Requirement
          +
Verification Plan
          +
Feasible Engineering States
          ↓
╔══════════════════════════════╗
║ Verification Stress Tester   ║
╚══════════════╤═══════════════╝
               ↓
      Adversarial Search
               ↓
 ┌─────────────┴─────────────┐
 ▼                           ▼
Minimum Escape        Worst Undetected State
가장 쉽게             검사를 통과하는
빠져나가는 상태       최악의 부적합 상태
 └─────────────┬─────────────┘
               ↓
      Vulnerability Analysis
               ↓
       Recommended Patch
               ↓
           Re-test
```

---

## 💡 Core Idea

Solver는 다음 조건을 만족하는 Engineering State `X`를 탐색합니다.

```text
Feasible(X)
AND Verification(X)
AND NOT Requirement(X)
```

즉,

> **현실적으로 발생 가능하면서 현재 검증계획은 통과하지만 실제 요구사항은 위반하는 상태**

를 찾습니다.

단순히 Counterexample 하나를 찾는 것에서 끝나지 않고 최종적으로 다음 두 질문에 답하는 것을 목표로 합니다.

### 1. Minimum Escape

> 요구사항 정상 상태에서 **얼마나 작은 변화만으로 검증계획을 빠져나갈 수 있는가?**

### 2. Worst Undetected Violation

> 현재 검증계획을 통과하면서 **최악으로 얼마나 크게 요구사항을 위반할 수 있는가?**

이를 통해 Verification Plan의 취약성을 정량적으로 비교합니다.

---

## ⚙️ Current PoC

현재 Z3 Solver를 이용해 Relationship Constraint에서  
검증을 통과하면서 Requirement를 위반하는 상태를 탐색하는 PoC를 구현했습니다.

```text
Verification Plan

9.9 ≤ A ≤ 10.1
19.9 ≤ B ≤ 20.1


Engineering Requirement

A + B ≤ 30.05
```

Solver가 발견한 Counterexample:

```text
A = 10.10
B = 20.10

A Verification → PASS
B Verification → PASS

A + B = 30.20

Requirement → FAIL
```

Verification Plan에 관계조건까지 추가한 경우에는:

```text
NO COUNTEREXAMPLE FOUND
```

가 반환되는 것까지 확인했습니다.

---

## 🎯 Target Output

최종 시스템은 다음과 같은 Verification Stress Test 결과를 제공하는 것을 목표로 합니다.

```text
ENGINEERING VERIFICATION STRESS TEST
====================================

Escape Possible
YES


Minimum Escape
------------------------------------

A = 10.03
B = 20.03

Total deviation from nominal
0.06

→ 작은 조합 편차만으로
  Verification Plan 통과 가능


Worst Undetected State
------------------------------------

A = 10.10
B = 20.10

A + B = 30.20

Requirement Limit
30.05

Maximum Undetected Violation
0.15


Verification Vulnerability
HIGH


Recommended Patch
------------------------------------

+ Verify A + B <= 30.05


Re-Test
------------------------------------

No identical escape found
within modeled constraints.

✓ GAP CLOSED
```

---

## 🔍 Initial Stress-Test Targets

초기 Prototype에서는 세 종류의 Verification Gap을 우선적으로 다룹니다.

```text
Acceptance Gap
→ 검증 허용범위가 실제 요구범위보다 넓은 경우

Relationship Gap
→ 개별 항목은 PASS하지만 변수 관계조건은 FAIL하는 경우

Coverage Gap
→ Requirement에는 존재하지만 검증하지 않는 조건이 있는 경우
```

이후 각 Gap에 대해:

```text
Escape 존재 여부
Minimum Escape
Worst Undetected Violation
Vulnerability
Recommended Patch
Re-test
```

를 계산하는 것을 목표로 합니다.

---

## 🤖 AI + Solver

AI가 Engineering PASS / FAIL을 직접 판단하지 않습니다.

```text
Vision / LLM
→ Drawing / Specification / Verification Plan 해석
→ Engineering Constraints 구조화

Constraint Solver
→ Adversarial State Search
→ Counterexample Generation
→ Stress Test

Application
→ 취약도 분석
→ Patch 제안
→ 재검증
```

비정형 문서의 해석은 AI가 담당하고,
최종 검증은 결정론적 Solver가 수행하는 구조를 목표로 합니다.

---

## 🛠 Tech Stack

```text
Python
├── Z3 Solver
├── Pydantic        [Planned]
├── Vision / LLM    [Planned]
└── Engineering Constraint Engine
```

---

## 🗺 Roadmap

```text
[x] Basic Counterexample Solver
[x] Relationship Gap PoC
[x] Gap / No-Gap validation

[ ] Feasible Domain
[ ] Minimum Escape Search
[ ] Worst Undetected Violation Search
[ ] Acceptance Gap
[ ] Coverage Gap
[ ] Multi-variable constraints

[ ] Verification Vulnerability Analysis
[ ] Recommended Patch
[ ] Automatic Re-test

[ ] Engineering Document Parser
[ ] Vision / LLM Integration
[ ] Report / Visualization
[ ] UI
```

---

## 🏆 Project Context

**제1회 HIMEC AI 활용 아이디어 공모전 출품을 목표로 개발 중인 프로젝트**

핵심 목표는 단순한 Verification 항목 누락 탐지가 아니라,

> **실제 적용 전에 Verification Plan을 가상으로 공격하여  
> 어떤 부적합 상태가 얼마나 쉽게 검증을 빠져나갈 수 있는지를 사전에 평가하는 것**

입니다.

---

## 📄 License

Private research and competition project.
