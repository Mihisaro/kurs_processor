
from enum import Enum

class TokenType(Enum):
    CONST = (1, "Ключевое слово const")
    IDENTIFIER = (2, "Идентификатор")
    COLON = (3, "Двоеточие")
    TYPE = (4, "Тип данных")
    ASSIGN = (5, "Оператор присваивания")
    NUMBER = (6, "Числовой литерал")
    SEMICOLON = (7, "Точка с запятой")
    SPACE = (8, "Пробел")
    TAB = (9, "Табуляция")
    NEWLINE = (10, "Перевод строки")
    ERROR = (99, "Недопустимый символ")
    
    def __init__(self, code, description):
        self.code = code
        self.description = description
    
    @property
    def is_error(self):
        return self.code == 99


class Token:
    def __init__(self, token_type, value, line, start_pos, end_pos):
        self.type = token_type
        self.value = value
        self.line = line
        self.start_pos = start_pos
        self.end_pos = end_pos
    
    def __str__(self):
        return f"{self.type.name}: '{self.value}' (строка {self.line}, позиция {self.start_pos}-{self.end_pos})"
    
    @property
    def is_error(self):
        return self.type.is_error


class LexicalAnalyzer:
    def __init__(self):
        # Допустимые символы для корректного объявления константы
        self.allowed_chars = set('abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_:=; ')
        
        # Ключевые слова
        self.keywords = {
            'const': TokenType.CONST,
        }
        
        # Типы данных
        self.types = {
            'i32': TokenType.TYPE,
            'i8': TokenType.TYPE,
            'i16': TokenType.TYPE,
            'i64': TokenType.TYPE,
            'i128': TokenType.TYPE,
            'u8': TokenType.TYPE,
            'u16': TokenType.TYPE,
            'u32': TokenType.TYPE,
            'u64': TokenType.TYPE,
            'u128': TokenType.TYPE,
        }
        
        # Допустимые одиночные символы
        self.single_chars = {
            ':': TokenType.COLON,
            '=': TokenType.ASSIGN,
            ';': TokenType.SEMICOLON,
        }
    
    def analyze(self, text):
        tokens = []
        lines = text.split('\n')
        
        for line_num, line in enumerate(lines, 1):
            line_tokens = self._analyze_line(line, line_num)
            tokens.extend(line_tokens)
            
            # Добавляем перевод строки
            if line_num < len(lines):
                tokens.append(Token(
                    TokenType.NEWLINE,
                    '\\n',
                    line_num,
                    len(line) + 1,
                    len(line) + 1
                ))
        
        return tokens
    
    def _analyze_line(self, line, line_num):
        tokens = []
        i = 0
        length = len(line)
        
        while i < length:
            # Пробелы и табуляция
            if line[i] == ' ':
                start = i
                while i < length and line[i] == ' ':
                    i += 1
                tokens.append(Token(
                    TokenType.SPACE,
                    line[start:i],
                    line_num,
                    start + 1,
                    i
                ))
                continue
            
            if line[i] == '\t':
                tokens.append(Token(
                    TokenType.TAB,
                    line[i],
                    line_num,
                    i + 1,
                    i + 1
                ))
                i += 1
                continue
            
            # Допустимые одиночные символы
            if line[i] in self.single_chars:
                tokens.append(Token(
                    self.single_chars[line[i]],
                    line[i],
                    line_num,
                    i + 1,
                    i + 1
                ))
                i += 1
                continue
            
            # Идентификаторы, ключевые слова и типы
            if line[i].isalpha() or line[i] == '_':
                start = i
                while i < length and (line[i].isalnum() or line[i] == '_'):
                    i += 1
                
                word = line[start:i]
                
                if word in self.keywords:
                    tokens.append(Token(
                        self.keywords[word],
                        word,
                        line_num,
                        start + 1,
                        i
                    ))
                elif word in self.types:
                    tokens.append(Token(
                        self.types[word],
                        word,
                        line_num,
                        start + 1,
                        i
                    ))
                else:
                    tokens.append(Token(
                        TokenType.IDENTIFIER,
                        word,
                        line_num,
                        start + 1,
                        i
                    ))
                continue
            
            # Числа
            if line[i].isdigit():
                start = i
                while i < length and line[i].isdigit():
                    i += 1
                
                tokens.append(Token(
                    TokenType.NUMBER,
                    line[start:i],
                    line_num,
                    start + 1,
                    i
                ))
                continue
            
            # Недопустимый символ
            tokens.append(Token(
                TokenType.ERROR,
                line[i],
                line_num,
                i + 1,
                i + 1
            ))
            i += 1
        
        return tokens
    
    def validate_const_declaration(self, tokens):
        """Просто проверяем наличие недопустимых символов"""
        for token in tokens:
            if token.is_error:
                return False, f"Строка {token.line}: недопустимый символ '{token.value}' на позиции {token.start_pos}"
        return True, "OK"