import json
import logging
import os
import sys
import threading
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
#                            Constant                            #
##################################################################
LANGUAGE_FILE = 'i18n/lang.json'
CONFIG_FILE = 'config.json'
QSS_FILE = 'gui.qss'
DEFAULT_SLEEP_TIME = 2


##################################################################
#                        Logging Handler                         #
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
    progress_signal = pyqtSignal()
    finished_signal = pyqtSignal()

    def __init__(self,
                 publisher: type,
                 paper_entry_list):
        super().__init__()
        self.publisher = publisher
        self.paper_entry_list = paper_entry_list

        self.paused = False
        self.stopped = False
        self.thread_id = None

    def pause(self):
        if self.isFinished():
            return

        self.paused = True
        logging.info(f'Thread {self.thread_id} is pausing...')

    def resume(self):
        if self.isFinished():
            return

        self.paused = False
        logging.info(f'Thread {self.thread_id} is resuming...')

    def stop(self):
        if self.isFinished():
            return

        self.stopped = True
        if self.paused:
            self.paused = False
        logging.info(f'Thread {self.thread_id} is stopping...')

    def run(self):
        self.thread_id = threading.get_native_id()

        for paper_entry in self.paper_entry_list:
            if self.stopped:
                break
            while self.paused:
                pass
            if self.stopped:
                break
            self.publisher.process_one(paper_entry)
            self.progress_signal.emit()

        logging.info(f'Thread {self.thread_id} Finished.')
        self.finished_signal.emit()


##################################################################
#                              GUI                               #
##################################################################
class PaperDownloaderGUI(QMainWindow):
    log_signal = pyqtSignal(str)

    def __init__(self):
        super().__init__()

        self.threads = []
        self.finished_threads = 0
        self.num_threads = 0
        self.task_complete_count = 0
        self.num_tasks = 0
        self.mutex = QMutex()

        self.init_language()
        self.init_ui()
        self.init_style()
        self.init_logging()

    def show_error_message(self, message, need_to_exit=False):
        QMessageBox.critical(self, 'Error', f'Error: \n{message}')
        if need_to_exit:
            sys.exit()

    def init_language(self):
        if os.path.exists(LANGUAGE_FILE):
            with open(LANGUAGE_FILE, 'r', encoding='utf-8') as file:
                self.languages = json.load(file)
        else:
            self.show_error_message(f'Cannot find {LANGUAGE_FILE}.', need_to_exit=True)

        # Initialize default language
        self.current_language = 'en'
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, 'r', encoding='utf-8') as file:
                config_dict = json.load(file)
                if config_dict and 'default_language' in config_dict:
                    self.current_language = config_dict['default_language']

    def init_ui(self):
        self.setWindowTitle(self.languages[self.current_language]['window_title'])

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
        self.sleep_time_input = QLineEdit(str(DEFAULT_SLEEP_TIME))
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

        execution_layout = QHBoxLayout()
        self.run_button = QPushButton(self.languages[self.current_language]['run'])
        self.run_button.clicked.connect(self.run_downloader)
        self.stop_button = QPushButton(self.languages[self.current_language]['stop'])
        self.stop_button.clicked.connect(self.stop_downloader)
        self.pause_button = QPushButton(self.languages[self.current_language]['pause'])
        self.pause_button.clicked.connect(self.pause_downloader)
        self.resume_button = QPushButton(self.languages[self.current_language]['resume'])
        self.resume_button.clicked.connect(self.resume_downloader)

        execution_layout.addWidget(self.run_button)
        execution_layout.addWidget(self.stop_button)
        execution_layout.addWidget(self.pause_button)
        execution_layout.addWidget(self.resume_button)
        self.main_layout.addLayout(execution_layout)

        # 初始化按钮状态
        self.run_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        self.pause_button.setEnabled(False)
        self.resume_button.setEnabled(False)

        self.progress_bar = QProgressBar(self)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setAlignment(Qt.AlignCenter)
        self.progress_bar.hide()
        self.main_layout.addWidget(self.progress_bar)

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

    def init_style(self):
        if not os.path.exists(QSS_FILE):
            self.show_error_message(f'Cannot find stylesheet {QSS_FILE}.', need_to_exit=True)

        with open(QSS_FILE, 'r', encoding='utf-8') as f:
            qss = f.read()
        if qss:
            self.setStyleSheet(qss)

    def init_logging(self):
        self.log_signal.connect(self.append_log)
        log_handler = QtLogHandler(self.log_signal)
        log_handler.setFormatter(logging.Formatter('%(asctime)s [%(levelname)s] %(message)s'))
        log_handler.setLevel(logging.INFO)

        logger = logging.getLogger()
        logger.setLevel(logging.INFO)
        for handler in logger.handlers[:]:
            logger.removeHandler(handler)
        logger.addHandler(log_handler)

    def start_progress(self):
        self.mutex.lock()
        self.progress_bar.setValue(0)
        self.mutex.unlock()

        self.progress_bar.show()

    def update_progress(self):
        self.mutex.lock()
        self.task_complete_count += 1
        progress_value = int(round(self.task_complete_count / self.num_tasks, 2) * 100)
        self.progress_bar.setValue(progress_value)
        self.mutex.unlock()

    def reset_progress(self):
        self.threads.clear()
        self.finished_threads = 0
        self.num_tasks = 0
        self.task_complete_count = 0
        self.progress_bar.hide()

    def update_language(self):
        if self.current_language == 'en':
            self.current_language = 'cn'
        else:
            self.current_language = 'en'

        with open(CONFIG_FILE, 'w+', encoding='utf-8') as file:
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
        self.pause_button.setText(self.languages[self.current_language]['pause'])
        self.resume_button.setText(self.languages[self.current_language]['resume'])

        self.log_group.setTitle(self.languages[self.current_language]['log'])
        self.log_export_button.setText(self.languages[self.current_language]['export'])
        self.log_clear_button.setText(self.languages[self.current_language]['clear'])

    def select_save_dir(self):
        directory = QFileDialog.getExistingDirectory(self, self.languages[self.current_language]['select_save_dir'])
        if directory:
            self.save_dir_input.setText(directory)

    def run_downloader(self):
        logging.info('Input Checking...')
        venue_name = self.venue_input.currentText().strip()
        save_dir = self.save_dir_input.text().strip()
        sleep_time_per_paper = self.sleep_time_input.text().strip()
        keyword = self.keyword_input.text().strip()
        year = self.year_input.text().strip()
        volume = self.volume_input.text().strip()
        http_proxy = self.http_proxy_input.text().strip()
        https_proxy = self.https_proxy_input.text().strip()
        parallel = self.btn_group.checkedButton().text() == self.languages[self.current_language]['enable']

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
                logging.warning(
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
                logging.warning(
                    f'Warning: The journal "{venue_name}" does not require the year field, but it is currently set to "{year}".')

        try:
            sleep_time_per_paper = float(sleep_time_per_paper) if sleep_time_per_paper else DEFAULT_SLEEP_TIME
        except ValueError:
            QMessageBox.warning(self, 'Input Error', self.languages[self.current_language]['sleep_time_number'])
            return

        logging.info('Check complete!')

        # 更新按钮状态
        self.run_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        self.pause_button.setEnabled(True)
        self.resume_button.setEnabled(False)
        logging.info('Starting download...')

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
            proxies=proxies
        )

        paper_list = publisher_instance.get_paper_list()
        if not paper_list:
            logging.warning('The paper list is empty!')
            return

        self.num_tasks = len(paper_list)

        # 创建线程
        self.num_threads = os.cpu_count() if parallel else 1
        task_per_thread = (len(paper_list) + self.num_threads - 1) // self.num_threads
        for i in range(self.num_threads):
            thread = DownloaderThread(publisher=publisher_instance,
                                      paper_entry_list=paper_list[
                                                       i * task_per_thread: (i + 1) * task_per_thread])
            thread.finished_signal.connect(self.task_finished)
            thread.progress_signal.connect(self.update_progress)
            self.threads.append(thread)

        # 启动线程
        self.start_progress()
        for thread in self.threads:
            thread.start()

    def stop_downloader(self):
        if self.threads:
            confirm = QMessageBox.question(
                self,
                self.languages[self.current_language]['stop_confirm_title'],
                self.languages[self.current_language]['stop_confirm_text'],
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )
            if confirm == QMessageBox.Yes:
                for thread in self.threads:
                    thread.stop()
                    thread.wait()
        else:
            QMessageBox.information(self, 'Info', self.languages[self.current_language]['no_active_to_stop'])

    def pause_downloader(self):
        for thread in self.threads:
            thread.pause()
        self.run_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        self.pause_button.setEnabled(False)
        self.resume_button.setEnabled(True)

    def resume_downloader(self):
        for thread in self.threads:
            thread.resume()
        self.run_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        self.pause_button.setEnabled(True)
        self.resume_button.setEnabled(False)

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

    @pyqtSlot()
    def task_finished(self):
        self.mutex.lock()
        self.finished_threads += 1
        self.mutex.unlock()

        if self.finished_threads == self.num_threads:
            self.run_button.setEnabled(True)
            self.stop_button.setEnabled(False)
            self.pause_button.setEnabled(False)
            self.resume_button.setEnabled(False)

            self.reset_progress()
            logging.info('Download Finished!')


if __name__ == '__main__':
    app = QApplication(sys.argv)
    gui = PaperDownloaderGUI()
    gui.resize(800, 600)
    gui.show()
    sys.exit(app.exec_())
