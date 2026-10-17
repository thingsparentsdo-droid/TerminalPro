import sys
import time
from difflib import SequenceMatcher
import re
from PyQt6.QtWidgets import QApplication, QCompleter, QHBoxLayout, QLineEdit, QMainWindow, QVBoxLayout, QWidget, QTextEdit, QLabel
from PyQt6.QtGui import QFont
from PyQt6.QtCore import QEventLoop, QStringListModel, QTimer, Qt
from typing import Optional


outputArea: Optional[QTextEdit] = None
textBox: Optional[QLineEdit] = None
promptLabel: Optional[QLabel] = None
player = None
userSubmittedInput: Optional[str] = None
inputSubmitted = False
app: Optional[QApplication] = None
window: Optional[QMainWindow] = None


class CommandInput(QLineEdit):
    def __init__(self, suggestions: tuple[tuple[str, str, str], ...]):
        super().__init__()
        self.suggestions = suggestions
        self.suggestions_enabled = False
        self.completion_tokens: dict[str, str] = {}
        self.completion_model = QStringListModel(self)
        self.completer = QCompleter(self.completion_model, self)
        self.completer.setWidget(self)
        self.completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.completer.activated[str].connect(self.applyCompletion)
        self.textEdited.connect(self.updateCompletions)

    def setSuggestionsEnabled(self, enabled: bool) -> None:
        self.suggestions_enabled = enabled
        self.completer.popup().hide()

    def updateCompletions(self, text: str) -> None:
        if not self.suggestions_enabled:
            return

        match = re.match(r"\s*(\S+)", text)
        if match is None:
            self.completer.popup().hide()
            return

        typed_command = match.group(1).rstrip(":").casefold()
        matches: list[tuple[float, str, str]] = []
        for insertion, description, syntax in self.suggestions:
            command_name = insertion.strip().rstrip(":").casefold()
            if command_name.startswith(typed_command):
                score = 2.0 + len(typed_command) / max(len(command_name), 1)
            else:
                score = SequenceMatcher(None, typed_command, command_name).ratio()
                if score < 0.55:
                    continue
            display = f"{description} — {syntax}"
            matches.append((score, display, insertion))

        matches.sort(key=lambda item: (-item[0], item[1]))
        self.completion_tokens = {
            display: insertion for _, display, insertion in matches[:6]
        }
        self.completion_model.setStringList(list(self.completion_tokens))
        if self.completion_tokens:
            self.completer.setCompletionPrefix("")
            self.completer.setCurrentRow(0)
            self.completer.complete()
        else:
            self.completer.popup().hide()

    def applyCompletion(self, display: str) -> None:
        insertion = self.completion_tokens.get(display)
        match = re.match(r"(\s*)(\S+)", self.text())
        if insertion is None or match is None:
            return

        suffix = self.text()[match.end():]
        if insertion.endswith(" ") and suffix.startswith(" "):
            suffix = suffix[1:]
        self.setText(f"{match.group(1)}{insertion}{suffix}")
        self.setCursorPosition(len(self.text()) - len(suffix))
        self.completer.popup().hide()

    def keyPressEvent(self, event) -> None:
        if event.key() == Qt.Key.Key_Tab and self.suggestions_enabled:
            popup = self.completer.popup()
            display = self.completer.currentCompletion()
            if not display and self.completion_tokens:
                display = next(iter(self.completion_tokens))
            if display:
                self.applyCompletion(display)
            event.accept()
            return
        super().keyPressEvent(event)


def clear():
    global outputArea
    if outputArea:
        outputArea.clear()

def printOutput(text):
    global outputArea
    if outputArea:
        outputArea.append(str(text))
        processEvents()


def typeOutput(text, delay=0.025):
    global outputArea
    if not outputArea:
        return

    message = str(text)
    for char in message:
        outputArea.insertPlainText(char)
        processEvents()
        time.sleep(delay)

    outputArea.insertPlainText("\n")
    processEvents()


def processEvents():
    """Process Qt events to update the display"""
    global app
    if app:
        app.processEvents()


def inputText(prompt=""):
    global outputArea, textBox, promptLabel, userSubmittedInput, inputSubmitted
    if promptLabel is None or textBox is None:
        raise RuntimeError("GUI must be set up before requesting input")
    prompt_widget = promptLabel
    input_widget = textBox
    prompt_widget.setText(prompt)
    userSubmittedInput = None
    inputSubmitted = False
    input_widget.setFocus()

    loop = QEventLoop()

    def checkInput():
        global inputSubmitted
        if inputSubmitted:
            loop.quit()

    timer = QTimer()
    timer.timeout.connect(checkInput)
    timer.start(50)

    loop.exec()
    timer.stop()

    return userSubmittedInput

def onSubmit():
    global textBox, outputArea, promptLabel, userSubmittedInput, inputSubmitted
    if textBox is None or outputArea is None or promptLabel is None:
        raise RuntimeError("GUI must be set up before submitting input")
    input_widget = textBox
    output_widget = outputArea
    prompt_widget = promptLabel
    userInput = input_widget.text()
    if not userInput:
        return
    output_widget.append(f"{prompt_widget.text()} {userInput}")
    userSubmittedInput = userInput
    inputSubmitted = True
    input_widget.clear()


def setupGUI(command_suggestions: tuple[tuple[str, str, str], ...] = ()):
    global app, window, outputArea, textBox, promptLabel, mainLayout

    app = QApplication(sys.argv)
    window = QMainWindow()
    window.setWindowTitle("Terminal Pro")
    window.setMinimumSize(1200, 600)
    window.setStyleSheet("background-color: rgb(0, 0, 0);")

    mainLayout = QVBoxLayout()
    container = QWidget()
    container.setLayout(mainLayout)
    window.setCentralWidget(container)

    outputArea = QTextEdit()
    outputArea.setReadOnly(True)
    outputArea.setFont(QFont("Roboto Mono", 12))
    outputArea.setStyleSheet("""
        QTextEdit {
            background-color: rgb(30, 30, 30);
            color: #f2f8fc;
            border: 1px solid #444;
            border-radius: 12px;
            padding: 15px;
            margin-bottom: 20px;
            line-height: 1.6;
        }
    """)
    mainLayout.addWidget(outputArea, 1)

    promptLayout = QHBoxLayout()
    promptLayout.setSpacing(8)

    promptLabel = QLabel(">>")
    promptLabel.setFont(QFont("Roboto Mono", 16))
    promptLabel.setStyleSheet("color: #f2f8fc;")
    promptLayout.addWidget(promptLabel, 0)

    textBox = CommandInput(command_suggestions)
    textBox.setPlaceholderText("Type commands here... (Tab for suggestions)")
    textBox.setFont(QFont("Roboto Mono", 16))
    textBox.returnPressed.connect(onSubmit)
    textBox.setMinimumHeight(50)
    textBox.setMaximumHeight(50)
    textBox.setStyleSheet("""
        QLineEdit {
            background-color: rgb(30, 30, 30);
            color: #f2f8fc;
            border: 1px solid #444;
            border-radius: 24px;
            padding: 12px 20px;
            font-size: 16px;
        }
        QLineEdit:focus {
            background-color: rgb(50, 50, 50);
            border: 1px solid #4f91b8;
        }
    """)
    promptLayout.addWidget(textBox, 1)
    mainLayout.addLayout(promptLayout, 0)

    mainLayout.setContentsMargins(40, 40, 40, 40)
    mainLayout.setSpacing(0)

    window.show()


def enableCommandSuggestions(enabled: bool = True) -> None:
    if isinstance(textBox, CommandInput):
        textBox.setSuggestionsEnabled(enabled)


def runApp():
    global app
    if app is None:
        raise RuntimeError("GUI must be set up before running the application")
    sys.exit(app.exec())

    
