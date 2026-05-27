import os
import json
import re
from datetime import datetime
from backend.agents.llm_client import complete

try:
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.lib.units import cm
    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False

GOV_REPORT_SYSTEM = """
당신은 한국 공공기관/대기업 기안서(보고서) 작성 전문가입니다.
주어진 데이터를 바탕으로 공문서 스타일의 보고서를 작성하세요.
반드시 아래 JSON 스키마를 엄격하게 지켜서 출력하세요. 다른 설명 텍스트는 절대 포함하지 마세요.

{
  "title": "보고서 대제목 (예: 코로나 재택근무 대비를 위한 플레이스테이션 5 구매계획)",
  "meta": "작성일 및 작성자 (예: 2024. 9. 4.(수) 기획처 사업부 홍길동)",
  "sections": [
    {
      "heading": "1. 대제목 (예: 1. 개요, 2. 배경 및 사전검토)",
      "items": [
        {
          "type": "square",  
          "text": "본문 내용",
          "highlight": "none" 
        }
      ]
    }
  ]
}

* 규칙 *
1. type은 "square"(□), "circle"(○), "hyphen"(-) 중 하나. 대분류는 square, 중분류는 circle, 소분류는 hyphen.
2. highlight는 "none", "blue", "red", "green" 중 하나. 중요한 문구 전체를 강조할 때만 색상 지정.
"""

def write_report(report_type: str, data: dict | list) -> dict:
    """
    report_type: "briefing" | "daily_summary" | "kpi_weekly" | "billing"
    data: 보고서에 포함할 항목들
    반환: {"report_type": ..., "content": str, "pdf_path": str}
    """
    if isinstance(data, str):
        data_str = data
    else:
        try:
            data_str = json.dumps(data, ensure_ascii=False, default=str)
        except Exception:
            data_str = str(data)
            
    prompt = f"[{report_type}] 데이터를 공문서 기안서 JSON 형태로 작성해줘:\n{data_str}"
    
    try:
        raw_output = complete(prompt, tier="smart", system=GOV_REPORT_SYSTEM)
        # Parse JSON
        start_idx = raw_output.find("{")
        end_idx = raw_output.rfind("}")
        if start_idx != -1 and end_idx != -1:
            raw_output = raw_output[start_idx:end_idx+1]
        
        parsed_data = json.loads(raw_output)
        
        # 채팅창에 띄울 마크다운 텍스트 조립
        md_content = f"# {parsed_data.get('title', '보고서')}\n"
        md_content += f"*{parsed_data.get('meta', '')}*\n\n"
        
        for sec in parsed_data.get('sections', []):
            md_content += f"### {sec.get('heading', '')}\n"
            for item in sec.get('items', []):
                bullet = "□" if item.get('type') == 'square' else "○" if item.get('type') == 'circle' else "-"
                text = item.get('text', '')
                md_content += f"{bullet} {text}\n"
            md_content += "\n"
            
        result = {"report_type": report_type, "content": md_content}
        
        # PDF 생성
        if REPORTLAB_AVAILABLE:
            pdf_path = _generate_gov_style_pdf(parsed_data, report_type)
            if pdf_path:
                result["pdf_path"] = pdf_path
                
        return result
    except Exception as e:
        return {"report_type": report_type, "content": f"보고서 생성 실패: {str(e)}", "error": str(e)}

def _generate_gov_style_pdf(data: dict, report_type: str) -> str:
    try:
        os.makedirs("outputs", exist_ok=True)
        filename = f"gov_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        pdf_path = os.path.join("outputs", filename)
        
        try:
            pdfmetrics.registerFont(TTFont("Malgun", "C:/Windows/Fonts/malgun.ttf"))
            pdfmetrics.registerFont(TTFont("Malgun-Bold", "C:/Windows/Fonts/malgunbd.ttf"))
            font_normal = "Malgun"
            font_bold = "Malgun-Bold"
        except Exception:
            font_normal = "Helvetica"
            font_bold = "Helvetica-Bold"
            
        # Left/Right/Top/Bottom margins adjusted for document style
        doc = SimpleDocTemplate(pdf_path, pagesize=A4, rightMargin=2*cm, leftMargin=2*cm, topMargin=2.5*cm, bottomMargin=2*cm)
        styles = getSampleStyleSheet()
        
        # Styles
        title_style = ParagraphStyle(
            name="GovTitle", parent=styles["Normal"], fontName=font_bold, fontSize=18, leading=22, alignment=1 # Center
        )
        meta_style = ParagraphStyle(
            name="GovMeta", parent=styles["Normal"], fontName=font_normal, fontSize=10, leading=14, alignment=2 # Right
        )
        heading_style = ParagraphStyle(
            name="GovHeading", parent=styles["Normal"], fontName=font_bold, fontSize=13, leading=20, spaceBefore=12, spaceAfter=6
        )
        
        def get_item_style(indent_level=0):
            return ParagraphStyle(
                name=f"GovItem_{indent_level}", parent=styles["Normal"], fontName=font_normal, fontSize=11, leading=16, 
                leftIndent=indent_level, wordWrap='CJK'
            )
            
        story = []
        
        # 1. Title
        title_text = data.get("title", "보고서")
        story.append(Paragraph(title_text, title_style))
        story.append(Spacer(1, 0.3*cm))
        
        # 2. Lines & Meta
        meta_text = data.get("meta", "")
        line_data = [[Paragraph(meta_text, meta_style)]]
        line_table = Table(line_data, colWidths=[doc.width])
        line_table.setStyle(TableStyle([
            ('LINEABOVE', (0,0), (-1,-1), 2, colors.black),
            ('LINEBELOW', (0,0), (-1,-1), 0.5, colors.black),
            ('TOPPADDING', (0,0), (-1,-1), 4),
            ('BOTTOMPADDING', (0,0), (-1,-1), 4),
            ('LEFTPADDING', (0,0), (-1,-1), 0),
            ('RIGHTPADDING', (0,0), (-1,-1), 0),
        ]))
        story.append(line_table)
        story.append(Spacer(1, 0.5*cm))
        
        # 3. Sections
        for sec in data.get("sections", []):
            heading = sec.get("heading", "")
            story.append(Paragraph(heading, heading_style))
            
            for item in sec.get("items", []):
                i_type = item.get("type", "square")
                i_text = item.get("text", "")
                highlight = item.get("highlight", "none")
                
                # Apply highlight color
                color_hex = "#000000"
                if highlight == "blue": color_hex = "#0000FF"
                elif highlight == "red": color_hex = "#FF0000"
                elif highlight == "green": color_hex = "#008000"
                
                formatted_text = f"<font color='{color_hex}'>{i_text}</font>"
                
                # Bullet and Indent
                bullet = "□"
                indent = 10
                if i_type == "circle":
                    bullet = "○"
                    indent = 25
                elif i_type == "hyphen":
                    bullet = "-"
                    indent = 40
                    
                p_text = f"{bullet} {formatted_text}"
                story.append(Paragraph(p_text, get_item_style(indent)))
                story.append(Spacer(1, 0.1*cm))
        
        doc.build(story)
        return pdf_path
    except Exception as e:
        print(f"PDF 생성 실패: {e}")
        return ""