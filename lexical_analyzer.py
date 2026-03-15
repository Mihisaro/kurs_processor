# lexical_analyzer.py
from enum import Enum
import re

class TokenType(Enum):
    # Ключевое слово
    CONST = (1, "Ключевое слово const")
    
    # Целочисленные типы Rust (ДОПУСТИМЫЕ)
    I8 = (2, "Тип i8")
    I16 = (3, "Тип i16")
    I32 = (4, "Тип i32")
    I64 = (5, "Тип i64")
    I128 = (6, "Тип i128")
    ISIZE = (7, "Тип isize")
    U8 = (8, "Тип u8")
    U16 = (9, "Тип u16")
    U32 = (10, "Тип u32")
    U64 = (11, "Тип u64")
    U128 = (12, "Тип u128")
    USIZE = (13, "Тип usize")
    
    # НЕДОПУСТИМЫЕ ТИПЫ (будут подсвечиваться красным)
    BOOL = (30, "ОШИБКА: Тип bool (недопустим, требуется целочисленный тип)")
    CHAR = (31, "ОШИБКА: Тип char (недопустим, требуется целочисленный тип)")
    F32 = (32, "ОШИБКА: Тип f32 (недопустим, требуется целочисленный тип)")
    F64 = (33, "ОШИБКА: Тип f64 (недопустим, требуется целочисленный тип)")
    STR = (34, "ОШИБКА: Тип &str (недопустим, требуется целочисленный тип)")
    STRING = (35, "ОШИБКА: Тип String (недопустим, требуется целочисленный тип)")
    
    # Идентификатор (имя константы)
    IDENTIFIER = (14, "Идентификатор (имя константы)")
    
    # Операторы и разделители
    ASSIGN = (15, "Оператор присваивания =")
    COLON = (16, "Разделитель :")
    SEMICOLON = (17, "Разделитель ;")
    
    # Целочисленные литералы (ДОПУСТИМЫЕ)
    DECIMAL_LITERAL = (18, "Десятичный литерал")
    HEX_LITERAL = (19, "Шестнадцатеричный литерал")
    BINARY_LITERAL = (20, "Двоичный литерал")
    OCTAL_LITERAL = (21, "Восьмеричный литерал")
    BYTE_LITERAL = (22, "Байтовый литерал")
    
    # НЕДОПУСТИМЫЕ ЛИТЕРАЛЫ (будут подсвечиваться красным)
    BOOL_LITERAL = (40, "ОШИБКА: Булев литерал (недопустим, требуется целочисленное значение)")
    FLOAT_LITERAL = (41, "ОШИБКА: Вещественный литерал (недопустим, требуется целочисленное значение)")
    CHAR_LITERAL = (42, "ОШИБКА: Символьный литерал (недопустим, требуется целочисленное значение)")
    STRING_LITERAL = (43, "ОШИБКА: Строковый литерал (недопустим, требуется целочисленное значение)")
    
    # Пробельные символы (НЕ являются ошибками)
    SPACE = (90, "Пробел")
    TAB = (91, "Табуляция")
    NEWLINE = (92, "Перевод строки")
    
    # Комментарии (недопустимы в объявлении констант)
    COMMENT = (93, "ОШИБКА: Комментарий (не допускается в объявлении константы)")
    
    # Общая ошибка
    ERROR = (99, "Ошибка: недопустимый символ")
    
    def __init__(self, code, description):
        self.code = code
        self.description = description
    
    @property
    def is_error(self):
        """Проверяет, является ли тип токена ошибкой"""
        # Ошибки: коды 30-49 (недопустимые типы и литералы), 93 (комментарии), 99 (общая ошибка)
        # Пробелы (90-92) НЕ являются ошибками
        return (30 <= self.code <= 49) or self.code == 93 or self.code == 99


class Token:
    def __init__(self, token_type, value, line, start_pos, end_pos):
        self.type = token_type
        self.value = value
        self.line = line
        self.start_pos = start_pos
        self.end_pos = end_pos
    
    def __str__(self):
        return f"{self.type.name}: '{self.value}' at line {self.line}, pos {self.start_pos}-{self.end_pos}"
    
    @property
    def is_error(self):
        """Проверяет, является ли токен ошибкой"""
        return self.type.is_error


class LexicalAnalyzer:
    def __init__(self):
        # ДОПУСТИМЫЕ целочисленные типы Rust
        self.integer_types = {
            'i8': TokenType.I8,
            'i16': TokenType.I16,
            'i32': TokenType.I32,
            'i64': TokenType.I64,
            'i128': TokenType.I128,
            'isize': TokenType.ISIZE,
            'u8': TokenType.U8,
            'u16': TokenType.U16,
            'u32': TokenType.U32,
            'u64': TokenType.U64,
            'u128': TokenType.U128,
            'usize': TokenType.USIZE,
        }
        
        # НЕДОПУСТИМЫЕ типы (для отлова ошибок)
        self.invalid_types = {
            'bool': TokenType.BOOL,
            'char': TokenType.CHAR,
            'f32': TokenType.F32,
            'f64': TokenType.F64,
            '&str': TokenType.STR,
            'String': TokenType.STRING,
            'str': TokenType.STR,
        }
        
        # Ключевые слова для объявления констант
        self.keywords = {
            'const': TokenType.CONST,
        }
        
        # Булевы литералы (НЕДОПУСТИМЫ)
        self.bool_literals = {
            'true': TokenType.BOOL_LITERAL,
            'false': TokenType.BOOL_LITERAL,
        }
        
        # Односимвольные операторы и разделители
        self.single_chars = {
            '=': TokenType.ASSIGN,
            ':': TokenType.COLON,
            ';': TokenType.SEMICOLON,
        }
    
    def analyze(self, text):
        """Основной метод анализа текста"""
        tokens = []
        lines = text.split('\n')
        
        for line_num, line in enumerate(lines, 1):
            line_tokens = self._analyze_line(line, line_num)
            tokens.extend(line_tokens)
            
            # Добавляем токен перевода строки после каждой строки (кроме последней)
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
        """Анализ одной строки"""
        tokens = []
        i = 0
        length = len(line)
        
        while i < length:
            # Обрабатываем пробелы (теперь не фильтруем)
            if line[i].isspace():
                start = i
                space_char = line[i]
                if space_char == ' ':
                    token_type = TokenType.SPACE
                elif space_char == '\t':
                    token_type = TokenType.TAB
                else:
                    token_type = TokenType.SPACE
                
                # Собираем все подряд идущие пробелы
                while i < length and line[i].isspace():
                    i += 1
                
                tokens.append(Token(
                    token_type,
                    line[start:i],
                    line_num,
                    start + 1,
                    i
                ))
                continue
            
            # Проверяем комментарии (в Rust комментарии начинаются с //)
            if i < length - 1 and line[i] == '/' and line[i+1] == '/':
                # Комментарий до конца строки - считаем ошибкой
                comment = line[i:]
                tokens.append(Token(
                    TokenType.COMMENT,
                    comment,
                    line_num,
                    i + 1,
                    length
                ))
                break  # Остальная часть строки - комментарий
            
            # Проверяем операторы и разделители (один символ)
            if line[i] in self.single_chars:
                token_type = self.single_chars[line[i]]
                tokens.append(Token(
                    token_type,
                    line[i],
                    line_num,
                    i + 1,
                    i + 1
                ))
                i += 1
                continue
            
            # Проверяем шестнадцатеричные литералы (0x...)
            if i < length - 2 and line[i] == '0' and line[i+1] == 'x':
                start = i
                i += 2
                while i < length and (line[i].isdigit() or line[i].lower() in 'abcdef'):
                    i += 1
                hex_literal = line[start:i]
                tokens.append(Token(
                    TokenType.HEX_LITERAL,
                    hex_literal,
                    line_num,
                    start + 1,
                    i
                ))
                continue
            
            # Проверяем двоичные литералы (0b...)
            if i < length - 2 and line[i] == '0' and line[i+1] == 'b':
                start = i
                i += 2
                while i < length and line[i] in '01':
                    i += 1
                bin_literal = line[start:i]
                tokens.append(Token(
                    TokenType.BINARY_LITERAL,
                    bin_literal,
                    line_num,
                    start + 1,
                    i
                ))
                continue
            
            # Проверяем восьмеричные литералы (0o...)
            if i < length - 2 and line[i] == '0' and line[i+1] == 'o':
                start = i
                i += 2
                while i < length and line[i] in '01234567':
                    i += 1
                oct_literal = line[start:i]
                tokens.append(Token(
                    TokenType.OCTAL_LITERAL,
                    oct_literal,
                    line_num,
                    start + 1,
                    i
                ))
                continue
            
            # Проверяем байтовые литералы (b'...' или b"...")
            if i < length - 1 and line[i] == 'b' and (line[i+1] == "'" or line[i+1] == '"'):
                start = i
                quote = line[i+1]
                i += 2
                while i < length and line[i] != quote:
                    if line[i] == '\\' and i + 1 < length:
                        i += 2
                    else:
                        i += 1
                if i < length and line[i] == quote:
                    i += 1
                    byte_literal = line[start:i]
                    tokens.append(Token(
                        TokenType.BYTE_LITERAL,
                        byte_literal,
                        line_num,
                        start + 1,
                        i
                    ))
                else:
                    tokens.append(Token(
                        TokenType.ERROR,
                        line[start:],
                        line_num,
                        start + 1,
                        length
                    ))
                    i = length
                continue
            
            # Проверяем строковые литералы (НЕДОПУСТИМЫ)
            if line[i] == '"':
                start = i
                i += 1
                while i < length and line[i] != '"':
                    if line[i] == '\\' and i + 1 < length:
                        i += 2
                    else:
                        i += 1
                if i < length and line[i] == '"':
                    i += 1
                    string_literal = line[start:i]
                    tokens.append(Token(
                        TokenType.STRING_LITERAL,
                        string_literal,
                        line_num,
                        start + 1,
                        i
                    ))
                else:
                    tokens.append(Token(
                        TokenType.ERROR,
                        line[start:],
                        line_num,
                        start + 1,
                        length
                    ))
                    i = length
                continue
            
            # Проверяем символьные литералы (НЕДОПУСТИМЫ)
            if line[i] == "'":
                start = i
                i += 1
                if i < length and line[i] != "'":
                    if line[i] == '\\' and i + 1 < length:
                        i += 2
                    else:
                        i += 1
                if i < length and line[i] == "'":
                    i += 1
                    char_literal = line[start:i]
                    tokens.append(Token(
                        TokenType.CHAR_LITERAL,
                        char_literal,
                        line_num,
                        start + 1,
                        i
                    ))
                else:
                    tokens.append(Token(
                        TokenType.ERROR,
                        line[start:],
                        line_num,
                        start + 1,
                        length
                    ))
                    i = length
                continue
            
            # Проверяем числа с плавающей точкой (НЕДОПУСТИМЫ)
            if i < length - 1 and line[i].isdigit() and line[i+1] == '.':
                start = i
                i += 2
                while i < length and line[i].isdigit():
                    i += 1
                # Проверяем экспоненциальную форму
                if i < length and line[i].lower() == 'e':
                    i += 1
                    if i < length and (line[i] == '+' or line[i] == '-'):
                        i += 1
                    while i < length and line[i].isdigit():
                        i += 1
                float_literal = line[start:i]
                tokens.append(Token(
                    TokenType.FLOAT_LITERAL,
                    float_literal,
                    line_num,
                    start + 1,
                    i
                ))
                continue
            
            # Проверяем десятичные числа
            if line[i].isdigit() or (line[i] == '-' and i + 1 < length and line[i+1].isdigit()):
                start = i
                
                # Обрабатываем знак минус для отрицательных чисел
                if line[i] == '-':
                    i += 1
                
                # Считываем цифры
                while i < length and line[i].isdigit():
                    i += 1
                
                # Проверяем наличие суффикса типа (u32, i64 и т.д.)
                suffix_start = i
                while i < length and line[i].isalpha():
                    i += 1
                
                number = line[start:i]
                suffix = line[suffix_start:i] if suffix_start < i else ""
                
                # Проверяем суффикс
                if suffix:
                    if suffix in self.integer_types:
                        tokens.append(Token(
                            TokenType.DECIMAL_LITERAL,
                            number,
                            line_num,
                            start + 1,
                            i
                        ))
                    elif suffix in self.invalid_types:
                        tokens.append(Token(
                            self.invalid_types[suffix],
                            number,
                            line_num,
                            start + 1,
                            i
                        ))
                    else:
                        tokens.append(Token(
                            TokenType.ERROR,
                            number,
                            line_num,
                            start + 1,
                            i
                        ))
                else:
                    tokens.append(Token(
                        TokenType.DECIMAL_LITERAL,
                        number,
                        line_num,
                        start + 1,
                        i
                    ))
                continue
            
            # Проверяем идентификаторы, ключевые слова, типы и булевы литералы
            if line[i].isalpha() or line[i] == '_':
                start = i
                while i < length and (line[i].isalnum() or line[i] == '_'):
                    i += 1
                
                word = line[start:i]
                
                # Проверяем булевы литералы (true/false)
                if word in self.bool_literals:
                    tokens.append(Token(
                        self.bool_literals[word],
                        word,
                        line_num,
                        start + 1,
                        i
                    ))
                # Проверяем ключевое слово const
                elif word in self.keywords:
                    tokens.append(Token(
                        self.keywords[word],
                        word,
                        line_num,
                        start + 1,
                        i
                    ))
                # Проверяем допустимые целочисленные типы
                elif word in self.integer_types:
                    tokens.append(Token(
                        self.integer_types[word],
                        word,
                        line_num,
                        start + 1,
                        i
                    ))
                # Проверяем недопустимые типы
                elif word in self.invalid_types:
                    tokens.append(Token(
                        self.invalid_types[word],
                        word,
                        line_num,
                        start + 1,
                        i
                    ))
                else:
                    # Обычный идентификатор (имя константы)
                    tokens.append(Token(
                        TokenType.IDENTIFIER,
                        word,
                        line_num,
                        start + 1,
                        i
                    ))
                continue
            
            # Если дошли до сюда - недопустимый символ
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
        """
        Проверяет, является ли последовательность токенов корректным
        объявлением целочисленной константы в Rust
        """
        # Фильтруем только значимые токены (убираем пробелы и переводы строк)
        significant_tokens = [t for t in tokens 
                              if t.type not in [TokenType.SPACE, TokenType.TAB, TokenType.NEWLINE]]
        
        if len(significant_tokens) < 5:
            return False, "Недостаточно токенов для объявления константы"
        
        # Ожидаемая структура: const ИДЕНТИФИКАТОР : ТИП = ЗНАЧЕНИЕ ;
        if len(significant_tokens) != 7:
            return False, f"Неверное количество элементов. Ожидается 7, получено {len(significant_tokens)}"
        
        # Проверка позиции 1: const
        if significant_tokens[0].type != TokenType.CONST:
            return False, f"Ошибка: ожидается 'const', получен {significant_tokens[0].type.description}"
        
        # Проверка позиции 2: идентификатор
        if significant_tokens[1].type != TokenType.IDENTIFIER:
            return False, f"Ошибка: ожидается идентификатор (имя константы), получен {significant_tokens[1].type.description}"
        
        # Проверка позиции 3: :
        if significant_tokens[2].type != TokenType.COLON:
            return False, f"Ошибка: ожидается ':', получен {significant_tokens[2].type.description}"
        
        # Проверка позиции 4: целочисленный тип (коды 2-13)
        type_token = significant_tokens[3]
        if type_token.type.code < 2 or type_token.type.code > 13:
            if type_token.type.code >= 30:
                return False, f"Ошибка: недопустимый тип '{type_token.value}'. Требуется целочисленный тип (i8, i16, i32, i64, i128, isize, u8, u16, u32, u64, u128, usize)"
            else:
                return False, f"Ошибка: ожидается целочисленный тип, получен {type_token.type.description}"
        
        # Проверка позиции 5: =
        if significant_tokens[4].type != TokenType.ASSIGN:
            return False, f"Ошибка: ожидается '=', получен {significant_tokens[4].type.description}"
        
        # Проверка позиции 6: целочисленный литерал (коды 18-22)
        value_token = significant_tokens[5]
        if value_token.type.code < 18 or value_token.type.code > 22:
            if value_token.type.code >= 40:
                return False, f"Ошибка: недопустимое значение '{value_token.value}'. Требуется целочисленный литерал"
            else:
                return False, f"Ошибка: ожидается целочисленный литерал, получен {value_token.type.description}"
        
        # Проверка позиции 7: ;
        if significant_tokens[6].type != TokenType.SEMICOLON:
            return False, f"Ошибка: ожидается ';', получен {significant_tokens[6].type.description}"
        
        return True, "Корректное объявление целочисленной константы"