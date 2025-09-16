import sys
import subprocess
import os
import urllib.request
import tempfile
import ctypes
import platform
from pathlib import Path

# 检查并尝试导入PyQt5，如果不存在则尝试安装
try:
    from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                                 QHBoxLayout, QTextEdit, QLineEdit, QPushButton, 
                                 QLabel, QProgressBar, QGroupBox, QMessageBox, QCheckBox)
    from PyQt5.QtCore import QThread, pyqtSignal, Qt
    from PyQt5.QtGui import QFont, QPalette, QColor
except ImportError:
    print("PyQt5未安装，尝试安装...")
    try:
        import pip
        pip.main(['install', 'pyqt5'])
        from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                                     QHBoxLayout, QTextEdit, QLineEdit, QPushButton, 
                                     QLabel, QProgressBar, QGroupBox, QMessageBox, QCheckBox)
        from PyQt5.QtCore import QThread, pyqtSignal, Qt
        from PyQt5.QtGui import QFont, QPalette, QColor
        print("PyQt5安装成功!")
    except:
        print("无法自动安装PyQt5，请手动安装: pip install pyqt5")
        sys.exit(1)

class CommandWorker(QThread):
    """工作线程，用于执行命令行操作"""
    output_signal = pyqtSignal(str)
    progress_signal = pyqtSignal(int)
    finished_signal = pyqtSignal(bool, str)

    def __init__(self, commands, cwd=None):
        super().__init__()
        self.commands = commands
        self.cwd = cwd
        self.is_running = True

    def run(self):
        try:
            total_commands = len(self.commands)
            for idx, command in enumerate(self.commands):
                if not self.is_running:
                    break
                    
                self.output_signal.emit(f"执行命令: {command}\n")
                self.progress_signal.emit(int((idx / total_commands) * 100))
                
                try:
                    # 执行命令并捕获输出
                    process = subprocess.Popen(
                        command, 
                        shell=True, 
                        stdout=subprocess.PIPE, 
                        stderr=subprocess.STDOUT,
                        cwd=self.cwd,
                        universal_newlines=True,
                        encoding='utf-8',
                        errors='replace'
                    )
                    
                    # 实时输出命令执行结果
                    for line in process.stdout:
                        if not self.is_running:
                            process.terminate()
                            break
                        self.output_signal.emit(line)
                    
                    process.wait()
                    
                    if process.returncode != 0:
                        self.output_signal.emit(f"\n命令执行失败，退出码: {process.returncode}\n")
                        self.finished_signal.emit(False, f"命令 '{command}' 执行失败")
                        return
                        
                except Exception as e:
                    self.output_signal.emit(f"\n执行命令时发生错误: {str(e)}\n")
                    self.finished_signal.emit(False, f"命令 '{command}' 执行错误: {str(e)}")
                    return
            
            self.progress_signal.emit(100)
            self.finished_signal.emit(True, "所有命令执行完成")
            
        except Exception as e:
            self.finished_signal.emit(False, f"执行过程中发生错误: {str(e)}")

    def stop(self):
        self.is_running = False


class DeploymentTool(QMainWindow):
    def __init__(self):
        super().__init__()
        self.worker = None
        self.git_installed = False
        self.conda_installed = False
        self.init_ui()
        self.check_dependencies()
        
    def init_ui(self):
        self.setWindowTitle("Git项目部署与Conda环境配置工具")
        self.setGeometry(100, 100, 900, 700)
        
        # 中央部件
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # 主布局
        layout = QVBoxLayout(central_widget)
        
        # 依赖检测组
        deps_group = QGroupBox("依赖检测")
        deps_layout = QVBoxLayout()
        
        # Git检测
        git_layout = QHBoxLayout()
        self.git_status = QLabel("检测中...")
        self.git_status.setStyleSheet("color: orange;")
        git_layout.addWidget(QLabel("Git:"))
        git_layout.addWidget(self.git_status)
        self.install_git_btn = QPushButton("安装Git")
        self.install_git_btn.clicked.connect(self.install_git)
        git_layout.addWidget(self.install_git_btn)
        git_layout.addStretch()
        deps_layout.addLayout(git_layout)
        
        # Conda检测
        conda_layout = QHBoxLayout()
        self.conda_status = QLabel("检测中...")
        self.conda_status.setStyleSheet("color: orange;")
        conda_layout.addWidget(QLabel("Conda:"))
        conda_layout.addWidget(self.conda_status)
        self.install_conda_btn = QPushButton("安装Miniconda")
        self.install_conda_btn.clicked.connect(self.install_miniconda)
        conda_layout.addWidget(self.install_conda_btn)
        conda_layout.addStretch()
        deps_layout.addLayout(conda_layout)
        
        deps_group.setLayout(deps_layout)
        layout.addWidget(deps_group)
        
        # 项目信息组
        project_group = QGroupBox("项目信息")
        project_layout = QVBoxLayout()
        
        # Git仓库URL
        url_layout = QHBoxLayout()
        url_layout.addWidget(QLabel("Git仓库URL:"))
        self.repo_url = QLineEdit("https://github.com/GEYUANwuqi/bilipy_bot.git")
        url_layout.addWidget(self.repo_url)
        project_layout.addLayout(url_layout)
        
        # 项目目录
        dir_layout = QHBoxLayout()
        dir_layout.addWidget(QLabel("项目目录:"))
        self.project_dir = QLineEdit(str(Path.home() / "bilipy_bot"))
        browse_btn = QPushButton("浏览...")
        browse_btn.clicked.connect(self.browse_directory)
        dir_layout.addWidget(self.project_dir)
        dir_layout.addWidget(browse_btn)
        project_layout.addLayout(dir_layout)
        
        project_group.setLayout(project_layout)
        layout.addWidget(project_group)
        
        # Conda环境组
        conda_group = QGroupBox("Conda环境配置")
        conda_layout = QVBoxLayout()
        
        # 环境名称
        env_layout = QHBoxLayout()
        env_layout.addWidget(QLabel("环境名称:"))
        self.env_name = QLineEdit("bilipy_bot")
        env_layout.addWidget(self.env_name)
        conda_layout.addLayout(env_layout)
        
        # Python版本
        pyver_layout = QHBoxLayout()
        pyver_layout.addWidget(QLabel("Python版本:"))
        self.py_version = QLineEdit("3.12.4")
        pyver_layout.addWidget(self.py_version)
        conda_layout.addLayout(pyver_layout)
        
        conda_group.setLayout(conda_layout)
        layout.addWidget(conda_group)
        
        # 选项
        options_layout = QHBoxLayout()
        self.auto_activate = QCheckBox("完成后自动激活环境")
        self.auto_activate.setChecked(True)
        options_layout.addWidget(self.auto_activate)
        options_layout.addStretch()
        layout.addLayout(options_layout)
        
        # 进度条
        self.progress_bar = QProgressBar()
        layout.addWidget(self.progress_bar)
        
        # 按钮
        btn_layout = QHBoxLayout()
        self.deploy_btn = QPushButton("开始部署")
        self.deploy_btn.clicked.connect(self.start_deployment)
        btn_layout.addWidget(self.deploy_btn)
        
        self.cancel_btn = QPushButton("取消")
        self.cancel_btn.clicked.connect(self.cancel_deployment)
        self.cancel_btn.setEnabled(False)
        btn_layout.addWidget(self.cancel_btn)
        
        layout.addLayout(btn_layout)
        
        # 输出窗口
        output_label = QLabel("输出日志:")
        layout.addWidget(output_label)
        self.output_area = QTextEdit()
        self.output_area.setReadOnly(True)
        layout.addWidget(self.output_area)
        
        # 设置样式
        self.apply_styles()
        
    def apply_styles(self):
        self.setStyleSheet("""
            QMainWindow {
                background-color: #f5f5f5;
            }
            QGroupBox {
                font-weight: bold;
                border: 2px solid #cccccc;
                border-radius: 5px;
                margin-top: 1ex;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
            }
            QPushButton {
                background-color: #4CAF50;
                border: none;
                color: white;
                padding: 8px 16px;
                text-align: center;
                text-decoration: none;
                font-size: 14px;
                margin: 4px 2px;
                border-radius: 4px;
            }
            QPushButton:disabled {
                background-color: #cccccc;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
            QPushButton#cancel_btn {
                background-color: #f44336;
            }
            QPushButton#cancel_btn:hover {
                background-color: #d32f2f;
            }
            QTextEdit {
                background-color: #2b2b2b;
                color: #ffffff;
                font-family: Consolas, monospace;
                border: 1px solid #444444;
                border-radius: 4px;
                font-size: 10pt;
            }
            QLineEdit {
                padding: 5px;
                border: 1px solid #cccccc;
                border-radius: 3px;
            }
        """)
        
        # 设置进度条样式
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                border: 2px solid grey;
                border-radius: 5px;
                text-align: center;
                height: 20px;
            }
            QProgressBar::chunk {
                background-color: #4CAF50;
                width: 10px;
            }
        """)
        
    def check_dependencies(self):
        """检查系统是否安装了必要的依赖"""
        self.append_output("正在检测系统依赖...")
        
        # 检查Git
        try:
            result = subprocess.run(["git", "--version"], capture_output=True, text=True, shell=True)
            if result.returncode == 0:
                self.git_installed = True
                self.git_status.setText("已安装")
                self.git_status.setStyleSheet("color: green;")
                self.install_git_btn.setEnabled(False)
                self.append_output(f"✓ Git已安装: {result.stdout.strip()}")
            else:
                self.git_installed = False
                self.git_status.setText("未安装")
                self.git_status.setStyleSheet("color: red;")
                self.append_output("✗ Git未安装")
        except:
            self.git_installed = False
            self.git_status.setText("未安装")
            self.git_status.setStyleSheet("color: red;")
            self.append_output("✗ Git未安装")
        
        # 检查Conda
        try:
            # 先尝试conda
            result = subprocess.run(["conda", "--version"], capture_output=True, text=True, shell=True)
            if result.returncode == 0:
                self.conda_installed = True
                self.conda_status.setText("已安装")
                self.conda_status.setStyleSheet("color: green;")
                self.install_conda_btn.setEnabled(False)
                self.append_output(f"✓ Conda已安装: {result.stdout.strip()}")
            else:
                # 尝试micromamba
                result = subprocess.run(["micromamba", "--version"], capture_output=True, text=True, shell=True)
                if result.returncode == 0:
                    self.conda_installed = True
                    self.conda_status.setText("已安装 (Micromamba)")
                    self.conda_status.setStyleSheet("color: green;")
                    self.install_conda_btn.setEnabled(False)
                    self.append_output(f"✓ Micromamba已安装: {result.stdout.strip()}")
                else:
                    self.conda_installed = False
                    self.conda_status.setText("未安装")
                    self.conda_status.setStyleSheet("color: red;")
                    self.append_output("✗ Conda/Micromamba未安装")
        except:
            self.conda_installed = False
            self.conda_status.setText("未安装")
            self.conda_status.setStyleSheet("color: red;")
            self.append_output("✗ Conda/Micromamba未安装")
            
        # 更新部署按钮状态
        self.update_deploy_button()
        
    def update_deploy_button(self):
        """更新部署按钮状态"""
        if self.git_installed and self.conda_installed:
            self.deploy_btn.setEnabled(True)
            self.deploy_btn.setToolTip("开始部署项目")
        else:
            self.deploy_btn.setEnabled(False)
            if not self.git_installed and not self.conda_installed:
                self.deploy_btn.setToolTip("请先安装Git和Conda")
            elif not self.git_installed:
                self.deploy_btn.setToolTip("请先安装Git")
            else:
                self.deploy_btn.setToolTip("请先安装Conda")
                
    def install_git(self):
        """安装Git"""
        self.append_output("开始安装Git...")
        
        # 根据系统类型选择不同的安装方式
        system = platform.system()
        if system == "Windows":
            # 下载Git for Windows
            git_url = "https://github.com/git-for-windows/git/releases/download/v2.45.1.windows.1/Git-2.45.1-64-bit.exe"
            try:
                import webbrowser
                webbrowser.open(git_url)
                self.append_output("已在浏览器中打开Git下载页面，请下载并安装Git")
                self.append_output("安装完成后请重启此工具")
            except:
                self.append_output("无法打开浏览器，请手动访问: https://git-scm.com/download/win")
        elif system == "Linux":
            # 提示Linux用户安装Git
            self.append_output("请使用包管理器安装Git:")
            self.append_output("Ubuntu/Debian: sudo apt install git")
            self.append_output("CentOS/RHEL: sudo yum install git")
            self.append_output("Fedora: sudo dnf install git")
        elif system == "Darwin":  # macOS
            self.append_output("请使用Homebrew安装Git: brew install git")
            self.append_output("或访问: https://git-scm.com/download/mac")
        else:
            self.append_output("请手动安装Git: https://git-scm.com/downloads")
            
    def install_miniconda(self):
        """安装Miniconda"""
        self.append_output("开始安装Miniconda...")
        
        system = platform.system()
        arch = platform.machine()
        
        if system == "Windows":
            # Windows版本
            conda_url = "https://repo.anaconda.com/miniconda/Miniconda3-latest-Windows-x86_64.exe"
            try:
                import webbrowser
                webbrowser.open(conda_url)
                self.append_output("已在浏览器中打开Miniconda下载页面，请下载并安装Miniconda")
                self.append_output("安装时请选择'Add to PATH'选项")
                self.append_output("安装完成后请重启此工具")
            except:
                self.append_output("无法打开浏览器，请手动访问: https://docs.conda.io/en/latest/miniconda.html")
        elif system == "Linux":
            # Linux版本
            if "aarch64" in arch or "arm64" in arch:
                conda_url = "https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-aarch64.sh"
            else:
                conda_url = "https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh"
                
            self.append_output(f"请运行以下命令安装Miniconda:")
            self.append_output(f"wget {conda_url} -O miniconda.sh")
            self.append_output("bash miniconda.sh -b -p $HOME/miniconda")
            self.append_output("source $HOME/miniconda/bin/activate")
            self.append_output("conda init")
        elif system == "Darwin":  # macOS
            if "arm64" in arch:
                conda_url = "https://repo.anaconda.com/miniconda/Miniconda3-latest-MacOSX-arm64.sh"
            else:
                conda_url = "https://repo.anaconda.com/miniconda/Miniconda3-latest-MacOSX-x86_64.sh"
                
            self.append_output(f"请运行以下命令安装Miniconda:")
            self.append_output(f"curl -O {conda_url}")
            self.append_output("bash Miniconda3-latest-MacOSX-*.sh -b -p $HOME/miniconda")
            self.append_output("source $HOME/miniconda/bin/activate")
            self.append_output("conda init")
        else:
            self.append_output("请手动安装Miniconda: https://docs.conda.io/en/latest/miniconda.html")
            
    def browse_directory(self):
        """浏览选择目录"""
        from PyQt5.QtWidgets import QFileDialog
        directory = QFileDialog.getExistingDirectory(self, "选择项目目录", str(Path.home()))
        if directory:
            self.project_dir.setText(directory)
        
    def start_deployment(self):
        # 检查依赖
        if not self.git_installed:
            QMessageBox.warning(self, "错误", "请先安装Git")
            return
            
        if not self.conda_installed:
            QMessageBox.warning(self, "错误", "请先安装Conda")
            return
        
        # 获取用户输入
        repo_url = self.repo_url.text().strip()
        project_dir = self.project_dir.text().strip()
        env_name = self.env_name.text().strip()
        py_version = self.py_version.text().strip()
        
        # 验证输入
        if not repo_url:
            QMessageBox.warning(self, "输入错误", "请输入Git仓库URL")
            return
            
        if not project_dir:
            QMessageBox.warning(self, "输入错误", "请输入项目目录")
            return
            
        if not env_name:
            QMessageBox.warning(self, "输入错误", "请输入Conda环境名称")
            return
            
        if not py_version:
            QMessageBox.warning(self, "输入错误", "请输入Python版本")
            return
        
        # 准备命令序列
        commands = [
            f"git clone {repo_url} {project_dir}",
            f"conda create -n {env_name} python={py_version} -y",
            f"conda activate {env_name} && pip install bilibili-api-python requests pywin32 pillow curl_cffi aiohttp aiofiles"
        ]
        
        # 更新UI状态
        self.deploy_btn.setEnabled(False)
        self.cancel_btn.setEnabled(True)
        self.output_area.clear()
        
        # 创建并启动工作线程
        self.worker = CommandWorker(commands, os.path.dirname(project_dir) if project_dir else None)
        self.worker.output_signal.connect(self.append_output)
        self.worker.progress_signal.connect(self.update_progress)
        self.worker.finished_signal.connect(self.deployment_finished)
        self.worker.start()
        
    def cancel_deployment(self):
        if self.worker and self.worker.isRunning():
            self.worker.stop()
            self.worker.wait()
            self.append_output("部署已取消")
            self.deployment_finished(False, "部署被用户取消")
        
    def append_output(self, text):
        self.output_area.moveCursor(self.output_area.textCursor().End)
        self.output_area.insertPlainText(text)
        self.output_area.moveCursor(self.output_area.textCursor().End)
        
    def update_progress(self, value):
        self.progress_bar.setValue(value)
        
    def deployment_finished(self, success, message):
        self.deploy_btn.setEnabled(True)
        self.cancel_btn.setEnabled(False)
        
        if success:
            QMessageBox.information(self, "成功", message)
            self.append_output("\n部署完成！")
            
            # 如果选择了自动激活环境
            if self.auto_activate.isChecked():
                env_name = self.env_name.text().strip()
                self.append_output(f"\n要激活环境，请运行: conda activate {env_name}")
        else:
            QMessageBox.critical(self, "错误", message)
            self.append_output("\n部署失败！")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = DeploymentTool()
    window.show()
    sys.exit(app.exec_())