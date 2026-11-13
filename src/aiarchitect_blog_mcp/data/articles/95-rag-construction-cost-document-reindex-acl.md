# RAG 구축 비용 산정: 문서 전처리·재색인·권한 설계가 비용을 바꾸는 이유

RAG 구축 비용을 물으면 사용자 수와 문서 수부터 묻는 경우가 많습니다. 필요한 입력이지만 두 숫자만으로는 부족합니다. 같은 문서 1만 건이라도 텍스트가 깨끗한 문서 파일인지, 표와 이미지가 섞인 스캔 PDF인지에 따라 처리 과정이 달라집니다. 문서가 매일 바뀌는지, 부서마다 접근 권한이 다른지, 변경할 때마다 품질을 다시 증명해야 하는지도 비용을 바꿉니다.

이 글은 특정 금액표를 제시하지 않습니다. 대신 RAG 구축 비용을 **문서 수가 아니라 처리 단위와 반복 빈도로 계산하는 방법**을 설명합니다. 견적 전에 어떤 수량을 세야 하는지, PoC와 운영의 범위를 어디서 나눠야 하는지, 서로 다른 업체의 제안을 같은 기준으로 비교하려면 무엇을 적어야 하는지가 핵심입니다.

![기업 RAG 구축에서 문서 처리, 청킹과 임베딩, 재색인, 권한 동기화, 벡터 저장과 평가가 각각 비용을 만드는 구조](assets/blog-95-rag-cost-drivers-hero.png)

<blockquote id="aiarchitect-toc" data-ke-style="box" style="background-color: #f6f9fc; color: #263746; font-family: Pretendard-Regular, AppleSDGothicNeo-Regular, sans-serif; font-weight: 400;" data-mce-style="background-color: #f6f9fc; color: #263746; font-family: Pretendard-Regular, AppleSDGothicNeo-Regular, sans-serif; font-weight: 400;">
<p style="color: #263746; font-weight: 700;" data-mce-style="color: #263746; font-family: Pretendard-Regular, AppleSDGothicNeo-Regular, sans-serif; font-weight: 700;"><b>목차</b></p>
<ol style="list-style-type: decimal; color: #555555; font-weight: 400;" data-mce-style="list-style-type: decimal; color: #555555; font-weight: 400;" data-ke-list-type="decimal">
<li><a href="#ai-section-1" style="color: #0070d1; text-decoration: underline; text-underline-offset: 2px;">RAG 비용은 문서에서 시작해 반복 작업에서 커진다</a></li>
<li><a href="#ai-section-2" style="color: #0070d1; text-decoration: underline; text-underline-offset: 2px;">견적 전에 문서 재고를 숫자로 만든다</a></li>
<li><a href="#ai-section-3" style="color: #0070d1; text-decoration: underline; text-underline-offset: 2px;">문서 형식과 품질이 전처리 원가를 바꾼다</a></li>
<li><a href="#ai-section-4" style="color: #0070d1; text-decoration: underline; text-underline-offset: 2px;">청킹과 임베딩은 파일이 아니라 Chunk 수로 계산한다</a></li>
<li><a href="#ai-section-5" style="color: #0070d1; text-decoration: underline; text-underline-offset: 2px;">재색인 비용은 변경률과 영향 범위가 결정한다</a></li>
<li><a href="#ai-section-6" style="color: #0070d1; text-decoration: underline; text-underline-offset: 2px;">벡터 저장소는 용량과 검색 경로를 함께 산정한다</a></li>
<li><a href="#ai-section-7" style="color: #0070d1; text-decoration: underline; text-underline-offset: 2px;">문서 단위 권한은 저장뿐 아니라 동기화 비용을 만든다</a></li>
<li><a href="#ai-section-8" style="color: #0070d1; text-decoration: underline; text-underline-offset: 2px;">평가셋은 선택 항목이 아니라 품질을 증명하는 원가다</a></li>
<li><a href="#ai-section-9" style="color: #0070d1; text-decoration: underline; text-underline-offset: 2px;">질문 한 건의 운영비를 실행 경로로 나눈다</a></li>
<li><a href="#ai-section-10" style="color: #0070d1; text-decoration: underline; text-underline-offset: 2px;">PoC·Pilot·운영은 서로 다른 범위로 견적한다</a></li>
<li><a href="#ai-section-11" style="color: #0070d1; text-decoration: underline; text-underline-offset: 2px;">예산이 제한되면 품질 기준이 아니라 범위를 줄인다</a></li>
<li><a href="#ai-section-12" style="color: #0070d1; text-decoration: underline; text-underline-offset: 2px;">견적 입력표를 채워 같은 조건으로 비교한다</a></li>
<li><a href="#ai-section-13" style="color: #0070d1; text-decoration: underline; text-underline-offset: 2px;">제안서에서 비용 경계를 확인한다</a></li>
<li><a href="#ai-section-14" style="color: #0070d1; text-decoration: underline; text-underline-offset: 2px;">마무리</a></li>
</ol>
</blockquote>

<a id="ai-section-1"></a>

## 1. RAG 비용은 문서에서 시작해 반복 작업에서 커진다

일반 AI 프로젝트 견적에는 기획, 화면, 시스템 통합, 보안, 인프라, 운영 인수처럼 RAG가 아니어도 필요한 항목이 포함됩니다. 이 전체 구조는 [AI 프로젝트 견적 10개 산정 항목](https://aiarchitect.tistory.com/21)에서 다뤘습니다. 이 글에서는 그중 RAG에만 생기는 비용을 분리합니다.

RAG 비용은 다음 두 묶음으로 나누면 빠진 항목이 보입니다.

| 구분 | RAG 고유 작업 | 주된 산정 단위 |
|---|---|---|
| 최초 구축 | 문서 실사·추출·정제 | 형식별 문서·페이지·처리 시간 |
| 최초 구축 | 청킹·임베딩·초기 색인 | Chunk 수·입력 Token·Index Record |
| 최초 구축 | 권한 모델 연결 | 원천 시스템·권한 유형·시험 Case |
| 최초 구축 | 평가셋과 인수 시험 | 질문·정답 근거·오류 유형 |
| 반복 운영 | 변경·삭제·권한 회수 반영 | 월 변경 문서·영향 Chunk·동기화 주기 |
| 반복 운영 | 검색·재순위화·생성 | 질문 수·실행 경로·검색 범위 |
| 반복 운영 | 회귀 평가·관측 | 변경 횟수·평가 Case·보존 기간 |

따라서 일정 기간의 RAG 비용은 다음 관계로 봅니다.

**RAG 총비용 = 최초 문서 처리·색인·권한·평가 비용 + 기간 중 재처리·검색·저장·평가·운영 비용**

각 항목은 다시 **수량 × 단위 작업 × 빈도**로 풀어야 합니다. 단위 가격부터 묻기 전에 수량과 반복 조건을 고정해야 업체 간 견적을 비교할 수 있습니다.

![RAG 비용을 최초 구축비와 반복 운영비로 나누고 수량, 단위 작업, 빈도를 하나의 기준선으로 연결한 도식](assets/blog-95-rag-cost-model.png)

<a id="ai-section-2"></a>

## 2. 견적 전에 문서 재고를 숫자로 만든다

문서 수는 시작점일 뿐입니다. 견적에 쓸 문서 재고는 **어디에 있고, 어떤 형식이며, 얼마나 바뀌고, 누가 볼 수 있는지**까지 포함해야 합니다.

먼저 원천별로 다음 항목을 셉니다.

| 항목 | 확인할 값 | 비용과 연결되는 이유 |
|---|---|---|
| 원천 시스템 | 파일 서버·업무 시스템·게시판·메일 등 | Connector와 인증 방식이 달라짐 |
| 문서량 | 파일 수·페이지 수·총 Byte | 추출·전송·초기 색인의 기준 |
| 형식 | 문서 파일·PDF·스캔·표·이미지·첨부 | 처리 Pipeline과 검수 방식이 달라짐 |
| 언어 | 한국어·영어·혼합·특수 용어 | 추출·청킹·평가 표본이 달라짐 |
| 변경 | 월 신규·수정·삭제 비율 | 반복 처리량의 기준 |
| 권한 | 공개·부서·프로젝트·개인·예외 | ACL Metadata와 동기화 방식이 달라짐 |
| 최신성 | 변경 후 허용 반영 시간 | Batch 주기와 처리 용량을 결정 |
| 보존 | 원문·Chunk·질문·답변·Log 기간 | Storage와 삭제 절차를 결정 |

전체를 처음부터 정밀 조사할 필요는 없습니다. 형식과 권한 조합별로 대표 표본을 뽑아 실제 처리 시간을 잰 뒤 전체 분포에 적용합니다. 다만 쉬운 문서만 표본으로 고르면 결과가 왜곡됩니다. 스캔 상태가 나쁜 PDF, 셀이 병합된 표, 이미지 안에 핵심 내용이 있는 문서, 권한 예외가 있는 문서를 의도적으로 포함해야 합니다.

문서 재고표의 목적은 숫자를 크게 만드는 것이 아닙니다. **자동 처리 가능한 범위와 사람의 검수가 필요한 범위를 분리하는 것**입니다.

<a id="ai-section-3"></a>

## 3. 문서 형식과 품질이 전처리 원가를 바꾼다

텍스트가 들어 있는 PDF와 종이를 스캔한 PDF는 확장자가 같아도 다른 작업입니다. 전자는 본문을 바로 추출할 수 있지만, 후자는 OCR과 회전·기울기 보정, 표 구조 복원이 필요할 수 있습니다. 이미지가 많은 문서에서는 캡션과 본문의 관계를 보존해야 하고, 스프레드시트는 시트·행·열의 위치를 출처로 되짚을 수 있어야 합니다.

문서 표본을 다음 네 등급으로 나누면 전처리 견적이 명확해집니다.

| 처리 등급 | 대표 조건 | 필요한 작업 |
|---|---|---|
| A | 깨끗한 Text 문서, 일관된 제목 구조 | 추출·정규화·기본 검수 |
| B | 표·각주·다단 편집이 섞인 PDF | Layout 보존·표 처리·출처 위치 검수 |
| C | 스캔·이미지 중심 문서 | OCR·회전 보정·인식 품질 검수 |
| D | 암호화·손상·오래된 형식·복합 첨부 | 예외 처리·수동 전환·재처리 |

[Amazon Textract의 표 추출 문서](https://docs.aws.amazon.com/textract/latest/dg/how-it-works-tables.html)처럼 공식 문서 추출 서비스도 단순 문자 탐지와 표·양식 분석을 별도 기능으로 구분합니다. 이는 제품을 반드시 사용해야 한다는 뜻이 아니라, **표와 구조를 보존하는 작업이 일반 텍스트 추출과 같은 단위가 아니라는 근거**입니다.

전처리 비용은 `문서 건수 × 평균 단가` 하나로 계산하지 않습니다. 최소한 **등급별 문서 또는 페이지 수 × 자동 처리 단위 비용 + 표본 검수 시간 + 예외 문서의 수동 처리 시간**으로 나눕니다.

여기서 검수율도 정해야 합니다. 전건 검수가 필요한 규제 문서와 표본 검수로 충분한 사내 FAQ를 같은 조건으로 계산하면 안 됩니다. 오류가 답변 위험으로 이어지는 정도에 따라 검수 범위를 정합니다.

<a id="ai-section-4"></a>

## 4. 청킹과 임베딩은 파일이 아니라 Chunk 수로 계산한다

벡터 색인에 들어가는 단위는 파일이 아니라 대개 Chunk입니다. 파일 한 건이 몇 개의 Chunk로 나뉘는지에 따라 임베딩 호출량, Index Record 수, Metadata 용량, 재색인 범위가 함께 바뀝니다.

초기 산정에는 다음 값이 필요합니다.

- 형식별 평균 추출 문자 또는 Token 수
- Chunk 목표 길이와 중첩 범위
- 제목·표·문단 경계를 보존하는 분할 규칙
- 하나의 원문에서 생성되는 평균·상위 Chunk 수
- Chunk마다 저장하는 출처·권한·버전 Metadata 크기
- 사용할 Embedding Model의 입력 과금 단위와 Vector 차원

`평균 Chunk 수 × 파일 수`만 쓰지 말고 상위 구간도 봐야 합니다. 긴 규정집 몇 권이 전체 Chunk의 큰 비중을 차지할 수 있기 때문입니다. 먼저 형식별 표본을 실제 Pipeline에 통과시켜 **원문 → 추출 결과 → Chunk → Embedding 입력 Token → Index Record**의 수를 계측합니다.

한국어가 항상 더 비싸다고 단정할 수는 없습니다. 토큰 수는 선택한 Tokenizer와 문서 내용에 따라 달라지고, Embedding 비용은 제품에 따라 Token·문자·호출·Compute 시간 등 다른 단위를 사용할 수 있습니다. 예를 들어 [OpenAI Embedding 공식 문서](https://developers.openai.com/api/docs/guides/embeddings)는 사용량을 입력 Token으로 표시하고 Vector 차원을 별도 Parameter로 조정하지만, 이 방식을 다른 제품에 그대로 적용할 수는 없습니다. 한국어·영어·혼합 문서 표본을 실제 후보 모델로 계측한 값을 사용해야 합니다.

Chunk를 작게 만들면 무조건 좋은 것도 아닙니다. Record가 늘어 저장·쓰기·검색 범위가 커질 수 있고, 지나치게 크면 필요한 근거를 정밀하게 찾기 어려워질 수 있습니다. [한국어 문서 청킹 설계](https://aiarchitect.tistory.com/32)처럼 품질 실험과 비용 계산을 같은 표본에서 수행해야 합니다.

<a id="ai-section-5"></a>

## 5. 재색인 비용은 변경률과 영향 범위가 결정한다

초기 색인은 한 번이지만 문서는 계속 바뀝니다. 운영비에서 중요한 것은 전체 문서량보다 **한 주기마다 무엇을 다시 처리하는가**입니다.

재처리량은 다음 관계로 계산할 수 있습니다.

**주기별 재처리 Chunk = 변경 문서 수 × 문서당 영향 Chunk + 삭제·권한 변경으로 다시 쓰거나 제거할 Record**

문서 일부가 바뀌었는데 전체 문서를 다시 청킹하는지, 바뀐 구간만 처리하는지에 따라 영향 범위가 달라집니다. Embedding Model이나 Chunk Schema를 바꾸면 전체 Corpus를 다시 색인해야 할 수도 있습니다. 이 작업은 평소 운영비가 아니라 별도 사건 비용으로 잡는 편이 명확합니다.

반드시 구분할 변경은 다음과 같습니다.

| 변경 유형 | 가능한 처리 범위 | 확인할 조건 |
|---|---|---|
| 새 문서 | 신규 문서와 Chunk 추가 | 중복 입력 방지 |
| 본문 수정 | 변경 문서 또는 변경 구간 재처리 | 기존 Chunk 제거·교체 방식 |
| 문서 삭제 | 관련 Chunk 전부 삭제 | 원천 삭제 탐지와 전파 시간 |
| 권한 변경 | ACL Metadata 갱신 또는 재색인 | 권한 회수 반영 목표 |
| Chunk 규칙 변경 | 일부 또는 전체 재색인 | Index Version 전환 방식 |
| Embedding Model 변경 | 대개 새 Vector 생성 | 병행 Index와 Rollback 공간 |

증분 색인을 지원하는 제품도 원천의 변경 탐지 방식과 삭제 정책에 따라 동작이 다릅니다. [Azure AI Search의 Indexer 문서](https://learn.microsoft.com/en-us/azure/search/search-how-to-create-indexers)와 [변경·삭제 탐지 문서](https://learn.microsoft.com/en-us/azure/search/search-how-to-index-azure-blob-changed-deleted)를 보면, 변경은 자동으로 감지해도 삭제는 Soft Delete 같은 별도 정책이 필요할 수 있습니다. 그러므로 견적에는 "증분 색인 지원" 한 줄이 아니라 **신규·수정·삭제·권한 회수 각각의 탐지 방식과 재처리 단위**가 들어가야 합니다.

같은 문서를 다시 넣어도 중복 Chunk가 쌓이지 않게 하는 방법은 [RAG 멱등 인덱싱과 중복 Chunk 방지](https://aiarchitect.tistory.com/9)에서 자세히 다뤘습니다.

<a id="ai-section-6"></a>

## 6. 벡터 저장소는 용량과 검색 경로를 함께 산정한다

Vector의 개수만으로 저장소 비용을 계산하면 Metadata를 놓칩니다. 기업 RAG의 Record에는 Vector 외에도 원문 ID, Chunk ID, 문서 버전, 출처 위치, Tenant, 권한 주체, 보존 상태가 들어갈 수 있습니다.

원시 데이터 크기의 기준선은 다음처럼 잡을 수 있습니다.

**예상 Record 크기 = ID + Metadata + Vector 차원 × 차원당 저장 Byte**

**예상 원시 Index 크기 = Record 수 × 평균 Record 크기**

실제 청구 용량은 제품의 Index 구조, 복제본, 압축, 여유 용량, Backup에 따라 달라질 수 있으므로 이 식은 최종 가격이 아니라 후보 제품에 같은 입력을 주기 위한 기준선입니다.

검색 비용도 배포 방식에 따라 다릅니다.

- 사용량 기반 서비스: 읽기·쓰기·저장·전송량을 각각 계측할 수 있음
- Provisioned 방식: 최소 Node·Partition·Replica와 최대 처리량을 함께 봐야 함
- 자체 운영: Compute뿐 아니라 Upgrade·Backup·장애 대응 인력이 필요함
- Tenant별 Index 분리: 격리는 강해질 수 있지만 작은 Index가 많이 생기는 운영 부담이 있음
- 공유 Index와 Metadata Filter: 자원 효율은 높을 수 있지만 권한 Filter와 부하 격리 검증이 필요함

후보마다 과금 단위가 다르므로 특정 업체의 단가를 전체 시장의 기준처럼 쓰면 안 됩니다. 동일한 **Record 수·평균 Metadata 크기·Vector 차원·월 Query 수·검색 범위·복제 조건**을 주고 견적을 받아야 합니다.

<a id="ai-section-7"></a>

## 7. 문서 단위 권한은 저장뿐 아니라 동기화 비용을 만든다

문서 단위 권한을 넣으면 Metadata가 늘어납니다. 실무에서 놓치기 쉬운 것은 Byte보다 **원천 권한을 가져오고, Chunk에 투영하고, 바뀐 권한을 제때 반영하고, 실제로 차단되는지 시험하는 작업**입니다.

권한 연결에는 다음 작업이 포함될 수 있습니다.

1. 원천 시스템의 사용자·그룹·역할 식별자 해석
2. 문서 ACL을 Chunk Metadata로 상속하거나 별도 정책 저장소와 연결
3. 로그인 사용자의 현재 권한을 Query Filter로 변환
4. 부서 이동·프로젝트 종료·개별 예외의 변경 탐지
5. 권한 회수 후 Index와 Cache에 남은 정보 제거
6. 허용 계정과 차단 계정으로 같은 질문을 실행하는 회귀 시험

[Azure AI Search의 문서 수준 접근 통제 개요](https://learn.microsoft.com/en-us/azure/search/search-document-level-access-overview)에서도 권한 Metadata를 색인하고 Query 시 사용자·그룹 정보와 대조하는 구조를 설명합니다. 일부 제품의 Native ACL 기능은 Preview이거나 원천별 제약이 있을 수 있으므로 기능 이름만 보고 공수를 0으로 잡아서는 안 됩니다. 선택한 데이터 원천과 Identity 체계에서 지원 수준을 확인해야 합니다.

견적 입력에는 **권한 유형 수, 문서당 평균·상위 ACL 항목 수, 사용자·그룹 수, 월 권한 변경 수, 권한 회수 반영 목표 시간, 차단 시험 Case 수**를 넣습니다. 개인별 ACL이 지나치게 많다면 Group 중심으로 단순화할 수 있는지도 함께 검토합니다.

권한 없는 문서가 모델 입력에 들어가기 전에 차단되어야 한다는 설계 원칙과 격리 패턴은 [멀티테넌트 RAG 보안](https://aiarchitect.tistory.com/25)에 정리했습니다.

<a id="ai-section-8"></a>

## 8. 평가셋은 선택 항목이 아니라 품질을 증명하는 원가다

RAG를 구축했다는 말은 검색 화면이 열렸다는 뜻이 아닙니다. 우리 문서에서 필요한 근거를 찾고, 답변이 그 근거에 맞으며, 권한과 최신성을 지킨다는 사실을 검증해야 합니다.

평가 비용은 다음 세 층으로 나눕니다.

| 평가 층 | 묻는 질문 | 필요한 자료 |
|---|---|---|
| 추출 | 원문의 핵심 내용과 구조가 보존됐는가 | 문서 표본·기대 추출 결과·검수 기준 |
| 검색 | 질문에 필요한 문서와 Chunk를 가져왔는가 | 질문·관련 문서 또는 Chunk 판정 |
| 답변 | 답이 근거에 부합하고 필요한 내용을 담았는가 | 질문·근거·기대 핵심·금지 오류 |

평가셋 구축비에는 현업 담당자의 시간이 들어갑니다. 질문만 모으는 것으로 끝나지 않고 정답 근거 위치, 허용 가능한 표현, 치명적 오류, 판정자와 이견 처리 절차를 정해야 합니다.

반복 평가량도 계산해야 합니다.

**평가 실행량 = 평가 Case 수 × 비교할 검색·Chunk·Model 구성 수 × 변경 또는 Release 횟수**

자동 평가를 사용해도 표본 사람 검토와 평가 기준의 Calibration이 필요합니다. [Microsoft Foundry의 RAG Evaluator 문서](https://learn.microsoft.com/en-us/azure/foundry/concepts/evaluation-evaluators/rag-evaluators)도 문서 검색 품질과 최종 답변의 Groundedness를 별도 평가 항목으로 구분합니다. 운영 Trace를 검토된 Dataset과 회귀 Gate로 연결하는 방법은 [AI Agent 평가와 회귀 Release Gate](https://aiarchitect.tistory.com/74)를 참고할 수 있습니다.

평가셋을 빼면 견적은 내려갑니다. 대신 품질이 좋아졌는지, 변경 뒤 나빠졌는지, 인수할 수 있는지를 판정할 수 없게 됩니다. 그러므로 평가를 없애기보다 **업무 위험과 대표 오류를 덮는 최소 평가 범위**를 먼저 합의해야 합니다.

<a id="ai-section-9"></a>

## 9. 질문 한 건의 운영비를 실행 경로로 나눈다

사용자 질문 한 건이 곧 모델 호출 한 번은 아닙니다. RAG 질문은 Query Embedding, 검색, Metadata Filter, 재순위화, Context 조립, 생성, 출처 검증을 거칠 수 있습니다. 복합 질문은 검색을 여러 번 실행하거나 실패 뒤 대체 경로를 사용할 수 있습니다.

질문 한 건의 비용 기준선은 다음 실행 경로로 나눕니다.

| 실행 단계 | 수량 입력 | 비용 또는 용량 입력 |
|---|---|---|
| Query 처리 | 질문 수·평균 입력 길이 | Embedding·Rewrite 호출 또는 Compute |
| 검색 | 검색 횟수·대상 Index·Top-K | Read·Node·Replica·Latency 용량 |
| 재순위화 | 적용 비율·후보 문서 수 | 요청·Token·Compute |
| Context | 전달 Chunk 수·평균 길이 | 생성 Model 입력 Token |
| 답변 | 출력 길이·재시도율 | 생성 Model 출력 Token·Compute |
| 기록 | Trace·질문·답변·근거 보존량 | Log Storage·Masking·보존 기간 |

평균 하나만 쓰지 말고 최소한 단순 질문과 복합 질문을 나눕니다. 운영 전에는 표본 Traffic Replay로 실행 횟수와 Token을 계측하고, 운영 후에는 실제 분포로 갱신합니다.

Cache는 비용을 줄일 수 있지만 권한과 최신성 조건이 Key에 들어가야 합니다. 다른 사용자의 결과를 재사용하거나 바뀐 문서의 답을 오래 유지하면 비용 절감이 권한·품질 사고로 바뀝니다. Cache 적중률뿐 아니라 무효화 조건을 견적 범위에 포함합니다.

<a id="ai-section-10"></a>

## 10. PoC·Pilot·운영은 서로 다른 범위로 견적한다

PoC는 운영 시스템의 할인판이 아닙니다. 기술적으로 가능한지 확인하는 단계와 실제 조직의 권한·변경·부하를 확인하는 단계, 지속 운영 책임을 인수하는 단계는 질문이 다릅니다.

| 단계 | 답해야 할 질문 | 최소 포함 범위 | 다음 단계로 넘길 것 |
|---|---|---|---|
| PoC | 대표 문서에서 검색과 답변이 가능한가 | 대표 형식 표본·핵심 질문·오류 유형·종료 기준 | 전체 연동·고가용성·전사 권한 |
| Pilot | 실제 사용자와 권한·갱신 조건에서 작동하는가 | 실제 Identity·증분 색인·삭제·제한 사용자·비용 계측 | 전사 확장·재해 복구·상시 지원 |
| 운영 | 합의한 품질·보안·가용성을 지속할 수 있는가 | 전체 범위·관측·장애 대응·Backup·이관·지속 평가 | 계약에서 명시한 제외 항목 |

![PoC에서 대표 문서와 검색 품질을 확인하고 Pilot에서 실제 권한과 증분 갱신을 검증한 뒤 운영 범위로 확장하는 단계별 Gate](assets/blog-95-phase-scope-gates.png)

PoC 견적이 낮은 이유는 같은 운영 시스템을 싸게 제공해서가 아니라 범위를 의도적으로 미뤘기 때문입니다. 무엇을 미뤘는지 적지 않으면 PoC 뒤의 본 구축 견적이 갑자기 커진 것처럼 보입니다.

각 단계에는 종료 조건이 필요합니다. PoC에서 검색 품질과 실패 범위를 확인하지 못하면 Pilot으로 가지 않고, Pilot에서 권한 회수·삭제·변경 반영과 비용 증가 곡선을 확인하지 못하면 운영 범위를 확정하지 않습니다. 측정 가능한 인수 문장을 만드는 방법은 [AI 프로젝트 성공 기준과 인수 Gate](https://aiarchitect.tistory.com/20)를 참고하십시오.

<a id="ai-section-11"></a>

## 11. 예산이 제한되면 품질 기준이 아니라 범위를 줄인다

예산을 맞추기 위해 평가나 권한 통제를 빼면 작은 데모는 만들 수 있어도 운영 여부를 판정하기 어렵습니다. 먼저 사용자·문서·업무 범위를 줄이고, 남은 범위 안에서는 품질·권한·삭제 기준을 유지하는 편이 낫습니다.

| 범위 유형 | 포함할 것 | 뒤로 미룰 것 | 적합한 목적 |
|---|---|---|---|
| 제한 검증 | 한 업무·대표 문서·단순 권한·핵심 평가 | 전체 원천·복합 권한·전사 배포 | 가능성과 주요 실패 원인 확인 |
| 운영 Pilot | 실제 원천 일부·실사용자·증분 갱신·권한·회귀 평가 | 전사 확장·다지역·상시 지원 | 운영 조건과 증가 곡선 확인 |
| 고위험 운영 | 전체 권한·감사·엄격한 평가·Rollback·장애 대응 | 계약상 명시한 비핵심 기능 | 규제·민감 정보·업무 영향이 큰 사용 |

비용을 줄일 때 검토할 순서는 다음과 같습니다.

1. 대상 업무를 한두 개로 제한합니다.
2. 실제 가치가 높은 문서 원천부터 연결합니다.
3. 형식별 대표성을 유지하면서 문서 수를 줄입니다.
4. 최신성 목표를 업무가 허용하는 범위에서 완화합니다.
5. 전체 평가셋을 핵심 오류 중심의 최소 세트로 시작합니다.
6. 품질과 권한 기준을 통과한 뒤 사용자와 원천을 늘립니다.

이렇게 하면 줄인 범위와 남긴 위험이 보입니다. 반대로 "RAG 전체"를 작은 고정 금액에 맞추면 어느 항목이 빠졌는지 알기 어렵습니다.

<a id="ai-section-12"></a>

## 12. 견적 입력표를 채워 같은 조건으로 비교한다

업체마다 다른 질문을 받으면 총액을 비교할 수 없습니다. 아래 입력표를 먼저 채우고 모든 후보에게 같은 값을 전달합니다. 모르는 값은 비워 두지 말고 `미측정`으로 표시해 Discovery 항목으로 견적받습니다.

| 영역 | 입력값 | 현재 값 | 산정·확인 방법 |
|---|---|---|---|
| 문서 | 원천 시스템 수 | | 시스템 목록과 인증 방식 확인 |
| 문서 | 형식별 파일·페이지·Byte | | 표본과 전체 재고 집계 |
| 문서 | A·B·C·D 처리 등급 비율 | | 형식별 대표 표본 시험 |
| 변경 | 월 신규·수정·삭제 문서 수 | | 원천 Audit 또는 변경 이력 |
| 최신성 | 변경 후 반영 목표 | | 업무 위험과 운영 시간 기준 |
| Chunk | 문서당 평균·상위 Chunk 수 | | 표본 Pipeline 실행 |
| Embedding | 입력 Token·Vector 차원 | | 후보 모델별 표본 계측 |
| Index | Record 수·Metadata Byte·복제 | | Schema와 용량 계산 |
| 권한 | 권한 유형·ACL 크기·월 변경 수 | | Identity·문서 권한 표본 |
| 평가 | 질문·근거·오류 유형 수 | | 현업 질문과 인수 기준 작성 |
| 사용 | 월 질문·복합 경로·Peak 동시성 | | 기존 문의량 또는 Pilot 관측 |
| 운영 | Log 보존·Backup·복구 목표 | | 보안·운영 정책 확인 |

이 표에서 가장 중요한 열은 `현재 값`보다 `산정·확인 방법`입니다. 숫자의 출처가 없으면 계약 후 실제 값이 달라졌을 때 누구의 가정이 틀렸는지 판단하기 어렵습니다.

견적서에는 각 비용 항목이 어떤 입력값과 연결되는지 표시하게 합니다. 예를 들어 `초기 색인`이라는 한 줄보다 **대상 문서 등급·예상 Chunk 수·Embedding Model·전체 또는 증분 처리 범위·실패 재처리 포함 여부**가 보여야 합니다.

<a id="ai-section-13"></a>

## 13. 제안서에서 비용 경계를 확인한다

총액보다 먼저 포함·제외 조건을 확인합니다. 특히 다음 질문에 답이 있어야 합니다.

- 표본 조사 뒤 문서 난도가 예상보다 높으면 어떤 단가나 범위가 바뀌는가
- OCR·표 복원·예외 문서의 수동 처리는 어디까지 포함되는가
- 전체 재색인과 증분 재색인의 비용·시간은 각각 어떻게 계산하는가
- 삭제와 권한 회수의 반영 목표를 지키기 위한 용량이 포함됐는가
- Vector DB의 저장·읽기·쓰기·Backup·전송 비용은 누가 부담하는가
- 평가셋 작성과 현업 검수 시간은 누구의 역할인가
- Model·Chunk 규칙·Schema 변경 뒤 회귀 평가가 포함되는가
- PoC에서 운영으로 갈 때 재사용되는 산출물과 다시 만드는 항목은 무엇인가
- 계약 종료 시 문서·Index·평가셋·운영 기록을 어떤 형식으로 인수하는가

업체를 비교할 때는 이 글의 입력표로 비용 기준을 맞추고, [RAG 구축 업체 선정 8가지 질문](https://aiarchitect.tistory.com/94)의 증빙·시험 기준으로 답변을 검증하십시오. BLOG-95가 **얼마나 필요한가**를 계산한다면 BLOG-94는 **그 범위를 실제로 수행할 수 있는가**를 확인합니다.

가격이 낮은 제안이 틀렸다는 뜻은 아닙니다. 표본 문서가 깨끗하고 변경이 드물며 권한이 단순하고 기존 Platform을 재사용할 수 있다면 합리적으로 낮아질 수 있습니다. 확인할 것은 숫자의 크기가 아니라 **같은 범위를 계산했는가**입니다.

<a id="ai-section-14"></a>

## 14. 마무리

RAG 구축 비용은 모델 가격표보다 앞에서 결정됩니다. 어떤 문서를 얼마나 손봐야 하는지, 파일이 몇 개의 Chunk가 되는지, 무엇이 바뀔 때 어디까지 다시 처리하는지, 권한 회수가 언제 반영되어야 하는지, 품질을 어떤 평가셋으로 다시 증명할지가 원가 구조를 만듭니다.

견적을 받을 때 총액부터 비교하지 마십시오. 문서 재고와 처리 등급을 만들고, 변경률·권한·평가·사용량을 같은 입력표에 적고, PoC·Pilot·운영의 종료 조건을 분리하십시오. 그러면 낮은 견적에서 빠진 범위와 높은 견적에 포함된 책임을 구별할 수 있습니다.

> RAG 구축 비용을 산정하기 전에 문서·권한·재색인·평가 범위를 같은 기준표로 정리하고 싶다면, 현재 보유한 자료에서 측정 가능한 입력값과 미측정 위험을 함께 구분할 수 있습니다.
> [크몽에서 RAG 구축 범위·견적 입력값 상담하기](https://kmong.com/gig/798627)

> 함께 읽으면 좋은 글: [AI 프로젝트 견적 10개 산정 항목](https://aiarchitect.tistory.com/21), [RAG 구축 업체 선정 8가지 질문](https://aiarchitect.tistory.com/94), [RAG 멱등 인덱싱](https://aiarchitect.tistory.com/9).

### 참고 자료

- [Amazon Textract: Tables](https://docs.aws.amazon.com/textract/latest/dg/how-it-works-tables.html)
- [Azure AI Search: Create an Indexer](https://learn.microsoft.com/en-us/azure/search/search-how-to-create-indexers)
- [Azure AI Search: Change and Delete Detection for Azure Storage](https://learn.microsoft.com/en-us/azure/search/search-how-to-index-azure-blob-changed-deleted)
- [Azure AI Search: Document-Level Access Control](https://learn.microsoft.com/en-us/azure/search/search-document-level-access-overview)
- [Microsoft Foundry: RAG Evaluators](https://learn.microsoft.com/en-us/azure/foundry/concepts/evaluation-evaluators/rag-evaluators)
- [OpenAI API: Vector Embeddings](https://developers.openai.com/api/docs/guides/embeddings)
