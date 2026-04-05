from lexical_analyzer import TokenType

SYNC_TOKENS = {TokenType.SEMICOLON, TokenType.CONST}

class ParserError:
    def __init__(self, fragment, line, position, description, *, cursor_only=False):
        self.fragment = fragment
        self.line = line
        self.position = position
        self.description = description
        self.cursor_only = cursor_only

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
        self._float_end_pos = set()
        lex_errors = []
        for idx, token in enumerate(tokens):
            if token.is_error:
                if _re.match(r'^\d+\.\d*$', token.value):
                    msg = f"Дробное число '{token.value}' недопустимо: используйте целое число"
                    found_next = False
                    for nxt in tokens[idx+1:]:
                        if nxt.type.name not in ('SPACE', 'TAB', 'NEWLINE') and not nxt.is_error:
                            self._float_before_pos.add(nxt.start_pos)
                            found_next = True
                            break
                    if not found_next:
                        self._float_end_pos.add(token.end_pos)
                else:
                    msg = f"Лексическая ошибка: недопустимый символ '{token.value}'"
                lex_errors.append(ParserError(
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
        self.errors.extend(lex_errors)
        self.errors.sort(key=lambda e: (e.line, e.position))
        return root, self.errors

    def _looks_like_const_keyword_typo(self, token):
        """Идентификатор вроде 'cons' вместо ключевого слова const."""
        if not token or token.type != TokenType.IDENTIFIER:
            return False
        v = token.value.lower()
        return v.startswith("con") and len(v) <= 5

    def _ident_then_type_before_sync(self):
        """
        Схема «имя тип значение» без ':' и '=' (например MARKS i32 100;).
        До ближайшего ';' или const есть TYPE после первого идентификатора.
        """
        if not self.current_token or self.current_token.type != TokenType.IDENTIFIER:
            return False
        for i in range(self.position + 1, len(self.significant_tokens)):
            t = self.significant_tokens[i].type
            if t == TokenType.CONST:
                return False
            if t == TokenType.SEMICOLON:
                return False
            if t == TokenType.TYPE:
                return True
        return False

    def _should_parse_declaration_body(self):
        """
        True только если дальше похоже на тело const IDENT : TYPE = NUM ;
        (без этого полный _parse_body даёт каскад ложных ошибок на мусор после ';').
        """
        t = self.current_token
        if not t:
            return False
        if t.type == TokenType.IDENTIFIER and self._peek_is(1, TokenType.COLON):
            return True
        if t.type == TokenType.TYPE and self._peek_is(1, TokenType.COLON):
            return True
        if (t.type == TokenType.TYPE
                and self._peek_is(1, TokenType.TYPE)
                and self._peek_is(2, TokenType.ASSIGN)):
            return True
        if t.type == TokenType.IDENTIFIER and self._ident_then_type_before_sync():
            return True
        if t.type == TokenType.IDENTIFIER and self._declaration_ahead():
            return True
        return False

    def _parse_one_declaration(self):
        """
        Разбираем одно объявление вида: const IDENT : TYPE = NUMBER ;
        Полный разбор тела только если токены действительно похожи на объявление;
        иначе одна ошибка и синхронизация (без каскада «пропущен :, =, …»).
        """
        if not self.current_token:
            return None

        if self.current_token.type == TokenType.SEMICOLON:
            self._advance()
            return None

        if self.current_token.type == TokenType.CONST:
            return self._parse_body(const_token=self._consume())

        # cons, cont, … — лексер даёт IDENTIFIER, а не CONST
        if self._looks_like_const_keyword_typo(self.current_token):
            bad = self.current_token
            self._add_error(
                bad, f"Ожидается ключевое слово 'const', найдено '{bad.value}'"
            )
            self._advance()
            return self._parse_body(const_token=None)

        if self._should_parse_declaration_body():
            bad = self.current_token
            looks_like_const_typo = (bad.type == TokenType.IDENTIFIER
                                     and bad.value.lower().startswith('con'))
            # i32: i32 = … или i32 i32 = … — «пропущен const», первое слово — имя (лексема TYPE)
            if bad.type == TokenType.TYPE and (
                    self._peek_is(1, TokenType.COLON)
                    or (self._peek_is(1, TokenType.TYPE)
                        and self._peek_is(2, TokenType.ASSIGN))):
                self._add_error(
                    bad, "Пропущено ключевое слово 'const'",
                    cursor_only=True, const_insert=True)
            elif bad.type == TokenType.IDENTIFIER and not looks_like_const_typo:
                self._add_error(
                    bad, "Пропущено ключевое слово 'const'",
                    cursor_only=True, const_insert=True)
                if not (self._peek_is(1, TokenType.COLON)
                        or self._peek_is(1, TokenType.TYPE)
                        or self._peek_is(1, TokenType.IDENTIFIER)):
                    self._advance()
            else:
                self._add_error(bad, f"Ожидается ключевое слово 'const', найдено '{bad.value}'")
                self._advance()
            return self._parse_body(const_token=None)

        bad = self.current_token
        self._add_error(bad, f"Неожиданный токен '{bad.value}'")
        self._synchronize()
        return None

    def _parse_body(self, const_token):
        """
        Разбираем тело: [IDENT] [:] [TYPE] [=] [NUMBER] [;]
        Каждый отсутствующий обязательный элемент — отдельная ошибка.
        Не прерываемся в середине — проходим всё объявление до конца.
        """
        root = SyntaxTreeNode("const_declaration")
        if const_token:
            root.add_child(SyntaxTreeNode(
                "keyword", const_token.value, const_token.line, const_token.start_pos))

        # ── 1. Идентификатор ─────────────────────────────────────────────────
        while (self.current_token
               and self.current_token.type != TokenType.IDENTIFIER
               and self.current_token.type not in SYNC_TOKENS
               and self.current_token.type != TokenType.COLON
               and not (self._cur_is(TokenType.TYPE) and self._peek_is(1, TokenType.COLON))
               and not (self._cur_is(TokenType.TYPE)
                        and self._peek_is(1, TokenType.TYPE)
                        and self._peek_is(2, TokenType.ASSIGN))
               and self._ident_ahead()):
            self._add_error(self.current_token,
                            f"Неожиданный токен '{self.current_token.value}', ожидается идентификатор")
            self._advance()

        ident = self._match(TokenType.IDENTIFIER)
        if not ident and self._cur_is(TokenType.TYPE):
            if self._peek_is(1, TokenType.COLON):
                ident = self._consume()
            elif (self._peek_is(1, TokenType.TYPE)
                  and self._peek_is(2, TokenType.ASSIGN)):
                ident = self._consume()
        if ident:
            root.add_child(SyntaxTreeNode(
                "identifier", ident.value, ident.line, ident.start_pos))
        else:
            cur = self.current_token or self._last()
            if self.current_token:
                self._add_error(cur, "Ожидается идентификатор", cursor_only=True)
            elif cur:
                self._add_error(cur, "Ожидается идентификатор", cursor_only=True, insert_after=True)
            else:
                self._add_error(None, "Ожидается идентификатор")

        # ── 2. Двоеточие ':' ─────────────────────────────────────────────────
        self._skip_junk(
            want=TokenType.COLON,
            hard_stop={TokenType.TYPE, TokenType.ASSIGN, TokenType.SEMICOLON},
            msg="Неожиданный токен '{val}' перед ':'"
        )

        colon_found = self._match_repeated(TokenType.COLON, ":")
        if not colon_found:
            self._add_error(
                self.current_token or self._last(), "Пропущен ':'", cursor_only=True)

        # ── 3. Тип данных ─────────────────────────────────────────────────────
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
            self._add_error(
                self.current_token or self._last(),
                "Ожидается тип данных (i8, i16, i32, i64, u8, u16, u32, u64...)",
                cursor_only=True)
            if self._cur_is(TokenType.IDENTIFIER):
                self._advance()

        # ── 4. Оператор присваивания '=' ──────────────────────────────────────
        self._skip_junk(
            want=TokenType.ASSIGN,
            hard_stop={TokenType.NUMBER, TokenType.SEMICOLON},
            msg="Неожиданный токен '{val}' перед '='"
        )

        if not self._match_repeated(TokenType.ASSIGN, "="):
            self._add_error(
                self.current_token or self._last(), "Пропущен '='", cursor_only=True)

        # ── 5. Числовой литерал ───────────────────────────────────────────────
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
            is_float = (hasattr(self, '_float_before_pos')
                        and cur and cur.start_pos in self._float_before_pos)
            is_float_at_end = (hasattr(self, '_float_end_pos')
                               and bool(self._float_end_pos))
            if not is_float and not is_float_at_end:
                self._add_error(cur, "Ожидается числовой литерал", cursor_only=True)

        # ── 6. Точка с запятой ';' ────────────────────────────────────────────
        self._skip_junk(
            want=TokenType.SEMICOLON,
            hard_stop=set(),
            msg="Неожиданный токен '{val}' перед ';'"
        )

        if not self._match_repeated(TokenType.SEMICOLON, ";"):
            cur = self.current_token or self._last()
            if cur and cur.type != TokenType.SEMICOLON:
                if self.current_token is not None:
                    self._add_error(cur, "Пропущен ';'", cursor_only=True)
                else:
                    self._add_error(cur, "Пропущен ';'", cursor_only=True, insert_after=True)
            self._synchronize()

        return root

    # ── Вспомогательные методы ────────────────────────────────────────────────

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

    def _peek_type_at(self, offset):
        idx = self.position + offset
        if idx < len(self.significant_tokens):
            return self.significant_tokens[idx].type
        return None

    def _ident_ahead(self):
        """True если IDENTIFIER есть впереди до SYNC_TOKENS."""
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
        """Пропускает токены до target_type или якоря. Возвращает True если нашли."""
        self._advance()
        while self.current_token:
            if self.current_token.type == target_type:
                return True
            if self.current_token.type in SYNC_TOKENS:
                return False
            self._advance()
        return False

    def _declaration_ahead(self):
        """
        True если впереди есть признаки объявления константы.
        Критерии (до ближайшего CONST/;):
          - есть ':'
          - или есть TYPE + '='
          - или есть 2+ IDENTIFIER + '='
        """
        has_colon = False
        has_type = False
        has_assign = False
        ident_count = 0
        for i in range(self.position, len(self.significant_tokens)):
            t = self.significant_tokens[i].type
            if t == TokenType.COLON:
                has_colon = True
            elif t == TokenType.TYPE:
                has_type = True
            elif t == TokenType.ASSIGN:
                has_assign = True
            elif t == TokenType.IDENTIFIER:
                ident_count += 1
            if t == TokenType.CONST:
                return False
            if t in SYNC_TOKENS:
                break
        return has_colon or (has_type and has_assign) or (ident_count >= 2 and has_assign)

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

    def _add_error(self, token, description, *, cursor_only=False,
                   insert_after=False, const_insert=False):
        if token:
            line = token.line
            if cursor_only:
                if const_insert:
                    col = max(1, token.start_pos - 1)
                elif insert_after:
                    col = token.end_pos + 1
                else:
                    col = token.start_pos
            else:
                col = token.start_pos
            self.errors.append(ParserError(
                token.value, line, col, description, cursor_only=cursor_only))
        else:
            self.errors.append(ParserError(
                "EOF", 0, 0, description, cursor_only=cursor_only))

    def _advance(self):
        self.position += 1
        self._update()

    def _update(self):
        if self.position < len(self.significant_tokens):
            self.current_token = self.significant_tokens[self.position]
        else:
            self.current_token = None