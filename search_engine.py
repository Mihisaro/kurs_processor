import re
from typing import List
from dataclasses import dataclass
from enum import Enum


class SearchType(Enum):
    PLAIN = "Обычный поиск"
    REGEX = "Регулярное выражение"
    WHOLE_WORD = "Целое слово"


@dataclass
class SearchResult:
    text: str
    line: int
    start_pos: int
    end_pos: int
    length: int

    def __str__(self):
        return f"'{self.text}' (строка {self.line}, позиция {self.start_pos})"


class SearchEngine:

    def __init__(self):
        self.last_pattern = ""
        self.last_results: List[SearchResult] = []

    def search(self, text: str, pattern: str,
               search_type: SearchType = SearchType.PLAIN,
               regex_flags: int = 0) -> List[SearchResult]:
        if not pattern or not text:
            return []

        self.last_pattern = pattern
        results = []
        flags = regex_flags

        try:
            if search_type == SearchType.REGEX:
                regex = re.compile(pattern, flags)
            elif search_type == SearchType.WHOLE_WORD:
                escaped = re.escape(pattern)
                regex = re.compile(rf'\b{escaped}\b', flags)
            else:
                escaped = re.escape(pattern)
                regex = re.compile(escaped, flags)

            lines = [ln.rstrip('\r') for ln in text.split('\n')]

            for line_num, line in enumerate(lines, 1):
                for match in regex.finditer(line):
                    start_in_line = match.start()
                    end_in_line = match.end()

                    result = SearchResult(
                        text=match.group(),
                        line=line_num,
                        start_pos=start_in_line + 1,
                        end_pos=end_in_line,
                        length=end_in_line - start_in_line
                    )
                    results.append(result)

        except re.error as e:
            raise ValueError(f"Ошибка в регулярном выражении: {str(e)}")

        self.last_results = results
        return results

    def get_count(self) -> int:
        return len(self.last_results)

    def highlight_result(self, text: str, result: SearchResult,
                          highlight_char: str = '^') -> str:
        lines = [ln.rstrip('\r') for ln in text.split('\n')]
        if result.line - 1 < len(lines):
            line = lines[result.line - 1]
            prefix = ' ' * (result.start_pos - 1)
            marker = highlight_char * result.length
            return f"{line}\n{prefix}{marker}"
        return ""
