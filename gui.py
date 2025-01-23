# -*- coding: utf-8 -*-
import json
import logging
import os
import sys
import threading
from datetime import datetime
from typing import List

from PyQt5.QtCore import QThread, pyqtSignal, pyqtSlot, QMutex, QWaitCondition, Qt, QUrl
from PyQt5.QtGui import QDesktopServices
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QFileDialog, QTextEdit,
    QMessageBox, QGridLayout, QGroupBox, QRadioButton,
    QButtonGroup, QMainWindow, QMenu, QAction, QComboBox,
    QProgressBar, QDialog
)
from core import utils, venue

##################################################################
#                            Constant                            #
##################################################################
LANGUAGE_FILE = utils.get_abs_path('config', os.path.join('i18n', 'lang.json'))
CONFIG_FILE = utils.get_abs_path('config', 'config.json')
QSS_FILE = utils.get_abs_path('config', 'gui.qss')
DEFAULT_SLEEP_TIME = 2

PROJECT_START_YEAR = 2024
PROJECT_VERSION = 'v1.0'
PROJECT_URL = 'https://github.com/hegongshan/paper-downloader'
PROJECT_AUTHORS = [
    '<a href="https://github.com/hegongshan">Gongshan He</a>',
    '<a href="https://github.com/zh-he">Zhihai He</a>'
]


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
class PaperListFetchThread(QThread):
    """
    专门用于获取 paper_list 的线程，防止在主线程里直接调用导致卡顿
    """
    paper_list_ready = pyqtSignal(list)
    error_signal = pyqtSignal(str)

    def __init__(self, publisher_instance):
        super().__init__()
        self.publisher_instance = publisher_instance

    def run(self):
        try:
            paper_list = self.publisher_instance.get_paper_list()
            self.paper_list_ready.emit(paper_list)
        except Exception as e:
            logging.exception("Exception occurred while fetching paper list.")
            self.error_signal.emit(str(e))


class DownloaderThread(QThread):
    progress_signal = pyqtSignal()
    finished_signal = pyqtSignal()
    resumed_signal = pyqtSignal()
    paused_signal = pyqtSignal()

    def __init__(self, publisher: type, paper_entry_list: List):
        super().__init__()
        self.publisher = publisher
        self.paper_entry_list = paper_entry_list

        self.paused = False
        self.stopped = False
        self.thread_id = None

        # 互斥锁 + 条件变量，用于暂停/恢复
        self.mutex = QMutex()
        self.condition = QWaitCondition()

    def pause(self):
        """请求暂停线程"""
        if self.isFinished():
            return
        self.mutex.lock()
        self.paused = True
        logging.info(f'Thread {self.thread_id} is pausing...')
        self.mutex.unlock()

    def resume(self):
        """请求恢复线程"""
        if self.isFinished():
            return
        self.mutex.lock()
        self.paused = False
        # 唤醒处于 wait() 的线程
        self.condition.wakeAll()
        logging.info(f'Thread {self.thread_id} is resuming...')
        self.mutex.unlock()

    def stop(self):
        """请求停止线程"""
        if self.isFinished():
            return
        self.mutex.lock()
        self.stopped = True
        # 如果当前处于暂停，也要唤醒，才能让 run() 里的 wait() 及时退出
        if self.paused:
            self.paused = False
            self.condition.wakeAll()
        logging.info(f'Thread {self.thread_id} is stopping...')
        self.mutex.unlock()

    def run(self):
        self.thread_id = threading.get_native_id()

        for paper_entry in self.paper_entry_list:
            self.mutex.lock()
            # 如果线程被请求停止，则立刻退出
            if self.stopped:
                self.mutex.unlock()
                break

            # 若处于暂停状态，则在这里等待
            if self.paused:
                logging.info(f'Thread {self.thread_id} has been paused.')
                self.paused_signal.emit()

                # 调用条件变量的 wait，会释放 mutex 并阻塞当前线程
                self.condition.wait(self.mutex)

                # 被唤醒后，若没有 stopped，则说明是 resume()
                if not self.stopped:
                    logging.info(f'Thread {self.thread_id} has been resumed.')
                    self.resumed_signal.emit()

            # 再次检查是否 stop，以防在暂停期间被 stop
            if self.stopped:
                self.mutex.unlock()
                break
            self.mutex.unlock()

            # 真正去执行任务
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
        self.paused_count = 0
        self.resumed_count = 0

        # 新增一个用于获取 paper_list 的线程引用
        self.list_fetch_thread = None
        self.publisher_instance = None

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
        self.setWindowTitle(self.languages[self.current_language]['project_abbreviation'])

        # Menu Bar
        menubar = self.menuBar()
        # Language Menu
        self.language_menu = QMenu(self.languages[self.current_language]['language'], self)
        self.language_action = QAction(self.languages[self.current_language]['language_switch'], self)
        self.language_action.triggered.connect(self.update_language)
        self.language_menu.addAction(self.language_action)
        menubar.addMenu(self.language_menu)
        # Help Menu
        self.help_menu = QMenu(self.languages[self.current_language]['help'])
        self.help_action = QAction(self.languages[self.current_language]['help'])
        self.help_action.triggered.connect(self.open_project_link)
        self.about_action = QAction(self.languages[self.current_language]['about'])
        self.about_action.triggered.connect(self.show_about)
        self.help_menu.addAction(self.help_action)
        self.help_menu.addAction(self.about_action)
        menubar.addMenu(self.help_menu)

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

    @staticmethod
    def open_project_link():
        QDesktopServices.openUrl(QUrl(PROJECT_URL))

    def show_about(self):
        about_dialog = QDialog()
        about_dialog.setWindowTitle(self.languages[self.current_language]['about'])
        vbox_layout = QVBoxLayout()

        project_name_label = QLabel(self.languages[self.current_language]['project_name'])
        project_name_label.setAlignment(Qt.AlignCenter)
        vbox_layout.addWidget(project_name_label)

        grid_layout = QGridLayout()
        project_abbreviation_label = QLabel(self.languages[self.current_language]['abbreviation'])
        project_abbreviation_content = QLabel(self.languages[self.current_language]['project_abbreviation'])
        project_version_label = QLabel(self.languages[self.current_language]['version'])
        project_version_content = QLabel(PROJECT_VERSION)
        author_label = QLabel(self.languages[self.current_language]["author"])
        author_list = QLabel(', '.join(PROJECT_AUTHORS))
        author_list.setOpenExternalLinks(True)
        grid_layout.addWidget(project_abbreviation_label, 0, 0)
        grid_layout.addWidget(project_abbreviation_content, 0, 1)
        grid_layout.addWidget(project_version_label, 1, 0)
        grid_layout.addWidget(project_version_content, 1, 1)
        grid_layout.addWidget(author_label, 2, 0)
        grid_layout.addWidget(author_list, 2, 1)
        vbox_layout.addLayout(grid_layout)

        copyright_label = QLabel(f'Copyright © {PROJECT_START_YEAR}-{datetime.now().year}')
        copyright_label.setAlignment(Qt.AlignCenter)
        vbox_layout.addWidget(copyright_label)

        about_dialog.setLayout(vbox_layout)
        about_dialog.exec_()

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

        self.setWindowTitle(self.languages[self.current_language]['project_abbreviation'])

        self.language_menu.setTitle(self.languages[self.current_language]['language'])
        self.language_action.setText(self.languages[self.current_language]['language_switch'])
        self.help_menu.setTitle(self.languages[self.current_language]['help'])
        self.help_action.setText(self.languages[self.current_language]['help'])
        self.about_action.setText(self.languages[self.current_language]['about'])

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
            return

        # 判定是会议还是期刊，并检查 year/volume
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
                    f'Warning: The conference "{venue_name}" does not require the volume field, but it is currently set to "{volume}".'
                )
        else:
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
                    f'Warning: The journal "{venue_name}" does not require the year field, but it is currently set to "{year}".'
                )

        try:
            sleep_time_per_paper = float(sleep_time_per_paper) if sleep_time_per_paper else DEFAULT_SLEEP_TIME
        except ValueError:
            QMessageBox.warning(self, 'Input Error', self.languages[self.current_language]['sleep_time_number'])
            return

        logging.info('Check complete!')

        # 更新按钮状态，先全部禁用，等获取列表成功后再启用
        self.run_button.setEnabled(False)
        self.stop_button.setEnabled(False)
        self.pause_button.setEnabled(False)
        self.resume_button.setEnabled(False)
        logging.info('Starting to fetch paper list...')

        # 设置代理
        proxies = {}
        if http_proxy:
            proxies['http'] = http_proxy
        if https_proxy:
            proxies['https'] = https_proxy

        # 实例化publisher
        self.publisher_instance = venue_publisher(
            save_dir=save_dir,
            sleep_time_per_paper=sleep_time_per_paper,
            keyword=keyword,
            venue_name=venue_name_lower,
            year=year,
            volume=volume,
            proxies=proxies
        )

        # 显示进度条，提示用户正在获取列表
        self.progress_bar.setValue(0)
        self.progress_bar.setFormat("Fetching paper list...")
        self.progress_bar.show()

        # 启动获取列表的线程
        self.list_fetch_thread = PaperListFetchThread(self.publisher_instance)
        self.list_fetch_thread.paper_list_ready.connect(self.on_paper_list_ready)
        self.list_fetch_thread.error_signal.connect(self.on_paper_list_error)
        self.list_fetch_thread.start()

    @pyqtSlot(list)
    def on_paper_list_ready(self, paper_list):
        self.list_fetch_thread = None

        self.progress_bar.setFormat("%p%")
        # 重置进度条文字
        if not paper_list:
            logging.warning('The paper list is empty!')
            QMessageBox.information(self, "Info", "No papers to download.")
            self.reset_progress()
            self.run_button.setEnabled(True)
            return

        logging.info(f"{len(paper_list)} papers have been fetched.")
        self.num_tasks = len(paper_list)
        self.task_complete_count = 0

        # 判断并行/串行
        parallel = (self.btn_group.checkedButton().text() == self.languages[self.current_language]['enable'])
        self.num_threads = min(os.cpu_count(), self.publisher_instance.max_thread_count) if parallel else 1
        logging.info(f"The total number of threads is {self.num_threads}.")

        # 进行任务切分并创建 DownloaderThread
        task_per_thread = (len(paper_list) + self.num_threads - 1) // self.num_threads
        for i in range(self.num_threads):
            sub_list = paper_list[i * task_per_thread: (i + 1) * task_per_thread]
            thread = DownloaderThread(
                publisher=self.publisher_instance,
                paper_entry_list=sub_list
            )
            thread.finished_signal.connect(self.finish_downloader)
            thread.progress_signal.connect(self.update_progress)
            thread.paused_signal.connect(self.on_thread_paused)
            thread.resumed_signal.connect(self.on_thread_resumed)
            self.threads.append(thread)

        # 更新按钮状态
        self.stop_button.setEnabled(True)
        self.pause_button.setEnabled(True)
        self.resume_button.setEnabled(False)

        # 启动下载线程
        self.start_progress()
        for thread in self.threads:
            thread.start()

    @pyqtSlot(str)
    def on_paper_list_error(self, err_msg):
        """
        当 PaperListFetchThread 出错时，触发此槽函数
        """
        self.list_fetch_thread = None
        logging.error(f"Failed to fetch paper list: {err_msg}")
        QMessageBox.critical(self, "Error", f"Error while fetching paper list:\n{err_msg}")

        self.reset_progress()
        # 恢复“Run”按钮可用
        self.run_button.setEnabled(True)

    def stop_downloader(self):
        """点击「Stop」按钮后，仅发送停止请求，不阻塞主线程"""
        if self.threads:
            confirm = QMessageBox.question(
                self,
                self.languages[self.current_language]['stop_confirm_title'],
                self.languages[self.current_language]['stop_confirm_text'],
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )
            if confirm == QMessageBox.Yes:
                logging.info('Stopping all downloader threads...')
                for thread in self.threads:
                    thread.stop()
                logging.info('Stop signal sent to all downloader threads.')
        else:
            QMessageBox.information(self, 'Info', self.languages[self.current_language]['no_active_to_stop'])

    def pause_downloader(self):
        logging.info('Pausing all downloader threads...')
        # 重置 paused_count/resumed_count
        self.paused_count = 0
        self.resumed_count = 0

        for thread in self.threads:
            thread.pause()

        self.run_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        self.pause_button.setEnabled(False)
        self.resume_button.setEnabled(True)

    def resume_downloader(self):
        logging.info('Resuming all downloader threads...')
        self.resumed_count = 0

        for thread in self.threads:
            thread.resume()

        self.run_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        self.pause_button.setEnabled(True)
        self.resume_button.setEnabled(False)

    @pyqtSlot()
    def on_thread_paused(self):
        """某个线程进入 paused 状态时的回调"""
        self.mutex.lock()
        self.paused_count += 1
        if self.paused_count == self.num_threads:
            logging.info("All threads have been paused.")
        self.mutex.unlock()

    @pyqtSlot()
    def on_thread_resumed(self):
        """某个线程恢复时的回调"""
        self.mutex.lock()
        self.resumed_count += 1
        if self.resumed_count == self.num_threads:
            logging.info("All threads have been resumed.")
        self.mutex.unlock()

    @pyqtSlot()
    def finish_downloader(self):
        """某个线程结束时的回调"""
        self.mutex.lock()
        self.finished_threads += 1
        if self.finished_threads == self.num_threads:
            # 所有线程都结束
            self.run_button.setEnabled(True)
            self.stop_button.setEnabled(False)
            self.pause_button.setEnabled(False)
            self.resume_button.setEnabled(False)
            logging.info('All downloader threads have been stopped or finished normally.')
            logging.info('Download Finished!')
            QMessageBox.information(self, "Finish", self.languages[self.current_language]['task_completed'])
            self.reset_progress()
        self.mutex.unlock()

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
        if filename:
            with open(filename, 'a', encoding='utf-8') as file:
                file.write(log)
                file.write('\n')

    @pyqtSlot()
    def clear_log(self):
        self.log_output.clear()


if __name__ == '__main__':
    app = QApplication(sys.argv)
    gui = PaperDownloaderGUI()
    gui.resize(600, 600)
    gui.show()
    sys.exit(app.exec_())
