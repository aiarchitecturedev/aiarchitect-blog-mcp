# AI 아키텍처 기술 블로그를 시작합니다

![데이터·보안·지식·에이전트·관측성 요소가 하나의 운영 가능한 엔터프라이즈 AI 아키텍처로 연결되는 모습을 표현한 이미지](assets/blog-01-ai-architecture-blog-introduction-hero.png)

안녕하세요. AI 아키텍처 기술 블로그를 시작합니다.

소프트웨어 개발 현장에서 시스템을 설계하고 구축해 왔으며, 최근에는 생성형 AI를 실제 업무 시스템에 적용하는 일에 집중하고 있습니다.

이 블로그는 새로운 기술을 단순히 소개하는 공간이 아닙니다. AI 기능을 기업 환경에 연결할 때 마주치는 설계 선택, 데이터 품질, 보안, 운영, 비용과 장애 대응 문제를 실무 관점에서 정리합니다.

아래 주제 허브는 기술 이름보다 **지금 해결하려는 문제**를 기준으로 글을 찾도록 구성했습니다. 처음 방문했다면 관심 있는 경로에서 한 편을 고르고, 글 안의 관련 글을 따라가면 됩니다.

<blockquote id="aiarchitect-toc" data-ke-style="box" style="background-color: #f6f9fc; color: #263746; font-family: Pretendard-Regular, AppleSDGothicNeo-Regular, sans-serif; font-weight: 400;" data-mce-style="background-color: #f6f9fc; color: #263746; font-family: Pretendard-Regular, AppleSDGothicNeo-Regular, sans-serif; font-weight: 400;">
<p><b>목차</b></p>
<ol>
<li><a href="#ai-section-1">이 블로그가 다루는 문제</a></li>
<li><a href="#ai-section-2">AI Agent·MCP와 업무 자동화</a></li>
<li><a href="#ai-section-3">RAG·STT와 데이터 파이프라인</a></li>
<li><a href="#ai-section-4">SDK·테스트와 릴리스 엔지니어링</a></li>
<li><a href="#ai-section-5">Secure Coding과 보안 운영</a></li>
<li><a href="#ai-section-6">처음 읽는 추천 경로</a></li>
<li><a href="#ai-section-7">작성 원칙</a></li>
<li><a href="#ai-section-8">이 블로그가 다루지 않는 것</a></li>
<li><a href="#ai-section-9">참고 자료</a></li>
</ol>
</blockquote>

## 1. 이 블로그가 다루는 문제

- AI Agent와 MCP를 이용한 업무 자동화
- RAG와 LLM 기반 지식 시스템 설계
- 엔터프라이즈 시스템 연동과 아키텍처
- 프로젝트에서 발생한 문제와 해결 과정
- 개발 도구와 반복 업무 자동화
- 기술 선택의 기준과 트레이드오프

![현장의 업무·데이터·보안·비용 제약을 AI Agent·MCP, RAG·LLM, 기업 시스템 통합, 데이터 품질·보안, 운영·비용, 실패·선택 기준의 여섯 관점으로 분석해 운영 가능한 엔터프라이즈 AI로 연결하는 주제 지도](assets/blog-01-enterprise-ai-topic-map.png)

*이 블로그는 개별 모델이나 도구보다, 현장의 제약을 설계·운영·개선의 전체 흐름으로 연결하는 방법을 다룹니다.*

2026년 8월 기준 **94편**을 다음 일곱 분류로 나눠 두었습니다. 편수는 그 주제를 얼마나 깊게 파고들었는지를 보여줍니다.

| 분류 | 편수 | 다루는 범위 | 시작점 |
|---|---:|---|---|
| 엔터프라이즈 아키텍처 | 30 | Agent 운영·복원력·용량·배포·증거 관리 | [Agentic AI SRE 설계](https://aiarchitect.tistory.com/82) |
| 보안 | 19 | Agent 보안 경계, OWASP Top 10:2025 Secure Coding | [OWASP Top 10:2025로 시작하는 Secure Coding](https://aiarchitect.tistory.com/51) |
| AI Agent · MCP | 14 | MCP·A2A 설계, Tool 계약, 인증, 통합 경계 | [MCP란 무엇인가](https://aiarchitect.tistory.com/2) |
| 개발 도구 · 자동화 | 11 | SDK·테스트·릴리스·업무 자동화 | [생성기를 위한 골든 테스트](https://aiarchitect.tistory.com/49) |
| 기술 인사이트 | 9 | 도입 판단, 인수 기준, 견적, 발주 | [AI 프로젝트 성공 기준 8가지](https://aiarchitect.tistory.com/20) |
| 프로젝트 문제 해결 | 6 | 실제로 막혔던 장애의 진단 순서 | [브라우저 WebRTC가 연결되지 않을 때](https://aiarchitect.tistory.com/6) |
| RAG · LLM 시스템 | 5 | 인덱싱, 청킹, 검색 품질, 멀티테넌트 격리 | [한국어 문서 청킹 전략](https://aiarchitect.tistory.com/32) |

## 2. AI Agent·MCP와 업무 자동화

AI Agent를 실제 업무에 연결할 때는 도구 호출 자체보다 권한, 데이터 범위, 실패 처리와 반복 실행의 안전성이 중요합니다.

- 이슈 트래커의 데이터를 수집해 보고서로 만들려면 [이슈 트래커 업무 자동화 리포팅: MCP 수집·사용자 매핑·범위 검증·민감정보 처리](https://aiarchitect.tistory.com/35)에서 수집 범위와 사용자 매핑부터 확인하세요.
- 팀이 AI 코딩 도구를 공통 규칙 안에서 사용하게 하려면 [AI 코딩 에이전트를 팀 표준에 가두기: 재사용 하네스 플러그인과 3겹 강제 훅](https://aiarchitect.tistory.com/47)이 구현 경계를 설명합니다.
- 에이전트의 취약한 행동을 출시 전후에 계속 검증하려면 [AI Agent Red Teaming과 Continuous Assurance 설계](https://aiarchitect.tistory.com/90)로 이어집니다.

## 3. RAG·STT와 데이터 파이프라인

AI 기능의 품질은 모델보다 입력 데이터가 만들어지고 검증되는 경로에서 먼저 무너지는 경우가 많습니다.

- 음성 인식은 끝났는데 요약 결과가 없을 때는 [STT는 성공했는데 AI 요약은 왜 실패할까: 비동기 파이프라인 장애 진단](https://aiarchitect.tistory.com/17)에서 단계별 상태와 재처리를 점검하세요.
- 문서와 미디어를 받는 입구부터 안전하게 만들려면 [안전한 파일 업로드 설계: Presigned URL·Quarantine·악성 파일과 압축 폭탄](https://aiarchitect.tistory.com/26)이 업로드 격리와 검증 경계를 다룹니다.

## 4. SDK·테스트와 릴리스 엔지니어링

재사용 가능한 AI 기능은 API 한 번 호출하는 예제보다 버전, 계약, 테스트와 배포 게이트가 갖춰져야 제품이 됩니다.

- 호환성을 깨뜨리지 않고 패키지를 배포하려면 [SDK 버전 관리와 배포 자동화: SemVer·호환성 표·패키지·릴리스 게이트](https://aiarchitect.tistory.com/46)를 출발점으로 삼으세요.
- 코드 생성 결과를 안정적으로 검증하려면 [생성기를 위한 골든 테스트: 결정성·정규화와 무의미한 스냅샷 피하기](https://aiarchitect.tistory.com/49)가 테스트 설계를 정리합니다.
- 사용자 화면부터 비공개 API까지 한 흐름으로 연결하려면 [고객 Mobile·Web에서 Server SDK와 Private API까지: End-to-End 통합 예제](https://aiarchitect.tistory.com/52)를 참고하세요.

## 5. Secure Coding과 보안 운영

보안은 마지막 점검표가 아니라 인증, 권한, 입력, 공급망, 로깅과 예외 처리 전반에 걸친 설계 조건입니다.

- 전체 지형은 [OWASP Top 10:2025로 시작하는 Secure Coding: SQL Injection·Brute Force·Log Forging 방어](https://aiarchitect.tistory.com/51)에서 잡을 수 있습니다.
- 권한과 테넌트 경계는 [Broken Access Control Secure Coding: IDOR·권한 우회·Tenant 격리](https://aiarchitect.tistory.com/53), 안전한 기본 설정은 [Security Misconfiguration Secure Coding: CORS·Debug·기본 계정·보안 Header](https://aiarchitect.tistory.com/54)에서 이어집니다.
- 공급망과 비밀 관리는 [Software Supply Chain Secure Coding: 의존성·SBOM·서명·배포 Gate](https://aiarchitect.tistory.com/55)와 [Cryptographic Failures Secure Coding: Password Hash·Token·Key 관리](https://aiarchitect.tistory.com/56)를 함께 보세요.
- 입력 경계와 설계 단계 방어는 [Injection Secure Coding 심화: SQL·NoSQL·Command·Template Injection](https://aiarchitect.tistory.com/57), [Insecure Design Secure Coding: Abuse Case·Rate Limit·업무 흐름 우회](https://aiarchitect.tistory.com/58)가 다룹니다.
- 사용자 인증과 배포 무결성은 [Authentication Failures Secure Coding: Brute Force·MFA·Session](https://aiarchitect.tistory.com/59), [Software or Data Integrity Secure Coding: 역직렬화·Update·Artifact 무결성](https://aiarchitect.tistory.com/60)에서 확인하세요.
- 운영 중 탐지와 실패 안전성은 [Security Logging & Alerting Secure Coding: Log Forging·민감정보·탐지](https://aiarchitect.tistory.com/61), [Exceptional Conditions Secure Coding: Fail Closed·Rollback·안전한 오류 응답](https://aiarchitect.tistory.com/62)으로 마무리합니다.

## 6. 처음 읽는 추천 경로

목적별로 정리한 대표 글 안내는 [무엇부터 읽으면 되는가](https://aiarchitect.tistory.com/notice/98)에 따로 두었습니다. 아래는 구축 순서 중심의 경로입니다.

목표에 따라 다음 순서로 읽으면 맥락을 빠르게 잡을 수 있습니다.

1. **업무 자동화 구축**: 업무 데이터의 범위를 정하고 → 에이전트를 팀 규칙에 묶고 → 지속적인 공격 검증으로 운영합니다.
2. **데이터 파이프라인 운영**: 안전하게 파일을 받고 → 비동기 처리 상태를 관측하고 → 실패 구간을 재처리합니다.
3. **제품화와 배포**: End-to-End 계약을 세우고 → 골든 테스트로 결과를 고정하고 → 호환성 게이트를 통과시킵니다.
4. **보안 체계화**: OWASP 전체 지형을 확인하고 → 가장 위험한 권한·입력 경계를 먼저 막고 → 로깅과 예외 처리로 운영 루프를 닫습니다.

## 7. 작성 원칙

글을 작성할 때는 다음 원칙을 지키겠습니다.

첫째, 동작하는 데모보다 운영 가능한 구조를 우선합니다.

둘째, 특정 제품을 맹목적으로 추천하지 않고 선택 기준과 한계를 함께 설명합니다.

셋째, 고객사와 개인을 식별할 수 있는 정보는 제거하고 재사용 가능한 기술적 교훈만 남깁니다.

넷째, 직접 확인하지 않은 내용은 사실처럼 단정하지 않습니다.

초안 작성에 AI를 어떻게 쓰는지, 코드와 도식을 무엇으로 확인하는지, 오류를 어떻게 정정하는지는 [편집·AI 활용 정책](https://aiarchitect.tistory.com/pages/editorial-policy)에 자세히 적었습니다.

### 핵심 설계 글 빠르게 찾아보기

아키텍처 도입과 구현 순서를 빠르게 확인하려면 다음 글을 이어서 보세요.

- **도입 기준**: [AI 프로젝트 성공 기준 8가지: 모델 정확도 전에 합의할 인수 기준](https://aiarchitect.tistory.com/20)
- **계약과 SDK**: [폴리글랏 보안 계약 검증: Java↔Python Golden Vector와 Canonical Byte](https://aiarchitect.tistory.com/34) · [프라이빗 API를 보호하는 멀티플랫폼 SDK 아키텍처](https://aiarchitect.tistory.com/40) · [고객 Mobile·Web에서 Server SDK와 Private API까지: End-to-End 통합 예제](https://aiarchitect.tistory.com/52)
- **Secure Coding**: [OWASP Top 10:2025로 시작하는 Secure Coding](https://aiarchitect.tistory.com/51) · [Insecure Design: Abuse Case·Rate Limit·업무 흐름 우회](https://aiarchitect.tistory.com/58) · [Exceptional Conditions: Fail Closed·Rollback·안전한 오류 응답](https://aiarchitect.tistory.com/62)
- **데이터 파이프라인**: [음성에서 인사이트까지: 실시간 STT·RAG로 만드는 실제 데이터 파이프라인](https://aiarchitect.tistory.com/67)

AI 시스템 도입을 검토하는 기업 담당자와 실제 구현을 책임지는 개발자 모두에게 도움이 되는 기록을 만들어가겠습니다.

## 8. 이 블로그가 다루지 않는 것

무엇을 쓰지 않는지도 밝혀 두는 편이 읽는 분의 시간을 아낍니다. 다음 주제는 의도적으로 다루지 않습니다.

| 다루지 않는 것 | 이유 |
|---|---|
| 모델 학습·파인튜닝·양자화 | 제 경험은 모델을 만드는 쪽이 아니라 **만들어진 모델을 업무 시스템에 안전하게 붙이는 쪽**에 있습니다 |
| 모델·벤더 성능 벤치마크 비교 | 버전마다 결과가 바뀌고 제 환경에서 재현을 보장할 수 없습니다. 대신 **선택 기준과 교체 가능한 구조**를 다룹니다 |
| 프롬프트 작성 요령 모음 | 프롬프트는 바뀌지만 권한·검증·실패 처리 경계는 남습니다. 후자에 집중합니다 |
| 논문 리뷰 | 연구 동향보다 **운영에서 무엇이 깨지는가**를 다룹니다 |
| 특정 회사의 실제 구성과 수치 | 익명 운영 원칙에 따라 고객사·제품명·내부 수치를 쓰지 않습니다. 예시는 합성이며 본문에 그렇게 표시합니다 |

그래서 이 블로그의 글은 대부분 **"어느 경계에 무엇을 둘 것인가"**와 **"틀렸을 때 무엇이 남는가"**를 묻는 형태입니다.

## 9. 참고 자료

이 블로그의 설계 논의는 다음 공개 표준과 지침을 기준으로 삼습니다. 각 글에서도 해당하는 절을 다시 인용합니다.

- [Model Context Protocol — Specification](https://modelcontextprotocol.io/specification/latest) · Tool·Resource·Prompt 선언과 전송 계층
- [A2A Protocol](https://a2a-protocol.org/latest/) · Agent Card·Task·Artifact와 Agent 간 위임
- [OWASP Top 10](https://owasp.org/Top10/) · Secure Coding 시리즈의 분류 기준
- [NIST AI Risk Management Framework](https://airc.nist.gov/AI_RMF_Knowledge_Base/AI_RMF) · 위험 식별·측정·관리 용어
- [Google Search — Creating helpful, reliable, people-first content](https://developers.google.com/search/docs/fundamentals/creating-helpful-content) · 글의 목적·출처·제작 방식 공개 기준
