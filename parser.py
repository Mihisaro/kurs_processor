from lexical_analyzer import TokenType

SYNC_TOKENS = {TokenType.SEMICOLON, TokenType.CONST}

class ParserError:
    def __init__(self, fragment, line, position, description):
        self.fragment = fragment
        self.line = line
        self.position = position
        self.description = description

    def __str__(self):
        return (f"[строка {self.line}, позиция {self.position}] "
                f"{self.description}: '{self.fragment}'")

class SyntaxTreeNode:
    def __init__(self, node_type, value=None, line=None, position=None):
        self.node_type = node_type
        self.value = value
        self.line = line
        self.position = position
        self.children = []

    def add_child(self, child):
        if child:
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
        self.significant_tokens = []
        self.position = 0
        self.current_token = None
        self.errors = []
        self.syntax_tree = None

    def parse(self, tokens):
        self.errors = []
        self.position = 0

        import re as _re
        self._float_before_pos = set()
        for idx, token in enumerate(tokens):
            if token.is_error:
                if _re.match(r'^\d+\.\d*$', token.value):
                    msg = f"Дробное число '{token.value}' недопустимо: используйте целое число"
                    for nxt in tokens[idx+1:]:
                        if nxt.type.name not in ('SPACE', 'TAB', 'NEWLINE') and not nxt.is_error:
                            self._float_before_pos.add(nxt.start_pos)
                            break
                else:
                    msg = f"Лексическая ошибка: недопустимый символ '{token.value}'"
                self.errors.append(ParserError(
                    token.value, token.line, token.start_pos, msg
                ))

        self.significant_tokens = [
            t for t in tokens
            if t.type not in (TokenType.SPACE, TokenType.TAB, TokenType.NEWLINE)
            and not t.is_error
        ]

        if not self.significant_tokens:
            return None, self.errors

        self._update()
        root = SyntaxTreeNode("program")

        while self.current_token:
            pos_before = self.position
            node = self._parse_one_declaration()
            if node:
                root.add_child(node)
            if self.position == pos_before:
                self._advance()

        self.syntax_tree = root
        return root, self.errors

    def _parse_one_declaration(self):
        if self.current_token.type == TokenType.CONST:
            return self._parse_body(const_token=self._consume())

        if self._declaration_ahead():
            bad = self.current_token
            self._add_error(bad, f"Ожидается ключевое слово 'const', найдено '{bad.value}'")
            self._advance()
            return self._parse_body(const_token=None)

        self._add_error(self.current_token, "Ожидается ключевое слово 'const'")
        self._synchronize()
        return None

    def _parse_body(self, const_token):
        root = SyntaxTreeNode("const_declaration")
        if const_token:
            root.add_child(SyntaxTreeNode(
                "keyword", const_token.value, const_token.line, const_token.start_pos))

        while (self.current_token
               and self.current_token.type != TokenType.IDENTIFIER
               and self.current_token.type not in SYNC_TOKENS
               and self.current_token.type != TokenType.COLON
               and self._ident_ahead()):
            self._add_error(self.current_token,
                            f"Неожиданный токен '{self.current_token.value}', ожидается идентификатор")
            self._advance()

        extra = []
        while self._cur_is(TokenType.IDENTIFIER) and self._peek_is(1, TokenType.IDENTIFIER):
            extra.append(self.current_token)
            self._advance()
        if extra:
            joined = " ".join(t.value for t in extra)
            self.errors.append(ParserError(
                joined, extra[0].line, extra[0].start_pos,
                f"Лишние идентификаторы перед именем константы: '{joined}'"
            ))

        ident = self._match(TokenType.IDENTIFIER)
        if ident:
            root.add_child(SyntaxTreeNode(
                "identifier", ident.value, ident.line, ident.start_pos))
        else:
            self._add_error(self.current_token or self._last(), "Ожидается идентификатор")
            if self._cur_is(TokenType.COLON):
                pass
            elif not self._skip_to(TokenType.COLON):
                self._synchronize()
                return root

        self._skip_junk(
            want=TokenType.COLON,
            hard_stop={TokenType.TYPE, TokenType.ASSIGN, TokenType.SEMICOLON},
            msg="Неожиданный токен '{val}' перед ':'"
        )

        if not self._match_repeated(TokenType.COLON, ":"):
            self._add_error(self.current_token or self._last(), "Пропущен ':'")

        if (self._cur_is(TokenType.ASSIGN)
                and self._peek_is(1, TokenType.IDENTIFIER)
                and self._peek_is(2, TokenType.COLON)):
            self._add_error(self.current_token,
                            f"Неожиданный токен '=' после ':', ожидается идентификатор")
            self._advance()
            late_ident = self.current_token
            self._add_error(late_ident,
                            f"Идентификатор '{late_ident.value}' должен стоять до ':', а не после")
            if not any(c.node_type == "identifier" for c in root.children):
                root.add_child(SyntaxTreeNode(
                    "identifier", late_ident.value, late_ident.line, late_ident.start_pos))
            self._advance()
            self._match_repeated(TokenType.COLON, ":")

        elif (self._cur_is(TokenType.IDENTIFIER)
                and self._peek_is(1, TokenType.COLON)):
            late_ident = self.current_token
            self._add_error(late_ident,
                            f"Идентификатор '{late_ident.value}' должен стоять до ':', а не после")
            if not any(c.node_type == "identifier" for c in root.children):
                root.add_child(SyntaxTreeNode(
                    "identifier", late_ident.value, late_ident.line, late_ident.start_pos))
            self._advance()
            self._match_repeated(TokenType.COLON, ":")

        while (self._cur_is(TokenType.ASSIGN)
               and (self._peek_is(1, TokenType.TYPE)
                    or self._peek_is(1, TokenType.IDENTIFIER))):
            self._add_error(self.current_token,
                            "Неожиданный токен '=' перед типом данных")
            self._advance()

        self._skip_junk(
            want=TokenType.TYPE,
            hard_stop={TokenType.IDENTIFIER, TokenType.ASSIGN, TokenType.SEMICOLON},
            msg="Неожиданный токен '{val}' перед типом данных"
        )

        type_tok = self._match(TokenType.TYPE)
        if type_tok:
            root.add_child(SyntaxTreeNode(
                "type", type_tok.value, type_tok.line, type_tok.start_pos))
        else:
            self._add_error(self.current_token or self._last(),
                            "Ожидается тип данных (i8, i16, i32, i64, u8, u16, u32, u64...)")
            if self._cur_is(TokenType.IDENTIFIER):
                self._advance()
            if not self._cur_is(TokenType.ASSIGN) and not self._cur_is(TokenType.NUMBER):
                if not self._cur_is(TokenType.SEMICOLON):
                    while (self.current_token
                           and self.current_token.type not in
                               (TokenType.ASSIGN, TokenType.NUMBER, *SYNC_TOKENS)):
                        self._advance()
            if self.current_token and self.current_token.type in SYNC_TOKENS and                     self.current_token.type != TokenType.SEMICOLON:
                self._synchronize()
                return root

        if not self._match_repeated(TokenType.ASSIGN, "="):
            self._add_error(self.current_token or self._last(), "Пропущен '='")

        self._skip_junk(
            want=TokenType.NUMBER,
            hard_stop={TokenType.SEMICOLON},
            msg="Неожиданный токен '{val}' перед числом"
        )

        number = self._match(TokenType.NUMBER)
        if number:
            root.add_child(SyntaxTreeNode(
                "value", number.value, number.line, number.start_pos))
        else:
            cur = self.current_token or self._last()
            is_float_before = (hasattr(self, '_float_before_pos')
                               and cur and cur.start_pos in self._float_before_pos)
            if not is_float_before:
                self._add_error(cur, "Ожидается числовой литерал")
            if not self._skip_to(TokenType.SEMICOLON):
                self._synchronize()
                return root

        self._skip_junk(
            want=TokenType.SEMICOLON,
            hard_stop=set(),
            msg="Неожиданный токен '{val}' перед ';'"
        )

        if not self._match_repeated(TokenType.SEMICOLON, ";"):
            self._add_error(self.current_token or self._last(), "Пропущен ';'")

        return root

    def _skip_junk(self, want, hard_stop, msg):
        """
        Пропускает токены != want и не из hard_stop|SYNC_TOKENS,
        НО только если want есть впереди до hard_stop|SYNC_TOKENS.
        """
        stop = hard_stop | SYNC_TOKENS
        while (self.current_token
               and self.current_token.type != want
               and self.current_token.type not in stop
               and self._lookahead(want, stop)):
            self._add_error(self.current_token, msg.replace("{val}", self.current_token.value))
            self._advance()

    def _ident_ahead(self):
        """True если IDENTIFIER есть впереди до SYNC_TOKENS (COLON не является стоп-токеном)."""
        for i in range(self.position, len(self.significant_tokens)):
            t = self.significant_tokens[i].type
            if t == TokenType.IDENTIFIER:
                return True
            if t in SYNC_TOKENS:
                return False
        return False

    def _lookahead(self, target, stop):
        """True если target есть в significant_tokens[position:] раньше любого stop."""
        for i in range(self.position, len(self.significant_tokens)):
            t = self.significant_tokens[i].type
            if t == target:
                return True
            if t in stop:
                return False
        return False

    def _skip_to(self, target_type):
        """
        Пропускает токены НАЧИНАЯ СО СЛЕДУЮЩЕГО до target_type или якоря.
        Останавливается НА target_type. Возвращает True если нашли.
        (В отличие от seek, делает хотя бы один advance перед поиском.)
        """
        self._advance()
        while self.current_token:
            if self.current_token.type == target_type:
                return True
            if self.current_token.type in SYNC_TOKENS:
                return False
            self._advance()
        return False

    def _declaration_ahead(self):
        for i in range(self.position, len(self.significant_tokens)):
            t = self.significant_tokens[i].type
            if t in (TokenType.COLON, TokenType.ASSIGN):
                return True
            if t == TokenType.CONST:
                return False
        return False

    def _synchronize(self):
        while self.current_token:
            if self.current_token.type == TokenType.SEMICOLON:
                self._advance()
                return
            if self.current_token.type == TokenType.CONST:
                return
            self._advance()

    def _match_repeated(self, token_type, symbol):
        if not self.current_token or self.current_token.type != token_type:
            return False
        start = self.current_token
        count = 0
        while self.current_token and self.current_token.type == token_type:
            count += 1
            self._advance()
        if count > 1:
            self.errors.append(ParserError(
                symbol * count, start.line, start.start_pos,
                f"Повторяющийся оператор '{symbol}' ({count} раз)"
            ))
        return True

    def _match(self, token_type):
        if self.current_token and self.current_token.type == token_type:
            tok = self.current_token
            self._advance()
            return tok
        return None

    def _consume(self):
        tok = self.current_token
        self._advance()
        return tok

    def _cur_is(self, token_type):
        return self.current_token and self.current_token.type == token_type

    def _peek_is(self, offset, token_type):
        idx = self.position + offset
        if idx < len(self.significant_tokens):
            return self.significant_tokens[idx].type == token_type
        return False

    def _last(self):
        return self.significant_tokens[-1] if self.significant_tokens else None

    def _add_error(self, token, description):
        if token:
            self.errors.append(ParserError(
                token.value, token.line, token.start_pos, description))
        else:
            self.errors.append(ParserError("EOF", 0, 0, description))

    def _advance(self):
        self.position += 1
        self._update()

    def _update(self):
        if self.position < len(self.significant_tokens):
            self.current_token = self.significant_tokens[self.position]
        else:
            self.current_token = None