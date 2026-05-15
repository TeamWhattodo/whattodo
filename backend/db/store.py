"""
TinyDB 구현체. tools/storage.py 의 함수가 이 파일에 위임한다.
직접 import하지 말고 tools/storage.py 를 통해 사용한다.
"""
from pathlib import Path

_DATA_DIR = Path(__file__).parent / "data"
_DATA_DIR.mkdir(exist_ok=True)
