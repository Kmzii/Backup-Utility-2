import sys
import json
import logging
import os
import shutil
import subprocess

from PyQt5.QtCore import QThread, pyqtSignal, Qt
from PyQt5.QtGui import QFont, QIcon
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QListWidget,
    QPushButton, QFileDialog, QMessageBox, QLabel, QGroupBox, QFormLayout,
    QProgressBar, QToolTip
)


class BackupWorker(QThread):
    progress_updated = pyqtSignal(int)  # Signal to update progress (0-100)
    status_updated = pyqtSignal(str)  # Signal to update status label
    completed = pyqtSignal()

    def __init__(self, items, destination_folder):
        super().__init__()
        self.items = items
        self.destination_folder = destination_folder
        self.total_items = len(items)  # Total items to backup

    def run(self):
        progress_step = 100 / self.total_items if self.total_items > 0 else 1
        current_progress = 0

        for index, item in enumerate(self.items):
            if os.path.isfile(item):
                self.backup_file(item)
            elif os.path.isdir(item):
                self.backup_folder(item)

            current_progress += progress_step
            self.progress_updated.emit(int(current_progress))

        self.completed.emit()

    def backup_file(self, file_path):
        destination_file_path = os.path.join(self.destination_folder, os.path.basename(file_path))
        try:
            if not self.is_same_file(file_path, destination_file_path):
                shutil.copy2(file_path, destination_file_path)
                self.status_updated.emit(f"Copied {file_path} to {destination_file_path}")
                logging.info(f"Copied {file_path} to {destination_file_path}")
            else:
                self.status_updated.emit(f"Skipped {file_path} (No changes)")
                logging.info(f"Skipped {file_path} (No changes)")
        except Exception as e:
            self.status_updated.emit(f"Error copying {file_path}: {e}")
            logging.error(f"Error copying {file_path}: {e}")

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
                self.status_updated.emit(f"Created new folder: {destination_path}")
                logging.info(f"Created new folder: {destination_path}")

            for root, _, files in os.walk(folder_path):
                for file in files:
                    file_path = os.path.join(root, file)
                    relative_path = os.path.relpath(root, folder_path)
                    destination_file_path = os.path.join(destination_path, relative_path, file)

                    destination_file_dir = os.path.dirname(destination_file_path)
                    if not os.path.exists(destination_file_dir):
                        os.makedirs(destination_file_dir)

                    if not self.is_same_file(file_path, destination_file_path):
                        try:
                            shutil.copy2(file_path, destination_file_path)
                            self.status_updated.emit(f"Copied {file_path} to {destination_file_path}")
                            logging.info(f"Copied {file_path} to {destination_file_path}")
                        except Exception as e:
                            self.status_updated.emit(f"Error copying {file_path}: {e}")
                            logging.error(f"Error copying {file_path}: {e}")
                    else:
                        self.status_updated.emit(f"Skipped {file_path} (No changes)")
                        logging.info(f"Skipped {file_path} (No changes)")

            summary_message = f"Backup completed for folder: {folder_path}"
            self.status_updated.emit(summary_message)
            logging.info(summary_message)
        except Exception as e:
            self.status_updated.emit(f"Error processing folder {folder_path}: {e}")
            logging.error(f"Error processing folder {folder_path}: {e}")


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

        self.add_file_button = QPushButton('Add File')
        self.add_folder_button = QPushButton('Add Folder')
        self.remove_button = QPushButton('Remove Selected')
        self.set_destination_button = QPushButton('Set Destination')
        self.backup_button = QPushButton('Backup')  # Make backup button an instance variable

        button_layout.addWidget(self.add_file_button)
        button_layout.addWidget(self.add_folder_button)
        button_layout.addWidget(self.remove_button)
        button_layout.addWidget(self.set_destination_button)
        button_layout.addWidget(self.backup_button)  # Use the instance variable
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

        open_log_button = QPushButton('Open Log File')
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

        # Adding h_layout to main_layout
        main_layout.addLayout(h_layout)

        # Progress Group
        progress_group = QGroupBox("Backup Progress")
        progress_layout = QVBoxLayout()

        self.progress_bar = QProgressBar()
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        progress_layout.addWidget(self.progress_bar)

        self.status_label = QLabel("Status: Idle")
        progress_layout.addWidget(self.status_label)

        progress_group.setLayout(progress_layout)
        main_layout.addWidget(progress_group)

        # Connect buttons to functions
        self.add_file_button.clicked.connect(self.add_file)
        self.add_folder_button.clicked.connect(self.add_folder)
        self.remove_button.clicked.connect(self.remove_selected)
        self.set_destination_button.clicked.connect(self.set_destination)
        self.backup_button.clicked.connect(self.start_backup)  # Use the instance variable

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
        self.destination_label.setFont(font)
        self.total_files_label.setFont(font)
        self.total_folders_label.setFont(font)
        self.status_label.setFont(font)

        # Set font for group headings
        for group_box in self.findChildren(QGroupBox):
            group_box.setFont(QFont(font.family(), font.pointSize() + 2))

        # Set font for buttons
        for button in self.findChildren(QPushButton):
            button.setFont(font)

        # Set font for progress bar
        self.progress_bar.setFont(font)

        # Set font for tooltips
        QToolTip.setFont(font)

    def add_file(self):
        options = QFileDialog.Options()
        files, _ = QFileDialog.getOpenFileNames(self, "Select Files to Backup", "", "All Files (*);;Text Files (*.txt)", options=options)
        for file in files:
            self.list_widget.addItem(file)
        self.update_info_labels()

    def add_folder(self):
        options = QFileDialog.Options()
        folder = QFileDialog.getExistingDirectory(self, "Select Folder to Backup", "", options=options)
        if folder:
            self.list_widget.addItem(folder)
        self.update_info_labels()

    def remove_selected(self):
        for item in self.list_widget.selectedItems():
            self.list_widget.takeItem(self.list_widget.row(item))
        self.update_info_labels()

    def set_destination(self):
        options = QFileDialog.Options()
        folder = QFileDialog.getExistingDirectory(self, "Select Destination Folder", options=options)
        if folder:
            self.destination_folder = folder
            self.destination_label.setText(f"Destination Folder: {folder}")

    def set_buttons_enabled(self, enabled):
        self.add_file_button.setEnabled(enabled)
        self.add_folder_button.setEnabled(enabled)
        self.remove_button.setEnabled(enabled)
        self.set_destination_button.setEnabled(enabled)
        self.backup_button.setEnabled(enabled)

    def start_backup(self):
        items = [self.list_widget.item(i).text() for i in range(self.list_widget.count())]
        if not items:
            QMessageBox.warning(self, "No Items", "Please add files or folders to backup.")
            return

        if not hasattr(self, 'destination_folder'):
            QMessageBox.warning(self, "No Destination", "Please set a destination folder.")
            return

        self.set_buttons_enabled(False)  # Disable all buttons
        self.worker = BackupWorker(items, self.destination_folder)
        self.worker.progress_updated.connect(self.update_progress)
        self.worker.status_updated.connect(self.update_status)
        self.worker.completed.connect(self.backup_complete)
        self.worker.start()

    def update_progress(self, progress):
        self.progress_bar.setValue(progress)

    def update_status(self, status):
        self.status_label.setText(f"Status: {status}")

    def backup_complete(self):
        self.set_buttons_enabled(True)  # Enable all buttons
        QMessageBox.information(self, "Backup Complete", "The backup process has completed.")

    def update_info_labels(self):
        total_files = sum(1 for i in range(self.list_widget.count()) if os.path.isfile(self.list_widget.item(i).text()))
        total_folders = sum(1 for i in range(self.list_widget.count()) if os.path.isdir(self.list_widget.item(i).text()))
        self.total_files_label.setText(f"Total Files: {total_files}")
        self.total_folders_label.setText(f"Total Folders: {total_folders}")

    def load_data(self):
        try:
            with open('backup_data.json', 'r') as f:
                data = json.load(f)
                self.destination_folder = data['destination_folder']
                self.destination_label.setText(f"Destination Folder: {self.destination_folder}")
                for item in data['items']:
                    self.list_widget.addItem(item)
                self.update_info_labels()
        except (FileNotFoundError, json.JSONDecodeError):
            pass

    def save_data(self):
        data = {
            'destination_folder': getattr(self, 'destination_folder', ''),
            'items': [self.list_widget.item(i).text() for i in range(self.list_widget.count())]
        }
        with open('backup_data.json', 'w') as f:
            json.dump(data, f)

    def closeEvent(self, event):
        self.save_data()
        event.accept()

    def open_log_file(self):
        try:
            os.startfile('backup.log')
        except AttributeError:
            subprocess.call(['open', 'backup.log'])


def setup_logging():
    logging.basicConfig(
        filename='backup.log',
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        filemode='w'  # Set the file mode to 'w' to overwrite the log file each time
    )


def main():
    app = QApplication(sys.argv)
    ex = BackupUtility()
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()
