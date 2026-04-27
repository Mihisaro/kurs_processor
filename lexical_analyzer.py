from enum import Enum
import re

# Алфавит исходного текста языка: буквы, цифры, _, :, =, ;, пробел, таб;
# слова из keywords/types распознаются отдельно.
_LEX_ALPHABET = set(
    "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_:=; \t"
)


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

def _is_float_error_lexeme(value: str) -> bool:
    return bool(re.match(r"^\d+\.\d*$", value or ""))


DATA_TYPE_NAMES = frozenset({
    "i8", "i16", "i32", "i64", "i128",
    "u8", "u16", "u32", "u64", "u128",
})


class LexicalAnalyzer:
    def __init__(self):
        self.allowed_chars = _LEX_ALPHABET
        self.keywords = {
            'const': TokenType.CONST,
        }

        self.types = {name: TokenType.TYPE for name in DATA_TYPE_NAMES}

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

            # Отрицательные целые: '-' допустим только вплотную перед цифрами.
            # И только в позиции литерала (после '=' с пробелами/табами или в начале строки).
            if line[i] == '-' and (i + 1) < length and line[i + 1].isdigit():
                k = i - 1
                while k >= 0 and line[k] in (' ', '\t'):
                    k -= 1
                allow_negative = (k < 0) or (line[k] == '=')
                if not allow_negative:
                    # Пусть обработается как лексическая ошибка ниже.
                    pass
                else:
                    start = i
                    i += 1
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

            if line[i].isdigit():
                start = i
                while i < length and line[i].isdigit():
                    i += 1

                if i < length and line[i] == '.':
                    i += 1
                    while i < length and line[i].isdigit():
                        i += 1
                    tokens.append(Token(
                        TokenType.ERROR,
                        line[start:i],
                        line_num,
                        start + 1,
                        i
                    ))
                else:
                    tokens.append(Token(
                        TokenType.NUMBER,
                        line[start:i],
                        line_num,
                        start + 1,
                        i
                    ))
                continue

            start = i
            while i < length and line[i] not in self.allowed_chars:
                i += 1
            tokens.append(Token(
                TokenType.ERROR,
                line[start:i],
                line_num,
                start + 1,
                i
            ))

        return tokens

    def validate_const_declaration(self, tokens):
        for token in tokens:
            if token.is_error:
                if _is_float_error_lexeme(token.value):
                    msg = (
                        f"Строка {token.line}: дробное число '{token.value}' недопустимо "
                        f"(позиция {token.start_pos}); используйте целый литерал"
                    )
                else:
                    msg = (
                        f"Строка {token.line}: недопустимый символ или лексема "
                        f"'{token.value}' на позиции {token.start_pos}"
                    )
                return False, msg
        return True, "OK"
    