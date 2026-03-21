from lexical_analyzer import TokenType


class ParserError:
    def __init__(self, fragment, line, position, description):
        self.fragment = fragment
        self.line = line
        self.position = position
        self.description = description

    def __str__(self):
        return f"[строка {self.line}, позиция {self.position}] {self.description}: '{self.fragment}'"


class SyntaxTreeNode:
    def __init__(self, node_type, value=None, line=None, position=None):
        self.node_type = node_type
        self.value = value
        self.line = line
        self.position = position
        self.children = []

    def add_child(self, child):
        self.children.append(child)

    def __str__(self, level=0):
        indent = "  " * level
        result = f"{indent}{self.node_type}"
        if self.value:
            result += f": {self.value}"
        if self.line:
            result += f" (строка {self.line})"
        result += "\n"
        for child in self.children:
            result += child.__str__(level + 1)
        return result


class Parser:
    def __init__(self):
        self.tokens = []
        self.significant_tokens = []
        self.position = 0
        self.current_token = None
        self.errors = []
        self.syntax_tree = None

    # =========================================
    # ОСНОВНОЙ МЕТОД
    # =========================================
    def parse(self, tokens):
        self.tokens = tokens
        self.errors = []
        self.position = 0

        # 1. Лексические ошибки
        for token in tokens:
            if token.is_error:
                self.errors.append(ParserError(
                    fragment=token.value,
                    line=token.line,
                    position=token.start_pos,
                    description=f"Лексическая ошибка: недопустимый символ '{token.value}'"
                ))

        # 2. Фильтрация
        self.significant_tokens = [
            t for t in tokens
            if t.type not in [TokenType.SPACE, TokenType.TAB, TokenType.NEWLINE]
            and not t.is_error
        ]

        if not self.significant_tokens:
            return None, self.errors

        self.update_current_token()

        # 3. Парсинг
        self.syntax_tree = self.parse_const_declaration()

        return self.syntax_tree, self.errors

    # =========================================
    # ГРАММАТИКА
    # =========================================
    def parse_const_declaration(self):
        root = SyntaxTreeNode("const_declaration")

        # 🔥 FIX: если нет const → синхронизация
        if not self.match_token(TokenType.CONST):
            self.missing_token_error("const")
            self.synchronize()
            return root
        else:
            token = self.previous_token()
            root.add_child(SyntaxTreeNode("keyword", token.value, token.line, token.start_pos))

        # identifier
        ident = self.match_token(TokenType.IDENTIFIER)
        if ident:
            root.add_child(SyntaxTreeNode("identifier", ident.value, ident.line, ident.start_pos))
        else:
            self.error_here("Ожидается идентификатор")

        # :
        self.expect(TokenType.COLON, ":")

        # type
        type_token = self.match_token(TokenType.TYPE)
        if type_token:
            root.add_child(SyntaxTreeNode("type", type_token.value,
                                         type_token.line, type_token.start_pos))
        else:
            self.error_here("Ожидается тип данных")

        # =
        self.expect(TokenType.ASSIGN, "=")

        # number
        number = self.match_token(TokenType.NUMBER)
        if number:
            root.add_child(SyntaxTreeNode("value", number.value,
                                         number.line, number.start_pos))
        else:
            self.error_here("Ожидается число")

        # ;
        self.expect(TokenType.SEMICOLON, ";")

        return root

    # =========================================
    # EXPECT
    # =========================================
    def expect(self, token_type, symbol):
        if self.match_with_repetition_check(token_type, symbol):
            return True

        self.missing_token_error(symbol)
        return False

    # =========================================
    # ПОВТОРЫ === ::: ;;;
    # =========================================
    def match_with_repetition_check(self, token_type, symbol):
        if not self.current_token:
            return False

        if self.current_token.type != token_type:
            return False

        start_token = self.current_token
        count = 0

        while self.current_token and self.current_token.type == token_type:
            count += 1
            self.advance()

        if count > 1:
            self.errors.append(ParserError(
                fragment=symbol * count,
                line=start_token.line,
                position=start_token.start_pos,
                description=f"Повторяющийся оператор '{symbol}' ({count} раз) недопустим"
            ))

        return True

    # =========================================
    # 🔥 АНТИ-КАСКАД (НОВОЕ)
    # =========================================
    def synchronize(self):
        """Перепрыгиваем к ; или следующему const"""
        while self.current_token:
            if self.current_token.type == TokenType.SEMICOLON:
                self.advance()
                break

            if self.current_token.type == TokenType.CONST:
                break

            self.advance()


    def missing_token_error(self, expected):
        if self.current_token:
            self.errors.append(ParserError(
                fragment=self.current_token.value,
                line=self.current_token.line,
                position=self.current_token.start_pos,
                description=f"Пропущен '{expected}' перед '{self.current_token.value}'"
            ))
        else:
            self.add_error_at_end(expected)

    def error_here(self, message):
        if self.current_token:
            self.add_error(self.current_token, message)
            self.advance()
        else:
            self.add_error_at_end(message)

    def add_error(self, token, description):
        self.errors.append(ParserError(
            fragment=token.value,
            line=token.line,
            position=token.start_pos,
            description=description
        ))

    def add_error_at_end(self, expected):
        line = 1
        pos = 1

        if self.significant_tokens:
            last = self.significant_tokens[-1]
            line = last.line
            pos = last.end_pos + 1

        self.errors.append(ParserError(
            fragment="EOF",
            line=line,
            position=pos,
            description=f"Ожидается {expected}, но достигнут конец файла"
        ))

    # =========================================
    # УТИЛИТЫ
    # =========================================
    def match_token(self, expected_type):
        if self.current_token and self.current_token.type == expected_type:
            token = self.current_token
            self.advance()
            return token
        return None

    def previous_token(self):
        if self.position > 0:
            return self.significant_tokens[self.position - 1]
        return None

    def advance(self):
        self.position += 1
        self.update_current_token()

    def update_current_token(self):
        if self.position < len(self.significant_tokens):
            self.current_token = self.significant_tokens[self.position]
        else:
            self.current_token = None