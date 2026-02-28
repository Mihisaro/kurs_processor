import sys
import os
from PyQt6.QtWidgets import *
from PyQt6.QtCore import *
from PyQt6.QtGui import *

class LineNumberArea(QWidget):
    """Виджет для отображения номеров строк"""
    def __init__(self, editor):
        super().__init__(editor)
        self.code_editor = editor
        
    def sizeHint(self):
        return QSize(self.code_editor.line_number_area_width(), 0)
    
    def paintEvent(self, event):
        self.code_editor.line_number_area_paint_event(event)


class CodeEditor(QPlainTextEdit):
    """Текстовый редактор с нумерацией строк"""
    def __init__(self):
        super().__init__()
        self.line_number_area = LineNumberArea(self)
        
        # Подключаем сигналы
        self.blockCountChanged.connect(self.update_line_number_area_width)
        self.updateRequest.connect(self.update_line_number_area)
        
        # Убираем подсветку текущей строки
        # self.cursorPositionChanged.connect(self.highlight_current_line)
        
        # Устанавливаем моноширинный шрифт
        font = QFont("Courier New", 12)
        font.setFixedPitch(True)
        self.setFont(font)
        
        # Настройка внешнего вида
        self.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self.update_line_number_area_width()
        
    def line_number_area_width(self):
        """Вычисляет ширину области номеров строк"""
        digits = 1
        max_num = max(1, self.blockCount())
        while max_num >= 10:
            max_num //= 10
            digits += 1
        
        space = 10 + self.fontMetrics().horizontalAdvance('9') * digits
        return space
    
    def update_line_number_area_width(self):
        """Обновляет ширину области номеров строк"""
        self.setViewportMargins(self.line_number_area_width(), 0, 0, 0)
    
    def update_line_number_area(self, rect, dy):
        """Обновляет область номеров строк при прокрутке"""
        if dy:
            self.line_number_area.scroll(0, dy)
        else:
            self.line_number_area.update(0, rect.y(), self.line_number_area.width(), rect.height())
        
        if rect.contains(self.viewport().rect()):
            self.update_line_number_area_width()
    
    def resizeEvent(self, event):
        """Обработчик изменения размера"""
        super().resizeEvent(event)
        cr = self.contentsRect()
        self.line_number_area.setGeometry(QRect(cr.left(), cr.top(), self.line_number_area_width(), cr.height()))
    
    def line_number_area_paint_event(self, event):
        """Отрисовывает номера строк"""
        painter = QPainter(self.line_number_area)
        
        # Заливаем фон таким же цветом, как панель инструментов (светло-серый)
        painter.fillRect(event.rect(), QColor(245, 245, 245))
        
        # Рисуем тонкую линию справа от номеров строк
        painter.setPen(QColor(200, 200, 200))
        painter.drawLine(self.line_number_area.width() - 1, event.rect().top(), 
                        self.line_number_area.width() - 1, event.rect().bottom())
        
        block = self.firstVisibleBlock()
        block_number = block.blockNumber()
        top = round(self.blockBoundingGeometry(block).translated(self.contentOffset()).top())
        bottom = top + round(self.blockBoundingRect(block).height())
        
        while block.isValid() and top <= event.rect().bottom():
            if block.isVisible() and bottom >= event.rect().top():
                number = str(block_number + 1)
                
                # Все номера строк одинаковым цветом
                painter.setPen(QColor(100, 100, 100))
                
                painter.drawText(0, top, self.line_number_area.width() - 5, 
                                self.fontMetrics().height(),
                                Qt.AlignmentFlag.AlignRight, number)
            
            block = block.next()
            top = bottom
            bottom = top + round(self.blockBoundingRect(block).height())
            block_number += 1


class TextEditor(QMainWindow):
    def __init__(self):
        super().__init__()
        self.current_file = None
        self.font_size = 12
        self.current_language = self.load_language()
        self.initUI()
        
    def load_language(self):
        """Загружает сохраненный язык из настроек"""
        settings = QSettings("MyApp", "TextEditor")
        return settings.value("language", "ru")
    
    def save_language(self, language):
        """Сохраняет выбранный язык в настройки"""
        settings = QSettings("MyApp", "TextEditor")
        settings.setValue("language", language)
    
    def initUI(self):
        # Настройка окна
        self.setWindowTitle(self.get_text("Текстовый редактор кода"))
        self.setGeometry(100, 100, 1000, 700)
        
        # Разрешаем изменение размера окна
        self.setMinimumSize(850, 500)
        
        # Центральный виджет
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # Создаем панель инструментов
        self.create_toolbar()
        
        # --- СОЗДАЕМ ВКЛАДКИ С РЕДАКТОРОМ ---
        
        # Главный сплиттер для разделения области редактирования и вывода
        self.main_splitter = QSplitter(Qt.Orientation.Vertical)
        
        # Верхняя часть - вкладки с текстовыми редакторами
        self.tab_widget = QTabWidget()
        self.tab_widget.setTabsClosable(True)
        self.tab_widget.tabCloseRequested.connect(self.close_tab)
        self.tab_widget.currentChanged.connect(self.tab_changed)
        
        # Создаем первую вкладку
        self.add_new_tab()
        
        # Нижняя часть - область вывода результатов
        self.output_area = QTextEdit()
        self.output_area.setPlaceholderText(self.get_text("Результаты работы языкового процессора..."))
        self.output_area.setReadOnly(True)
        
        # Добавляем виджеты в сплиттер
        self.main_splitter.addWidget(self.tab_widget)
        self.main_splitter.addWidget(self.output_area)
        
        # Устанавливаем начальные размеры
        self.main_splitter.setSizes([int(self.height() * 0.7), int(self.height() * 0.3)])
        self.main_splitter.setChildrenCollapsible(False)
        self.main_splitter.setHandleWidth(5)
        
        main_layout.addWidget(self.main_splitter)
        
        # Создаем меню
        self.create_menu()
        
        # Статус бар
        self.statusBar().showMessage(self.get_text("Готов"))
        
    def get_text(self, key):
        """Возвращает текст на выбранном языке"""
        translations = {
            "ru": {
                # Общие
                "Текстовый редактор кода": "Текстовый редактор кода",
                "Готов": "Готов",
                "Размер: {}x{}": "Размер: {}x{}",
                "Размер шрифта: {} pt": "Размер шрифта: {} pt",
                
                # Плейсхолдеры
                "Введите текст программы...": "Введите текст программы...",
                "Результаты работы языкового процессора...": "Результаты работы языкового процессора...",
                
                # Меню
                "Файл": "Файл",
                "Правка": "Правка",
                "Вид": "Вид",
                "Пуск": "Пуск",
                "Справка": "Справка",
                
                # Файл
                "Новый": "Новый",
                "Открыть": "Открыть",
                "Сохранить": "Сохранить",
                "Сохранить как": "Сохранить как",
                "Закрыть вкладку": "Закрыть вкладку",
                "Выход": "Выход",
                
                # Правка
                "Отмена": "Отмена",
                "Повтор": "Повтор",
                "Вырезать": "Вырезать",
                "Копировать": "Копировать",
                "Вставить": "Вставить",
                "Удалить": "Удалить",
                "Выделить всё": "Выделить всё",
                
                # Вид
                "Размер текста": "Размер текста",
                "Увеличить (Ctrl++)": "Увеличить (Ctrl++)",
                "Уменьшить (Ctrl+-)": "Уменьшить (Ctrl+-)",
                "Сбросить (Ctrl+0)": "Сбросить (Ctrl+0)",
                "Показать номера строк": "Показать номера строк",
                "Язык интерфейса": "Язык интерфейса",
                "Русский": "Русский",
                "Английский": "Английский",
                "Области 70/30": "Области 70/30",
                "Области 60/40": "Области 60/40",
                "Области 50/50": "Области 50/50",
                "Сбросить размер окна": "Сбросить размер окна",
                
                # Пуск
                "Запустить": "Запустить",
                
                # Справка
                "Справка": "Справка",
                "О программе": "О программе",
                
                # Диалоги
                "Открыть файл": "Открыть файл",
                "Сохранить файл": "Сохранить файл",
                "Текстовые файлы (*.txt);;Все файлы (*)": "Текстовые файлы (*.txt);;Все файлы (*)",
                "Подтверждение": "Подтверждение",
                "Документ '{}' был изменен. Сохранить изменения?": "Документ '{}' был изменен. Сохранить изменения?",
                "Ошибка": "Ошибка",
                "Не удалось открыть файл: {}": "Не удалось открыть файл: {}",
                "Не удалось сохранить файл: {}": "Не удалось сохранить файл: {}",
                
                # Статус бар
                "Новый файл создан": "Новый файл создан",
                "Открыто: {}": "Открыто: {}",
                "Сохранено: {}": "Сохранено: {}",
                "Текущий файл: {}": "Текущий файл: {}",
                "Новый документ": "Новый документ",
                "Синтаксический анализ выполнен": "Синтаксический анализ выполнен",
                
                # Вкладки
                "Новый документ {}": "Новый документ {}",
                
                # Анализатор
                "🔍 ЗАПУСК СИНТАКСИЧЕСКОГО АНАЛИЗА": "🔍 ЗАПУСК СИНТАКСИЧЕСКОГО АНАЛИЗА",
                "Анализируемый текст (вкладка: {}):": "Анализируемый текст (вкладка: {}):",
                "Результаты анализа:": "Результаты анализа:",
                "• Строк для анализа: {}": "• Строк для анализа: {}",
                "• Символов: {}": "• Символов: {}",
                "• Анализ завершен (заглушка)": "• Анализ завершен (заглушка)",
                
                # Подсказки на панели инструментов
                "Создать новый документ (Ctrl+N)": "Создать новый документ (Ctrl+N)",
                "Открыть документ (Ctrl+O)": "Открыть документ (Ctrl+O)",
                "Сохранить документ (Ctrl+S)": "Сохранить документ (Ctrl+S)",
                "Отменить последнее действие (Ctrl+Z)": "Отменить последнее действие (Ctrl+Z)",
                "Повторить последнее действие (Ctrl+Y)": "Повторить последнее действие (Ctrl+Y)",
                "Копировать выделенный текст (Ctrl+C)": "Копировать выделенный текст (Ctrl+C)",
                "Вырезать выделенный текст (Ctrl+X)": "Вырезать выделенный текст (Ctrl+X)",
                "Вставить текст из буфера (Ctrl+V)": "Вставить текст из буфера (Ctrl+V)",
                "Уменьшить размер текста (Ctrl+-)": "Уменьшить размер текста (Ctrl+-)",
                "Увеличить размер текста (Ctrl++)": "Увеличить размер текста (Ctrl++)",
                "Запустить синтаксический анализ (F5)": "Запустить синтаксический анализ (F5)",
                "Вызов справки (F1)": "Вызов справки (F1)",
                "Информация о программе": "Информация о программе",
                
                # Сообщение о перезапуске
                "Смена языка": "Смена языка",
                "Для применения нового языка необходимо перезапустить приложение. Перезапустить сейчас?": "Для применения нового языка необходимо перезапустить приложение. Перезапустить сейчас?",
            },
            "en": {
                # Общие
                "Текстовый редактор кода": "Code Editor",
                "Готов": "Ready",
                "Размер: {}x{}": "Size: {}x{}",
                "Размер шрифта: {} pt": "Font size: {} pt",
                
                # Плейсхолдеры
                "Введите текст программы...": "Enter program text...",
                "Результаты работы языкового процессора...": "Language processor results...",
                
                # Меню
                "Файл": "File",
                "Правка": "Edit",
                "Вид": "View",
                "Пуск": "Run",
                "Справка": "Help",
                
                # Файл
                "Новый": "New",
                "Открыть": "Open",
                "Сохранить": "Save",
                "Сохранить как": "Save As",
                "Закрыть вкладку": "Close Tab",
                "Выход": "Exit",
                
                # Правка
                "Отмена": "Undo",
                "Повтор": "Redo",
                "Вырезать": "Cut",
                "Копировать": "Copy",
                "Вставить": "Paste",
                "Удалить": "Delete",
                "Выделить всё": "Select All",
                
                # Вид
                "Размер текста": "Text Size",
                "Увеличить (Ctrl++)": "Increase (Ctrl++)",
                "Уменьшить (Ctrl+-)": "Decrease (Ctrl+-)",
                "Сбросить (Ctrl+0)": "Reset (Ctrl+0)",
                "Язык интерфейса": "Interface Language",
                "Русский": "Russian",
                "Английский": "English",
                "Области 70/30": "Areas 70/30",
                "Области 60/40": "Areas 60/40",
                "Области 50/50": "Areas 50/50",
                "Сбросить размер окна": "Reset Window Size",
                
                # Пуск
                "Запустить": "Run",
                
                # Справка
                "Справка": "Help",
                "О программе": "About",
                
                # Диалоги
                "Открыть файл": "Open File",
                "Сохранить файл": "Save File",
                "Текстовые файлы (*.txt);;Все файлы (*)": "Text files (*.txt);;All files (*)",
                "Подтверждение": "Confirmation",
                "Документ '{}' был изменен. Сохранить изменения?": "Document '{}' has been modified. Save changes?",
                "Ошибка": "Error",
                "Не удалось открыть файл: {}": "Could not open file: {}",
                "Не удалось сохранить файл: {}": "Could not save file: {}",
                
                # Статус бар
                "Новый файл создан": "New file created",
                "Открыто: {}": "Opened: {}",
                "Сохранено: {}": "Saved: {}",
                "Текущий файл: {}": "Current file: {}",
                "Новый документ": "New document",
                "Синтаксический анализ выполнен": "Syntax analysis completed",
                
                # Вкладки
                "Новый документ {}": "New document {}",
                
                # Анализатор
                "🔍 ЗАПУСК СИНТАКСИЧЕСКОГО АНАЛИЗА": "🔍 SYNTAX ANALYSIS START",
                "Анализируемый текст (вкладка: {}):": "Analyzed text (tab: {}):",
                "Результаты анализа:": "Analysis results:",
                "• Строк для анализа: {}": "• Lines to analyze: {}",
                "• Символов: {}": "• Characters: {}",
                "• Анализ завершен (заглушка)": "• Analysis completed (stub)",
                
                # Подсказки на панели инструментов
                "Создать новый документ (Ctrl+N)": "Create new document (Ctrl+N)",
                "Открыть документ (Ctrl+O)": "Open document (Ctrl+O)",
                "Сохранить документ (Ctrl+S)": "Save document (Ctrl+S)",
                "Отменить последнее действие (Ctrl+Z)": "Undo last action (Ctrl+Z)",
                "Повторить последнее действие (Ctrl+Y)": "Redo last action (Ctrl+Y)",
                "Копировать выделенный текст (Ctrl+C)": "Copy selected text (Ctrl+C)",
                "Вырезать выделенный текст (Ctrl+X)": "Cut selected text (Ctrl+X)",
                "Вставить текст из буфера (Ctrl+V)": "Paste text from clipboard (Ctrl+V)",
                "Уменьшить размер текста (Ctrl+-)": "Decrease text size (Ctrl+-)",
                "Увеличить размер текста (Ctrl++)": "Increase text size (Ctrl++)",
                "Запустить синтаксический анализ (F5)": "Run syntax analysis (F5)",
                "Вызов справки (F1)": "Show help (F1)",
                "Информация о программе": "About program",
                
                # Сообщение о перезапуске
                "Смена языка": "Language Change",
                "Для применения нового языка необходимо перезапустить приложение. Перезапустить сейчас?": "To apply the new language, you need to restart the application. Restart now?",
            }
        }
        
        return translations[self.current_language].get(key, key)
    
    def change_language(self, language):
        """Изменяет язык интерфейса"""
        if language != self.current_language:
            reply = QMessageBox.question(
                self, 
                self.get_text("Смена языка"),
                self.get_text("Для применения нового языка необходимо перезапустить приложение. Перезапустить сейчас?"),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            
            if reply == QMessageBox.StandardButton.Yes:
                self.save_language(language)
                QProcess.startDetached(sys.executable, sys.argv)
                sys.exit()
    
    def toggle_line_numbers(self):
        """Включает/выключает отображение номеров строк"""
        current_editor = self.get_current_text_edit()
        if current_editor:
            # В нашем редакторе номера строк всегда включены
            pass
    
    def add_new_tab(self, content="", filename=None):
        """Добавляет новую вкладку с текстовым редактором"""
        text_edit = CodeEditor()
        text_edit.setPlainText(content)
        
        # Устанавливаем размер шрифта
        font = QFont("Courier New", self.font_size)
        font.setFixedPitch(True)
        text_edit.setFont(font)
        
        # Подключаем сигнал изменения текста
        text_edit.textChanged.connect(lambda: self.update_tab_title(text_edit))
        
        # Определяем название вкладки
        if filename:
            tab_name = os.path.basename(filename)
            text_edit.setProperty("file_path", filename)
        else:
            tab_name = self.get_text("Новый документ {}").format(self.tab_widget.count() + 1)
            text_edit.setProperty("file_path", None)
        
        # Добавляем вкладку
        tab_index = self.tab_widget.addTab(text_edit, tab_name)
        self.tab_widget.setCurrentIndex(tab_index)
        
        return text_edit
    
    def get_current_text_edit(self):
        """Возвращает текущий текстовый редактор"""
        if self.tab_widget and self.tab_widget.currentWidget():
            return self.tab_widget.currentWidget()
        return None
    
    def close_tab(self, index):
        """Закрывает вкладку"""
        if self.tab_widget.count() <= 1:
            if self.maybe_save_tab(index):
                self.tab_widget.removeTab(index)
                self.add_new_tab()
        else:
            if self.maybe_save_tab(index):
                self.tab_widget.removeTab(index)
    
    def tab_changed(self, index):
        """Обработчик смены вкладки"""
        text_edit = self.tab_widget.widget(index)
        if text_edit:
            file_path = text_edit.property("file_path")
            if file_path:
                self.statusBar().showMessage(self.get_text("Текущий файл: {}").format(file_path))
            else:
                self.statusBar().showMessage(self.get_text("Новый документ"))
    
    def update_tab_title(self, text_edit):
        """Обновляет заголовок вкладки"""
        index = self.tab_widget.indexOf(text_edit)
        if index >= 0:
            current_title = self.tab_widget.tabText(index)
            if not current_title.endswith("*"):
                self.tab_widget.setTabText(index, current_title + "*")
    
    def maybe_save_tab(self, index):
        """Проверяет, нужно ли сохранить изменения"""
        text_edit = self.tab_widget.widget(index)
        if not text_edit.document().isModified():
            return True
        
        tab_name = self.tab_widget.tabText(index).rstrip("*")
        reply = QMessageBox.question(
            self, self.get_text("Подтверждение"),
            self.get_text("Документ '{}' был изменен. Сохранить изменения?").format(tab_name),
            QMessageBox.StandardButton.Yes | 
            QMessageBox.StandardButton.No | 
            QMessageBox.StandardButton.Cancel
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            return self.save_current_file()
        elif reply == QMessageBox.StandardButton.No:
            return True
        else:
            return False
    
    def update_font_size(self):
        """Обновляет размер шрифта"""
        font = QFont("Courier New", self.font_size)
        font.setFixedPitch(True)
        for i in range(self.tab_widget.count()):
            text_edit = self.tab_widget.widget(i)
            text_edit.setFont(font)
    
    def resizeEvent(self, event):
        """Обработчик изменения размера окна"""
        super().resizeEvent(event)
        self.update_size_label()
    
    def create_menu(self):
        menubar = self.menuBar()
        menubar.clear()
        
        # Меню Файл
        file_menu = menubar.addMenu(self.get_text("Файл"))
        
        new_action = QAction(self.get_text("Новый"), self)
        new_action.setShortcut("Ctrl+N")
        new_action.triggered.connect(self.new_file)
        file_menu.addAction(new_action)
        
        open_action = QAction(self.get_text("Открыть"), self)
        open_action.setShortcut("Ctrl+O")
        open_action.triggered.connect(self.open_file)
        file_menu.addAction(open_action)
        
        save_action = QAction(self.get_text("Сохранить"), self)
        save_action.setShortcut("Ctrl+S")
        save_action.triggered.connect(self.save_file)
        file_menu.addAction(save_action)
        
        save_as_action = QAction(self.get_text("Сохранить как"), self)
        save_as_action.setShortcut("Ctrl+Shift+S")
        save_as_action.triggered.connect(self.save_as_file)
        file_menu.addAction(save_as_action)
        
        file_menu.addSeparator()
        
        close_tab_action = QAction(self.get_text("Закрыть вкладку"), self)
        close_tab_action.setShortcut("Ctrl+W")
        close_tab_action.triggered.connect(lambda: self.close_tab(self.tab_widget.currentIndex()))
        file_menu.addAction(close_tab_action)
        
        file_menu.addSeparator()
        
        exit_action = QAction(self.get_text("Выход"), self)
        exit_action.setShortcut("Ctrl+Q")
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)
        
        # Меню Правка
        edit_menu = menubar.addMenu(self.get_text("Правка"))
        
        undo_action = QAction(self.get_text("Отмена"), self)
        undo_action.setShortcut("Ctrl+Z")
        undo_action.triggered.connect(lambda: self.get_current_text_edit().undo() if self.get_current_text_edit() else None)
        edit_menu.addAction(undo_action)
        
        redo_action = QAction(self.get_text("Повтор"), self)
        redo_action.setShortcut("Ctrl+Y")
        redo_action.triggered.connect(lambda: self.get_current_text_edit().redo() if self.get_current_text_edit() else None)
        edit_menu.addAction(redo_action)
        
        edit_menu.addSeparator()
        
        cut_action = QAction(self.get_text("Вырезать"), self)
        cut_action.setShortcut("Ctrl+X")
        cut_action.triggered.connect(lambda: self.get_current_text_edit().cut() if self.get_current_text_edit() else None)
        edit_menu.addAction(cut_action)
        
        copy_action = QAction(self.get_text("Копировать"), self)
        copy_action.setShortcut("Ctrl+C")
        copy_action.triggered.connect(lambda: self.get_current_text_edit().copy() if self.get_current_text_edit() else None)
        edit_menu.addAction(copy_action)
        
        paste_action = QAction(self.get_text("Вставить"), self)
        paste_action.setShortcut("Ctrl+V")
        paste_action.triggered.connect(lambda: self.get_current_text_edit().paste() if self.get_current_text_edit() else None)
        edit_menu.addAction(paste_action)
        
        delete_action = QAction(self.get_text("Удалить"), self)
        delete_action.setShortcut("Del")
        delete_action.triggered.connect(self.delete_text)
        edit_menu.addAction(delete_action)
        
        edit_menu.addSeparator()
        
        select_all_action = QAction(self.get_text("Выделить всё"), self)
        select_all_action.setShortcut("Ctrl+A")
        select_all_action.triggered.connect(lambda: self.get_current_text_edit().selectAll() if self.get_current_text_edit() else None)
        edit_menu.addAction(select_all_action)
        
        # Меню Вид
        view_menu = menubar.addMenu(self.get_text("Вид"))
        
        # Подменю для размера текста
        text_size_menu = view_menu.addMenu(self.get_text("Размер текста"))
        
        increase_font = QAction(self.get_text("Увеличить (Ctrl++)"), self)
        increase_font.setShortcut("Ctrl++")
        increase_font.triggered.connect(self.increase_font_size)
        text_size_menu.addAction(increase_font)
        
        decrease_font = QAction(self.get_text("Уменьшить (Ctrl+-)"), self)
        decrease_font.setShortcut("Ctrl+-")
        decrease_font.triggered.connect(self.decrease_font_size)
        text_size_menu.addAction(decrease_font)
        
        reset_font = QAction(self.get_text("Сбросить (Ctrl+0)"), self)
        reset_font.setShortcut("Ctrl+0")
        reset_font.triggered.connect(self.reset_font_size)
        text_size_menu.addAction(reset_font)
        
        text_size_menu.addSeparator()
        
        font_sizes = [8, 9, 10, 11, 12, 14, 16, 18, 20, 22, 24, 26, 28, 36, 48, 72]
        for size in font_sizes:
            size_action = QAction(f"{size}", self)
            size_action.triggered.connect(lambda checked, s=size: self.set_font_size(s))
            if size == self.font_size:
                size_action.setCheckable(True)
                size_action.setChecked(True)
            text_size_menu.addAction(size_action)
        
        view_menu.addSeparator()
        
        # Нумерация строк (всегда включена)
        line_numbers_action = QAction(self.get_text("Показать номера строк"), self)
        line_numbers_action.setCheckable(True)
        line_numbers_action.setChecked(True)
        line_numbers_action.setEnabled(False)  # Всегда включено
        view_menu.addAction(line_numbers_action)
        
        view_menu.addSeparator()
        
        # Подменю для выбора языка
        language_menu = view_menu.addMenu(self.get_text("Язык интерфейса"))
        
        russian_action = QAction(self.get_text("Русский"), self)
        russian_action.setCheckable(True)
        russian_action.setChecked(self.current_language == "ru")
        russian_action.triggered.connect(lambda: self.change_language("ru"))
        language_menu.addAction(russian_action)
        
        english_action = QAction(self.get_text("Английский"), self)
        english_action.setCheckable(True)
        english_action.setChecked(self.current_language == "en")
        english_action.triggered.connect(lambda: self.change_language("en"))
        language_menu.addAction(english_action)
        
        view_menu.addSeparator()
        
        # Действия для изменения соотношения областей
        split_70_30 = QAction(self.get_text("Области 70/30"), self)
        split_70_30.triggered.connect(lambda: self.main_splitter.setSizes([int(self.height() * 0.7), int(self.height() * 0.3)]))
        view_menu.addAction(split_70_30)
        
        split_60_40 = QAction(self.get_text("Области 60/40"), self)
        split_60_40.triggered.connect(lambda: self.main_splitter.setSizes([int(self.height() * 0.6), int(self.height() * 0.4)]))
        view_menu.addAction(split_60_40)
        
        split_50_50 = QAction(self.get_text("Области 50/50"), self)
        split_50_50.triggered.connect(lambda: self.main_splitter.setSizes([int(self.height() * 0.5), int(self.height() * 0.5)]))
        view_menu.addAction(split_50_50)
        
        view_menu.addSeparator()
        
        reset_size_action = QAction(self.get_text("Сбросить размер окна"), self)
        reset_size_action.triggered.connect(lambda: self.setGeometry(100, 100, 1000, 700))
        view_menu.addAction(reset_size_action)
        
        # Меню Пуск
        run_menu = menubar.addMenu(self.get_text("Пуск"))
        
        run_action = QAction(self.get_text("Запустить"), self)
        run_action.setShortcut("F5")
        run_action.triggered.connect(self.run_analyzer)
        run_menu.addAction(run_action)
        
        # Меню Справка
        help_menu = menubar.addMenu(self.get_text("Справка"))
        
        help_action = QAction(self.get_text("Справка"), self)
        help_action.setShortcut("F1")
        help_action.triggered.connect(self.show_help)
        help_menu.addAction(help_action)
        
        about_action = QAction(self.get_text("О программе"), self)
        about_action.triggered.connect(self.show_about)
        help_menu.addAction(about_action)
        
    def create_colored_icon(self, text, color, bg_color=Qt.GlobalColor.white):
        """Создает цветную иконку"""
        pixmap = QPixmap(32, 32)
        pixmap.fill(Qt.GlobalColor.transparent)
        
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        painter.setBrush(QColor(bg_color))
        painter.setPen(QPen(QColor(color), 2))
        painter.drawEllipse(2, 2, 28, 28)
        
        painter.setPen(QColor(color))
        font = QFont("Arial", 14, QFont.Weight.Bold)
        painter.setFont(font)
        painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, text)
        
        painter.end()
        return QIcon(pixmap)
        
    def create_toolbar(self):
        toolbar = self.addToolBar("Панель инструментов")
        toolbar.setMovable(False)
        toolbar.setIconSize(QSize(32, 32))
        toolbar.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
        
        # Очищаем тулбар перед созданием
        toolbar.clear()
        
        # Кнопки
        new_btn = QAction(self.create_colored_icon("+", "#0078D7", "#E6F2FF"), self.get_text("Новый"), self)
        new_btn.setToolTip(self.get_text("Создать новый документ (Ctrl+N)"))
        new_btn.triggered.connect(self.new_file)
        toolbar.addAction(new_btn)
        
        open_btn = QAction(self.create_colored_icon("📂", "#107C10", "#E6FFE6"), self.get_text("Открыть"), self)
        open_btn.setToolTip(self.get_text("Открыть документ (Ctrl+O)"))
        open_btn.triggered.connect(self.open_file)
        toolbar.addAction(open_btn)
        
        save_btn = QAction(self.create_colored_icon("💾", "#0099BC", "#E6F3FF"), self.get_text("Сохранить"), self)
        save_btn.setToolTip(self.get_text("Сохранить документ (Ctrl+S)"))
        save_btn.triggered.connect(self.save_file)
        toolbar.addAction(save_btn)
        
        toolbar.addSeparator()
        
        undo_btn = QAction(self.create_colored_icon("↩", "#D83B01", "#FFF2E6"), self.get_text("Отмена"), self)
        undo_btn.setToolTip(self.get_text("Отменить последнее действие (Ctrl+Z)"))
        undo_btn.triggered.connect(lambda: self.get_current_text_edit().undo() if self.get_current_text_edit() else None)
        toolbar.addAction(undo_btn)
        
        redo_btn = QAction(self.create_colored_icon("↪", "#D83B01", "#FFF2E6"), self.get_text("Повтор"), self)
        redo_btn.setToolTip(self.get_text("Повторить последнее действие (Ctrl+Y)"))
        redo_btn.triggered.connect(lambda: self.get_current_text_edit().redo() if self.get_current_text_edit() else None)
        toolbar.addAction(redo_btn)
        
        toolbar.addSeparator()
        
        copy_btn = QAction(self.create_colored_icon("📋", "#881798", "#F3E6FF"), self.get_text("Копировать"), self)
        copy_btn.setToolTip(self.get_text("Копировать выделенный текст (Ctrl+C)"))
        copy_btn.triggered.connect(lambda: self.get_current_text_edit().copy() if self.get_current_text_edit() else None)
        toolbar.addAction(copy_btn)
        
        cut_btn = QAction(self.create_colored_icon("✂", "#E81123", "#FFE6E6"), self.get_text("Вырезать"), self)
        cut_btn.setToolTip(self.get_text("Вырезать выделенный текст (Ctrl+X)"))
        cut_btn.triggered.connect(lambda: self.get_current_text_edit().cut() if self.get_current_text_edit() else None)
        toolbar.addAction(cut_btn)
        
        paste_btn = QAction(self.create_colored_icon("📌", "#E3008C", "#FFE6F3"), self.get_text("Вставить"), self)
        paste_btn.setToolTip(self.get_text("Вставить текст из буфера (Ctrl+V)"))
        paste_btn.triggered.connect(lambda: self.get_current_text_edit().paste() if self.get_current_text_edit() else None)
        toolbar.addAction(paste_btn)
        
        toolbar.addSeparator()
        
        # Элементы управления размером шрифта
        font_widget = QWidget()
        font_layout = QHBoxLayout(font_widget)
        font_layout.setContentsMargins(5, 0, 5, 0)
        font_layout.setSpacing(2)
        
        font_icon = QLabel()
        font_icon.setPixmap(self.create_colored_icon("A", "#0078D7", "#E6F2FF").pixmap(24, 24))
        font_layout.addWidget(font_icon)
        
        self.font_size_combo = QComboBox()
        self.font_size_combo.setEditable(True)
        self.font_size_combo.setMinimumWidth(70)
        self.font_size_combo.setMaximumWidth(90)
        
        font_sizes = [8, 9, 10, 11, 12, 14, 16, 18, 20, 22, 24, 26, 28, 36, 48, 72]
        for size in font_sizes:
            self.font_size_combo.addItem(str(size))
        
        self.font_size_combo.setCurrentText(str(self.font_size))
        self.font_size_combo.setMaxVisibleItems(15)
        self.font_size_combo.currentTextChanged.connect(self.on_font_size_changed)
        self.font_size_combo.lineEdit().returnPressed.connect(self.on_font_size_entered)
        
        font_layout.addWidget(self.font_size_combo)
        
        decrease_btn = QToolButton()
        decrease_btn.setText("−")
        decrease_btn.setToolTip(self.get_text("Уменьшить размер текста (Ctrl+-)"))
        decrease_btn.clicked.connect(self.decrease_font_size)
        decrease_btn.setFixedSize(24, 24)
        font_layout.addWidget(decrease_btn)
        
        increase_btn = QToolButton()
        increase_btn.setText("+")
        increase_btn.setToolTip(self.get_text("Увеличить размер текста (Ctrl++)"))
        increase_btn.clicked.connect(self.increase_font_size)
        increase_btn.setFixedSize(24, 24)
        font_layout.addWidget(increase_btn)
        
        toolbar.addWidget(font_widget)
        
        toolbar.addSeparator()
        

        
        toolbar.addSeparator()
        
        run_btn = QAction(self.create_colored_icon("▶", "#107C10", "#E6FFE6"), self.get_text("Пуск"), self)
        run_btn.setToolTip(self.get_text("Запустить синтаксический анализ (F5)"))
        run_btn.triggered.connect(self.run_analyzer)
        toolbar.addAction(run_btn)
        
        toolbar.addSeparator()
        
        help_btn = QAction(self.create_colored_icon("?", "#0078D7", "#E6F2FF"), self.get_text("Справка"), self)
        help_btn.setToolTip(self.get_text("Вызов справки (F1)"))
        help_btn.triggered.connect(self.show_help)
        toolbar.addAction(help_btn)
        
        about_btn = QAction(self.create_colored_icon("i", "#666666", "#F0F0F0"), self.get_text("О программе"), self)
        about_btn.setToolTip(self.get_text("Информация о программе"))
        about_btn.triggered.connect(self.show_about)
        toolbar.addAction(about_btn)
        
        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        toolbar.addWidget(spacer)
        
        self.size_label = QLabel(self.get_text("Размер: {}x{}").format(self.width(), self.height()))
        self.size_label.setStyleSheet("padding: 5px; color: gray;")
        toolbar.addWidget(self.size_label)
        
        self.update_size_label()
    
    def on_font_size_changed(self, text):
        try:
            size = int(text)
            if 6 <= size <= 72:
                self.set_font_size(size)
        except ValueError:
            pass
    
    def on_font_size_entered(self):
        text = self.font_size_combo.currentText()
        try:
            size = int(text)
            if 6 <= size <= 72:
                self.set_font_size(size)
            else:
                self.font_size_combo.setCurrentText(str(self.font_size))
        except ValueError:
            self.font_size_combo.setCurrentText(str(self.font_size))
    
    def increase_font_size(self):
        font_sizes = [8, 9, 10, 11, 12, 14, 16, 18, 20, 22, 24, 26, 28, 36, 48, 72]
        current_index = font_sizes.index(self.font_size) if self.font_size in font_sizes else -1
        
        if current_index < len(font_sizes) - 1:
            new_size = font_sizes[current_index + 1]
        else:
            new_size = min(self.font_size + 2, 72)
        
        self.set_font_size(new_size)
    
    def decrease_font_size(self):
        font_sizes = [8, 9, 10, 11, 12, 14, 16, 18, 20, 22, 24, 26, 28, 36, 48, 72]
        current_index = font_sizes.index(self.font_size) if self.font_size in font_sizes else -1
        
        if current_index > 0:
            new_size = font_sizes[current_index - 1]
        else:
            new_size = max(self.font_size - 2, 6)
        
        self.set_font_size(new_size)
    
    def reset_font_size(self):
        self.set_font_size(12)
    
    def set_font_size(self, size):
        self.font_size = size
        self.update_font_size()
        self.font_size_combo.setCurrentText(str(size))
        self.statusBar().showMessage(self.get_text("Размер шрифта: {} pt").format(size))
    
    def update_size_label(self):
        if hasattr(self, 'size_label'):
            self.size_label.setText(self.get_text("Размер: {}x{}").format(self.width(), self.height()))
    
    def delete_text(self):
        text_edit = self.get_current_text_edit()
        if text_edit:
            cursor = text_edit.textCursor()
            if cursor.hasSelection():
                cursor.removeSelectedText()
    
    def run_analyzer(self):
        text_edit = self.get_current_text_edit()
        if not text_edit:
            return
            
        text = text_edit.toPlainText()
        
        self.output_area.clear()
        self.output_area.append(self.get_text("🔍 ЗАПУСК СИНТАКСИЧЕСКОГО АНАЛИЗА"))
        self.output_area.append("=" * 50)
        self.output_area.append(self.get_text("Анализируемый текст (вкладка: {}):").format(
            self.tab_widget.tabText(self.tab_widget.currentIndex())))
        self.output_area.append(text)
        self.output_area.append("=" * 50)
        self.output_area.append(self.get_text("Результаты анализа:"))
        
        # Подсчет строк с учетом номеров
        lines = text.split('\n')
        self.output_area.append(self.get_text("• Строк для анализа: {}").format(len(lines)))
        self.output_area.append(self.get_text("• Символов: {}").format(len(text)))
        
        # Показываем первые 5 строк с номерами для примера
        self.output_area.append(self.get_text("• Первые строки:"))
        for i, line in enumerate(lines[:5]):
            self.output_area.append(f"{i+1:3d}: {line[:50]}")
        
        self.output_area.append(self.get_text("• Анализ завершен (заглушка)"))
        self.output_area.append("=" * 50)
        self.statusBar().showMessage(self.get_text("Синтаксический анализ выполнен"))
    
    def new_file(self):
        self.add_new_tab()
        self.statusBar().showMessage(self.get_text("Новый файл создан"))
    
    def open_file(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, self.get_text("Открыть файл"), "", 
            self.get_text("Текстовые файлы (*.txt);;Все файлы (*)")
        )
        if file_path:
            try:
                with open(file_path, 'r', encoding='utf-8') as file:
                    content = file.read()
                self.add_new_tab(content, file_path)
                self.statusBar().showMessage(self.get_text("Открыто: {}").format(file_path))
            except Exception as e:
                QMessageBox.critical(self, self.get_text("Ошибка"), 
                                    self.get_text("Не удалось открыть файл: {}").format(str(e)))
    
    def save_current_file(self):
        text_edit = self.get_current_text_edit()
        if not text_edit:
            return False
            
        file_path = text_edit.property("file_path")
        
        if file_path:
            try:
                with open(file_path, 'w', encoding='utf-8') as file:
                    file.write(text_edit.toPlainText())
                text_edit.document().setModified(False)
                current_title = self.tab_widget.tabText(self.tab_widget.currentIndex())
                self.tab_widget.setTabText(self.tab_widget.currentIndex(), current_title.rstrip("*"))
                return True
            except Exception as e:
                QMessageBox.critical(self, self.get_text("Ошибка"), 
                                    self.get_text("Не удалось сохранить файл: {}").format(str(e)))
                return False
        else:
            return self.save_as_file()
    
    def save_file(self):
        self.save_current_file()
    
    def save_as_file(self):
        text_edit = self.get_current_text_edit()
        if not text_edit:
            return False
            
        file_path, _ = QFileDialog.getSaveFileName(
            self, self.get_text("Сохранить файл"), "", 
            self.get_text("Текстовые файлы (*.txt);;Все файлы (*)")
        )
        if file_path:
            try:
                with open(file_path, 'w', encoding='utf-8') as file:
                    file.write(text_edit.toPlainText())
                text_edit.setProperty("file_path", file_path)
                text_edit.document().setModified(False)
                self.tab_widget.setTabText(self.tab_widget.currentIndex(), os.path.basename(file_path))
                self.statusBar().showMessage(self.get_text("Сохранено: {}").format(file_path))
                return True
            except Exception as e:
                QMessageBox.critical(self, self.get_text("Ошибка"), 
                                    self.get_text("Не удалось сохранить файл: {}").format(str(e)))
                return False
        return False
    
    def closeEvent(self, event):
        for i in range(self.tab_widget.count()):
            if not self.maybe_save_tab(i):
                event.ignore()
                return
        event.accept()
    
    def show_help(self):
        help_text = self.get_text("РУКОВОДСТВО ПОЛЬЗОВАТЕЛЯ") + "\n\n"
        help_text += self.get_text("Функции программы:") + "\n\n"
        help_text += self.get_text("📄 Файл:") + "\n"
        help_text += self.get_text("  • Новый (Ctrl+N) - создать новый документ в новой вкладке") + "\n"
        help_text += self.get_text("  • Открыть (Ctrl+O) - открыть файл в новой вкладке") + "\n"
        help_text += self.get_text("  • Сохранить (Ctrl+S) - сохранить текущий документ") + "\n"
        help_text += self.get_text("  • Сохранить как (Ctrl+Shift+S) - сохранить под новым именем") + "\n"
        help_text += self.get_text("  • Закрыть вкладку (Ctrl+W) - закрыть текущую вкладку") + "\n"
        help_text += self.get_text("  • Выход (Ctrl+Q) - выход из программы") + "\n\n"
        
        help_text += self.get_text("✏️ Правка:") + "\n"
        help_text += self.get_text("  • Отмена (Ctrl+Z) - отменить последнее действие") + "\n"
        help_text += self.get_text("  • Повтор (Ctrl+Y) - повторить отмененное действие") + "\n"
        help_text += self.get_text("  • Вырезать (Ctrl+X) - вырезать выделенный текст") + "\n"
        help_text += self.get_text("  • Копировать (Ctrl+C) - копировать выделенный текст") + "\n"
        help_text += self.get_text("  • Вставить (Ctrl+V) - вставить текст из буфера") + "\n"
        help_text += self.get_text("  • Удалить (Del) - удалить выделенный текст") + "\n"
        help_text += self.get_text("  • Выделить всё (Ctrl+A) - выделить весь текст") + "\n\n"
        
        help_text += self.get_text("👁️ Вид:") + "\n"
        help_text += self.get_text("  • Размер текста:") + "\n"
        help_text += self.get_text("    - Выпадающий список с размерами (8-72 pt)") + "\n"
        help_text += self.get_text("    - Кнопки + и - для изменения") + "\n"
        help_text += self.get_text("    - Можно ввести свой размер (от 6 до 72)") + "\n"
        help_text += self.get_text("  • Нумерация строк (всегда включена)") + "\n"
        help_text += self.get_text("  • Язык интерфейса:") + "\n"
        help_text += self.get_text("    - Русский / English") + "\n"
        help_text += self.get_text("  • Пропорции областей: 70/30, 60/40, 50/50") + "\n"
        help_text += self.get_text("  • Сбросить размер окна") + "\n\n"
        
        help_text += self.get_text("▶ Пуск:") + "\n"
        help_text += self.get_text("  • Запустить синтаксический анализ (F5)") + "\n\n"
        
        help_text += self.get_text("❓ Справка:") + "\n"
        help_text += self.get_text("  • Справка (F1) - вызов руководства пользователя") + "\n"
        help_text += self.get_text("  • О программе - информация о программе") + "\n\n"
        
        help_text += self.get_text("📑 Вкладки:") + "\n"
        help_text += self.get_text("  • Одновременная работа с несколькими документами") + "\n"
        help_text += self.get_text("  • Закрытие вкладок с подтверждением сохранения") + "\n"
        help_text += self.get_text("  • Звездочка (*) показывает несохраненные изменения")
        
        QMessageBox.information(self, self.get_text("Справка"), help_text)
    
    def show_about(self):
        about_text = self.get_text("КОМПИЛЯТОР - Языковой процессор") + "\n\n"
        about_text += self.get_text("Версия: 4.0") + "\n\n"
        about_text += self.get_text("Разработчик: Учебный проект") + "\n"
        about_text += self.get_text("Год: 2024") + "\n\n"
        about_text += self.get_text("Платформа: PyQt6") + "\n\n"
        about_text += self.get_text("Новые возможности:") + "\n"
        about_text += self.get_text("✓ Многодокументный интерфейс с вкладками") + "\n"
        about_text += self.get_text("✓ Одновременная работа с несколькими файлами") + "\n"
        about_text += self.get_text("✓ Нумерация строк в редакторе") + "\n"
        about_text += self.get_text("✓ Визуальная индикация несохраненных изменений (*)") + "\n"
        about_text += self.get_text("✓ Закрытие вкладок с подтверждением") + "\n"
        about_text += self.get_text("✓ Выбор языка интерфейса (русский/английский)") + "\n\n"
        about_text += self.get_text("Другие особенности:") + "\n"
        about_text += self.get_text("✓ Адаптивный интерфейс") + "\n"
        about_text += self.get_text("✓ Изменяемые размеры областей") + "\n"
        about_text += self.get_text("✓ Выпадающий список размеров текста") + "\n"
        about_text += self.get_text("✓ Цветные иконки") + "\n"
        about_text += self.get_text("✓ Горячие клавиши")
        
        QMessageBox.about(self, self.get_text("О программе"), about_text)