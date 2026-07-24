import os
import glob
import time
from dotenv import load_dotenv
from langchain_community.document_loaders import PyPDFLoader
import re
from langchain_core.documents import Document
from langchain_text_splitters import (
    CharacterTextSplitter,
    RecursiveCharacterTextSplitter
)

def split_documents_by_clause(documents):
    clause_documents = []
    # KORA 규정/내규의 조항 '제 X 조' 형태 분할 정규식
    pattern = r"\n(?=\s*제\s*\d+\s*조)"
    for doc in documents:
        text = doc.page_content
        metadata = doc.metadata.copy()
        parts = re.split(pattern, text)
        for part in parts:
            part_content = part.strip()
            if part_content:
                clause_documents.append(Document(page_content=part_content, metadata=metadata))
    return clause_documents
from langchain_experimental.text_splitter import SemanticChunker
from langchain_openai import OpenAIEmbeddings
from langchain_chroma import Chroma

# 1. 환경변수 로드
load_dotenv(dotenv_path="../../.env")
print("✅ 환경변수 로드 완료!")

# 2. PDF 로딩 테스트
docs_dir = "../../docs"
pdf_pattern = os.path.join(docs_dir, "*.pdf")
pdf_files = glob.glob(pdf_pattern)

print(f"📂 감지된 PDF 파일 개수: {len(pdf_files)}개")
all_documents = []
for path in pdf_files:
    try:
        loader = PyPDFLoader(path)
        docs = loader.load()
        all_documents.extend(docs)
    except Exception as e:
        print(f"  ❌ {os.path.basename(path)} 로드 실패: {e}")

print(f"🎉 통합 PDF 로딩 완료! 총 {len(all_documents)}개 페이지 확보.")

# 임베딩 모델 로드
embedding_model = OpenAIEmbeddings(model='text-embedding-3-large')
print("✨ OpenAI Embeddings 모델 로드 완료!\n")

# 3. 5대 청킹 전략별 쪼개기(Split) 및 검증
print("="*60)
print("🚀 5대 청킹 전략별 쪼개기(Splitting) 시뮬레이션 및 검증 시작")
print("="*60)

# (1) 고정 크기 청킹
fixed_splitter = CharacterTextSplitter(chunk_size=1000, chunk_overlap=200, separator=" ")
fixed_chunks = fixed_splitter.split_documents(all_documents)
print(f"  [1] 고정 크기 청킹 (CharacterTextSplitter): 총 {len(fixed_chunks)}개 청크 생성 완료.")

# (2) 재귀적 청킹
recursive_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
recursive_chunks = recursive_splitter.split_documents(all_documents)
print(f"  [2] 재귀적 청킹 (RecursiveCharacterTextSplitter): 총 {len(recursive_chunks)}개 청크 생성 완료.")

# (3) 문서 구조화 청킹 (Regex 조항별 분할)
structure_chunks = split_documents_by_clause(all_documents)
print(f"  [3] 문서 구조화 청킹 (정규식 기반 조항 단위): 총 {len(structure_chunks)}개 조항 청크 확보 완료.")
# 샘플 조항 청크 출력
if structure_chunks:
    print(f"      👉 샘플 조항 텍스트 (앞 100자):\n{structure_chunks[5].page_content[:150].strip()}...")

# (4) 의미 청킹
print("  ⏳ 의미 청킹 (SemanticChunker) 연산 중... (OpenAI 임베딩 분석 가동)")
semantic_splitter = SemanticChunker(embedding_model, breakpoint_threshold_type="percentile")
semantic_chunks = semantic_splitter.split_documents(all_documents[:15]) # 전체 페이지의 임베딩은 비용/시간 상 일부(15페이지)만 시뮬레이션
print(f"  [4] 의미 청킹 (SemanticChunker - 15p 샘플링): 총 {len(semantic_chunks)}개 의미론적 분할 청크 확보 완료.")

# (5) 계층적 청킹 (Parent-Child)
parent_splitter = RecursiveCharacterTextSplitter(chunk_size=1500, chunk_overlap=300)
child_splitter = RecursiveCharacterTextSplitter(chunk_size=300, chunk_overlap=50)

parent_docs = parent_splitter.split_documents(all_documents)
child_chunks = []
for p_idx, p_doc in enumerate(parent_docs[:5]): # 테스트 속도를 위해 상위 5개 부모 페이지만 자식 쪼개기 매핑
    c_docs = child_splitter.split_documents([p_doc])
    for c_doc in c_docs:
        c_doc.metadata['parent_text'] = p_doc.page_content
        c_doc.metadata['parent_id'] = p_idx
        child_chunks.append(c_doc)
print(f"  [5] 계층적 청킹 (Parent-Child - 상위 5p 샘플링): 부모 5개 페이지에 대한 자식 청크 {len(child_chunks)}개 매핑 생성 완료.")

# 4. 계층적 검색 커스텀 체인(Custom Hierarchical Retriever) 검증
print("\n" + "="*60)
print("🚀 계층적 RAG Custom Retriever 검색 기능 및 매핑 검증")
print("="*60)

# 계층적 DB 테스트 구축 (상위 5p 샘플링을 활용하여 Chroma에 직접 저장)
test_hier_dir = "./chroma_multi_test_hierarchical"
print(f"💾 계층적 테스트 DB '{test_hier_dir}' 저장 중...")
db_hier = Chroma.from_documents(
    documents=child_chunks,
    embedding=embedding_model,
    collection_name="chroma-multi-test-hierarchical",
    persist_directory=test_hier_dir
)

# 유사도 검색 테스트 수행
query = "한국순환자원유통지원센터 신규 직원이 제출해야 하는 서류는 무엇인가요?"
print(f"❓ 검색 테스트 질문: '{query}'")

retriever = db_hier.as_retriever(search_kwargs={'k': 3})
retrieved_child_docs = retriever.invoke(query)

print(f"🎯 검색된 자식 청크 개수: {len(retrieved_child_docs)}")

# 중복을 피하며 부모 텍스트 매핑 및 복원
seen_parents = set()
parent_contexts = []
for idx, doc in enumerate(retrieved_child_docs):
    parent_text = doc.metadata.get('parent_text')
    parent_id = doc.metadata.get('parent_id')
    print(f"  - 자식 청크 {idx+1} 매칭! (Parent ID: {parent_id}) | 자식 본문: {doc.page_content[:80].strip()}...")
    if parent_text and parent_text not in seen_parents:
        seen_parents.add(parent_text)
        parent_contexts.append(parent_text)

print(f"\n✨ 최종 LLM에 제공할 부모 문맥(복원된 Context) 개수: {len(parent_contexts)}개")
if parent_contexts:
    print(f"--- [복원된 부모 문맥 1순위 앞부분] ---\n{parent_contexts[0][:300].strip()}...\n")

print("🎉 5대 청킹 전략 핵심 시뮬레이션 및 계층적 검색 기능 최종 검증 성공!")
