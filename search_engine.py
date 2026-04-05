import re
from typing import List, Tuple, Optional
from dataclasses import dataclass
from enum import Enum


class SearchType(Enum):
    """Типы поиска"""
    PLAIN = "Обычный поиск"
    REGEX = "Регулярное выражение"
    WHOLE_WORD = "Целое слово"


@dataclass
class SearchResult:
    """Результат поиска"""
    text: str
    line: int
    start_pos: int
    end_pos: int
    length: int
    
    def __str__(self):
        return f"'{self.text}' (строка {self.line}, позиция {self.start_pos})"


class SearchEngine:
    """Поисковая система с поддержкой регулярных выражений"""
    
    def __init__(self):
        self.last_pattern = ""
        self.last_results: List[SearchResult] = []
    
    def search(self, text: str, pattern: str, 
               search_type: SearchType = SearchType.PLAIN,
               regex_flags: int = 0) -> List[SearchResult]:
        """
        Поиск подстрок в тексте
        
        Args:
            text: Исходный текст
            pattern: Шаблон поиска
            search_type: Тип поиска
            regex_flags: Флаги для регулярных выражений
            
        Returns:
            Список результатов поиска
        """
        if not pattern or not text:
            return []
        
        self.last_pattern = pattern
        results = []
        flags = regex_flags

        try:
            # Компилируем регулярное выражение
            if search_type == SearchType.REGEX:
                regex = re.compile(pattern, flags)
            elif search_type == SearchType.WHOLE_WORD:
                # Поиск целых слов
                escaped = re.escape(pattern)
                regex = re.compile(rf'\b{escaped}\b', flags)
            else:
                # Обычный поиск
                escaped = re.escape(pattern)
                regex = re.compile(escaped, flags)
            
            # Разбиваем текст на строки
            lines = text.split('\n')
            global_pos = 0
            
            for line_num, line in enumerate(lines, 1):
                line_start = global_pos
                
                # Ищем все совпадения в строке
                for match in regex.finditer(line):
                    start_in_line = match.start()
                    end_in_line = match.end()
                    
                    result = SearchResult(
                        text=match.group(),
                        line=line_num,
                        start_pos=start_in_line + 1,  # 1-based позиция
                        end_pos=end_in_line,
                        length=end_in_line - start_in_line
                    )
                    results.append(result)
                
                global_pos += len(line) + 1  # +1 для символа новой строки
        
        except re.error as e:
            # Ошибка в регулярном выражении
            raise ValueError(f"Ошибка в регулярном выражении: {str(e)}")
        
        self.last_results = results
        return results
    
    def get_count(self) -> int:
        """Получить количество найденных совпадений"""
        return len(self.last_results)
    
    def highlight_result(self, text: str, result: SearchResult, 
                          highlight_char: str = '^') -> str:
        """Создать строку с подсветкой результата"""
        lines = text.split('\n')
        if result.line - 1 < len(lines):
            line = lines[result.line - 1]
            prefix = ' ' * (result.start_pos - 1)
            marker = highlight_char * result.length
            return f"{line}\n{prefix}{marker}"
        return ""