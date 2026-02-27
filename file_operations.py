from PyQt6.QtWidgets import QFileDialog, QMessageBox

class FileOperations:
    def __init__(self, parent):
        self.parent = parent
        self.current_file = None
    
    def new_file(self):
        if self.maybe_save():
            self.parent.text_edit.clear()
            self.current_file = None
            self.parent.statusBar().showMessage("Новый файл создан")
    
    def open_file(self):
        if self.maybe_save():
            file_path, _ = QFileDialog.getOpenFileName(
                self.parent, "Открыть файл", "", 
                "Текстовые файлы (*.txt);;Все файлы (*)"
            )
            if file_path:
                try:
                    with open(file_path, 'r', encoding='utf-8') as file:
                        self.parent.text_edit.setText(file.read())
                    self.current_file = file_path
                    self.parent.statusBar().showMessage(f"Открыто: {file_path}")
                except Exception as e:
                    QMessageBox.critical(self.parent, "Ошибка", f"Не удалось открыть файл: {str(e)}")
    
    def save_file(self):
        if self.current_file:
            try:
                with open(self.current_file, 'w', encoding='utf-8') as file:
                    file.write(self.parent.text_edit.toPlainText())
                self.parent.statusBar().showMessage(f"Сохранено: {self.current_file}")
            except Exception as e:
                QMessageBox.critical(self.parent, "Ошибка", f"Не удалось сохранить файл: {str(e)}")
        else:
            self.save_as_file()
    
    def save_as_file(self):
        file_path, _ = QFileDialog.getSaveFileName(
            self.parent, "Сохранить файл", "", 
            "Текстовые файлы (*.txt);;Все файлы (*)"
        )
        if file_path:
            try:
                with open(file_path, 'w', encoding='utf-8') as file:
                    file.write(self.parent.text_edit.toPlainText())
                self.current_file = file_path
                self.parent.statusBar().showMessage(f"Сохранено: {file_path}")
            except Exception as e:
                QMessageBox.critical(self.parent, "Ошибка", f"Не удалось сохранить файл: {str(e)}")
    
    def maybe_save(self):
        if not self.parent.text_edit.document().isModified():
            return True
        
        reply = QMessageBox.question(
            self.parent, "Подтверждение",
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