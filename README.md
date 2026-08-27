# AI-Engineering-Verification

> **AI-assisted Engineering Verification Gap Analysis & Counterexample Generation**  
> 설계·기술 요구사항과 검사·시험·검증계획 사이의 빈틈을 탐색하고,  
> 실제로 검증을 통과하면서 요구사항을 위반하는 반례를 생성하는 엔지니어링 검증 시스템

---

<p align="center">

![Python](https://img.shields.io/badge/Python-3.13-3776AB?logo=python&logoColor=white)
![Z3](https://img.shields.io/badge/Solver-Z3-5C2D91)
![Status](https://img.shields.io/badge/Status-PoC-orange)
![Project](https://img.shields.io/badge/Project-HIMEC_AI_Contest-0A7EA4)

</p>

---

## 📌 프로젝트 소개 (Overview)

엔지니어링 업무에서는 설계 요구사항을 만족하는지 확인하기 위해  
**검사계획(Inspection Plan), 시험계획(Test Plan), 검증계획(Verification Plan)** 을 작성합니다.

하지만 검증 항목이 존재한다는 사실만으로  
실제 요구사항을 완전히 보증할 수 있는 것은 아닙니다.

예를 들어 다음과 같은 요구사항이 있다고 가정합니다.

```text
Engineering Requirement

A = 10 ± 0.1
B = 20 ± 0.1
A + B ≤ 30.05
```

현재 검증계획이 다음과 같다면,

```text
Verification Plan

A = 10 ± 0.1
B = 20 ± 0.1
```

A와 B는 각각 허용범위 안에 있으면서도  
두 변수의 관계조건을 위반하는 상태가 존재할 수 있습니다.

```text
A = 10.10    → PASS
B = 20.10    → PASS

A + B = 30.20

Requirement:
A + B ≤ 30.05

→ FAIL
```

즉,

> **Verification은 PASS하지만 실제 Engineering Requirement는 FAIL하는 상태**

가 존재합니다.

본 프로젝트는 이러한 상태를 사람이 직접 예상하는 대신  
**Constraint Solver를 이용해 자동으로 역탐색하고 구체적인 Counterexample로 증명하는 것**을 목표로 합니다.

---

## 💡 핵심 아이디어 (Core Idea)

본 시스템의 핵심 문제는 다음과 같습니다.

```text
Find X such that

Verification(X) = PASS
        AND
Requirement(X)  = FAIL
```

해당 조건을 만족하는 `X`가 존재한다면,

```text
COUNTEREXAMPLE FOUND
```

즉 현재 검증계획에 **Verification Gap**이 존재한다는 의미입니다.

반대로 이러한 상태가 존재하지 않는다면,

```text
NO COUNTEREXAMPLE FOUND
```

현재 모델링된 제약조건 범위에서는  
검증계획이 해당 요구사항 위반을 허용하지 않는다고 판단할 수 있습니다.

---

## 🧠 시스템 구조 (Architecture)

```text
┌─────────────────────────────┐
│  Engineering Requirements   │
│                             │
│ Drawing / Spec / PDF / Text │
└──────────────┬──────────────┘
               │
               ▼
          Vision / LLM
               │
               ▼
┌─────────────────────────────┐
│ Requirement Constraint Model│
└──────────────┬──────────────┘
               │
               │
               │
┌──────────────┴──────────────┐
│ Verification / Inspection   │
│ Plan                        │
│                             │
│ CSV / Excel / PDF / Text    │
└──────────────┬──────────────┘
               │
               ▼
          Vision / LLM
               │
               ▼
┌─────────────────────────────┐
│ Verification Constraint     │
│ Model                       │
└──────────────┬──────────────┘
               │
               ▼
╔═════════════════════════════╗
║   Verification Gap Solver   ║
║                             ║
║ Verification(X) = PASS      ║
║ Requirement(X)  = FAIL      ║
╚══════════════╤══════════════╝
               │
       ┌───────┴────────┐
       ▼                ▼
 Counterexample       No Gap Found
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

---

## ⚙️ 현재 PoC (Proof of Concept)

현재 첫 번째 Solver PoC에서는 두 개의 변수 `A`, `B`와  
하나의 관계조건을 이용해 Verification Gap 탐색을 검증했습니다.

### Case 1 — 관계조건을 검증하지 않는 경우

Verification Plan:

```text
9.9 ≤ A ≤ 10.1
19.9 ≤ B ≤ 20.1
```

Engineering Requirement:

```text
A + B ≤ 30.05
```

Solver Result:

```text
COUNTEREXAMPLE FOUND
--------------------

A = 10.10
B = 20.10

Verification:
A range -> PASS
B range -> PASS

A + B = 30.20

Requirement:
A + B <= 30.05

Requirement -> FAIL
```

✅ **Verification Gap 탐색 성공**

---

### Case 2 — 관계조건까지 검증하는 경우

Verification Plan:

```text
9.9 ≤ A ≤ 10.1
19.9 ≤ B ≤ 20.1

A + B ≤ 30.05
```

동일한 Requirement를 위반하면서  
Verification Plan을 모두 만족하는 상태는 존재할 수 없습니다.

Solver Result:

```text
NO COUNTEREXAMPLE FOUND
```

✅ **Gap 제거 후 재검증 성공**

---

## 🔍 기존 방식과의 차이

기존의 검사계획 검토는 주로 다음과 같은 방식으로 수행됩니다.

```text
Requirement A → 검사 항목 있음?  YES
Requirement B → 검사 항목 있음?  YES
Requirement C → 검사 항목 있음?  NO
```

본 프로젝트는 단순한 항목 존재 여부 비교를 넘어,

```text
현재 검증조건을 모두 만족할 수 있는 상태 중

실제 Engineering Requirement를
위반하는 상태가 존재하는가?
```

를 직접 탐색합니다.

즉,

```text
Missing Item Detection
```

이 아니라,

```text
Counterexample Generation
+
Constraint-based Verification
```

을 핵심으로 합니다.

---

## 🎯 목표 결과물

최종 시스템은 다음과 같은 **Engineering Verification Report** 생성을 목표로 합니다.

```text
ENGINEERING VERIFICATION REPORT
================================

Result:
⚠ VERIFICATION GAP FOUND


Counterexample #001

A = 10.08
B = 20.04

Verification Plan
A -> PASS
B -> PASS

Engineering Requirement
A + B <= 30.05

Actual
A + B = 30.12

Requirement -> FAIL


Cause
Relationship constraint is not
covered by the current verification plan.


Recommended Patch

+ Verify:
A + B <= 30.05


Re-verification

Counterexample eliminated.

✓ GAP CLOSED
within modeled constraints.
```

---

## 🧩 적용 가능 영역

본 프로젝트의 핵심 Solver는 특정 Hole 또는 공차 문제에만 종속되지 않도록 설계하는 것을 목표로 합니다.

예상 가능한 적용 예시는 다음과 같습니다.

```text
Design Requirement ↔ Inspection Plan
→ Quality Verification Gap

Engineering Specification ↔ Test Plan
→ Test Coverage Gap

Design Requirement ↔ Design Review Checklist
→ Review Coverage Gap

Construction Specification ↔ Inspection Plan
→ Site Verification Gap
```

초기 Prototype에서는 구현 가능성과 검증 명확성을 위해  
**기계설계 요구사항과 검사계획 간의 Verification Gap**을 중심으로 개발합니다.

---

## 🛠 기술 스택 (Tech Stack)

```text
Python
├── Z3 Solver
├── Pydantic          [Planned]
├── Vision / LLM      [Planned]
└── Engineering Constraint Engine
```

### 역할 분리

```text
Vision / LLM
→ 비정형 엔지니어링 문서 해석
→ Requirement / Verification 조건 구조화

Constraint Solver
→ 수학적 반례 탐색
→ Verification Gap 증명

Application Layer
→ 원인 분석
→ 수정안 생성
→ 재검증
→ Report 생성
```

LLM의 추론 결과를 그대로 PASS/FAIL 판정에 사용하는 것이 아니라,  
**최종 검증은 결정론적인 Constraint Solver가 수행하는 구조**를 목표로 합니다.

---

## 🗺 Development Roadmap

```text
Phase 1
[x] Basic Verification Gap Solver
[x] Counterexample generation
[x] Gap / No-Gap two-case validation

Phase 2
[ ] Automated solver tests
[ ] Acceptance-range mismatch
[ ] Three-variable constraints
[ ] Multiple relationship constraints

Phase 3
[ ] Generic Requirement data model
[ ] Verification Plan data model
[ ] Gap cause classification
[ ] Recommended verification patch
[ ] Automatic re-verification

Phase 4
[ ] Engineering document parsing
[ ] Vision / LLM integration
[ ] Existing drawing parser integration
[ ] Structured report generation

Phase 5
[ ] UI
[ ] Visual counterexample representation
[ ] Engineering case-study evaluation
```

---

## 📂 프로젝트 구조

```text
AI-Engineering-Verification/
├── README.md
├── main.py
├── requirements.txt
│
├── src/
│   └── escape_solver.py
│
└── tests/
    └── test_escape_solver.py
```

프로젝트가 확장됨에 따라 Solver, data model, parser, report 모듈을 분리할 예정입니다.

---

## ⚠️ 현재 개발 범위

현재 프로젝트는 **Proof of Concept 단계**입니다.

초기 버전에서는 다음과 같은 단순화된 조건을 우선 지원합니다.

```text
Range Constraints
Relationship Constraints
Linear Constraints
Multiple Engineering Variables
```

Sampling, measurement uncertainty, operator error, process drift 등  
모든 실제 Quality Escape 원인을 해결하는 시스템을 의미하지 않습니다.

본 프로젝트가 검증하고자 하는 핵심 영역은:

> **Engineering Requirement와 Verification Plan 사이의 논리적 Coverage Gap**

입니다.

또한 `NO COUNTEREXAMPLE FOUND`는 절대적인 안전을 의미하지 않으며,

> **현재 시스템에 모델링된 변수와 제약조건 범위에서 반례가 발견되지 않았음**

을 의미합니다.

---

## 🏆 Project Context

**제1회 HIMEC AI 활용 아이디어 공모전 출품 프로젝트**

본 프로젝트는 AI와 Constraint Solving을 결합하여  
엔지니어링 설계·품질·검증 업무에서 발생할 수 있는  
**Verification Gap을 생산·시공·시험 이전 단계에서 발견하는 방법**을 탐구합니다.

---

## 📄 License

This repository is currently maintained as a private research and competition project.