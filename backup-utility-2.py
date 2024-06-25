import sys
import json
import logging

from PyQt5.QtGui import QFont, QIcon
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QListWidget,
    QPushButton, QFileDialog, QMessageBox, QLabel, QProgressBar,
    QGroupBox, QFormLayout, QGridLayout
)
from PyQt5.QtCore import QThread, pyqtSignal
import shutil
import os


class BackupWorker(QThread):
    progress = pyqtSignal(str, int)
    completed = pyqtSignal()

    def __init__(self, items, destination_folder):
        super().__init__()
        self.items = items
        self.destination_folder = destination_folder
        self.total_files = 0
        self.processed_files = 0

    def run(self):
        self.total_files = self.calculate_total_files(self.items)
        for item in self.items:
            if os.path.isfile(item):
                self.backup_file(item)
            elif os.path.isdir(item):
                self.backup_folder(item)
        self.completed.emit()

    def calculate_total_files(self, items):
        total_files = 0
        for item in items:
            if os.path.isfile(item):
                total_files += 1
            elif os.path.isdir(item):
                for _, _, files in os.walk(item):
                    total_files += len(files)
        return total_files

    def update_progress(self, message):
        self.processed_files += 1
        progress_percent = int((self.processed_files / self.total_files) * 100)
        self.progress.emit(message, progress_percent)

    def backup_file(self, file_path):
        destination_file_path = os.path.join(self.destination_folder, os.path.basename(file_path))
        try:
            if not self.is_same_file(file_path, destination_file_path):
                shutil.copy2(file_path, destination_file_path)
                self.update_progress(f"Copied {file_path} to {destination_file_path}")
                logging.info(f"Copied {file_path} to {destination_file_path}")
            else:
                self.update_progress(f"Skipped {file_path} (No changes)")
                logging.info(f"Skipped {file_path} (No changes)")
        except Exception as e:
            self.update_progress(f"Skipped {file_path} ({e})")
            logging.warning(f"Skipped {file_path} ({e})")

    def is_same_file(self, src, dst):
        if not os.path.exists(dst):
            return False
        return os.path.getmtime(src) == os.path.getmtime(dst) and os.path.getsize(src) == os.path.getsize(dst)

    def backup_folder(self, folder_path):
        folder_name = os.path.basename(folder_path)
        destination_path = os.path.join(self.destination_folder, folder_name)
        try:
            if not os.path.exists(destination_path):
                os.makedirs(destination_path)
                logging.info(f"Created new folder: {destination_path}")

            num_files = 0
            num_copied = 0
            num_skipped = 0

            for root, dirs, files in os.walk(folder_path):
                for file in files:
                    num_files += 1
                    file_path = os.path.join(root, file)
                    relative_path = os.path.relpath(root, folder_path)
                    destination_file_path = os.path.join(destination_path, relative_path, file)

                    destination_file_dir = os.path.dirname(destination_file_path)
                    if not os.path.exists(destination_file_dir):
                        os.makedirs(destination_file_dir)

                    if not self.is_same_file(file_path, destination_file_path):
                        try:
                            shutil.copy2(file_path, destination_file_path)
                            num_copied += 1
                            self.update_progress(f"Copied {file_path} to {destination_file_path}")
                            logging.info(f"Copied {file_path} to {destination_file_path}")
                        except Exception as e:
                            num_skipped += 1
                            self.update_progress(f"Skipped {file_path} ({e})")
                            logging.warning(f"Skipped {file_path} ({e})")
                    else:
                        num_skipped += 1
                        self.update_progress(f"Skipped {file_path} (No changes)")
                        logging.info(f"Skipped {file_path} (No changes)")

            summary_message = f"Detected {num_files} files in {folder_path}, copied {num_copied}, skipped {num_skipped}"
            self.update_progress(summary_message)
            logging.info(summary_message)
        except Exception as e:
            self.update_progress(f"Skipped folder: {folder_path} ({e})")
            logging.warning(f"Skipped folder: {folder_path} ({e})")


class BackupUtility(QWidget):
    def __init__(self):
        super().__init__()
        self.initUI()
        self.load_data()
        setup_logging()

    def initUI(self):
        # Main layout
        main_layout = QVBoxLayout()

        # Horizontal layout for list and buttons
        h_layout = QHBoxLayout()

        # File and Folder List Group
        list_group = QGroupBox("Files and Folders to Backup")
        list_layout = QVBoxLayout()
        self.list_widget = QListWidget()
        list_layout.addWidget(self.list_widget)
        list_group.setLayout(list_layout)

        # Adding list group to horizontal layout
        h_layout.addWidget(list_group)

        # Vertical layout for Actions and Info Groups
        actions_info_layout = QVBoxLayout()

        # Button Group
        button_group = QGroupBox("Actions")
        button_layout = QVBoxLayout()

        add_file_button = QPushButton('Add File')
        add_folder_button = QPushButton('Add Folder')
        remove_button = QPushButton('Remove Selected')
        set_destination_button = QPushButton('Set Destination')
        backup_button = QPushButton('Backup')

        button_layout.addWidget(add_file_button)
        button_layout.addWidget(add_folder_button)
        button_layout.addWidget(remove_button)
        button_layout.addWidget(set_destination_button)
        button_layout.addWidget(backup_button)
        button_layout.addStretch()
        button_group.setLayout(button_layout)

        # Setting fixed width for button group
        button_group.setFixedWidth(300)

        # Adding button group to actions_info_layout
        actions_info_layout.addWidget(button_group)

        # Info Group
        self.info_group = QGroupBox("Info")
        info_layout = QVBoxLayout()

        self.destination_label = QLabel("Destination Folder: Not set")
        self.total_files_label = QLabel("Total Files: 0")
        self.total_folders_label = QLabel("Total Folders: 0")

        open_log_button = QPushButton()
        open_log_button.setIcon(QIcon('assets/log-file.svg'))
        open_log_button.clicked.connect(self.open_log_file)

        info_layout.addWidget(self.destination_label)
        info_layout.addWidget(self.total_files_label)
        info_layout.addWidget(self.total_folders_label)
        info_layout.addWidget(open_log_button)
        info_layout.addStretch()
        self.info_group.setLayout(info_layout)
        self.info_group.setFixedWidth(300)

        # Adding info group to actions_info_layout
        actions_info_layout.addWidget(self.info_group)

        # Adding actions_info_layout to h_layout
        h_layout.addLayout(actions_info_layout)

        # Progress and Status Group
        progress_group = QGroupBox("Backup Progress")
        progress_layout = QVBoxLayout()
        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        self.status_label = QLabel('')
        progress_layout.addWidget(self.progress_bar)
        progress_layout.addWidget(self.status_label)
        progress_group.setLayout(progress_layout)

        # Adding progress group to main_layout
        main_layout.addLayout(h_layout)
        main_layout.addWidget(progress_group)

        # Connect buttons to functions
        add_file_button.clicked.connect(self.add_file)
        add_folder_button.clicked.connect(self.add_folder)
        remove_button.clicked.connect(self.remove_selected)
        set_destination_button.clicked.connect(self.set_destination)
        backup_button.clicked.connect(self.start_backup)

        self.setLayout(main_layout)
        self.setWindowTitle('Backup Utility')
        self.setMinimumSize(960, 700)  # Set minimum size here
        self.show()

        # Increase font size for all widgets and set heading fonts
        self.update_fonts()

    def update_fonts(self):
        font = QFont()
        font.setPointSize(10)  # Adjust the font size as needed

        # Set font for all widgets
        self.list_widget.setFont(font)
        self.progress_bar.setFont(font)
        self.status_label.setFont(font)
        self.destination_label.setFont(font)
        self.total_files_label.setFont(font)
        self.total_folders_label.setFont(font)

        # Set font for group headings
        for group_box in self.findChildren(QGroupBox):
            group_box.setFont(QFont(font.family(), font.pointSize() + 2))

        # Set font for buttons
        for button in self.findChildren(QPushButton):
            button.setFont(font)

    def add_file(self):
        options = QFileDialog.Options()
        file, _ = QFileDialog.getOpenFileName(self, "Select File to Add", "", "All Files (*)", options=options)
        if file:
            self.list_widget.addItem(file)
            self.update_info_labels()

    def add_folder(self):
        options = QFileDialog.Options()
        folder = QFileDialog.getExistingDirectory(self, "Select Folder to Add", options=options)
        if folder:
            self.list_widget.addItem(folder)
            self.update_info_labels()

    def remove_selected(self):
        selected_items = self.list_widget.selectedItems()
        if not selected_items:
            return
        for item in selected_items:
            self.list_widget.takeItem(self.list_widget.row(item))
        self.update_info_labels()

    def set_destination(self):
        options = QFileDialog.Options()
        self.destination_folder = QFileDialog.getExistingDirectory(self, "Select Destination Folder", options=options)
        if self.destination_folder:
            self.destination_label.setText(f"Destination Folder: {self.destination_folder}")
            QMessageBox.information(self, "Destination Set", f"Backup destination set to: {self.destination_folder}")

    def start_backup(self):
        if not hasattr(self, 'destination_folder') or not self.destination_folder:
            QMessageBox.warning(self, "No Destination", "Please set a backup destination first.")
            return

        items = [self.list_widget.item(i).text() for i in range(self.list_widget.count())]
        if not items:
            QMessageBox.warning(self, "No Items", "Please add files or folders to backup.")
            return

        self.status_label.setText('Backup in progress...')
        self.progress_bar.setValue(0)
        self.backup_worker = BackupWorker(items, self.destination_folder)
        self.backup_worker.progress.connect(self.update_progress)
        self.backup_worker.completed.connect(self.backup_complete)
        self.backup_worker.start()

    def update_progress(self, item, progress):
        self.status_label.setText(f'Backing up: {item}')
        self.progress_bar.setValue(progress)

    def backup_complete(self):
        self.status_label.setText('Backup completed successfully.')
        QMessageBox.information(self, "Backup Complete", "Backup completed successfully.")

    def closeEvent(self, event):
        self.save_data()
        event.accept()

    def save_data(self):
        items = [self.list_widget.item(i).text() for i in range(self.list_widget.count())]
        data = {
            'items': items,
            'destination_folder': getattr(self, 'destination_folder', '')
        }
        with open('backup_data.json', 'w') as f:
            json.dump(data, f)

    def load_data(self):
        if os.path.exists('backup_data.json'):
            with open('backup_data.json', 'r') as f:
                data = json.load(f)
                for item in data.get('items', []):
                    self.list_widget.addItem(item)
                self.destination_folder = data.get('destination_folder', '')
                if self.destination_folder:
                    self.destination_label.setText(f"Destination Folder: {self.destination_folder}")
        self.update_info_labels()

    def update_info_labels(self):
        total_files = 0
        total_folders = 0

        for i in range(self.list_widget.count()):
            item_path = self.list_widget.item(i).text()
            if os.path.isfile(item_path):
                total_files += 1
            elif os.path.isdir(item_path):
                total_folders += 1

        self.total_files_label.setText(f"Total Files: {total_files}")
        self.total_folders_label.setText(f"Total Folders: {total_folders}")

    def open_log_file(self):
        try:
            os.startfile('backup.log')  # Opens the log file using the default application
        except OSError as e:
            QMessageBox.warning(self, "Error Opening Log File", f"Failed to open log file: {e}")


def setup_logging():
    logging.basicConfig(filename='backup.log', level=logging.INFO,
                        format='%(asctime)s - %(levelname)s - %(message)s')


if __name__ == '__main__':
    app = QApplication(sys.argv)
    backup_utility = BackupUtility()
    sys.exit(app.exec_())
