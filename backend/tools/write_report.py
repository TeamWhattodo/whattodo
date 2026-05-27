import os
import json
import re
from datetime import datetime
from backend.agents.llm_client import complete

try:
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
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

DAILY_REPORT_SYSTEM = """
당신은 '일일 업무보고서' 작성 전문가입니다.
주어진 데이터를 바탕으로 일일 업무보고서 항목을 작성하세요.
반드시 아래 JSON 스키마를 엄격하게 지켜서 출력하세요. 다른 텍스트는 절대 포함하지 마세요.

{
  "date": "2024. 9. 4",
  "author": "작성자 이름",
  "department": "소속팀명",
  "position": "직급 (예: 사원, 대리)",
  "today_tasks": "오늘의 주요업무 내용 (텍스트로 길게 작성 가능)",
  "pending_tasks": "미결·결 업무사항 내용",
  "tomorrow_tasks": "익일 업무계획 내용",
  "other_notes": "기타사항 내용"
}
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
            
    is_daily = (report_type == "daily_summary")
    system = DAILY_REPORT_SYSTEM if is_daily else GOV_REPORT_SYSTEM
    prompt = f"[{report_type}] 데이터를 바탕으로 JSON 보고서를 작성해줘:\n{data_str}"
    
    try:
        raw_output = complete(prompt, tier="smart", system=system)
        
        start_idx = raw_output.find("{")
        end_idx = raw_output.rfind("}")
        if start_idx != -1 and end_idx != -1:
            raw_output = raw_output[start_idx:end_idx+1]
        
        parsed_data = json.loads(raw_output)
        
        if is_daily:
            # 일일 업무보고서 마크다운
            md_content = f"# 일일 업무보고서\n"
            md_content += f"**작성자:** {parsed_data.get('department', '')} {parsed_data.get('position', '')} {parsed_data.get('author', '')} ({parsed_data.get('date', '')})\n\n"
            md_content += f"### ▶ 오늘의 주요업무\n{parsed_data.get('today_tasks', '')}\n\n"
            md_content += f"### ▶ 미결·결 업무사항\n{parsed_data.get('pending_tasks', '')}\n\n"
            md_content += f"### ▶ 익일 업무계획\n{parsed_data.get('tomorrow_tasks', '')}\n\n"
            md_content += f"### ▶ 기타사항\n{parsed_data.get('other_notes', '')}"
        else:
            # 공문서 마크다운
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
        
        if REPORTLAB_AVAILABLE:
            if is_daily:
                pdf_path = _generate_daily_report_pdf(parsed_data, report_type)
            else:
                pdf_path = _generate_gov_style_pdf(parsed_data, report_type)
                
            if pdf_path:
                result["pdf_path"] = pdf_path
                
        return result
    except Exception as e:
        return {"report_type": report_type, "content": f"보고서 생성 실패: {str(e)}", "error": str(e)}

def _setup_fonts():
    try:
        pdfmetrics.registerFont(TTFont("Malgun", "C:/Windows/Fonts/malgun.ttf"))
        pdfmetrics.registerFont(TTFont("Malgun-Bold", "C:/Windows/Fonts/malgunbd.ttf"))
        return "Malgun", "Malgun-Bold"
    except Exception:
        return "Helvetica", "Helvetica-Bold"

def _generate_gov_style_pdf(data: dict, report_type: str) -> str:
    try:
        os.makedirs("outputs", exist_ok=True)
        filename = f"gov_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        pdf_path = os.path.join("outputs", filename)
        
        font_normal, font_bold = _setup_fonts()
        doc = SimpleDocTemplate(pdf_path, pagesize=A4, rightMargin=2*cm, leftMargin=2*cm, topMargin=2.5*cm, bottomMargin=2*cm)
        styles = getSampleStyleSheet()
        
        title_style = ParagraphStyle(
            name="GovTitle", parent=styles["Normal"], fontName=font_bold, fontSize=18, leading=22, alignment=1 
        )
        meta_style = ParagraphStyle(
            name="GovMeta", parent=styles["Normal"], fontName=font_normal, fontSize=10, leading=14, alignment=2 
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
        story.append(Paragraph(data.get("title", "보고서"), title_style))
        story.append(Spacer(1, 0.3*cm))
        
        line_data = [[Paragraph(data.get("meta", ""), meta_style)]]
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
        
        for sec in data.get("sections", []):
            story.append(Paragraph(sec.get("heading", ""), heading_style))
            for item in sec.get("items", []):
                i_type = item.get("type", "square")
                i_text = item.get("text", "")
                highlight = item.get("highlight", "none")
                
                color_hex = "#000000"
                if highlight == "blue": color_hex = "#0000FF"
                elif highlight == "red": color_hex = "#FF0000"
                elif highlight == "green": color_hex = "#008000"
                
                formatted_text = f"<font color='{color_hex}'>{i_text}</font>"
                bullet = "□"
                indent = 10
                if i_type == "circle":
                    bullet = "○"
                    indent = 25
                elif i_type == "hyphen":
                    bullet = "-"
                    indent = 40
                    
                story.append(Paragraph(f"{bullet} {formatted_text}", get_item_style(indent)))
                story.append(Spacer(1, 0.1*cm))
        
        doc.build(story)
        return pdf_path
    except Exception as e:
        print(f"PDF 생성 실패: {e}")
        return ""

def _generate_daily_report_pdf(data: dict, report_type: str) -> str:
    try:
        os.makedirs("outputs", exist_ok=True)
        filename = f"daily_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        pdf_path = os.path.join("outputs", filename)
        
        font_normal, font_bold = _setup_fonts()
        doc = SimpleDocTemplate(pdf_path, pagesize=A4, rightMargin=2*cm, leftMargin=2*cm, topMargin=2*cm, bottomMargin=2*cm)
        styles = getSampleStyleSheet()
        
        # Styles
        title_style = ParagraphStyle(name="DTitle", fontName=font_bold, fontSize=18, alignment=0)
        table_normal = ParagraphStyle(name="TNormal", fontName=font_normal, fontSize=10, alignment=1)
        section_title = ParagraphStyle(name="SecTitle", fontName=font_bold, fontSize=11, alignment=0, textColor=colors.black)
        body_style = ParagraphStyle(name="DBody", fontName=font_normal, fontSize=10, leading=16, alignment=0)
        
        story = []
        cw = doc.width
        
        # Header (Title and Approval Box)
        # Approval box is right aligned.
        app_box_width = cw * 0.4
        t_title = Paragraph("일일 업무보고서", title_style)
        
        # Approval table
        t_app_data = [
            [Paragraph("담당", table_normal), '', ''],
            ['', '', '']
        ]
        t_app = Table(t_app_data, colWidths=[app_box_width/3.0]*3, rowHeights=[0.6*cm, 1.2*cm])
        t_app.setStyle(TableStyle([
            ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
            ('BACKGROUND', (0,0), (-1,0), colors.lightgrey),
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
            ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ]))
        
        t_header_data = [[t_title, t_app]]
        t_header = Table(t_header_data, colWidths=[cw*0.6, cw*0.4])
        t_header.setStyle(TableStyle([
            ('VALIGN', (0,0), (-1,-1), 'BOTTOM'),
        ]))
        story.append(t_header)
        story.append(Spacer(1, 0.2*cm))
        
        # Horizontal line below header
        story.append(HRFlowable(width="100%", thickness=1, color=colors.black, spaceAfter=0.5*cm))
        
        # Info Box
        lbl_w = cw * 0.15
        val_w = cw * 0.35
        t_info_data = [
            [Paragraph("일 자", table_normal), Paragraph(data.get("date", ""), table_normal), Paragraph("작 성 자", table_normal), Paragraph(data.get("author", ""), table_normal)],
            [Paragraph("부 서", table_normal), Paragraph(data.get("department", ""), table_normal), Paragraph("직 급", table_normal), Paragraph(data.get("position", ""), table_normal)]
        ]
        t_info = Table(t_info_data, colWidths=[lbl_w, val_w, lbl_w, val_w], rowHeights=[0.8*cm, 0.8*cm])
        t_info.setStyle(TableStyle([
            ('GRID', (0,0), (-1,-1), 0.5, colors.lightgrey),
            ('LINEABOVE', (0,0), (-1,0), 1, colors.black),
            ('LINEBELOW', (0,1), (-1,1), 1, colors.black),
            ('BACKGROUND', (0,0), (0,1), colors.whitesmoke),
            ('BACKGROUND', (2,0), (2,1), colors.whitesmoke),
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
            ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ]))
        story.append(t_info)
        story.append(Spacer(1, 0.5*cm))
        
        # Sections Helper
        def add_section(title, content):
            # Section Title with grey background
            t_sec_data = [[Paragraph(title, section_title)]]
            t_sec = Table(t_sec_data, colWidths=[cw], rowHeights=[0.8*cm])
            t_sec.setStyle(TableStyle([
                ('BACKGROUND', (0,0), (-1,-1), colors.whitesmoke),
                ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
                ('LEFTPADDING', (0,0), (-1,-1), 5),
            ]))
            story.append(t_sec)
            story.append(Spacer(1, 0.2*cm))
            
            # Content
            # Replace newlines with <br/> for ReportLab
            safe_content = content.replace("\n", "<br/>")
            story.append(Paragraph(safe_content, body_style))
            
            # Spacer for padding
            story.append(Spacer(1, 2.5*cm))
            
            # Horizontal line separator
            story.append(HRFlowable(width="100%", thickness=0.5, color=colors.grey, spaceAfter=0.5*cm))
            
        add_section("▶ 오늘의 주요업무", data.get("today_tasks", ""))
        add_section("▶ 미종결 업무사항", data.get("pending_tasks", ""))
        add_section("▶ 익일 업무계획", data.get("tomorrow_tasks", ""))
        add_section("▶ 기타사항", data.get("other_notes", ""))
        
        doc.build(story)
        return pdf_path
    except Exception as e:
        print(f"PDF 생성 실패: {e}")
        return ""