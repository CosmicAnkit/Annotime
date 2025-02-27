from PyQt5.QtWidgets import QMessageBox

def show_error(message):
    """Displays an error message in a popup."""
    msg_box = QMessageBox()
    msg_box.setIcon(QMessageBox.Critical)
    msg_box.setText("Error")
    msg_box.setInformativeText(message)
    msg_box.setStandardButtons(QMessageBox.Ok)
    msg_box.exec_()
