import json
import logging
import os
import sys
import time

import venue
from PyQt5.QtCore import QThread, pyqtSignal, pyqtSlot, QMutex, QWaitCondition, Qt
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QFileDialog, QTextEdit,
    QMessageBox, QGridLayout, QGroupBox, QRadioButton,
    QButtonGroup, QMainWindow, QMenu, QAction, QComboBox,
    QProgressBar
)

##################################################################
#                             Constant                           #
##################################################################
language_file = 'i18n/lang.json'
config_file = 'config.json'
qss_file = 'gui.qss'


##################################################################
#                         Logging Handler                        #
##################################################################
class QtLogHandler(logging.Handler):
    def __init__(self, signal):
        super().__init__()
        self.signal = signal

    def emit(self, record):
        msg = self.format(record)
        self.signal.emit(msg)


##################################################################
#                         Worker Thread                          #
##################################################################
class DownloaderThread(QThread):
    log_signal = pyqtSignal(str)
    error_signal = pyqtSignal(str)
    finished_signal = pyqtSignal(str)
    update_progress = pyqtSignal(int)

    def __init__(self, publisher: type):
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
        self.log_signal.emit("Download paused.")

    def resume(self):
        self.mutex.lock()
        self.paused = False
        self.pause_condition.wakeAll()
        self.mutex.unlock()
        self.log_signal.emit("Download resumed.")

    def stop(self):
        self.mutex.lock()
        self.stop_flag = True
        if self.paused:
            self.paused = False
            self.pause_condition.wakeAll()
        self.mutex.unlock()
        self.log_signal.emit("Download stopping...")

    def check_paused_or_stopped(self):
        self.mutex.lock()
        if self.stop_flag:
            self.mutex.unlock()
            raise Exception("Download stopped by user.")
        while self.paused:
            self.pause_condition.wait(self.mutex)
            if self.stop_flag:
                self.mutex.unlock()
                raise Exception("Download stopped by user.")
        self.mutex.unlock()

    def run(self):
        # 初始化日志
        logger = logging.getLogger()
        logger.setLevel(logging.INFO)
        qt_log_handler = QtLogHandler(self.log_signal)
        qt_log_handler.setFormatter(logging.Formatter('%(asctime)s [%(levelname)s] %(message)s'))
        logger.addHandler(qt_log_handler)

        # 设置暂停和停止的回调
        self.publisher.set_pause_stop_callback(self.check_paused_or_stopped)

        for progress in self.publisher.process(use_tqdm=False):
            self.update_progress.emit(progress)

        self.finished_signal.emit("Download Finished.")


##################################################################
#                             GUI                                #
##################################################################
class PaperDownloaderGUI(QMainWindow):
    def __init__(self):
        super().__init__()

        if os.path.exists(language_file):
            with open(language_file, 'r', encoding='utf-8') as file:
                self.languages = json.load(file)
        else:
            self.show_error_message_and_exit(f'Cannot find {language_file}.')

        # Initialize default language
        self.current_language = 'en'
        if os.path.exists(config_file):
            with open(config_file, 'r', encoding='utf-8') as file:
                config_dict = json.load(file)
                if config_dict and 'default_language' in config_dict:
                    self.current_language = config_dict['default_language']

        self.thread = None

        self.init_ui()

    def show_error_message_and_exit(self, message):
        QMessageBox.critical(self, 'Error', f'Error: \n{message}')
        sys.exit()

    def init_ui(self):
        self.setWindowTitle(self.languages[self.current_language]['window_title'])
        if not os.path.exists(qss_file):
            self.show_error_message_and_exit(f'Cannot find stylesheet {qss_file}.')

        with open(qss_file, 'r', encoding='utf-8') as f:
            qss = f.read()
        if qss:
            self.setStyleSheet(qss)

        # Menu Bar
        menubar = self.menuBar()
        self.language_menu = QMenu(self.languages[self.current_language]['language'], self)
        self.language_action = QAction(self.languages[self.current_language]['language_switch'], self)
        self.language_action.triggered.connect(self.update_language)
        self.language_menu.addAction(self.language_action)
        menubar.addMenu(self.language_menu)

        central_widget = QWidget(self)
        self.setCentralWidget(central_widget)

        self.main_layout = QVBoxLayout()

        # Group 1: Basic Settings
        self.basic_settings = QGroupBox(self.languages[self.current_language]['basic_settings'])
        basic_layout = QGridLayout()

        self.venue_label = QLabel(self.languages[self.current_language]['venue_label'])
        basic_layout.addWidget(self.venue_label, 0, 0)
        self.venue_input = QComboBox()
        self.venue_input.addItems(venue.get_available_venue_list(lower_case=False))
        basic_layout.addWidget(self.venue_input, 0, 1)

        self.save_dir_label = QLabel(self.languages[self.current_language]['save_dir_label'])
        basic_layout.addWidget(self.save_dir_label, 1, 0)
        self.save_dir_input = QLineEdit()
        basic_layout.addWidget(self.save_dir_input, 1, 1)

        self.browse_button = QPushButton(self.languages[self.current_language]['browse_btn'])
        self.browse_button.clicked.connect(self.select_save_dir)
        basic_layout.addWidget(self.browse_button, 1, 2)

        self.sleep_time_label = QLabel(self.languages[self.current_language]['sleep_time_label'])
        basic_layout.addWidget(self.sleep_time_label, 2, 0)
        self.sleep_time_input = QLineEdit('2')
        basic_layout.addWidget(self.sleep_time_input, 2, 1)

        self.keyword_label = QLabel(self.languages[self.current_language]['keyword'])
        basic_layout.addWidget(self.keyword_label, 3, 0)
        self.keyword_input = QLineEdit()
        self.keyword_input.setPlaceholderText(self.languages[self.current_language]['keyword_placeholder'])
        basic_layout.addWidget(self.keyword_input, 3, 1)

        self.basic_settings.setLayout(basic_layout)
        self.main_layout.addWidget(self.basic_settings)

        # Group 2: Additional Parameters
        self.additional_params = QGroupBox(self.languages[self.current_language]['additional_params'])
        params_layout = QGridLayout()

        self.year_label = QLabel(self.languages[self.current_language]['year_label'])
        params_layout.addWidget(self.year_label, 0, 0)
        self.year_input = QLineEdit()
        params_layout.addWidget(self.year_input, 0, 1)

        self.volume_label = QLabel(self.languages[self.current_language]['volume_label'])
        params_layout.addWidget(self.volume_label, 1, 0)
        self.volume_input = QLineEdit()
        params_layout.addWidget(self.volume_input, 1, 1)

        self.additional_params.setLayout(params_layout)
        self.main_layout.addWidget(self.additional_params)

        # Group 3: Advanced Settings
        self.advanced_settings = QGroupBox(self.languages[self.current_language]['advanced_settings'])
        self.http_proxy_label = QLabel(self.languages[self.current_language]['http_proxy_label'])
        self.http_proxy_input = QLineEdit()

        self.https_proxy_label = QLabel(self.languages[self.current_language]['https_proxy_label'])
        self.https_proxy_input = QLineEdit()

        self.parallel_label = QLabel(self.languages[self.current_language]['parallel'])
        self.parallel_enable_button = QRadioButton(self.languages[self.current_language]['enable'])
        self.parallel_disable_button = QRadioButton(self.languages[self.current_language]['disable'])
        self.parallel_disable_button.setChecked(True)
        self.btn_group = QButtonGroup()
        self.btn_group.addButton(self.parallel_enable_button)
        self.btn_group.addButton(self.parallel_disable_button)
        self.btn_group.setExclusive(True)

        combined_label_layout = QVBoxLayout()
        combined_label_layout.addWidget(self.http_proxy_label)
        combined_label_layout.addWidget(self.https_proxy_label)
        combined_label_layout.addWidget(self.parallel_label)

        combined_input_layout = QVBoxLayout()
        combined_input_layout.addWidget(self.http_proxy_input)
        combined_input_layout.addWidget(self.https_proxy_input)
        parallel_btn_group = QHBoxLayout()
        parallel_btn_group.addWidget(self.parallel_enable_button)
        parallel_btn_group.addWidget(self.parallel_disable_button)
        combined_input_layout.addLayout(parallel_btn_group)

        combined_layout = QHBoxLayout()
        combined_layout.addLayout(combined_label_layout)
        combined_layout.addLayout(combined_input_layout)
        self.advanced_settings.setLayout(combined_layout)
        self.main_layout.addWidget(self.advanced_settings)

        execution_layout = QGridLayout()
        self.run_button = QPushButton(self.languages[self.current_language]['run'])
        self.run_button.clicked.connect(self.run_downloader)
        self.stop_button = QPushButton(self.languages[self.current_language]['stop'])
        self.stop_button.clicked.connect(self.stop_downloader)
        self.pause_resume_button = QPushButton(self.languages[self.current_language]['pause'])
        self.pause_resume_button.clicked.connect(self.toggle_pause_resume)
        execution_layout.addWidget(self.run_button, 0, 0)
        execution_layout.addWidget(self.stop_button, 0, 1)
        execution_layout.addWidget(self.pause_resume_button, 0, 2)
        self.main_layout.addLayout(execution_layout)

        # 初始化按钮状态
        self.run_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        self.pause_resume_button.setEnabled(False)

        # Logs Section
        self.log_group = QGroupBox(self.languages[self.current_language]['log'])
        log_layout = QVBoxLayout()
        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)
        log_layout.addWidget(self.log_output)
        log_button_layout = QHBoxLayout()
        log_button_layout.addStretch(1)
        self.log_export_button = QPushButton(self.languages[self.current_language]['export'])
        self.log_export_button.clicked.connect(self.export_log)
        self.log_clear_button = QPushButton(self.languages[self.current_language]['clear'])
        self.log_clear_button.clicked.connect(self.clear_log)
        log_button_layout.addWidget(self.log_export_button)
        log_button_layout.addWidget(self.log_clear_button)
        log_layout.addLayout(log_button_layout)
        self.log_group.setLayout(log_layout)
        self.main_layout.addWidget(self.log_group)

        central_widget.setLayout(self.main_layout)

    def start_progress(self):
        self.progress_bar = QProgressBar(self)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setAlignment(Qt.AlignCenter)
        self.main_layout.insertWidget(self.main_layout.count() - 1, self.progress_bar)

    def update_progress(self, progress):
        self.progress_bar.setValue(progress)

    def update_language(self):
        if self.current_language == 'en':
            self.current_language = 'cn'
        else:
            self.current_language = 'en'

        with open(config_file, 'w+', encoding='utf-8') as file:
            json.dump({
                'default_language': self.current_language
            }, file, ensure_ascii=False, indent=4)

        self.setWindowTitle(self.languages[self.current_language]['window_title'])

        self.language_menu.setTitle(self.languages[self.current_language]['language'])
        self.language_action.setText(self.languages[self.current_language]['language_switch'])

        self.basic_settings.setTitle(self.languages[self.current_language]['basic_settings'])
        self.venue_label.setText(self.languages[self.current_language]['venue_label'])
        self.save_dir_label.setText(self.languages[self.current_language]['save_dir_label'])
        self.browse_button.setText(self.languages[self.current_language]['browse_btn'])
        self.sleep_time_label.setText(self.languages[self.current_language]['sleep_time_label'])
        self.keyword_label.setText(self.languages[self.current_language]['keyword'])
        self.keyword_input.setPlaceholderText(self.languages[self.current_language]['keyword_placeholder'])

        self.additional_params.setTitle(self.languages[self.current_language]['additional_params'])
        self.year_label.setText(self.languages[self.current_language]['year_label'])
        self.volume_label.setText(self.languages[self.current_language]['volume_label'])

        self.advanced_settings.setTitle(self.languages[self.current_language]['advanced_settings'])
        self.http_proxy_label.setText(self.languages[self.current_language]['http_proxy_label'])
        self.https_proxy_label.setText(self.languages[self.current_language]['https_proxy_label'])
        self.parallel_label.setText(self.languages[self.current_language]['parallel'])
        self.parallel_enable_button.setText(self.languages[self.current_language]['enable'])
        self.parallel_disable_button.setText(self.languages[self.current_language]['disable'])

        self.run_button.setText(self.languages[self.current_language]['run'])
        self.stop_button.setText(self.languages[self.current_language]['stop'])
        if self.thread and self.thread.paused:
            self.pause_resume_button.setText(self.languages[self.current_language]['resume'])
        else:
            self.pause_resume_button.setText(self.languages[self.current_language]['pause'])

        self.log_group.setTitle(self.languages[self.current_language]['log'])
        self.log_export_button.setText(self.languages[self.current_language]['export'])
        self.log_clear_button.setText(self.languages[self.current_language]['clear'])

    def select_save_dir(self):
        directory = QFileDialog.getExistingDirectory(self, self.languages[self.current_language]['select_save_dir'])
        if directory:
            self.save_dir_input.setText(directory)

    def run_downloader(self):
        venue_name = self.venue_input.currentText().strip()
        save_dir = self.save_dir_input.text().strip()
        sleep_time_per_paper = self.sleep_time_input.text().strip()
        keyword = self.keyword_input.text().strip()
        year = self.year_input.text().strip()
        volume = self.volume_input.text().strip()
        http_proxy = self.http_proxy_input.text().strip()
        https_proxy = self.https_proxy_input.text().strip()
        parallel = self.btn_group.checkedButton().text() == self.languages[self.current_language]['enable']

        self.log_output.clear()

        if not venue_name:
            QMessageBox.warning(self, 'Input Error', self.languages[self.current_language]['venue_required'])
            return

        if not save_dir:
            QMessageBox.warning(self, 'Input Error', self.languages[self.current_language]['save_dir_required'])
            return

        # 解析venue
        venue_name_lower = venue.get_lower_name(venue_name)
        venue_publisher = venue.parse_venue(venue_name_lower)
        if not venue_publisher:
            QMessageBox.warning(self, 'Input Error',
                                f'{self.languages[self.current_language]["venue_unsupported"]}{venue_name_lower}')
            return None

        if venue.is_conference(venue_publisher):
            if not year:
                QMessageBox.warning(self, 'Input Error', self.languages[self.current_language]['year_required'])
                return

            try:
                year = int(year)
            except ValueError:
                QMessageBox.warning(self, 'Input Error', self.languages[self.current_language]['year_integer'])
                return

            if volume:
                self.log_output.append(
                    f'Warning: The conference "{venue_name}" does not require the volume field, but it is currently set to "{volume}".')
        elif venue.is_journal(venue_publisher):
            if not volume:
                QMessageBox.warning(self, 'Input Error', self.languages[self.current_language]['volume_required'])
                return

            try:
                volume = int(volume)
            except ValueError:
                QMessageBox.warning(self, 'Input Error', self.languages[self.current_language]['volume_integer'])
                return

            if year:
                self.log_output.append(
                    f'Warning: The journal "{venue_name}" does not require the year field, but it is currently set to "{year}".')

        try:
            sleep_time_per_paper = float(sleep_time_per_paper) if sleep_time_per_paper else 2
        except ValueError:
            QMessageBox.warning(self, 'Input Error', self.languages[self.current_language]['sleep_time_number'])
            return

        # 更新按钮状态
        self.run_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        self.pause_resume_button.setEnabled(True)
        self.pause_resume_button.setText(self.languages[self.current_language]['pause'])

        self.log_output.append("Starting download...")

        # 设置代理
        proxies = {}
        if http_proxy:
            proxies['http'] = http_proxy
        if https_proxy:
            proxies['https'] = https_proxy

        # 实例化publisher
        publisher_instance = venue_publisher(
            save_dir=save_dir,
            sleep_time_per_paper=sleep_time_per_paper,
            keyword=keyword,
            venue_name=venue_name_lower,
            year=year,
            volume=volume,
            parallel=parallel,
            proxies=proxies
        )
        self.start_progress()

        # 创建线程
        self.thread = DownloaderThread(publisher=publisher_instance)
        self.thread.log_signal.connect(self.append_log)
        self.thread.error_signal.connect(self.show_error)
        self.thread.finished_signal.connect(self.task_finished)
        self.thread.update_progress.connect(self.update_progress)
        self.thread.start()

    def stop_downloader(self):
        if self.thread and self.thread.isRunning():
            confirm = QMessageBox.question(
                self,
                self.languages[self.current_language]['stop_confirm_title'],
                self.languages[self.current_language]['stop_confirm_text'],
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )
            if confirm == QMessageBox.Yes:
                self.thread.stop()
                self.thread.wait()  # 等待线程结束
                self.log_output.append("Download stopped.")
                self.run_button.setEnabled(True)
                self.stop_button.setEnabled(False)
                self.pause_resume_button.setEnabled(False)
                self.pause_resume_button.setText(self.languages[self.current_language]['pause'])
        else:
            QMessageBox.information(self, 'Info', self.languages[self.current_language]['no_active_to_stop'])

    def toggle_pause_resume(self):
        if not self.thread:
            return
        if self.thread.paused:
            # 恢复下载
            self.thread.resume()
            self.pause_resume_button.setText(self.languages[self.current_language]['pause'])
        else:
            # 暂停下载
            self.thread.pause()
            self.pause_resume_button.setText(self.languages[self.current_language]['resume'])

    @pyqtSlot(str)
    def append_log(self, log):
        self.log_output.append(log)
        self.log_output.ensureCursorVisible()

    @pyqtSlot()
    def export_log(self):
        log = self.log_output.toPlainText()
        if not log:
            QMessageBox.information(self, 'Info', self.languages[self.current_language]['no_log_to_export'])
            return

        filename, _ = QFileDialog.getSaveFileName(self, self.languages[self.current_language]['select_save_file'])
        with open(filename, 'a', encoding='utf-8') as file:
            file.write(log)
            file.write('\n')

    @pyqtSlot()
    def clear_log(self):
        self.log_output.clear()

    @pyqtSlot(str)
    def show_error(self, error):
        QMessageBox.critical(self, 'Error', error)
        self.log_output.append(f"[Error] {error}")
        # 判断是否与暂停/恢复相关
        if "does not support pause/resume" in error:
            self.pause_resume_button.setEnabled(False)
        self.run_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        self.pause_resume_button.setEnabled(False)
        self.pause_resume_button.setText(self.languages[self.current_language]['pause'])

    @pyqtSlot(str)
    def task_finished(self, msg):
        self.log_output.append(msg)
        self.run_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        self.pause_resume_button.setEnabled(False)
        self.pause_resume_button.setText(self.languages[self.current_language]['pause'])

        self.main_layout.removeWidget(self.progress_bar)
        self.progress_bar.deleteLater()


if __name__ == '__main__':
    app = QApplication(sys.argv)
    gui = PaperDownloaderGUI()
    gui.resize(800, 600)
    gui.show()
    sys.exit(app.exec_())
