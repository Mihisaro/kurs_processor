import sys
from PyQt6.QtWidgets import *
from PyQt6.QtCore import *
from PyQt6.QtGui import *

class TextEditor(QMainWindow):
    def __init__(self):
        super().__init__()
        self.current_file = None
        self.initUI()
        
    def initUI(self):
        # Настройка окна
        self.setWindowTitle("Текстовый редактор кода")
        self.setGeometry(100, 100, 1000, 700)
        
        # Разрешаем изменение размера окна
        self.setMinimumSize(750, 500)  # Минимальный размер окна
        
        # Центральный виджет
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # Создаем текстовое поле и область вывода
        self.text_edit = QTextEdit()
        self.text_edit.setPlaceholderText("Введите текст программы...")
        
        self.output_area = QTextEdit()
        self.output_area.setPlaceholderText("Результаты работы языкового процессора...")
        self.output_area.setReadOnly(True)
        
        # Создаем сплиттер с возможностью изменения размеров
        splitter = QSplitter(Qt.Orientation.Vertical)
        splitter.addWidget(self.text_edit)
        splitter.addWidget(self.output_area)
        
        # Устанавливаем начальные размеры (пропорционально)
        splitter.setSizes([int(self.height() * 0.6), int(self.height() * 0.4)])
        
        # Настраиваем свойства сплиттера для лучшей адаптивности
        splitter.setChildrenCollapsible(False)  # Запрещаем сворачивание областей
        splitter.setHandleWidth(5)  # Ширина ползунка для удобства
        
        main_layout.addWidget(splitter)
        
        # Создаем панель инструментов
        self.create_toolbar()
        
        # Создаем меню
        self.create_menu()
        
        # Статус бар
        self.statusBar().showMessage("Готов")
        
        # Сохраняем ссылку на сплиттер для доступа в других методах
        self.splitter = splitter
        
    def resizeEvent(self, event):
        """Обработчик изменения размера окна"""
        super().resizeEvent(event)
        
        # Адаптируем размеры сплиттера при изменении окна
        if hasattr(self, 'splitter'):
            current_sizes = self.splitter.sizes()
            total_height = sum(current_sizes)
            
            # Если общая высота изменилась, пересчитываем пропорции
            if total_height != self.height():
                # Сохраняем пропорции 60/40
                self.splitter.setSizes([int(self.height() * 0.6), int(self.height() * 0.4)])
    
    def create_menu(self):
        menubar = self.menuBar()
        
        # Меню Файл
        file_menu = menubar.addMenu("Файл")
        
        new_action = QAction("Новый", self)
        new_action.setShortcut("Ctrl+N")
        new_action.triggered.connect(self.new_file)
        file_menu.addAction(new_action)
        
        open_action = QAction("Открыть", self)
        open_action.setShortcut("Ctrl+O")
        open_action.triggered.connect(self.open_file)
        file_menu.addAction(open_action)
        
        save_action = QAction("Сохранить", self)
        save_action.setShortcut("Ctrl+S")
        save_action.triggered.connect(self.save_file)
        file_menu.addAction(save_action)
        
        save_as_action = QAction("Сохранить как", self)
        save_as_action.setShortcut("Ctrl+Shift+S")
        save_as_action.triggered.connect(self.save_as_file)
        file_menu.addAction(save_as_action)
        
        file_menu.addSeparator()
        
        exit_action = QAction("Выход", self)
        exit_action.setShortcut("Ctrl+Q")
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)
        
        # Меню Правка
        edit_menu = menubar.addMenu("Правка")
        
        undo_action = QAction("Отмена", self)
        undo_action.setShortcut("Ctrl+Z")
        undo_action.triggered.connect(self.text_edit.undo)
        edit_menu.addAction(undo_action)
        
        redo_action = QAction("Повтор", self)
        redo_action.setShortcut("Ctrl+Y")
        redo_action.triggered.connect(self.text_edit.redo)
        edit_menu.addAction(redo_action)
        
        edit_menu.addSeparator()
        
        cut_action = QAction("Вырезать", self)
        cut_action.setShortcut("Ctrl+X")
        cut_action.triggered.connect(self.text_edit.cut)
        edit_menu.addAction(cut_action)
        
        copy_action = QAction("Копировать", self)
        copy_action.setShortcut("Ctrl+C")
        copy_action.triggered.connect(self.text_edit.copy)
        edit_menu.addAction(copy_action)
        
        paste_action = QAction("Вставить", self)
        paste_action.setShortcut("Ctrl+V")
        paste_action.triggered.connect(self.text_edit.paste)
        edit_menu.addAction(paste_action)
        
        delete_action = QAction("Удалить", self)
        delete_action.setShortcut("Del")
        delete_action.triggered.connect(self.delete_text)
        edit_menu.addAction(delete_action)
        
        edit_menu.addSeparator()
        
        select_all_action = QAction("Выделить всё", self)
        select_all_action.setShortcut("Ctrl+A")
        select_all_action.triggered.connect(self.text_edit.selectAll)
        edit_menu.addAction(select_all_action)
        
        # Меню Вид (новое меню для управления отображением)
        view_menu = menubar.addMenu("Вид")
        
        # Действия для изменения соотношения областей
        split_60_40 = QAction("Области 60/40", self)
        split_60_40.triggered.connect(lambda: self.splitter.setSizes([int(self.height() * 0.6), int(self.height() * 0.4)]))
        view_menu.addAction(split_60_40)
        
        split_50_50 = QAction("Области 50/50", self)
        split_50_50.triggered.connect(lambda: self.splitter.setSizes([int(self.height() * 0.5), int(self.height() * 0.5)]))
        view_menu.addAction(split_50_50)
        
        split_70_30 = QAction("Области 70/30", self)
        split_70_30.triggered.connect(lambda: self.splitter.setSizes([int(self.height() * 0.7), int(self.height() * 0.3)]))
        view_menu.addAction(split_70_30)
        
        view_menu.addSeparator()
        
        # Действие для сброса размеров окна
        reset_size_action = QAction("Сбросить размер окна", self)
        reset_size_action.triggered.connect(lambda: self.setGeometry(100, 100, 1000, 700))
        view_menu.addAction(reset_size_action)
        
        # Меню Пуск
        run_menu = menubar.addMenu("Пуск")
        
        run_action = QAction("Запустить", self)
        run_action.setShortcut("F5")
        run_action.triggered.connect(self.run_analyzer)
        run_menu.addAction(run_action)
        
        # Меню Справка
        help_menu = menubar.addMenu("Справка")
        
        help_action = QAction("Справка", self)
        help_action.setShortcut("F1")
        help_action.triggered.connect(self.show_help)
        help_menu.addAction(help_action)
        
        about_action = QAction("О программе", self)
        about_action.triggered.connect(self.show_about)
        help_menu.addAction(about_action)
        
    def create_colored_icon(self, text, color, bg_color=Qt.GlobalColor.white):
        """Создает цветную иконку с текстом"""
        pixmap = QPixmap(32, 32)
        pixmap.fill(Qt.GlobalColor.transparent)
        
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Рисуем круглый фон
        painter.setBrush(QColor(bg_color))
        painter.setPen(QPen(QColor(color), 2))
        painter.drawEllipse(2, 2, 28, 28)
        
        # Рисуем текст
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
        
        # 1) Создание документа - синий
        new_btn = QAction(self.create_colored_icon("+", "#0078D7", "#E6F2FF"), "Новый", self)
        new_btn.setToolTip("Создать новый документ (Ctrl+N)")
        new_btn.triggered.connect(self.new_file)
        toolbar.addAction(new_btn)
        
        # 2) Открытие документа - зеленый
        open_btn = QAction(self.create_colored_icon("📂", "#107C10", "#E6FFE6"), "Открыть", self)
        open_btn.setToolTip("Открыть документ (Ctrl+O)")
        open_btn.triggered.connect(self.open_file)
        toolbar.addAction(open_btn)
        
        # 3) Сохранение - голубой
        save_btn = QAction(self.create_colored_icon("💾", "#0099BC", "#E6F3FF"), "Сохранить", self)
        save_btn.setToolTip("Сохранить документ (Ctrl+S)")
        save_btn.triggered.connect(self.save_file)
        toolbar.addAction(save_btn)
        
        toolbar.addSeparator()
        
        # 4) Отмена - оранжевый
        undo_btn = QAction(self.create_colored_icon("↩", "#D83B01", "#FFF2E6"), "Отмена", self)
        undo_btn.setToolTip("Отменить последнее действие (Ctrl+Z)")
        undo_btn.triggered.connect(self.text_edit.undo)
        toolbar.addAction(undo_btn)
        
        # 5) Повтор - оранжевый
        redo_btn = QAction(self.create_colored_icon("↪", "#D83B01", "#FFF2E6"), "Повтор", self)
        redo_btn.setToolTip("Повторить последнее действие (Ctrl+Y)")
        redo_btn.triggered.connect(self.text_edit.redo)
        toolbar.addAction(redo_btn)
        
        toolbar.addSeparator()
        
        # 6) Копировать - фиолетовый
        copy_btn = QAction(self.create_colored_icon("📋", "#881798", "#F3E6FF"), "Копировать", self)
        copy_btn.setToolTip("Копировать выделенный текст (Ctrl+C)")
        copy_btn.triggered.connect(self.text_edit.copy)
        toolbar.addAction(copy_btn)
        
        # 7) Вырезать - красный
        cut_btn = QAction(self.create_colored_icon("✂", "#E81123", "#FFE6E6"), "Вырезать", self)
        cut_btn.setToolTip("Вырезать выделенный текст (Ctrl+X)")
        cut_btn.triggered.connect(self.text_edit.cut)
        toolbar.addAction(cut_btn)
        
        # 8) Вставить - розовый
        paste_btn = QAction(self.create_colored_icon("📌", "#E3008C", "#FFE6F3"), "Вставить", self)
        paste_btn.setToolTip("Вставить текст из буфера (Ctrl+V)")
        paste_btn.triggered.connect(self.text_edit.paste)
        toolbar.addAction(paste_btn)
        
        toolbar.addSeparator()
        
        # 9) Запуск анализатора - зеленый
        run_btn = QAction(self.create_colored_icon("▶", "#107C10", "#E6FFE6"), "Пуск", self)
        run_btn.setToolTip("Запустить синтаксический анализ (F5)")
        run_btn.triggered.connect(self.run_analyzer)
        toolbar.addAction(run_btn)
        
        toolbar.addSeparator()
        
        # 10) Справка - синий
        help_btn = QAction(self.create_colored_icon("?", "#0078D7", "#E6F2FF"), "Справка", self)
        help_btn.setToolTip("Вызов справки (F1)")
        help_btn.triggered.connect(self.show_help)
        toolbar.addAction(help_btn)
        
        # 11) О программе - серый
        about_btn = QAction(self.create_colored_icon("i", "#666666", "#F0F0F0"), "О программе", self)
        about_btn.setToolTip("Информация о программе")
        about_btn.triggered.connect(self.show_about)
        toolbar.addAction(about_btn)
        
        # Добавляем растягивающийся пробел для адаптивности
        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        toolbar.addWidget(spacer)
        
        # Добавляем информацию о размере окна
        self.size_label = QLabel(f"Размер: {self.width()}x{self.height()}")
        self.size_label.setStyleSheet("padding: 5px; color: gray;")
        toolbar.addWidget(self.size_label)
        
        # Обновляем информацию о размере при изменении
        self.update_size_label()
    
    def update_size_label(self):
        """Обновляет информацию о размере окна"""
        if hasattr(self, 'size_label'):
            self.size_label.setText(f"Размер: {self.width()}x{self.height()}")
    
    def resizeEvent(self, event):
        """Обработчик изменения размера окна"""
        super().resizeEvent(event)
        self.update_size_label()
    
    def delete_text(self):
        cursor = self.text_edit.textCursor()
        if cursor.hasSelection():
            cursor.removeSelectedText()
    
    def run_analyzer(self):
        """Запуск синтаксического анализатора"""
        text = self.text_edit.toPlainText()
        self.output_area.clear()
        self.output_area.append("🔍 ЗАПУСК СИНТАКСИЧЕСКОГО АНАЛИЗА")
        self.output_area.append("=" * 50)
        self.output_area.append("Анализируемый текст:")
        self.output_area.append(text)
        self.output_area.append("=" * 50)
        self.output_area.append("Результаты анализа:")
        self.output_area.append("• Строк для анализа: " + str(len(text.split('\n'))))
        self.output_area.append("• Символов: " + str(len(text)))
        self.output_area.append("• Анализ завершен (заглушка)")
        self.output_area.append("=" * 50)
        self.statusBar().showMessage("Синтаксический анализ выполнен")
    
    def new_file(self):
        if self.maybe_save():
            self.text_edit.clear()
            self.current_file = None
            self.statusBar().showMessage("Новый файл создан")
    
    def open_file(self):
        if self.maybe_save():
            file_path, _ = QFileDialog.getOpenFileName(
                self, "Открыть файл", "", 
                "Текстовые файлы (*.txt);;Все файлы (*)"
            )
            if file_path:
                try:
                    with open(file_path, 'r', encoding='utf-8') as file:
                        self.text_edit.setText(file.read())
                    self.current_file = file_path
                    self.statusBar().showMessage(f"Открыто: {file_path}")
                except Exception as e:
                    QMessageBox.critical(self, "Ошибка", f"Не удалось открыть файл: {str(e)}")
    
    def save_file(self):
        if self.current_file:
            try:
                with open(self.current_file, 'w', encoding='utf-8') as file:
                    file.write(self.text_edit.toPlainText())
                self.statusBar().showMessage(f"Сохранено: {self.current_file}")
            except Exception as e:
                QMessageBox.critical(self, "Ошибка", f"Не удалось сохранить файл: {str(e)}")
        else:
            self.save_as_file()
    
    def save_as_file(self):
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Сохранить файл", "", 
            "Текстовые файлы (*.txt);;Все файлы (*)"
        )
        if file_path:
            try:
                with open(file_path, 'w', encoding='utf-8') as file:
                    file.write(self.text_edit.toPlainText())
                self.current_file = file_path
                self.statusBar().showMessage(f"Сохранено: {file_path}")
            except Exception as e:
                QMessageBox.critical(self, "Ошибка", f"Не удалось сохранить файл: {str(e)}")
    
    def maybe_save(self):
        if not self.text_edit.document().isModified():
            return True
        
        reply = QMessageBox.question(
            self, "Подтверждение",
            "Документ был изменен. Сохранить изменения?",
            QMessageBox.StandardButton.Yes | 
            QMessageBox.StandardButton.No | 
            QMessageBox.StandardButton.Cancel
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            self.save_file()
            return True
        elif reply == QMessageBox.StandardButton.No:
            return True
        else:
            return False
    
    def show_help(self):
        QMessageBox.information(self, "Справка", 
            "РУКОВОДСТВО ПОЛЬЗОВАТЕЛЯ\n\n"
            "Функции программы:\n\n"
            "📄 Файл:\n"
            "  • Новый (Ctrl+N) - создать новый документ\n"
            "  • Открыть (Ctrl+O) - открыть существующий файл\n"
            "  • Сохранить (Ctrl+S) - сохранить текущий документ\n"
            "  • Сохранить как (Ctrl+Shift+S) - сохранить под новым именем\n"
            "  • Выход (Ctrl+Q) - выход из программы\n\n"
            "✏️ Правка:\n"
            "  • Отмена (Ctrl+Z) - отменить последнее действие\n"
            "  • Повтор (Ctrl+Y) - повторить отмененное действие\n"
            "  • Вырезать (Ctrl+X) - вырезать выделенный текст\n"
            "  • Копировать (Ctrl+C) - копировать выделенный текст\n"
            "  • Вставить (Ctrl+V) - вставить текст из буфера\n"
            "  • Удалить (Del) - удалить выделенный текст\n"
            "  • Выделить всё (Ctrl+A) - выделить весь текст\n\n"
            "👁️ Вид:\n"
            "  • Области 60/40 - установить пропорции областей\n"
            "  • Области 50/50 - равные области\n"
            "  • Области 70/30 - увеличить область ввода\n"
            "  • Сбросить размер окна - вернуть окно к исходному размеру\n\n"
            "▶ Пуск:\n"
            "  • Запустить синтаксический анализ (F5) - анализ исходного кода\n\n"
            "❓ Справка:\n"
            "  • Справка (F1) - вызов руководства пользователя\n"
            "  • О программе - информация о программе\n\n"
            "📊 Адаптивный дизайн:\n"
            "  • Изменяйте размер окна - интерфейс подстраивается автоматически\n"
            "  • Перетаскивайте разделитель областей для изменения пропорций\n"
            "  • Текущий размер окна отображается в правой части панели инструментов")
    
    def show_about(self):
        QMessageBox.about(self, "О программе",
            "КОМПИЛЯТОР - Языковой процессор\n\n"
            "Версия: 2.0\n\n"
            "Разработчик: Учебный проект\n"
            "Год: 2024\n\n"
            "Платформа: PyQt6\n\n"
            "Особенности:\n"
            "✓ Адаптивный интерфейс\n"
            "✓ Изменяемые размеры областей\n"
            "✓ Цветные иконки\n"
            "✓ Горячие клавиши\n"
            "✓ Поддержка всех основных операций")
    
    def closeEvent(self, event):
        if self.maybe_save():
            event.accept()
        else:
            event.ignore()