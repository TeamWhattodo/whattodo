from backend.tools.write_report import write_report

result = write_report('daily_summary', {
    'author': '홍길동',
    'department': '개발팀',
    'position': '사원',
    'today_tasks': '기능 테스트 진행',
    'pending_tasks': '없음',
    'tomorrow_tasks': '버그 수정',
    'other_notes': '특이사항 없음'
})
print(result['content'])