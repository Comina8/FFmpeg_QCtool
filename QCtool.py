import os
import subprocess
import sys
import threading
import time
import datetime
import configparser
import tkinter.messagebox as tkmsg
from tkinter import filedialog, colorchooser, messagebox
import ntplib
import base64
import uuid
import re

from PyQt5 import QtWidgets, QtCore
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt5.QtGui import QPixmap
from PyQt5.QtWidgets import (QApplication, QFileDialog, QLabel, QMainWindow,
                             QMessageBox, QProgressBar)

def get_first_mac_address():
    # 모든 네트워크 인터페이스의 정보를 가져옵니다.
    nic_info = uuid.getnode()

    # MAC 주소를 가져옵니다.
    mac_address = hex(nic_info)[2:].zfill(12)
    mac_address = '-'.join(re.findall('..', mac_address))
    return mac_address


def generate_license_key():
    # MAC 주소와 4자리 숫자를 결합하여 라이선스 키를 생성합니다.
    mac_address = get_first_mac_address()
    custom_number = '1404'
    license_key = mac_address + custom_number
    license_key_base64 = base64.b64encode(license_key.encode('utf-8')).decode('utf-8')

    # license.ini 파일에 라이선스 키를 저장합니다.
    config = configparser.ConfigParser()
    config['general'] = {}
    config['general']['key'] = license_key_base64
    with open('license.ini', 'w') as configfile:
        config.write(configfile)


def is_valid_license_key():
    # license.ini 파일에서 라이선스 키를 읽어옵니다.
    config = configparser.ConfigParser()
    try:
        config.read('license.ini')
        license_key_base64 = config['general']['key']

        # 라이선스 키를 디코딩합니다.
        license_key = base64.b64decode(license_key_base64.encode('utf-8')).decode('utf-8')

        # 저장된 MAC 주소와 현재 시스템의 MAC 주소를 비교합니다.
        mac_address = get_first_mac_address()
        saved_mac_address = license_key[:17]
        if mac_address != saved_mac_address:
            return False
        else:
            return True
    except:
        return False

if __name__ == '__main__':
    if is_valid_license_key():
        print("Valid license key found. Running the program...")
        config = configparser.ConfigParser()
        config.read('license.ini')
        # 프로그램 실행 코드 추가
    else:
        messagebox.showinfo("알림", "라이센스 키가 올바르지 않습니다. 오프라인 사용이 제한됩니다.")
        config = configparser.ConfigParser()

        try:
            ntp_server = 'time.google.com'
        except Exception:
            messagebox.showerror("에러", "Error0001. 프로그램을 종료합니다.")
            sys.exit()

        ntp_client = ntplib.NTPClient()

        try:
            response = ntp_client.request(ntp_server)
        except Exception:
            messagebox.showerror("에러", "Error0002. 프로그램을 종료합니다.")
            sys.exit()
        if datetime.datetime.fromtimestamp(response.tx_time) < datetime.datetime(2024, 1, 1):
            pass
        else:
            messagebox.showinfo("알림", f"사용기한이 만료되었습니다. 프로그램이 종료됩니다.")
            sys.exit()

ffmpeg_path = 'ffmpeg.exe'
config = configparser.ConfigParser()
config.read('config.ini')
filter_str = config['general']['filter']

class QCThread(QThread):
    """비디오 QC를 수행하는 스레드"""
    
    progress_signal = pyqtSignal(str, int)
    message_signal = pyqtSignal(str)

    def __init__(self, file_path):
        super().__init__()
        self.file_path = file_path

    def run(self):
        # ffmpeg 명령어를 생성
        cmd = [
            ffmpeg_path,
            '-i', self.file_path,
            '-filter_complex', filter_str,
            '-threads', '16',
            '-f', 'null', '-'
        ]

        # ffmpeg 명령어를 실행
        process = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True, executable=ffmpeg_path, encoding='utf-8')

        # ffmpeg의 로그 메시지에서 결과를 추출
        freeze_detects = []
        black_detects = []
        silence_detects_ch1 = []
        silence_detects_ch2 = []

        for line in iter(process.stdout.readline, ""):
            line = line.replace('\xEB', ' ')
            print(f'{self.file_path} : {line.strip()}')
            start_time = 0.0
            duration = 0.0
            freeze_start_time = None

            if 'freeze_start' in line:
                freeze_start_time = float(line.split(':')[1].split()[0])
            elif 'freeze_duration' in line and freeze_start_time is not None:
                duration_seconds = float(line.split(':')[1].split()[0])
                start_time = str(datetime.timedelta(seconds=freeze_start_time)).split('.')[0]
                duration = str(datetime.timedelta(seconds=duration_seconds)).split('.')[0]
                start_time = datetime.datetime.strptime(start_time, '%H:%M:%S').strftime('%H:%M:%S')
                duration = datetime.datetime.strptime(duration, '%H:%M:%S').strftime('%H:%M:%S')
                freeze_detects.append((start_time, duration))
                freeze_start_time = None
            elif 'channel: 0 | silence_start' in line:
                silence_start_time_ch1 = float(line.split(':')[1].split()[0])
            elif 'channel: 1 | silence_start' in line:
                silence_start_time_ch2 = float(line.split(':')[1].split()[0])
            elif 'channel: 0 | silence_end' in line and silence_start_time_ch1 is not None:
                start_time = str(datetime.timedelta(seconds=silence_start_time_ch1)).split('.')[0]
                duration_seconds = float(line.split(':')[2].split()[0])
                duration = str(datetime.timedelta(seconds=duration_seconds)).split('.')[0]
                start_time = datetime.datetime.strptime(start_time, '%H:%M:%S').strftime('%H:%M:%S')
                duration = datetime.datetime.strptime(duration, '%H:%M:%S').strftime('%H:%M:%S')
                silence_detects_ch1.append((start_time, duration))
                silence_start_time_ch1 = None
            elif 'channel: 1 | silence_end' in line and silence_start_time_ch2 is not None:
                start_time = str(datetime.timedelta(seconds=silence_start_time_ch2)).split('.')[0]
                duration_seconds = float(line.split(':')[2].split()[0])
                duration = str(datetime.timedelta(seconds=duration_seconds)).split('.')[0]
                start_time = datetime.datetime.strptime(start_time, '%H:%M:%S').strftime('%H:%M:%S')
                duration = datetime.datetime.strptime(duration, '%H:%M:%S').strftime('%H:%M:%S')
                silence_detects_ch2.append((start_time, duration))
                silence_start_time_ch2 = None                
            elif 'black_start' in line:
                start_time_seconds = float(line.split(':')[1].split()[0])
                duration_seconds = float(line.split(':')[3].split()[0])
                start_time = str(datetime.timedelta(seconds=start_time_seconds)).split('.')[0]
                duration = str(datetime.timedelta(seconds=duration_seconds)).split('.')[0]
                start_time = datetime.datetime.strptime(start_time, '%H:%M:%S').strftime('%H:%M:%S')
                duration = datetime.datetime.strptime(duration, '%H:%M:%S').strftime('%H:%M:%S')
                black_detects.append((start_time, duration))
            
            #파일 길이 추출
            elif 'Duration:' in line:
                parts = line.strip().split(',')
                duration = parts[0].split('Duration: ')[1]
                duration = duration.split('.')[0]
                duration = datetime.datetime.strptime(duration, '%H:%M:%S')
                duration = duration - datetime.datetime(1900, 1, 1)
                duration = duration.total_seconds()
                self.duration = duration

            # ffmpeg의 로그 메시지 GUI에 업데이트
            if 'frame=' in line:
                parts = line.strip().split('time=')
                if len(parts) > 1:
                    time_part = parts[1].split()[0]
                    if len(time_part.split('.')) > 1:
                        time_part = time_part.split('.')[0]
                    if len(time_part.split(':')) == 3:
                        current_time = datetime.datetime.strptime(time_part, '%H:%M:%S')
                        current_time = current_time - datetime.datetime(1900, 1, 1)
                        current_time = current_time.total_seconds()
                        progress = int(current_time / self.duration * 100)
                        file_path = os.path.basename(self.file_path)
                        self.progress_signal.emit(file_path, progress)

        # 결과를 CSV 파일로 저장
        csv_file_path = os.path.splitext(self.file_path)[0] + '.csv'
        with open(csv_file_path, 'w') as f:
            f.write(f'검수 파일명 : {os.path.basename(self.file_path)}\n')
            f.write('검수 결과\n')
            if len(freeze_detects) == 0 and len(black_detects) == 0 and len(silence_detects_ch1) == 0 and len(silence_detects_ch2) == 0:
                f.write('오류가 없습니다.\n')
            else:
                for i, (start_time, duration) in enumerate(freeze_detects):
                    f.write(f'Freeze Detect-{i+1} : 시작 {start_time} 길이 {duration}\n')
                for i, (start_time, duration) in enumerate(black_detects):
                    f.write(f'Black Detect-{i+1} : 시작 {start_time} 길이 {duration}\n')
                for i, (start_time, duration) in enumerate(silence_detects_ch1):
                    f.write(f'Silence Detect_CH1-{i+1} : 시작 {start_time} 길이 {duration}\n')
                for i, (start_time, duration) in enumerate(silence_detects_ch2):
                    f.write(f'Silence Detect_CH2-{i+1} : 시작 {start_time} 길이 {duration}\n')

        # 결과를 메시지로 전송
        self.message_signal.emit(f'검수가 완료되었습니다. 결과는 {csv_file_path}에 저장되었습니다.')


class MainWindow(QMainWindow):
    """메인 윈도우"""

    def __init__(self):
        super().__init__()

        # 윈도우 타이틀 설정
        self.setWindowTitle('FFmpeg QC Tool - By SEOMINUK')

        # 윈도우 크기 설정
        self.setGeometry(100, 100, 420, 630)

        # QScrollArea 위젯 생성
        scroll_area = QtWidgets.QScrollArea(self)
        scroll_area.setGeometry(10, 120, 400, 500)
        scroll_area.setWidgetResizable(True)

        # QLabel 위젯 생성
        self.drop_label = QtWidgets.QLabel(scroll_area)
        self.drop_label.setAlignment(QtCore.Qt.AlignCenter)
        self.drop_label.setText('')

         # 파일 드래그&드롭 안내 문구 생성
        self.drop_label_b = QLabel(self)
        self.drop_label_b.setGeometry(10, 10, 400, 100)
        self.drop_label_b.setAlignment(Qt.AlignCenter)
        self.drop_label_b.setText('파일을 여기에 하나씩 Drag&Drop 하여 파일 검수를 시작하세요.\n여러파일 동시 검수 가능합니다.')

        # QLabel 위젯을 QScrollArea 위젯에 설정
        scroll_area.setWidget(self.drop_label)

        # 파일 드래그&드롭 이벤트 핸들러 등록
        self.setAcceptDrops(True)

        # QC를 수행하는 스레드
        self.qc_thread = None

    def dragEnterEvent(self, event):
        """파일 드래그&드롭 이벤트 처리"""

        # 파일인 경우에만 드롭 허용
        if event.mimeData().hasUrls():
            for url in event.mimeData().urls():
                if url.isLocalFile() and os.path.isfile(url.toLocalFile()):
                    event.accept()
                    return

        event.ignore()

    def dropEvent(self, event):
        """파일 드롭 핸들러"""

        # 파일 경로 추출
        file_path = event.mimeData().urls()[0].toLocalFile()

        # QC를 수행하는 스레드 생성 및 시작
        self.qc_thread = QCThread(file_path)
        self.qc_thread.message_signal.connect(self.show_message)
        self.qc_thread.progress_signal.connect(self.show_progress)
        self.qc_thread.start()

    def show_message(self, message):
        """메시지 박스 표시"""
        QMessageBox.information(self, '알림', message)

    def show_progress(self, file_path, progress):
        """진행 상황 표시"""
        current_text = self.drop_label.text()
        lines = current_text.split('\n')
        if file_path is not None:
            for i, line in enumerate(lines):
                if file_path in line:
                    # 파일 경로가 포함된 라인인 경우, 숫자 부분만 변경
                    parts = line.split(':')
                    file_name = parts[0].strip()
                    current_progress = int(parts[1].strip().replace('%', ''))
                    if current_progress != progress:
                        lines[i] = f'{file_name}: {progress}%'
                    break
            else:
                # 파일 경로가 포함되지 않은 라인인 경우, 새로운 라인 추가
                if current_text and current_text[-1] != '\n':
                    current_text += '\n'
                lines.append(f'{file_path}: {progress}%')
        else:
            # 파일 경로가 설정되지 않은 경우, 새로운 라인 추가
            if current_text and current_text[-1] != '\n':
                current_text += '\n'
            lines.append(f'진행 상황: {progress}%')
        self.drop_label.setText('\n'.join(lines))

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())
