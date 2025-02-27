from PyQt5.QtCore import QTime


def format_time(milliseconds):
    """Converts milliseconds to HH:MM:SS.zzz format."""
    time = QTime(0, 0, 0).addMSecs(milliseconds)
    return time.toString("hh:mm:ss.zzz")
