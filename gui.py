import logging
import queue
import sys
from logging.handlers import QueueListener, QueueHandler

from PyQt5.QtCore import QThread, pyqtSignal, pyqtSlot, QMutex, QWaitCondition
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QFileDialog, QTextEdit, QMessageBox, QGridLayout, QGroupBox, QRadioButton,
    QButtonGroup, QMainWindow, QMenu, QAction, QComboBox
)

import utils
import venue
from log_handler import QtLogHandler


# -------------------------------------------
# 在GUI中显示日志的Logging Handler
class QtLogHandler(logging.Handler):
    def __init__(self, signal):
        super().__init__()
        self.signal = signal

    def emit(self, record):
        msg = self.format(record)
        self.signal.emit(msg)


_venues = venue.get_available_venues(lower_case=False)

_languages = {
    'cn': {
        'window_title': '面向开放获取刊物的学术论文批量下载器',

        'language': '语言',
        'language_switch': '切换到英文',
        'help': '帮助',
        'usage': '使用说明',
        'usage_text': f"""
            <b>开源论文批量下载器:</b><br>
            <ul>
                <li>在“基本设置”中填写必填字段。</li>
                <li>配置可选参数、代理和高级设置。</li>
                <li>点击“运行”按钮开始下载，或点击“暂停”按钮暂停。</li>
                <li>使用“切换到英文”按钮切换语言。</li>
            </ul>
            <p>目前可直接下载的刊物:<b>{_venues}</b><p>
            """,

        'basic_settings': '基本设置',
        'browse_btn': '浏览',
        'additional_params': '附加设置',
        'advanced_settings': '高级设置',
        'log': '日志',
        'venue_label': '会议:',
        'save_dir_label': '保存目录:',
        'sleep_time_label': '每篇论文间隔时间 (秒):',
        'keyword': '关键词:',
        'keyword_placeholder': '支持正则表达式',
        'year_label': '年份 (仅限会议):',
        'volume_label': '卷号 (仅限期刊):',
        'http_proxy_label': 'HTTP 代理:',
        'https_proxy_label': 'HTTPS 代理:',
        'parallel': '并行:',
        'enable': '启用',
        'disable': '禁用',
        'run': '运行',
        'stop': '停止',
        'pause': '暂停',
        'resume': '恢复'
    },
    'en': {
        'window_title': 'APBDOAV',

        'language': 'Language',
        'language_switch': 'Switch to Chinese',
        'help': 'Help',
        'usage': 'Usage',
        'usage_text': f"""
            <b>Academic Paper Bulk Downloader for Open Access Venues:</b><br>
            <ul>
                <li>Fill in the required fields under Basic Settings.</li>
                <li>Configure optional parameters, proxies, and advanced settings.</li>
                <li>Click "Run" to start downloading, or "Pause" to pause.</li>
                <li>Use the "Switch to Chinese" button to toggle languages.</li>
            </ul>
            <p>Currently supported venues:<b>{_venues}</b></p>
            """,

        'basic_settings': 'Basic Settings',
        'browse_btn': 'Browse',
        'additional_params': 'Additional Settings',
        'advanced_settings': 'Advanced Settings',
        'log': 'Log',
        'venue_label': 'Venue:',
        'save_dir_label': 'Save Directory:',
        'sleep_time_label': 'Sleep time per paper(second):',
        'keyword': 'Keyword:',
        'keyword_placeholder': 'Support regular expressions.',
        'year_label': 'Year (Conference Only):',
        'volume_label': 'Volume (Journal only):',
        'http_proxy_label': 'HTTP Proxy:',
        'https_proxy_label': 'HTTPS Proxy:',
        'parallel': 'Parallel:',
        'enable': 'Enable',
        'disable': 'Disable',
        'run': 'Run',
        'stop': 'Stop',
        'pause': 'Pause',
        'resume': 'Resume'
    }
}


# -------------------------------------------
# 任务执行的工作线程
class DownloaderThread(QThread):
    log_signal = pyqtSignal(str)
    error_signal = pyqtSignal(str)
    finished_signal = pyqtSignal(str)

    def __init__(self, publisher: type):
        super().__init__()
        self.publisher = publisher

        self.paused = False
        self.stop_flag = False
        self.mutex = QMutex()
        self.pause_condition = QWaitCondition()

        self.log_queue = queue.Queue()
        self.queue_handler = QueueHandler(self.log_queue)
        self.listener = None

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
        try:
            logger = logging.getLogger()
            logger.setLevel(logging.INFO)

            # 清除现有的 handler
            for h in logger.handlers[:]:
                logger.removeHandler(h)

            # 设置 QueueHandler
            logger.addHandler(self.queue_handler)

            # 设置 QueueListener
            qt_log_handler = QtLogHandler(self.log_signal)
            qt_log_handler.setFormatter(logging.Formatter('%(asctime)s [%(levelname)s] %(message)s'))
            self.listener = QueueListener(self.log_queue, qt_log_handler)
            self.listener.start()

            # 设置暂停和停止的回调
            if hasattr(self.publisher, 'set_pause_stop_callback'):
                self.publisher.set_pause_stop_callback(self.check_paused_or_stopped)
            else:
                self.log_signal.emit(f"Warning: Publisher '{self.publisher.venue_name}' does not support pause/resume.")
                self.error_signal.emit(f"Publisher '{self.publisher.venue_name}' does not support pause/resume.")

            self.publisher.process()

            self.finished_signal.emit("Download Finished.")

        except Exception as e:
            self.error_signal.emit(f"Error: {str(e)}")
        finally:
            if self.listener:
                self.listener.stop()
                self.listener = None


# -------------------------------------------
# GUI类定义
class PaperDownloaderGUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.current_language = 'en'  # Initialize default language
        self.init_ui()

    def init_ui(self):
        self.setWindowTitle(_languages[self.current_language]['window_title'])
        try:
            with open("gui.qss", "r", encoding="utf-8") as f:
                qss = f.read()
        except IOError:
            utils.print_and_exit('cannot find stylesheet.')
        self.setStyleSheet(qss)

        # Menu Bar
        menubar = self.menuBar()
        self.language_menu = QMenu(_languages[self.current_language]['language'], self)
        self.language_action = QAction(_languages[self.current_language]['language_switch'], self)
        self.language_action.triggered.connect(self.toggle_language)
        self.language_menu.addAction(self.language_action)
        menubar.addMenu(self.language_menu)

        self.help_menu = QMenu(_languages[self.current_language]['help'], self)
        self.help_action = QAction(_languages[self.current_language]['usage'], self)
        self.help_action.triggered.connect(self.show_usage_dialog)
        self.help_menu.addAction(self.help_action)
        menubar.addMenu(self.help_menu)

        central_widget = QWidget(self)
        self.setCentralWidget(central_widget)

        main_layout = QVBoxLayout()

        # Group 1: Basic Settings
        self.basic_settings = QGroupBox(_languages[self.current_language]['basic_settings'])
        basic_layout = QGridLayout()

        self.venue_label = QLabel(_languages[self.current_language]['venue_label'])
        basic_layout.addWidget(self.venue_label, 0, 0)
        self.venue_input = QComboBox()
        self.venue_input.addItems(venue.get_available_venue_list(lower_case=False))
        basic_layout.addWidget(self.venue_input, 0, 1)

        self.save_dir_label = QLabel(_languages[self.current_language]['save_dir_label'])
        basic_layout.addWidget(self.save_dir_label, 1, 0)
        self.save_dir_input = QLineEdit()
        basic_layout.addWidget(self.save_dir_input, 1, 1)

        self.browse_button = QPushButton(_languages[self.current_language]['browse_btn'])
        self.browse_button.clicked.connect(self.select_save_dir)
        basic_layout.addWidget(self.browse_button, 1, 2)

        self.sleep_time_label = QLabel(_languages[self.current_language]['sleep_time_label'])
        basic_layout.addWidget(self.sleep_time_label, 2, 0)
        self.sleep_time_input = QLineEdit('2')
        basic_layout.addWidget(self.sleep_time_input, 2, 1)

        self.keyword_label = QLabel(_languages[self.current_language]['keyword'])
        basic_layout.addWidget(self.keyword_label, 3, 0)
        self.keyword_input = QLineEdit()
        self.keyword_input.setPlaceholderText(_languages[self.current_language]['keyword_placeholder'])
        basic_layout.addWidget(self.keyword_input, 3, 1)

        self.basic_settings.setLayout(basic_layout)
        main_layout.addWidget(self.basic_settings)

        # Group 2: Additional Parameters
        self.additional_params = QGroupBox(_languages[self.current_language]['additional_params'])
        params_layout = QGridLayout()

        self.year_label = QLabel(_languages[self.current_language]['year_label'])
        params_layout.addWidget(self.year_label, 0, 0)
        self.year_input = QLineEdit()
        params_layout.addWidget(self.year_input, 0, 1)

        self.volume_label = QLabel(_languages[self.current_language]['volume_label'])
        params_layout.addWidget(self.volume_label, 1, 0)
        self.volume_input = QLineEdit()
        params_layout.addWidget(self.volume_input, 1, 1)

        self.additional_params.setLayout(params_layout)
        main_layout.addWidget(self.additional_params)

        # Group 3: Advanced Settings
        self.advanced_settings = QGroupBox(_languages[self.current_language]['advanced_settings'])
        self.http_proxy_label = QLabel(_languages[self.current_language]['http_proxy_label'])
        self.http_proxy_input = QLineEdit()

        self.https_proxy_label = QLabel(_languages[self.current_language]['https_proxy_label'])
        self.https_proxy_input = QLineEdit()

        self.parallel_label = QLabel(_languages[self.current_language]['parallel'])
        self.parallel_enable_button = QRadioButton(_languages[self.current_language]['enable'])
        self.parallel_disable_button = QRadioButton(_languages[self.current_language]['disable'])
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
        main_layout.addWidget(self.advanced_settings)

        execution_layout = QGridLayout()
        self.run_button = QPushButton(_languages[self.current_language]['run'])
        self.run_button.clicked.connect(self.run_downloader)
        self.stop_button = QPushButton(_languages[self.current_language]['stop'])
        self.stop_button.clicked.connect(self.stop_downloader)
        self.pause_resume_button = QPushButton(_languages[self.current_language]['pause'])
        self.pause_resume_button.clicked.connect(self.toggle_pause_resume)
        execution_layout.addWidget(self.run_button, 0, 0)
        execution_layout.addWidget(self.stop_button, 0, 1)
        execution_layout.addWidget(self.pause_resume_button, 0, 2)
        main_layout.addLayout(execution_layout)

        # 初始化按钮状态
        self.run_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        self.pause_resume_button.setEnabled(False)

        # Logs Section
        self.log_group = QGroupBox(_languages[self.current_language]['log'])
        log_layout = QVBoxLayout()
        self.log_output = QTextEdit()
        log_layout.addWidget(self.log_output)
        self.log_group.setLayout(log_layout)
        main_layout.addWidget(self.log_group)

        central_widget.setLayout(main_layout)

    def toggle_language(self):
        if self.current_language == 'en':
            self.current_language = 'cn'
        else:
            self.current_language = 'en'
        self.update_language()

    def update_language(self):
        self.setWindowTitle(_languages[self.current_language]['window_title'])

        self.language_menu.setTitle(_languages[self.current_language]['language'])
        self.language_action.setText(_languages[self.current_language]['language_switch'])
        self.help_menu.setTitle(_languages[self.current_language]['help'])
        self.help_action.setText(_languages[self.current_language]['usage'])

        self.basic_settings.setTitle(_languages[self.current_language]['basic_settings'])
        self.browse_button.setText(_languages[self.current_language]['browse_btn'])
        self.additional_params.setTitle(_languages[self.current_language]['additional_params'])
        self.advanced_settings.setTitle(_languages[self.current_language]['advanced_settings'])
        self.log_group.setTitle(_languages[self.current_language]['log'])

        self.venue_label.setText(_languages[self.current_language]['venue_label'])
        self.save_dir_label.setText(_languages[self.current_language]['save_dir_label'])
        self.sleep_time_label.setText(_languages[self.current_language]['sleep_time_label'])
        self.keyword_label.setText(_languages[self.current_language]['keyword'])
        self.keyword_input.setPlaceholderText(_languages[self.current_language]['keyword_placeholder'])

        self.year_label.setText(_languages[self.current_language]['year_label'])
        self.volume_label.setText(_languages[self.current_language]['volume_label'])

        self.http_proxy_label.setText(_languages[self.current_language]['http_proxy_label'])
        self.https_proxy_label.setText(_languages[self.current_language]['https_proxy_label'])
        self.parallel_label.setText(_languages[self.current_language]['parallel'])
        self.parallel_enable_button.setText(_languages[self.current_language]['enable'])
        self.parallel_disable_button.setText(_languages[self.current_language]['disable'])

        self.run_button.setText(_languages[self.current_language]['run'])
        self.stop_button.setText(_languages[self.current_language]['stop'])
        if self.thread and self.thread.paused:
            self.pause_resume_button.setText(_languages[self.current_language]['resume'])
        else:
            self.pause_resume_button.setText(_languages[self.current_language]['pause'])

    def select_save_dir(self):
        directory = QFileDialog.getExistingDirectory(self, 'Select Save Directory')
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
        parallel = self.btn_group.checkedButton().text() == _languages[self.current_language]['enable']

        self.log_output.clear()

        if not venue_name:
            QMessageBox.warning(self, 'Input Error', '"Venue" is a required field.')
            return

        if not save_dir:
            QMessageBox.warning(self, 'Input Error', '"Save directory" is a required field.')
            return

        # 解析venue
        venue_name_lower = venue.get_lower_name(venue_name)
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

            if volume:
                self.log_output.append(
                    f'Warning: The conference "{venue_name}" does not require the volume field, but it is currently set to "{volume}".')
        elif venue.is_journal(venue_publisher):
            if not volume:
                QMessageBox.warning(self, 'Input Error', '"Volume" is a required field.')
                return

            try:
                volume = int(volume)
            except ValueError:
                QMessageBox.warning(self, 'Input Error', '"Volume" must be an integer.')
                return

            if year:
                self.log_output.append(
                    f'Warning: The journal "{venue_name}" does not require the year field, but it is currently set to "{year}".')

        try:
            sleep_time_per_paper = float(sleep_time_per_paper) if sleep_time_per_paper else 2
        except ValueError:
            QMessageBox.warning(self, 'Input Error', '"Sleep time" must be a number.')
            return

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

        # 创建线程
        self.thread = DownloaderThread(publisher=publisher_instance)
        self.thread.log_signal.connect(self.append_log)
        self.thread.error_signal.connect(self.show_error)
        self.thread.finished_signal.connect(self.task_finished)
        self.thread.start()

        # 更新按钮状态
        self.run_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        self.pause_resume_button.setEnabled(True)
        self.pause_resume_button.setText(_languages[self.current_language]['pause'])

    def stop_downloader(self):
        if self.thread and self.thread.isRunning():
            confirm = QMessageBox.question(
                self, 'Confirm Stop', 'Are you sure you want to stop the download?',
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No
            )
            if confirm == QMessageBox.Yes:
                self.thread.stop()
                self.thread.wait()  # 等待线程结束
                self.log_output.append("Download stopped.")
                self.run_button.setEnabled(True)
                self.stop_button.setEnabled(False)
                self.pause_resume_button.setEnabled(False)
                self.pause_resume_button.setText(_languages[self.current_language]['pause'])
        else:
            QMessageBox.information(self, 'Info', 'No active download to stop.')

    def toggle_pause_resume(self):
        if not self.thread:
            return
        if self.thread.paused:
            # 恢复下载
            self.thread.resume()
            self.pause_resume_button.setText(_languages[self.current_language]['pause'])
        else:
            # 暂停下载
            self.thread.pause()
            self.pause_resume_button.setText(_languages[self.current_language]['resume'])

    @pyqtSlot(str)
    def append_log(self, log):
        self.log_output.append(log)
        self.log_output.ensureCursorVisible()

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
        self.pause_resume_button.setText(_languages[self.current_language]['pause'])

    @pyqtSlot(str)
    def task_finished(self, msg):
        self.log_output.append(msg)
        self.run_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        self.pause_resume_button.setEnabled(False)
        self.pause_resume_button.setText(_languages[self.current_language]['pause'])

    def show_usage_dialog(self):
        QMessageBox.information(self,
                                _languages[self.current_language]['usage'],
                                _languages[self.current_language]['usage_text'])


if __name__ == '__main__':
    app = QApplication(sys.argv)
    gui = PaperDownloaderGUI()
    gui.resize(800, 600)
    gui.show()
    sys.exit(app.exec_())
