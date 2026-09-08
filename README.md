# Engineering Verification Stress Test

> **제품을 검사하는 시스템이 아니라, 제품을 검사하는 ‘검증계획 자체가 충분한지’를 실제 적용 전에 가상으로 공격해보는 시스템**

설계·기술 요구조건과 실제 검사·시험 기준을 비교하여,  
**검사에서는 합격하지만 실제 설계 요구조건은 위반하는 상태**가 존재하는지를 탐색합니다.

현재는 AI가 text-based Requirement/Verification PDF에서 지원되는 조건 후보를 추출하고,
Engineer의 검토와 근거 기반 Feasible Domain 입력을 거쳐 결정론적 Solver인 **Z3**가
검증계획의 escape를 계산하는 prototype을 제공합니다.

## 실행

Python virtual environment에서 다음 순서로 실행합니다.

```bash
python -m pip install -r requirements.txt
export OPENAI_API_KEY="your-api-key"
python -m streamlit run src/ui/app.py
```

현재 PDF ingress는 extractable text가 있는 PDF만 지원합니다. OCR, scanned/image-only PDF,
암호화 PDF, 임의 형식의 모든 engineering document에 대한 자동 이해는 지원하지 않습니다.
Requirement와 Verification의 AI extraction 결과는 반드시 사람이 검토해야 하며,
Feasible Domain은 별도의 Engineer-Supplied Operating Evidence로 입력합니다.

---

## 핵심 용어

아래 용어만 이해하면 프로젝트의 전체 흐름을 쉽게 볼 수 있습니다.

| 용어 | 쉬운 의미 | 이 프로젝트에서의 의미 |
|---|---|---|
| **Requirement** | 설계·기술 요구조건 | 제품이나 시스템이 실제로 만족해야 하는 설계 기준 |
| **Verification Plan** | 검사·시험·검증 계획 | 실제 현장에서 합격/불합격을 판단하기 위해 사용하는 검사 및 시험 기준 |
| **Feasible Domain** | 현실적으로 가능한 범위 | 물리적·공정적·운영상 실제로 발생할 수 있는 상태 범위 |
| **Verification Escape** | 검사망을 빠져나가는 요구조건 위반 상태 | 현실적으로 가능하고 검사에는 합격하지만 실제 요구조건은 위반하는 상태 |
| **Stress Test** | 검증계획 허점 공격 | 현재 검사계획을 가상으로 공격하여 빠져나갈 수 있는 상태를 능동적으로 찾는 과정 |
| **Worst Undetected Violation** | 최대 미검출 위반 | 검사에 걸리지 않으면서 요구조건을 가장 크게 위반할 수 있는 경우 |
| **Nearest Escape** | 정상 상태에 가장 가까운 허점 | 정상 설계 상태에서 가장 작은 변화로 검사망을 빠져나가는 경우 |
| **Patch** | 검증계획 수정안 | 발견된 허점을 줄이거나 제거하기 위한 검사·시험 기준 수정 후보 |
| **Re-test** | 수정 후 재검증 | 수정된 검사 기준을 다시 공격하여 허점이 실제로 사라졌는지 확인하는 과정 |
| **Validator** | 입력 오류 검사기 | 잘못된 범위, 단위 오류, 존재하지 않는 변수 등을 Solver 실행 전에 차단하는 기능 |
| **Logical Consistency** | 조건들의 논리적 일관성 | 여러 설계 요구조건을 현실적으로 동시에 만족할 수 있는지 확인하는 것 |
| **Conflict Diagnosis** | 충돌 조건 진단 | 여러 조건이 서로 모순될 때 어떤 조건들이 충돌하는지 찾아주는 기능 |
| **Constraint Engine** | 공학 조건 변환 엔진 | `A + B <= 30.05`와 같은 공학 조건을 Solver가 계산할 수 있는 제약식으로 변환하는 기능 |
| **Solver (Z3)** | 수학적 조건 계산기 | 주어진 조건을 만족하거나 위반하는 상태가 존재하는지를 결정론적으로 계산하는 도구 |

---

## 1. 어떤 문제를 해결하려는가?

검사계획을 통과했다고 해서 실제 설계 요구조건까지 항상 만족한다고 보장할 수 있을까요?

예를 들어 실제 설계 요구조건이 다음과 같다고 가정합니다.

```text
A + B <= 30.05
```

하지만 실제 검사에서는 각각의 값만 확인한다고 가정합니다.

```text
9.90 <= A <= 10.10
19.90 <= B <= 20.10
```

그러면 다음 상태는 검사에서는 합격입니다.

```text
A = 10.10
B = 20.10
```

그러나 실제 설계 요구조건을 계산하면,

```text
A + B = 30.20
```

이므로 요구조건은 위반합니다.

즉,

```text
현실적으로 가능한 상태
        AND
현재 검사계획은 PASS
        AND
실제 설계 요구조건은 FAIL
```

인 상태가 존재합니다.

이 프로젝트에서는 이러한 상태를 **Verification Escape**라고 정의합니다.

---

## 2. 핵심 수학 모델

프로젝트에서는 세 가지 상태공간을 구분합니다.

- **F — Feasible Domain**  
  현실적으로 가능한 상태

- **V — Verification PASS Region**  
  현재 검사·시험 계획이 합격으로 판단하는 상태

- **R — Requirement PASS Region**  
  실제 설계·기술 요구조건을 만족하는 상태

우리가 찾는 것은 다음 영역입니다.

```text
F ∩ V ∩ ¬R
```

즉,

> **현실적으로 가능하고, 현재 검사에는 합격하지만, 실제 요구조건은 위반하는 상태**

입니다.

이 영역이 존재한다면 현재 Verification Plan만으로는 실제 Requirement 만족을 보장할 수 없습니다.

---

## 3. 단순한 Gap 비교와 무엇이 다른가?

기존의 Requirement 관리, Inspection Plan 관리, Traceability 도구는 주로 다음과 같은 문제를 다룹니다.

- 어떤 Requirement가 존재하는가
- 어떤 검사 항목과 연결되어 있는가
- 검사 항목이 누락되었는가
- 검사계획을 어떻게 생성하고 관리할 것인가

본 프로젝트는 단순한 항목 비교에서 더 나아가,

> **현재 검증계획 자체를 가상으로 공격하여, 실제로 빠져나갈 수 있는 Counterexample을 찾는 것**

을 핵심으로 합니다.

### 핵심 발전 방향

**1. Verification Escape 탐색**

```text
Feasible
AND
Verification PASS
AND
Requirement FAIL
```

인 실제 상태를 Solver가 탐색합니다.

**2. 허점의 심각도 분석**

단순히 Escape의 존재 여부만 확인하지 않습니다.

```text
가장 심하게 빠져나가는 경우
→ Worst Undetected Violation

정상 상태에서 가장 조금 변해도 빠져나가는 경우
→ Nearest Escape
```

를 분석합니다.

**3. 수정 후 다시 공격**

```text
Escape 발견
    ↓
검증계획 수정안 생성
    ↓
수정된 Verification Plan
    ↓
다시 Stress Test
    ↓
Escape가 실제로 사라졌는지 확인
```

하는 폐쇄형 검증 흐름을 목표로 합니다.

> Z3, Counterexample, Unsat Core 자체를 새로운 알고리즘이라고 주장하는 프로젝트는 아닙니다.  
> 핵심은 이러한 기술을 **Engineering Verification Plan의 충분성을 검증하는 Workflow**로 구성하는 것입니다.

---

## 4. 현재 시스템의 전체 흐름

현재 개발 중인 구조는 다음과 같습니다.

```text
Engineering Case
        ↓
입력 오류 검사
Validator
        ↓
조건 간 논리적 모순 검사
Logical Consistency Check
        ↓
공학 조건을 Solver 식으로 변환
Constraint Engine
        ↓
검사계획 허점 공격
Verification Stress Test
        ↓
Verification Escape 탐색
        ↓
Worst / Nearest Escape 분석
        ↓
검증계획 수정 후보
Patch Candidate
        ↓
수정안의 공학적 적절성 확인
        ↓
수정 후 재검증
Re-test
```

최종 합격/불합격 논리는 LLM이 직접 판단하지 않고,  
**결정론적인 Solver(Z3)** 가 계산하도록 설계하고 있습니다.

---

## 5. 지금까지 검증한 기능

초기 Prototype에서는 기능을 하나씩 분리하여 TEST 1~14로 검증했습니다.

| 단계 | 검증한 내용 |
|---|---|
| **TEST 1** | 검사에는 합격하지만 Requirement를 위반하는 Escape 탐색 |
| **TEST 2** | 검사망을 통과하면서 가능한 최대 위반량 계산 |
| **TEST 3** | 현실적으로 가능한 범위 안에서만 Escape 탐색 |
| **TEST 4** | 정상 상태에서 가장 가까운 Escape 탐색 |
| **TEST 5** | 검증계획 수정 후 Escape가 사라지는지 Re-test |
| **TEST 6** | 여러 수정 후보 비교 |
| **TEST 7** | Gap을 기반으로 수정 후보 자동 생성 |
| **TEST 8** | 정상 설계 상태를 파괴하는 비현실적 수정안 차단 |
| **TEST 9** | 변수 이름과 개수가 달라도 동일 엔진이 작동하는지 확인 |
| **TEST 10** | 여러 종류의 공학 Constraint 처리 |
| **TEST 11** | 잘못된 변수, 범위, 단위 등을 Solver 실행 전에 차단 |
| **TEST 12** | Validator와 Solver 연결 |
| **TEST 13** | 형식은 정상이나 논리적으로 불가능한 Engineering Model 탐지 |
| **TEST 14** | 서로 충돌하는 Constraint 묶음 식별 |

---

## 6. 현재 지원하는 공학 조건

현재 Core Prototype에서는 다음과 같은 기본 조건을 지원합니다.

### 범위 조건

```text
min <= X <= max
```

예:

```text
9.95 <= D <= 10.05
```

### 차이 조건

```text
Y - X >= limit
```

예:

```text
Y - X >= 20.00
```

### 합계 상한 조건

```text
X + Y + ... <= limit
```

예:

```text
X + Y <= 40.05
```

현재는 핵심 개념 검증을 위한 제한된 Constraint Type만 지원하며,  
모든 Engineering Constraint를 처리하는 범용 해석기를 구현한 상태는 아닙니다.

---

## 7. 잘못된 입력을 그대로 계산하지 않도록 한다

Solver는 입력된 수식을 매우 정확하게 계산하지만,  
입력 자체가 잘못되었다면 잘못된 문제를 정확하게 풀게 됩니다.

이를 방지하기 위해 Solver 실행 전에 Engineering Model을 검증합니다.

현재 다음 문제를 탐지할 수 있습니다.

- 존재하지 않는 변수 참조
- 최소값과 최대값이 뒤집힌 범위
- Nominal 값이 Feasible Domain 밖에 존재하는 경우
- Verification Range와 Feasible Domain이 완전히 분리된 경우
- 지원하지 않는 Constraint Type
- 서로 다른 Unit을 잘못 결합한 경우
- 모든 Requirement를 동시에 만족할 수 없는 논리적 모순

예를 들어,

```text
X >= 9.50
Y >= 29.50
X + Y <= 38.90
```

는 각 식의 문법 자체는 정상입니다.

하지만 앞의 두 조건 때문에,

```text
X + Y >= 39.00
```

이므로 세 조건을 동시에 만족할 수 없습니다.

이러한 경우 Solver 실행 전에 **논리적 모순**으로 판단합니다.

---

## 8. 충돌하는 조건까지 찾아낸다

모델이 논리적으로 불가능하다고 판단하는 것에서 끝나지 않고,  
Z3의 Unsat Core를 이용하여 충돌에 관여한 조건 묶음을 찾아냅니다.

예:

```text
Feasible Domain: X >= 9.50
Feasible Domain: Y >= 29.50
Requirement R3: X + Y <= 38.90
```

이를 통해 엔지니어에게 단순히,

```text
MODEL ERROR
```

라고 알리는 것이 아니라,

```text
이 조건들이 서로 동시에 만족될 수 없습니다.
```

라고 수정해야 할 위치를 제시할 수 있습니다.

현재 Unsat Core는 **충돌에 관여하는 Constraint subset**을 식별하는 용도로 사용하며,  
항상 수학적으로 가장 작은 최소 충돌 집합을 보장한다고 주장하지 않습니다.

---

## 9. Verification Stress Test

### Verification Escape

현재 검사계획을 통과하면서 실제 Requirement를 위반하는 상태를 탐색합니다.

```text
Feasible
AND
Verification PASS
AND
Requirement FAIL
```

### Worst Undetected Violation

검사에서 합격으로 처리되는 상태 가운데  
실제 Requirement를 가장 크게 위반할 수 있는 경우를 계산합니다.

### Nearest Escape

정상 설계 상태인 Nominal State에서  
가장 작은 변화로 발생할 수 있는 Escape를 탐색합니다.

이를 통해 단순히,

```text
허점 있음 / 없음
```

만 판단하는 것이 아니라,

```text
얼마나 쉽게 뚫리는가?
얼마나 심하게 뚫리는가?
```

를 함께 분석합니다.

---

## 10. 검증계획 수정과 Re-test

발견된 Gap을 기반으로 Verification Plan 수정 후보를 만들고,  
수정된 계획을 다시 동일한 방식으로 공격합니다.

```text
현재 Verification Plan
        ↓
Escape 발견
        ↓
Patch Candidate
        ↓
수정된 Verification Plan
        ↓
Re-test
```

수정 후,

```text
NO COUNTEREXAMPLE FOUND
```

가 나오면 현재 모델링된 조건과 Feasible Domain 안에서는  
동일한 Escape가 더 이상 발견되지 않았다고 판단합니다.

---

## 11. 수학적으로 맞는 수정안과 공학적으로 좋은 수정안은 다르다

Escape를 없앴다고 해서 항상 좋은 수정안은 아닙니다.

예를 들어 정상 설계값이,

```text
A = 10.00
```

인데 수정안이,

```text
A <= 9.95
```

라면 Escape는 제거할 수 있지만 정상 설계 상태까지 불합격으로 처리하게 됩니다.

따라서 수정 후보는 최소한 다음 조건을 함께 확인합니다.

```text
Escape 제거
AND
정상 설계 상태 보존
```

현재는 이를 **Engineering Practicality Filter**의 첫 단계로 사용하고 있습니다.

향후 실제 데이터가 확보되면 검사 시간, 비용, False Reject, 공정 Capability 등도 추가 검토할 수 있습니다.

---

## 12. 현재 Core 개발 상태

초기 TEST 1~14에서 개별적으로 검증한 기능을  
현재 하나의 재사용 가능한 Core Engine으로 통합하고 있습니다.

현재 Core 구조:

```text
src/core/
├── models.py
├── validator.py
├── constraint_engine.py
├── stress_tester.py
└── conflict_analyzer.py
```

현재까지 Core에 통합된 기능:

```text
공통 Engineering Data Model
        ↓
입력 검증
        ↓
공학 Constraint 변환
        ↓
논리적 모순 분석
        ↓
충돌 조건 진단
        ↓
Verification Escape Stress Test
```

다음 통합 대상은 Verification Plan의 관계조건 모델과 Patch Engine, 전체 Pipeline입니다.

---

## 13. 최종 목표 구조

최종적으로는 비정형 Engineering Document를 AI가 구조화하고,  
엔지니어가 이를 확인한 뒤 Solver가 검증하도록 하는 구조를 목표로 합니다.

```text
도면 / Specification / Inspection Plan
                ↓
        AI Constraint Extraction
                ↓
          원문 Source 표시
                ↓
        Engineer Review / Edit
                ↓
             승인
                ↓
        Engineering Validator
                ↓
       Logical Consistency Check
                ↓
      Verification Stress Test
                ↓
          Escape Analysis
                ↓
      Verification Plan 개선안
                ↓
              Re-test
```

### AI의 역할

AI는 비정형 문서에서 다음과 같은 정보를 구조화하는 역할을 담당합니다.

```text
변수
단위
허용 범위
설계 Requirement
검사 기준
관계식
원문 출처
```

### Solver의 역할

최종적으로,

```text
검사에는 합격하지만
실제 Requirement는 위반하는 상태가 존재하는가?
```

라는 논리 판단은 LLM이 아니라 **결정론적 Solver**가 수행합니다.

즉,

```text
AI = 문서 이해 및 구조화 보조
Engineer = 검토 및 승인
Solver = 최종 논리 검증
```

의 역할 분리를 목표로 합니다.

---

## 14. 현재 범위와 한계

이 프로젝트는 모든 품질 문제나 Engineering Failure Mode를 탐지하는 시스템이 아닙니다.

현재 주요 대상은 다음과 같은 **모델링 가능한 Verification Gap**입니다.

- 검사 허용범위와 실제 요구 허용범위가 다른 경우
- 개별 변수는 합격하지만 변수 간 관계조건을 위반하는 경우
- Requirement가 존재하지만 Verification Plan에서 충분히 다루지 않는 경우

현재 주요 범위 밖의 항목:

- Measurement Uncertainty
- Sampling Strategy
- Calibration
- Operator Error
- Process Drift
- 전체 GD&T 자동 해석
- 모든 종류의 비선형 Engineering Constraint

또한,

```text
NO COUNTEREXAMPLE FOUND
```

는

> **현재 모델링된 Constraint와 Feasible Domain 안에서 Counterexample을 발견하지 못했다**

는 의미입니다.

실제 물리 시스템의 절대적 안전을 의미하지 않습니다.

---

## 프로젝트 한 문장 요약

> **설계 요구조건과 실제 검사계획을 각각 제약조건으로 모델링하고, 현실적으로 가능한 상태 중 검사에는 합격하지만 실제 요구조건은 위반하는 상태를 능동적으로 탐색하여 검증계획 자체의 충분성을 평가하는 Engineering Verification Stress Test 시스템**
