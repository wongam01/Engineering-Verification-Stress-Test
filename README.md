# AI-Engineering-Verification

<p align="center">
  <strong>AI-Assisted Engineering Verification Gap & Counterexample Solver</strong>
</p>

<p align="center">
설계 요구사항과 검사·시험·검증계획 사이의 논리적 빈틈을 탐색하고,<br>
검증을 통과하면서 실제 요구사항은 위반하는 반례를 자동으로 생성하는 엔지니어링 검증 시스템
</p>

<p align="center">

![Python](https://img.shields.io/badge/Python-3.13-3776AB?logo=python&logoColor=white)
![Z3](https://img.shields.io/badge/Solver-Z3-5C2D91)
![Status](https://img.shields.io/badge/Status-Proof_of_Concept-orange)
![Project](https://img.shields.io/badge/HIMEC-AI_Contest-0A7EA4)

</p>

---

## 📌 Overview

엔지니어링 업무에서는 설계 요구사항을 만족하는지 확인하기 위해  
Inspection Plan, Test Plan, Verification Plan 등의 검증계획을 사용합니다.

하지만 개별 검사항목이 모두 정상이어도  
**여러 조건 사이의 관계까지 실제 요구사항을 보증하지 못하는 경우**가 존재할 수 있습니다.

예를 들어,

```text
Verification Plan

9.9 ≤ A ≤ 10.1
19.9 ≤ B ≤ 20.1
```

두 조건을 모두 통과하는

```text
A = 10.10
B = 20.10
```

이라는 상태가 있다고 가정합니다.

하지만 실제 Engineering Requirement가

```text
A + B ≤ 30.05
```

라면,

```text
A + B = 30.20

Verification → PASS
Requirement  → FAIL
```

이 됩니다.

본 프로젝트는 이러한 **Verification Gap**을 사람이 직접 예상하는 대신  
Constraint Solver가 상태공간을 탐색하여 **구체적인 Counterexample**로 찾아내는 것을 목표로 합니다.

---

## 💡 Core Idea

최종적으로 다음 조건을 만족하는 Engineering State `X`를 탐색합니다.

```text
Feasible(X)
AND Verification(X)
AND NOT Requirement(X)
```

의미는 다음과 같습니다.

```text
Feasible(X)
→ 현실적으로 가능한 Engineering State

Verification(X)
→ 현재 검사·시험·검증계획을 통과

Requirement(X)
→ 실제 Engineering Requirement를 만족
```

따라서,

```text
COUNTEREXAMPLE FOUND
```

가 나오면 현재 Verification Plan을 통과하면서도  
실제 Requirement를 위반할 수 있는 상태가 존재한다는 뜻입니다.

---

## 🧠 Architecture

```text
 Engineering Requirement
          │
          ▼
 Requirement Constraints
          │
          │
 Verification / Inspection Plan
          │
          ▼
 Verification Constraints
          │
          │
     Feasible Domain
          │
          ▼
╔════════════════════════════╗
║  Verification Gap Solver   ║
║                            ║
║ Feasible(X)                ║
║ AND Verification(X)       ║
║ AND NOT Requirement(X)    ║
╚═════════════╤══════════════╝
              │
      ┌───────┴────────┐
      ▼                ▼
Counterexample     No Gap Found
      │
      ▼
  Gap Analysis
      │
      ▼
Recommended Patch
      │
      ▼
 Re-verification
```

향후 Vision / LLM을 이용해 도면, Specification, Inspection Plan 등의  
비정형 문서를 위 Constraint Model로 자동 변환하는 기능을 연결할 예정입니다.

---

## 🔍 Verification Gap Types

초기 Prototype에서는 세 가지 유형을 우선적으로 다룹니다.

```text
1. Acceptance Gap
   설계 허용범위와 검증 허용범위의 불일치

2. Relationship Gap
   개별 조건은 PASS하지만 변수 간 관계조건은 FAIL

3. Coverage Gap
   Requirement에는 존재하지만 Verification에서 확인하지 않는 조건
```

이들을 서로 다른 단순 비교 규칙이 아니라  
**하나의 Counterexample Solver 구조로 탐색하는 것**을 목표로 합니다.

---

## ⚙️ Current PoC

현재 Z3 Solver를 이용한 첫 번째 Relationship Gap PoC를 구현했습니다.

```text
Verification

9.9 ≤ A ≤ 10.1
19.9 ≤ B ≤ 20.1

Requirement

A + B ≤ 30.05
```

Solver 결과:

```text
COUNTEREXAMPLE FOUND
--------------------

A = 10.10
B = 20.10

Verification
A range -> PASS
B range -> PASS

A + B = 30.20

Requirement
A + B <= 30.05

Requirement -> FAIL
```

Verification Plan에 동일한 관계조건을 추가한 경우에는:

```text
NO COUNTEREXAMPLE FOUND
```

가 반환되는 것까지 확인했습니다.

---

## 🎯 Target Output

최종 시스템은 단순한 경고 대신 다음과 같은 결과를 제공하는 것을 목표로 합니다.

```text
ENGINEERING VERIFICATION REPORT

⚠ VERIFICATION GAP FOUND

Counterexample
A = 10.08
B = 20.04

Verification → PASS

Requirement
A + B <= 30.05

Actual
A + B = 30.12

Requirement → FAIL


Cause
Relationship constraint is not covered.


Recommended Patch
+ Verify A + B <= 30.05


Re-verification
✓ GAP CLOSED
within modeled constraints.
```

즉,

```text
Gap 탐색
→ 반례 생성
→ 원인 분석
→ 수정안 제안
→ 재검증
```

의 Closed Loop를 목표로 합니다.

---

## 🛠 Tech Stack

```text
Python
├── Z3 Solver      # Counterexample / Constraint Solving
├── Pydantic       # Engineering Data Model (Planned)
└── Vision / LLM   # Document Interpretation (Planned)
```

AI가 직접 PASS / FAIL을 추측하는 것이 아니라,

```text
Vision / LLM
→ Engineering 문서를 구조화

Constraint Solver
→ 결정론적으로 반례 탐색 및 검증
```

하는 역할 분리를 목표로 합니다.

---

## 🗺 Roadmap

```text
[x] Basic Verification Gap Solver
[x] Relationship Counterexample PoC
[x] Gap / No-Gap validation

[ ] Feasible Domain
[ ] Acceptance Gap
[ ] Coverage Gap
[ ] Multiple / 3-variable constraints
[ ] Automatic solver tests

[ ] Engineering Constraint Data Model
[ ] Gap Cause Analysis
[ ] Recommended Patch
[ ] Automatic Re-verification

[ ] Vision / LLM Document Parser
[ ] Engineering Verification Report
[ ] UI / Counterexample Visualization
```

---

## 📂 Structure

```text
AI-Engineering-Verification/
├── README.md
├── main.py
├── requirements.txt
├── src/
│   └── escape_solver.py
└── tests/
    └── test_escape_solver.py
```

---

## 🏆 Project Context

**제1회 HIMEC AI 활용 아이디어 공모전 출품을 목표로 개발 중인 프로젝트**

현재는 Proof of Concept 단계이며,  
향후 실제 Engineering Requirement와 Verification Plan을 대상으로  
Verification Gap을 사전에 탐색하는 시스템으로 확장할 예정입니다.

---

## 📄 License

Private research and competition project.