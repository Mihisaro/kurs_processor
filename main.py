import sys
from PyQt6.QtWidgets import QApplication
from editor import TextEditor

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setApplicationName("Compiler")
    
    window = TextEditor()
    window.show()
    
    sys.exit(app.exec())