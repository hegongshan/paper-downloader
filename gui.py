import logging
import os
import sys
import threading

import utils
import venue

from PyQt5.QtCore import QThread, pyqtSignal, pyqtSlot, QMutex, QWaitCondition, Qt
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QFileDialog, QTextEdit, QMessageBox,QGridLayout,QGroupBox
)


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

    def __init__(self, publisher: venue.Base):
        super().__init__()

        self.publisher = publisher

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

            # 注意：目前没有对publisher内部流程进行暂停逻辑的插入
            # 如需暂停，需要在publisher.process()内部适当位置调用self.check_paused()

            self.publisher.process()

            self.finished_signal.emit("Download Finished.")

        except Exception as e:
            self.error_signal.emit(f"Error: {str(e)}")


# -------------------------------------------
# GUI类定义
class PaperDownloaderGUI(QWidget):
    def __init__(self):
        super().__init__()
        self.current_language = 'English'  # Initialize default language
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

        # Language Switch Button
        self.language_button = QPushButton('Switch to Chinese')
        self.language_button.clicked.connect(self.toggle_language)
        lang_help_layout.addWidget(self.language_button)

        # Help Button
        self.help_button = QPushButton('Help')
        self.help_button.clicked.connect(self.show_help_dialog)
        lang_help_layout.addWidget(self.help_button)

        lang_help_layout.addStretch(1)
        main_layout.addLayout(lang_help_layout)

        # Group 1: Basic Settings
        self.basic_settings = QGroupBox("Basic Settings")
        basic_layout = QGridLayout()

        self.venue_label = QLabel('Venue:')
        basic_layout.addWidget(self.venue_label, 0, 0)
        self.venue_input = QLineEdit()
        basic_layout.addWidget(self.venue_input, 0, 1)

        self.save_dir_label = QLabel('Save Directory:')
        basic_layout.addWidget(self.save_dir_label, 1, 0)
        self.save_dir_input = QLineEdit()
        basic_layout.addWidget(self.save_dir_input, 1, 1)
        self.browse_button = QPushButton('Browse')
        self.browse_button.clicked.connect(self.select_save_dir)
        basic_layout.addWidget(self.browse_button, 1, 2)

        self.basic_settings.setLayout(basic_layout)
        main_layout.addWidget(self.basic_settings)

        # Group 2: Additional Parameters
        self.additional_params = QGroupBox("Additional Settings")
        params_layout = QGridLayout()

        self.year_label = QLabel('Year (Conference Only):')
        params_layout.addWidget(self.year_label, 0, 0)
        self.year_input = QLineEdit()
        params_layout.addWidget(self.year_input, 0, 1)

        self.sleep_time_label = QLabel('Sleep time per paper(second):')
        params_layout.addWidget(self.sleep_time_label, 1, 0)
        self.sleep_time_input = QLineEdit('0.2')
        params_layout.addWidget(self.sleep_time_input, 1, 1)

        self.volume_label = QLabel('Volume (Journal only):')
        params_layout.addWidget(self.volume_label, 2, 0)
        self.volume_input = QLineEdit()
        params_layout.addWidget(self.volume_input, 2, 1)

        self.additional_params.setLayout(params_layout)
        main_layout.addWidget(self.additional_params)

        # Group 3: Advanced Settings
        self.advanced_settings = QGroupBox("Advanced Settings")
        combined_layout = QVBoxLayout()

        proxy_layout = QGridLayout()
        self.http_proxy_label = QLabel('HTTP Proxy:')
        proxy_layout.addWidget(self.http_proxy_label, 0, 0)
        self.http_proxy_input = QLineEdit()
        proxy_layout.addWidget(self.http_proxy_input, 0, 1)

        self.https_proxy_label = QLabel('HTTPS Proxy:')
        proxy_layout.addWidget(self.https_proxy_label, 1, 0)
        self.https_proxy_input = QLineEdit()
        proxy_layout.addWidget(self.https_proxy_input, 1, 1)

        combined_layout.addLayout(proxy_layout)

        execution_layout = QHBoxLayout()
        self.parallel_button = QPushButton("Parallel: Disabled")
        self.parallel_button.setCheckable(True)
        execution_layout.addWidget(self.parallel_button)
        combined_layout.addLayout(execution_layout)

        self.advanced_settings.setLayout(combined_layout)
        main_layout.addWidget(self.advanced_settings)

        # Logs Section
        self.log_group = QGroupBox("Logs")
        log_layout = QVBoxLayout()
        self.log_output = QTextEdit()
        log_layout.addWidget(self.log_output)
        self.log_group.setLayout(log_layout)
        main_layout.addWidget(self.log_group)

        self.setLayout(main_layout)

    def toggle_language(self):
        if self.current_language == 'English':
            self.current_language = 'Chinese'
        else:
            self.current_language = 'English'
        self.update_language()

    def update_language(self):
        if self.current_language == 'Chinese':
            self.setWindowTitle('开源论文批量下载器')
            self.language_button.setText('切换到英文')
            self.help_button.setText("帮助")
            self.basic_settings.setTitle('基本设置')
            self.browse_button.setText("浏览")
            self.additional_params.setTitle('附加设置')
            self.advanced_settings.setTitle('高级设置')
            self.log_group.setTitle('日志')

            self.venue_label.setText('会议:')
            self.save_dir_label.setText('保存目录:')
            self.year_label.setText('年份 (仅限会议):')
            self.sleep_time_label.setText('每篇论文间隔时间 (秒):')
            self.volume_label.setText('卷号 (仅限期刊):')
            self.http_proxy_label.setText('HTTP 代理:')
            self.https_proxy_label.setText('HTTPS 代理:')
            self.parallel_button.setText('并行: 禁用')
        else:
            self.setWindowTitle('Paper Bulk Downloader')
            self.language_button.setText('Switch to Chinese')
            self.help_button.setText("Help")
            self.basic_settings.setTitle('Basic Settings')
            self.browse_button.setText('Browse')
            self.additional_params.setTitle('Additional Settings')
            self.advanced_settings.setTitle('Advanced Settings')
            self.log_group.setTitle('Logs')

            self.venue_label.setText('Venue:')
            self.save_dir_label.setText('Save Directory:')
            self.year_label.setText('Year (Conference Only):')
            self.sleep_time_label.setText('Sleep time per paper(second):')
            self.volume_label.setText('Volume (Journal only):')
            self.http_proxy_label.setText('HTTP Proxy:')
            self.https_proxy_label.setText('HTTPS Proxy:')
            self.parallel_button.setText('Parallel: Disabled')



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
        sleep_time_per_paper = self.sleep_time_input.text().strip()
        volume = self.volume_input.text().strip()
        http_proxy = self.http_proxy_input.text().strip()
        https_proxy = self.https_proxy_input.text().strip()
        parallel = self.parallel_button.isChecked()

        if not venue_name:
            QMessageBox.warning(self, 'Input Error', '"Venue" is a required field.')
            return

        if not save_dir:
            QMessageBox.warning(self, 'Input Error', '"Save directory" is a required field..')
            return

        # 解析venue
        venue_name_lower = venue_name.lower()
        venue_publisher = venue.parse_venue(venue_name_lower)
        if not venue_publisher:
            QMessageBox.warning(self, 'Input Error', f'Unsupported venue: {venue_name_lower}')
            return None

        if venue.is_conference(venue_publisher):
            if not year:
                QMessageBox.warning(self, 'Input Error', '"Year" is a required field.')
                return

            try:
                year = int(year)
            except ValueError:
                QMessageBox.warning(self, 'Input Error', '"Year" must be an integer.')
                return

        if venue.is_journal(venue_publisher):
            if not volume:
                QMessageBox.warning(self, 'Input Error', '"Volume" is a required field.')
                return

            try:
                volume = int(volume)
            except ValueError:
                QMessageBox.warning(self, 'Input Error', '"Volume" must be an integer.')
                return

        try:
            sleep_time_per_paper = float(sleep_time_per_paper) if sleep_time_per_paper else 0.2
        except ValueError:
            QMessageBox.warning(self, 'Input Error', '"Sleep time" must be a number.')
            return

        self.log_output.clear()
        self.log_output.append("Starting download...")

        # 设置代理
        proxies = {}
        if http_proxy:
            proxies['http'] = http_proxy
        if https_proxy:
            proxies['https'] = https_proxy

        # 实例化publisher
        publisher = venue_publisher(
            save_dir=save_dir,
            sleep_time_per_paper=sleep_time_per_paper,
            venue_name=venue_name_lower,
            year=year if year else None,
            volume=volume if volume else None,
            parallel=parallel,
            proxies=proxies if proxies else None
        )

        # 创建线程
        self.thread = DownloaderThread(publisher=publisher)
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
        if self.current_language == 'Chinese':
            help_text = """
            <b>开源论文批量下载器帮助:</b><br>
            <ul>
                <li>在“基本设置”中填写必填字段。</li>
                <li>配置可选参数、代理和高级设置。</li>
                <li>点击“运行”按钮开始下载，或点击“暂停”按钮暂停。</li>
                <li>使用“切换到英文”按钮切换语言。</li>
            </ul>
            <p>目前可直接下载的论文：<b>AAAI, IJCAI, CVPR, ICCV, ECCV, ICLR, ICML, NeurIPS, JMLR, ACL, EMNLP, NAACL, 
            NSDI, VLDB, USENIX Security, NDSS, OSDI, FAST, USENIX ATC, RSS</b></p>
            """
            title = '帮助'
        else:
            help_text = """
            <b>Paper Bulk Downloader for OPen Access Venues Help:</b><br>
            <ul>
                <li>Fill in the required fields under Basic Settings.</li>
                <li>Configure optional parameters, proxies, and advanced settings.</li>
                <li>Click "Run" to start downloading, or "Pause" to pause.</li>
                <li>Use the "Switch to Chinese" button to toggle languages.</li>
            </ul>
            <p>Currently supported publications:<b>AAAI, IJCAI, CVPR, ICCV, ECCV, ICLR, ICML, NeurIPS, JMLR, ACL, EMNLP, NAACL, 
            NSDI, VLDB, USENIX Security, NDSS, OSDI, FAST, USENIX ATC, RSS</b></p>
            """
            title = 'Help'

        QMessageBox.information(self, title, help_text)


if __name__ == '__main__':
    app = QApplication(sys.argv)
    gui = PaperDownloaderGUI()
    gui.resize(800, 600)
    gui.show()
    sys.exit(app.exec_())
