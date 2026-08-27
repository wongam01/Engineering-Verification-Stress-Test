cat > README.md <<'EOF'
# Engineering Verification Stress Test

설계·기술 요구사항(Requirement)과 실제 검사·시험·검증계획(Verification Plan)을 비교하여,  
현재 검증계획을 통과하면서도 실제 요구사항을 위반할 수 있는 상태를 탐색하는  
**Engineering Verification Stress Test** 프로젝트입니다.

현재는 핵심 검증 엔진의 프로토타입을 개발하고 있으며,  
향후 AI를 이용한 엔지니어링 문서의 Constraint 추출 기능을 연결하는 것을 목표로 합니다.

---

## 1. 프로젝트의 핵심 문제

검사계획을 통과했다고 해서 실제 기술 요구사항까지 항상 만족한다고 보장할 수 있을까?

이 프로젝트는 다음 상태가 존재하는지를 탐색합니다.

```text
현실적으로 가능한 상태
AND
현재 Verification Plan PASS
AND
실제 Requirement FAIL
```

이를 수학적으로 표현하면:

```text
F ∩ V ∩ ¬R
```

- **F — Feasible Domain**  
  현실적으로 가능한 Engineering State

- **V — Verification PASS Region**  
  현재 검사·시험 계획이 허용하는 상태

- **R — Requirement PASS Region**  
  실제 설계·기술 요구사항을 만족하는 상태

`F ∩ V ∩ ¬R`에 해당하는 상태가 존재하면,  
현재 Verification Plan에는 실제 요구사항 위반 상태가 빠져나갈 수 있는  
**Verification Escape**가 존재한다고 판단합니다.

---

## 2. 핵심 아이디어

이 프로젝트는 제품 자체를 검증하는 것이 아니라,

> **제품을 검증하기 위해 만들어진 Verification Plan 자체가 충분한지를 검증합니다.**

현재 검증계획을 실제 적용 전에 가상으로 Stress Test하여 다음을 확인합니다.

- 검사를 통과하면서 Requirement를 위반할 수 있는가?
- 정상 상태에서 얼마나 작은 변화로 Escape가 발생하는가?
- 검사를 통과하면서 Requirement를 얼마나 크게 위반할 수 있는가?
- Verification Plan을 수정하면 Escape가 실제로 사라지는가?

---

## 3. 기존 접근과 구분되는 방향

기존의 Requirement 관리, Inspection Plan 관리, Traceability 도구는 주로 다음을 다룹니다.

- 어떤 Requirement가 존재하는가
- 어떤 검사 항목과 연결되어 있는가
- 검사 항목이 누락되었는가
- 검사계획을 어떻게 생성하거나 관리할 것인가

본 프로젝트는 여기서 한 단계 더 나아가,

> **현재 Verification Plan을 가상으로 공격하여, PASS하면서 Requirement를 위반하는 Counterexample을 찾는 것**

을 핵심으로 합니다.

주요 방향은 다음과 같습니다.

1. **Requirement와 Verification의 허용 상태공간 비교**
2. **`F ∩ V ∩ ¬R` 형태의 Verification Escape 탐색**
3. **Nearest Escape / Worst Undetected Violation을 통한 Stress Test**
4. **Patch 생성 후 Re-test를 통한 검증계획 개선 확인**

Z3, Counterexample, Unsat Core 자체가 새로운 기술이라는 의미는 아닙니다.  
본 프로젝트의 핵심은 이러한 기술을  
**Engineering Verification Plan의 충분성 검증 Workflow**로 구성하는 데 있습니다.

---

## 4. 현재 구현 흐름

```text
Engineering Case
        ↓
Constraint Validator
        ↓
Logical Consistency Check
        ↓
Verification Sufficiency Test
        ↓
Escape Detection
        ↓
Worst / Nearest Escape Analysis
        ↓
Patch Candidate Generation
        ↓
Engineering Practicality Filter
        ↓
Patch Re-test
```

최종 Verification 판단은 LLM이 아니라  
**결정론적인 Solver(Z3)** 가 수행합니다.

---

## 5. TEST 1 ~ 14에서 검증한 내용

| TEST | 검증 내용 | 의미 |
|---|---|---|
| TEST 1 | Escape Detection | Verification PASS이면서 Requirement FAIL인 상태 탐색 |
| TEST 2 | Worst Undetected Violation | 검사망을 통과하면서 가능한 최대 Requirement 위반량 계산 |
| TEST 3 | Feasible Domain | 현실적으로 가능한 상태 범위 안에서만 Escape 탐색 |
| TEST 4 | Nearest Escape | Nominal State에서 가장 가까운 Escape 탐색 |
| TEST 5 | Patch → Re-test | Verification Plan 수정 후 Escape가 사라지는지 재검증 |
| TEST 6 | Patch Comparison | 여러 Patch 후보를 Stress Test하여 비교 |
| TEST 7 | Automatic Patch Generation | 발견된 Gap으로부터 Patch 후보 자동 생성 |
| TEST 8 | Engineering Practicality Filter | Nominal State를 파괴하는 Patch 차단 |
| TEST 9 | Generic Variable Engine | 변수 이름과 개수가 달라도 동일 엔진이 작동하는지 확인 |
| TEST 10 | Multiple Constraint Types | Range, Difference, Sum Constraint 처리 |
| TEST 11 | Constraint Validator | 잘못된 변수, 범위, 단위 등을 Solver 이전에 차단 |
| TEST 12 | Validator → Solver Pipeline | 검증된 입력만 Solver로 전달 |
| TEST 13 | Logical Consistency | 형식상 정상이나 전체적으로 모순된 Engineering Model 탐지 |
| TEST 14 | Conflict Diagnosis | Unsat Core를 이용해 충돌 Constraint subset 식별 |

---

## 6. 현재 지원하는 Constraint 예시

### Range

```text
min <= X <= max
```

예:

```text
9.95 <= D <= 10.05
```

### Difference Minimum

```text
Y - X >= limit
```

예:

```text
Y - X >= 20.00
```

### Sum Upper Bound

```text
X + Y + ... <= limit
```

예:

```text
X + Y <= 40.05
```

현재는 제한된 Constraint Type을 대상으로 프로토타입을 검증하고 있으며,  
모든 Engineering Constraint를 지원하는 상태는 아닙니다.

---

## 7. Engineering Validation Layer

Solver 실행 전에 입력된 Engineering Model을 검증합니다.

현재 확인하는 항목:

- 존재하지 않는 변수 참조
- 잘못된 `min / max` 범위
- Nominal 값이 Feasible Domain 밖에 존재하는 경우
- Verification Range와 Feasible Domain이 완전히 분리된 경우
- 지원하지 않는 Constraint Type
- Unit 불일치
- 전체 Requirement의 논리적 모순

논리적 모순이 발견되면 Z3의 Unsat Core를 이용하여  
충돌에 관련된 Constraint subset을 식별할 수 있습니다.

예:

```text
X >= 9.50
Y >= 29.50
X + Y <= 38.90
```

위 세 조건은 동시에 만족할 수 없으므로 Logical Conflict로 판단합니다.

---

## 8. Verification Stress Analysis

### Escape Detection

현재 Verification Plan을 통과하면서 Requirement를 위반하는 상태를 탐색합니다.

```text
Feasible
AND
Verification PASS
AND
Requirement FAIL
```

### Worst Undetected Violation

검사를 통과하면서 Requirement를 얼마나 크게 위반할 수 있는지를 계산합니다.

### Nearest Escape

Nominal Engineering State에서 얼마나 작은 변화로 첫 Escape가 발생할 수 있는지를 탐색합니다.

### Patch Re-test

발견된 Verification Gap에 대한 수정 후보를 적용한 뒤  
동일한 Stress Test를 다시 수행하여 Gap이 실제로 제거되었는지 확인합니다.

---

## 9. Engineering Practicality Filter

수학적으로 Escape를 제거한다고 해서 항상 좋은 Patch는 아닙니다.

예를 들어 Nominal 값이:

```text
A = 10.00
```

인데 Patch가:

```text
A <= 9.95
```

라면 Escape는 제거할 수 있지만 정상 설계 상태까지 Reject하게 됩니다.

따라서 현재 Prototype에서는 최소한 다음 조건을 확인합니다.

```text
Escape 제거
AND
Nominal State 보존
```

이를 통해 수학적으로는 효과적이지만  
Engineering 관점에서는 부적절한 Patch를 구분합니다.

---

## 10. 향후 목표 구조

최종적으로는 다음과 같은 AI-assisted Verification Workflow를 목표로 합니다.

```text
도면 / Specification / Inspection Plan
                ↓
        AI Constraint Extraction
                ↓
          Source Traceability
                ↓
       Engineer Review / Approval
                ↓
         Constraint Validator
                ↓
      Logical Consistency Check
                ↓
     Verification Stress Test
                ↓
        Escape Analysis
                ↓
 Verification Improvement Candidate
                ↓
             Re-test
```

AI는 비정형 엔지니어링 문서에서 Constraint를 구조화하는 역할을 담당하고,  
최종 Verification Sufficiency 판단은 결정론적인 Solver가 수행하는 구조를 목표로 합니다.

---

## 11. 현재 개발 단계

현재는 완성된 제품이 아니라  
**핵심 Verification Engine의 Prototype 단계**입니다.

TEST 1~14를 통해 주요 개념과 개별 기능을 검증했으며,  
다음 단계에서는 여러 Prototype 파일에 흩어진 기능을  
하나의 재사용 가능한 Core Engine으로 통합할 예정입니다.

예상 구조:

```text
src/
├── models.py
├── validator.py
├── constraint_engine.py
├── stress_tester.py
├── conflict_analyzer.py
├── patch_engine.py
└── pipeline.py
```

---

## 12. 현재 범위의 한계

현재 Prototype은 모든 품질 문제나 Engineering Failure Mode를 탐지하는 시스템이 아닙니다.

현재 주요 대상은 다음과 같은 Verification Gap입니다.

- **Acceptance Gap**
- **Relationship Gap**
- **Requirement Coverage Gap**

다음 항목은 현재 Prototype의 주요 범위 밖입니다.

- Measurement Uncertainty
- Sampling Strategy
- Calibration
- Operator Error
- Process Drift
- 전체 GD&T 자동 해석
- 모든 종류의 비선형 Engineering Constraint

또한 다음 결과:

```text
NO COUNTEREXAMPLE FOUND
```

은

> **현재 모델링된 Constraint와 Feasible Domain 안에서 Counterexample을 발견하지 못했다.**

는 의미이며, 실제 물리 시스템의 절대적인 안전을 의미하지 않습니다.

---

## 13. 프로젝트 한 문장 요약

> **제품을 검증하는 시스템이 아니라, 제품을 검증하는 Verification Plan 자체를 실제 적용 전에 가상으로 공격하여 그 충분성을 검증하는 Engineering Verification Stress Test 시스템**
EOF

echo "README.md 교체 완료"
git diff -- README.md