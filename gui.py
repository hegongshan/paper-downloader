import sys
import os
import logging
from PyQt5.QtCore import QThread, pyqtSignal, pyqtSlot, QMutex, QWaitCondition, Qt
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QFileDialog, QTextEdit, QMessageBox,QGridLayout,QGroupBox
)

import utils
import venue


# -------------------------------------------
# 在GUI中显示日志的Logging Handler
class QtLogHandler(logging.Handler):
    def __init__(self, signal):
        super().__init__()
        self.signal = signal

    def emit(self, record):
        msg = self.format(record)
        self.signal.emit(msg)


# -------------------------------------------
# 任务执行的工作线程
class DownloaderThread(QThread):
    log_signal = pyqtSignal(str)
    error_signal = pyqtSignal(str)
    finished_signal = pyqtSignal(str)

    def __init__(self, venue_name, save_dir, year, sleep_time_per_paper=0.2, volume=None,
                 http_proxy=None, https_proxy=None, parallel=False):
        super().__init__()
        self.venue_name = venue_name
        self.save_dir = save_dir
        self.year = year
        self.sleep_time_per_paper = sleep_time_per_paper
        self.volume = volume
        self.http_proxy = http_proxy
        self.https_proxy = https_proxy
        self.parallel = parallel

        self.paused = False
        self.stop_flag = False
        self.mutex = QMutex()
        self.pause_condition = QWaitCondition()

    def pause(self):
        self.mutex.lock()
        self.paused = True
        self.mutex.unlock()

    def resume(self):
        self.mutex.lock()
        self.paused = False
        self.pause_condition.wakeAll()
        self.mutex.unlock()

    def check_paused(self):
        self.mutex.lock()
        while self.paused:
            self.pause_condition.wait(self.mutex)
        self.mutex.unlock()

    def run(self):
        try:
            logger = logging.getLogger()
            logger.setLevel(logging.INFO)
            # 清除原有handler，添加我们的handler
            for h in logger.handlers[:]:
                logger.removeHandler(h)

            stream_handler = QtLogHandler(self.log_signal)
            stream_handler.setFormatter(logging.Formatter('%(asctime)s [%(levelname)s] %(message)s'))
            logger.addHandler(stream_handler)

            # 设置代理
            proxies = {}
            if self.http_proxy:
                proxies['http'] = self.http_proxy
            if self.https_proxy:
                proxies['https'] = self.https_proxy

            # 解析venue
            venue_name_lower = self.venue_name.lower()
            venue_publisher = venue.parse_venue(venue_name_lower)
            if not venue_publisher:
                logging.error(f'Unsupported venue: {venue_name_lower}')
                return None

            # 实例化publisher
            publisher = venue_publisher(
                save_dir=self.save_dir,
                sleep_time_per_paper=self.sleep_time_per_paper,
                venue_name=venue_name_lower,
                year=self.year if self.year else None,
                volume=self.volume if self.volume else None,
                parallel=self.parallel,
                proxies=proxies if proxies else None
            )

            # 注意：目前没有对publisher内部流程进行暂停逻辑的插入
            # 如需暂停，需要在publisher.process()内部适当位置调用self.check_paused()

            publisher.process()

            self.finished_signal.emit("Download Finished.")

        except Exception as e:
            self.error_signal.emit(f"Error: {str(e)}")


# -------------------------------------------
# GUI类定义
class PaperDownloaderGUI(QWidget):
    def __init__(self):
        super().__init__()
        self.init_ui()

    def init_ui(self):
        self.setWindowTitle('Paper Bulk Downloader')
        self.setStyleSheet("""
            QWidget {
                background-color: #f9f9f9;
                font-family: Arial, sans-serif;
                font-size: 14px;
            }
            QLineEdit, QPushButton, QTextEdit {
                border: 1px solid #cccccc;
                border-radius: 5px;
                padding: 6px;
                background-color: #ffffff;
            }
            QPushButton {
                background-color: #007BFF;
                color: white;
                border: 1px solid #0056b3;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #0056b3;
            }
            QPushButton:pressed {
                background-color: #003f7f;
                border: 1px solid #002a5b;
            }
            QPushButton:disabled {
                background-color: #d6d6d6;
                color: #a9a9a9;
            }
            QLabel {
                font-weight: bold;
                color: #333333;
            }
            QGroupBox {
                border: 1px solid #cccccc;
                border-radius: 8px;
                margin-top: 10px;
                padding: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top center;
                color: #333333;
                font-weight: bold;
                padding: 0 5px;
            }
            QTextEdit {
                border: 1px solid #cccccc;
                border-radius: 5px;
                background-color: #ffffff;
            }
        """)

        main_layout = QVBoxLayout()
        lang_help_layout = QHBoxLayout()
        lang_help_layout.addStretch(1)  # Add space before buttons

        # Language Switch Button
        self.language_button = QPushButton('Language')
        self.language_button.clicked.connect(self.toggle_language)
        lang_help_layout.addWidget(self.language_button)

        # Help Button
        self.help_button = QPushButton('Help')
        self.help_button.clicked.connect(self.show_help_dialog)
        lang_help_layout.addWidget(self.help_button)

        main_layout.addLayout(lang_help_layout)

        # Group 1: Basic Settings
        basic_settings = QGroupBox("Basic Settings")
        basic_layout = QGridLayout()

        basic_layout.addWidget(QLabel('Venue:'), 0, 0)
        self.venue_input = QLineEdit()
        basic_layout.addWidget(self.venue_input, 0, 1)

        basic_layout.addWidget(QLabel('Save Directory:'), 1, 0)
        self.save_dir_input = QLineEdit()
        basic_layout.addWidget(self.save_dir_input, 1, 1)
        browse_button = QPushButton('Browse')
        browse_button.clicked.connect(self.select_save_dir)
        basic_layout.addWidget(browse_button, 1, 2)

        basic_settings.setLayout(basic_layout)
        main_layout.addWidget(basic_settings)

        # Group 2: Additional Parameters
        additional_params = QGroupBox("Additional Settings")
        params_layout = QGridLayout()

        params_layout.addWidget(QLabel('Year (Conference Only):'), 0, 0)
        self.year_input = QLineEdit()
        params_layout.addWidget(self.year_input, 0, 1)

        params_layout.addWidget(QLabel('Sleep time per paper:'), 1, 0)
        self.sleep_time_input = QLineEdit('0.2')
        params_layout.addWidget(self.sleep_time_input, 1, 1)

        params_layout.addWidget(QLabel('Volume (Journal only):'), 2, 0)
        self.volume_input = QLineEdit()
        params_layout.addWidget(self.volume_input, 2, 1)

        additional_params.setLayout(params_layout)
        main_layout.addWidget(additional_params)

        # Group 3: Advanced Settings
        advanced_settings = QGroupBox("Advanced Settings")
        combined_layout = QVBoxLayout()  # Combine proxy and execution layouts

        # Proxy Settings
        proxy_layout = QGridLayout()
        proxy_layout.addWidget(QLabel('HTTP Proxy:'), 0, 0)
        self.http_proxy_input = QLineEdit()
        proxy_layout.addWidget(self.http_proxy_input, 0, 1)

        proxy_layout.addWidget(QLabel('HTTPS Proxy:'), 1, 0)
        self.https_proxy_input = QLineEdit()
        proxy_layout.addWidget(self.https_proxy_input, 1, 1)

        combined_layout.addLayout(proxy_layout)  # Add proxy layout to combined layout

        # Execution Options
        execution_layout = QHBoxLayout()
        self.parallel_button = QPushButton("Parallel: Disabled")
        self.parallel_button.setCheckable(True)
        self.parallel_button.toggled.connect(self.toggle_parallel)
        execution_layout.addWidget(self.parallel_button)

        combined_layout.addLayout(execution_layout)  # Add execution layout to combined layout

        # Set the combined layout for the group box
        advanced_settings.setLayout(combined_layout)

        # Add the group box to the main layout
        main_layout.addWidget(advanced_settings)

        # Run and Pause Buttons
        button_layout = QHBoxLayout()
        self.run_button = QPushButton('Run')
        self.run_button.clicked.connect(self.run_downloader)
        button_layout.addWidget(self.run_button)

        self.pause_button = QPushButton('Pause')
        self.pause_button.setEnabled(False)
        button_layout.addWidget(self.pause_button)

        main_layout.addLayout(button_layout)

        # Group 5: Logs
        log_group = QGroupBox("Logs")
        log_layout = QVBoxLayout()

        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)
        log_layout.addWidget(self.log_output)

        log_group.setLayout(log_layout)
        main_layout.addWidget(log_group)

        self.setLayout(main_layout)

    def select_save_dir(self):
        directory = QFileDialog.getExistingDirectory(self, 'Select Save Directory')
        if directory:
            self.save_dir_input.setText(directory)

    def toggle_parallel(self, checked):
        if checked:
            self.parallel_button.setText("Enabled")
        else:
            self.parallel_button.setText("Disabled")

    def run_downloader(self):
        venue_name = self.venue_input.text().strip()
        save_dir = self.save_dir_input.text().strip()
        year = self.year_input.text().strip()
        sleep_time = self.sleep_time_input.text().strip()
        volume = self.volume_input.text().strip()
        http_proxy = self.http_proxy_input.text().strip()
        https_proxy = self.https_proxy_input.text().strip()
        parallel = self.parallel_button.isChecked()

        if not venue_name or not save_dir:
            QMessageBox.warning(self, 'Input Error', 'Please fill in required fields (venue, save-dir).')
            return

        try:
            year = int(year) if year else None
        except ValueError:
            QMessageBox.warning(self, 'Input Error', 'Year must be an integer.')
            return

        try:
            sleep_time = float(sleep_time) if sleep_time else 0.2
        except ValueError:
            QMessageBox.warning(self, 'Input Error', 'Sleep time must be a number.')
            return

        try:
            volume = int(volume) if volume else None
        except ValueError:
            QMessageBox.warning(self, 'Input Error', 'Volume must be an integer.')
            return

        self.log_output.clear()
        self.log_output.append("Starting download...")

        # 创建线程
        self.thread = DownloaderThread(venue_name, save_dir, year,
                                       sleep_time_per_paper=sleep_time,
                                       volume=volume,
                                       http_proxy=http_proxy,
                                       https_proxy=https_proxy,
                                       parallel=parallel)
        self.thread.log_signal.connect(self.append_log)
        self.thread.error_signal.connect(self.show_error)
        self.thread.finished_signal.connect(self.task_finished)
        self.thread.start()

        self.run_button.setEnabled(False)
        self.pause_button.setEnabled(True)
        self.pause_button.setText("Pause")

    def toggle_pause(self):
        if not self.thread:
            return
        if self.thread.paused:
            # Resume
            self.thread.resume()
            self.pause_button.setText("Pause")
        else:
            # Pause
            self.thread.pause()
            self.pause_button.setText("Resume")

    @pyqtSlot(str)
    def append_log(self, log):
        self.log_output.append(log)
        self.log_output.ensureCursorVisible()

    @pyqtSlot(str)
    def show_error(self, error):
        QMessageBox.critical(self, 'Error', error)
        self.log_output.append(f"[Error] {error}")
        self.run_button.setEnabled(True)
        self.pause_button.setEnabled(False)

    @pyqtSlot(str)
    def task_finished(self, msg):
        self.log_output.append(msg)
        self.run_button.setEnabled(True)
        self.pause_button.setEnabled(False)

    def show_help_dialog(self):
        help_text = """
        Paper Bulk Downloader Help:
        - Fill in the required fields under Basic Settings.
        - Configure optional parameters, proxies, and execution options.
        - Click "Run" to start downloading, or "Pause" to pause.
        - Use the "Switch Language" button to toggle languages.
        """
        QMessageBox.information(self, 'Help', help_text)

    def toggle_language(self):
        if self.language_button.text() == 'Switch to Chinese':
            self.language_button.setText('Switch to English')
            self.update_language('Chinese')
        else:
            self.language_button.setText('Switch to Chinese')
            self.update_language('English')

    def update_language(self, language):
        if language == 'Chinese':
            self.setWindowTitle('论文批量下载器')
            self.language_button.setText('切换到英文')
            self.help_button.setText('帮助')
            # Update other labels in the UI
        else:
            self.setWindowTitle('Paper Bulk Downloader')
            self.language_button.setText('Switch to Chinese')
            self.help_button.setText('Help')
            # Update other labels in the UI


if __name__ == '__main__':
    app = QApplication(sys.argv)
    gui = PaperDownloaderGUI()
    gui.resize(800, 600)
    gui.show()
    sys.exit(app.exec_())
