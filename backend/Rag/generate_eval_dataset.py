import os
import json
import random
from dotenv import load_dotenv
from langchain_community.document_loaders import PyPDFLoader
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field

def main():
    print("🔄 평가 데이터셋 자동 생성 유틸리티 기동 중...")
    
    # 1. 환경변수 로드
    load_dotenv(dotenv_path="../../.env")
    if not os.environ.get("OPENAI_API_KEY"):
        print("❌ OPENAI_API_KEY가 환경변수에 없습니다!")
        return

    # 2. PDF 로드
    pdf_path = "../../docs/KORA 규정집.pdf"
    if not os.path.exists(pdf_path):
        print(f"❌ PDF 규정집 파일을 찾을 수 없습니다: {pdf_path}")
        return

    loader = PyPDFLoader(pdf_path)
    documents = loader.load()
    num_pages = len(documents)
    print(f"📖 KORA 규정집 로드 성공! 총 {num_pages} 페이지 확보")

    # 의미 있는 페이지 샘플링 (10~50페이지 사이의 구체적 규정 페이지 위주로 10개 선택)
    random.seed(42)
    start_page = 10
    end_page = min(60, num_pages)
    
    if end_page > start_page:
        pages_pool = list(range(start_page, end_page))
        sampled_indices = random.sample(pages_pool, min(10, len(pages_pool)))
    else:
        sampled_indices = list(range(min(10, num_pages)))
        
    sampled_docs = [documents[i] for i in sampled_indices]
    print(f"🎯 샘플링된 페이지 번호 목록: {[i+1 for i in sampled_indices]}페이지")

    # 3. Pydantic을 이용한 OpenAI 구조화 출력 스키마 정의
    class QAPair(BaseModel):
        question: str = Field(description="본문 내용을 기반으로 하는 구체적이고 명확한 한국어 질문")
        ground_truth: str = Field(description="본문 내용에 전적으로 기반하여 도출된 정확한 한국어 모범 답안")

    class QADataset(BaseModel):
        dataset: list[QAPair]

    llm = ChatOpenAI(model="gpt-4o", temperature=0.3)
    structured_llm = llm.with_structured_output(QADataset)

    prompt_template = """당신은 한국순환자원유통지원센터(KORA)의 규정집 문서를 분석하는 전문가입니다.
제공된 아래 [Context] 문서 내용을 꼼꼼히 읽고, 이 내용에 기반하여 임직원들이 실제로 궁금해할 법한 구체적인 '질문(question)'과 본문 내용에만 근거한 정확한 '모범 답안(ground_truth)' 쌍을 1~2개 생성해 주세요.

[Context]
{context}

반드시 본문 내용에 명시된 사실만을 활용하여 질문과 정답을 구성해야 하며, 추측하거나 임의로 지어내지 마십시오.
"""

    final_dataset = []
    print(f"\n🧠 GPT-4o를 이용한 RAGAS 평가용 질문 및 정답 추출 진행 중...")
    
    for i, doc in enumerate(sampled_docs):
        page_num = doc.metadata.get("page", 0) + 1
        content = doc.page_content.strip()
        
        if len(content) < 150:
            print(f" -> [{i+1}/{len(sampled_docs)}] {page_num}페이지는 본문 내용이 너무 짧아 건너뜁니다.")
            continue
            
        print(f" -> [{i+1}/{len(sampled_docs)}] {page_num}페이지 질문/답변 생성 중...")
        
        prompt = prompt_template.format(context=content)
        try:
            qa_output = structured_llm.invoke(prompt)
            for qa in qa_output.dataset:
                final_dataset.append({
                    "question": qa.question,
                    "ground_truth": qa.ground_truth
                })
        except Exception as e:
            print(f"  ⚠️ {page_num}페이지 처리 중 오류 발생: {e}")

    # 4. JSON 파일 저장
    output_path = "../../docs/kora_eval_dataset.json"
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump({"dataset": final_dataset}, f, ensure_ascii=False, indent=2)

    print(f"\n✅ 평가용 골든 데이터셋 생성 성공! 생성된 문항 수: {len(final_dataset)}개")
    print(f"💾 저장 경로: {os.path.abspath(output_path)}")

if __name__ == "__main__":
    main()
