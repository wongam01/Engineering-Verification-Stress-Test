# Engineering Verification Stress Test

> **제품을 검사하는 것이 아니라,  
> 제품을 검사하는 ‘검증 기준 자체가 충분한지’를 먼저 검증합니다.**

**Engineering Verification Stress Test (EVST)**는 기존 Engineering Document에서  
설계 요구조건, 실제 검사·합격 기준, 실제 관측 근거를 구조화하고,

> **“현실적으로 가능한 상태인데 검사에는 합격하고, 실제 설계 요구조건은 위반하는 상태가 존재하는가?”**

를 검증하는 Engineering Assurance prototype입니다.

AI는 문서를 읽고 근거를 구조화하는 **Semantic Bridge** 역할을 담당하며,  
최종 판단은 Engineer Review를 거친 Formal Model과  
결정론적인 Validator / Z3 Solver가 수행합니다.

---

## 핵심 아이디어

EVST가 찾는 상태는 다음과 같습니다.

```text
∃x : F(x) ∧ V(x) ∧ ¬R(x)
```

- **R(x) — Requirement**  
  실제 제품이나 시스템이 만족해야 하는 Engineering Requirement

- **V(x) — Verification**  
  현장에서 사용되는 Inspection / Test / Acceptance Criterion

- **F(x) — Feasible / Observed Evidence**  
  시험, 측정, 생산 기록 등 실제 문서 근거로 확인된 Engineering State

즉,

```text
실제로 가능한 상태
        AND
현재 검사에는 합격
        AND
실제 설계 요구조건은 위반
```

하는 상태가 존재하면 이를 **Verification Escape**라고 정의합니다.

---

## 핵심 용어

| 용어 | 의미 |
|---|---|
| **Requirement (R)** | 실제로 만족해야 하는 설계·기술 요구조건 |
| **Verification (V)** | 현장에서 사용하는 검사·시험·합격 기준 |
| **Observed / Feasible Evidence (F)** | 실제 측정·시험·생산 기록 등에서 확인된 상태 |
| **Verification Escape** | `F ∧ V ∧ ¬R`를 만족하는 상태 |
| **Evidence Candidate** | AI가 문서에서 발견한 R / V / F 근거 후보 |
| **Role Grounding** | Candidate가 실제 R / V / F 역할에 해당하는지 source context를 기반으로 검토하는 과정 |
| **Engineer Review** | Source, Role, Variable Mapping, Evidence 사용 여부를 사람이 확인하는 단계 |
| **Formalization** | 승인된 근거를 `R(x), V(x), F(x)` 형태로 변환하는 과정 |
| **Witness** | Verification Escape를 실제로 만족하는 구체적인 값 |

---

## 전체 흐름

```text
Engineering PDF
        ↓
Source Intake
        ↓
Text / Vision Recovery
        ↓
AI Evidence Discovery
(R / V / F Candidates)
        ↓
Role Grounding
        ↓
Engineer Review
        ↓
Source Provenance
+ Variable Mapping
        ↓
Formalization
R(x), V(x), F(x)
        ↓
Strict Validator
        ↓
Z3 Deterministic Verification
        ↓
Witness / Result
        ↓
Evidence Trace
```

EVST에서는 역할을 의도적으로 분리합니다.

```text
AI
= Semantic Bridge

Engineer
= Evidence / Role Review

Deterministic Core
= Formal Validation + Solver
```

AI가 최종 Verification Escape를 결정하지 않습니다.

---

## 사용 방법

현재 UI에서는 두 가지 경로를 제공합니다.

### 1. Validated Real-World Case

실제 공개 산업문서를 이용한  
**Ford Nano Intake Valve Hardness** 사례를 통해 전체 pipeline을 확인할 수 있습니다.

```text
Source PDF
→ Evidence Discovery
→ Role Grounding
→ Engineer Review
→ Formalization
→ Solver
→ Evidence Trace
```

원문 PDF와 실제 source page도 UI에서 확인할 수 있습니다.

### 2. Analyze Your Document

새로운 Engineering PDF를 업로드하여 동일한 Generic Pipeline을 실행할 수 있습니다.

```text
Upload PDF
→ Candidate Discovery
→ Grounding
→ Engineer Review
→ Compatibility Check
→ Formalization
→ Verification
```

단,

> **모든 PDF에서 Verification Escape가 발견되는 것은 아닙니다.**

근거가 부족하거나 의미가 불명확하거나  
R / V / F가 같은 Engineering State로 연결되지 않는 경우에는

```text
FORMALIZATION BLOCKED
```

상태에서 안전하게 멈춥니다.

---

## Ford Validated Case

Ford Nano Intake Valve 사례에서 구성한 Formal Model은 다음과 같습니다.

### Requirement

```text
R(H) := 50 ≤ H ≤ 57 HRC
```

### Historical Verification

```text
V(H) := H ≥ 50 HRC
```

### Observed Evidence

```text
F(H) := 58 ≤ H ≤ 60 HRC
```

Solver query:

```text
∃H : F(H) ∧ V(H) ∧ ¬R(H)
```

확인된 witness:

```text
H = 60 HRC
```

결과:

```text
F(60) = PASS
V(60) = PASS
R(60) = FAIL
```

따라서 해당 Formal Model에서는 **Verification Escape가 존재합니다.**

> `58–60 HRC`는 전체 manufacturing domain이 아니라  
> 문서에서 확인된 Observed Evidence Envelope입니다.

---

## Validation Evidence

Ford 한 사례에 맞춘 hardcoding이 아닌지,  
그리고 불완전한 입력에서 시스템이 안전하게 동작하는지를 별도로 검증했습니다.

### Anti-hardcoding Mutation

```text
4 automated tests
```

- Feasible Domain 변경 → Solver 결과 변화
- Requirement 변경 → Solver 결과 변화
- Ford와 무관한 변수 / 단위에서도 동일 Core 동작
- Case name / source identity 변경이 수학적 결과에 영향을 주지 않음

### Controlled Fault Injection

```text
8 / 8 cases PASS
14 assertions
```

검증 항목에는 다음이 포함됩니다.

```text
Unsupported semantics
Invalid Core input
Missing Feasible Evidence
Human Review incomplete
Solver UNKNOWN / timeout
Conflicting correction history
```

### Unseen Real Document

**Kyogle ATSB 59-page real-world report**

```text
✓ PDF ingestion
✓ Evidence candidate discovery
✓ Source provenance
✓ Grounding pipeline

✕ Compatible independent R / V / F not established
✕ Solver intentionally NOT RUN
```

새 문서에서 숫자가 발견되었다는 이유만으로  
억지로 Formal Model을 생성하지 않는 것을 확인했습니다.

### Semantic / Input Boundary

```text
Barnawartha
→ Conditional semantics
→ Formalization BLOCKED

Ely
→ Relational semantics
→ Formalization BLOCKED

Encrypted PDF
→ Unsupported input
→ Fail-safe BLOCK
```

---

## 지원 범위

현재 prototype은 특히 다음과 같은  
**source-backed numeric engineering constraints**를 중심으로 지원합니다.

```text
Range
min ≤ X ≤ max

Lower Bound
X ≥ min

Upper Bound
X ≤ max
```

EVST는 특정 Ford 문서나 특정 숫자에 맞춘 시스템은 아니지만,  
모든 Engineering 문장을 자동으로 Solver 식으로 변환하는 범용 자연어 Solver도 아닙니다.

지원되지 않거나 의미가 불명확한 경우에는  
임의로 해석하지 않고 **Review / Block** 상태를 유지합니다.

---

## Fail-safe Principle

EVST의 목표는

> **답을 많이 만드는 것보다, 근거 없는 답을 만들지 않는 것**

입니다.

다음과 같은 경우 Solver 실행 이전에 차단할 수 있습니다.

```text
Missing Evidence
Ambiguous Role
Unit Mismatch
Different Engineering Variable
Unsupported Semantics
Incomplete Human Review
Solver UNKNOWN / Timeout
```

또한,

```text
NO_ESCAPE_FOUND
```

는

> 현재 승인된 Formal Model과 Evidence 범위 안에서  
> Verification Escape를 발견하지 못했다

는 의미이며, 실제 물리 시스템의 절대적인 안전을 의미하지 않습니다.

---

## 실행

### 1. Dependency 설치

```bash
python -m pip install -r requirements.txt
```

### 2. OpenAI API Key 설정

macOS / Linux:

```bash
export OPENAI_API_KEY="your-api-key"
```

### 3. Streamlit 실행

```bash
PYTHONPATH="$(pwd)" python -m streamlit run src/ui/app.py
```

---

## Project Structure

```text
src/
├── ai/
│   └── AI extraction / grounding
│
├── application/
│   └── PDF / provenance / review orchestration
│
├── core/
│   └── Validator / Constraint Engine / Z3
│
└── ui/
    └── Streamlit application

tests/
validation/
```

---

## 한 문장으로 정리하면

> **EVST는 기존 Engineering Document에서 설계 요구조건, 실제 검증 기준, 관측 근거를 구조화하고, 검사에는 합격하지만 실제 요구조건은 위반하는 상태가 존재하는지를 source-backed Formal Model과 deterministic Solver로 검증하는 Engineering Assurance System입니다.**
