"""Utilitários para Messageboxes - PySide6"""

from PySide6.QtWidgets import QMessageBox, QWidget


def showinfo(title: str, message: str, parent: QWidget | None = None):
    QMessageBox.information(parent, title, message)


def showwarning(title: str, message: str, parent: QWidget | None = None):
    QMessageBox.warning(parent, title, message)


def showerror(title: str, message: str, parent: QWidget | None = None):
    QMessageBox.critical(parent, title, message)


def askyesno(title: str, message: str, parent: QWidget | None = None) -> bool:
    resposta = QMessageBox.question(
        parent,
        title,
        message,
        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        QMessageBox.StandardButton.No,
    )
    return resposta == QMessageBox.StandardButton.Yes


def askokcancel(title: str, message: str, parent: QWidget | None = None) -> bool:
    resposta = QMessageBox.question(
        parent,
        title,
        message,
        QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Cancel,
        QMessageBox.StandardButton.Cancel,
    )
    return resposta == QMessageBox.StandardButton.Ok


def askretrycancel(title: str, message: str, parent: QWidget | None = None) -> bool:
    resposta = QMessageBox.question(
        parent,
        title,
        message,
        QMessageBox.StandardButton.Retry | QMessageBox.StandardButton.Cancel,
        QMessageBox.StandardButton.Cancel,
    )
    return resposta == QMessageBox.StandardButton.Retry


def askyesnocancel(title: str, message: str, parent: QWidget | None = None) -> bool | None:
    resposta = QMessageBox.question(
        parent,
        title,
        message,
        QMessageBox.StandardButton.Yes
        | QMessageBox.StandardButton.No
        | QMessageBox.StandardButton.Cancel,
        QMessageBox.StandardButton.Cancel,
    )
    if resposta == QMessageBox.StandardButton.Cancel:
        return None
    return resposta == QMessageBox.StandardButton.Yes
