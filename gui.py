import sys
import os
import argparse
import logging
import threading

from PyQt5.QtCore import QThread, pyqtSignal, pyqtSlot, QMutex, QWaitCondition, Qt
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QFileDialog, QTextEdit, QMessageBox
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
                utils.print_and_exit(f'Unsupported venue: {venue_name_lower}')

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

            utils.print_success('Task Done!')
            self.finished_signal.emit("Download Finished.")

        except Exception as e:
            self.error_signal.emit(f"Error: {str(e)}")


# -------------------------------------------
# GUI类定义
class PaperDownloaderGUI(QWidget):
    def __init__(self):
        super().__init__()
        self.thread = None
        self.init_ui()

    def init_ui(self):
        self.setWindowTitle('Paper Bulk Downloader')

        layout = QVBoxLayout()

        # Venue输入
        venue_layout = QHBoxLayout()
        venue_layout.addWidget(QLabel('Venue:'))
        self.venue_input = QLineEdit()
        venue_layout.addWidget(self.venue_input)

        # 保存目录
        save_dir_layout = QHBoxLayout()
        save_dir_layout.addWidget(QLabel('Save Directory:'))
        self.save_dir_input = QLineEdit()
        save_dir_layout.addWidget(self.save_dir_input)
        save_dir_btn = QPushButton('Browse')
        save_dir_btn.clicked.connect(self.select_save_dir)
        save_dir_layout.addWidget(save_dir_btn)

        # 年份
        year_layout = QHBoxLayout()
        year_layout.addWidget(QLabel('Year:'))
        self.year_input = QLineEdit()
        year_layout.addWidget(self.year_input)

        # 下载间隔
        sleep_time_layout = QHBoxLayout()
        sleep_time_layout.addWidget(QLabel('Sleep time per paper (s):'))
        self.sleep_time_input = QLineEdit('0.2')
        sleep_time_layout.addWidget(self.sleep_time_input)

        # Volume（可选）
        volume_layout = QHBoxLayout()
        volume_layout.addWidget(QLabel('Volume (Journal only):'))
        self.volume_input = QLineEdit()
        volume_layout.addWidget(self.volume_input)

        # HTTP/HTTPS Proxy
        proxy_layout = QHBoxLayout()
        proxy_layout.addWidget(QLabel('HTTP Proxy:'))
        self.http_proxy_input = QLineEdit()
        proxy_layout.addWidget(self.http_proxy_input)
        proxy_layout.addWidget(QLabel('HTTPS Proxy:'))
        self.https_proxy_input = QLineEdit()
        proxy_layout.addWidget(self.https_proxy_input)

        # Parallel
        parallel_layout = QHBoxLayout()
        parallel_layout.addWidget(QLabel('Parallel:'))
        self.parallel_button = QPushButton("Disabled")
        self.parallel_button.setCheckable(True)
        self.parallel_button.toggled.connect(self.toggle_parallel)
        parallel_layout.addWidget(self.parallel_button)

        # 按钮区：Run / Pause / Resume
        button_layout = QHBoxLayout()
        self.run_button = QPushButton('Run')
        self.run_button.clicked.connect(self.run_downloader)
        button_layout.addWidget(self.run_button)

        self.pause_button = QPushButton('Pause')
        self.pause_button.setEnabled(False)
        self.pause_button.clicked.connect(self.toggle_pause)
        button_layout.addWidget(self.pause_button)

        # 日志显示
        layout.addLayout(venue_layout)
        layout.addLayout(save_dir_layout)
        layout.addLayout(year_layout)
        layout.addLayout(sleep_time_layout)
        layout.addLayout(volume_layout)
        layout.addLayout(proxy_layout)
        layout.addLayout(parallel_layout)
        layout.addLayout(button_layout)

        layout.addWidget(QLabel('Logs:'))
        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)
        layout.addWidget(self.log_output)

        self.setLayout(layout)

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


if __name__ == '__main__':
    app = QApplication(sys.argv)
    gui = PaperDownloaderGUI()
    gui.resize(800, 600)
    gui.show()
    sys.exit(app.exec_())
