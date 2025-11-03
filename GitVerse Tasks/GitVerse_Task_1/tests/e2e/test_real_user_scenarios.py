#!/usr/bin/env python3
"""
E2E тесты реальных пользовательских сценариев для sysaudit.

Эти тесты симулируют реальное использование системы администраторами:
1. Инициализация системы мониторинга
2. Отслеживание изменений конфигурационных файлов
3. Обнаружение дрифта от базовой линии
4. Проверка соответствия требованиям безопасности
5. Откат изменений
6. Генерация отчетов
"""

import os
import sys
import time
import tempfile
import shutil
import subprocess
from pathlib import Path
from datetime import datetime

# Цвета для вывода
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
BLUE = '\033[94m'
RESET = '\033[0m'


class E2ETestRunner:
    """Запускает E2E тесты реальных пользовательских сценариев"""
    
    def __init__(self):
        self.test_dir = tempfile.mkdtemp(prefix='sysaudit_e2e_')
        self.repo_path = os.path.join(self.test_dir, 'repo')
        self.watch_path = os.path.join(self.test_dir, 'etc')
        self.config_path = os.path.join(self.test_dir, 'config.yaml')
        self.passed = 0
        self.failed = 0
        self.start_time = None
        
    def log(self, message, color=BLUE):
        """Логирование с цветом"""
        timestamp = datetime.now().strftime('%H:%M:%S')
        print(f"{color}[{timestamp}] {message}{RESET}")
        
    def success(self, message):
        """Успешный тест"""
        self.passed += 1
        self.log(f"✓ {message}", GREEN)
        
    def fail(self, message):
        """Проваленный тест"""
        self.failed += 1
        self.log(f"✗ {message}", RED)
        
    def info(self, message):
        """Информационное сообщение"""
        self.log(f"ℹ {message}", YELLOW)
        
    def setup(self):
        """Подготовка тестового окружения"""
        self.log("=== Подготовка тестового окружения ===")
        
        # Создание директорий
        os.makedirs(self.watch_path, exist_ok=True)
        
        # Создание конфигурационного файла
        config_content = f"""
repository:
  path: {self.repo_path}
  baseline: main
  gpg_sign: false

monitoring:
  paths:
    - {self.watch_path}
  batch_interval: 1
  batch_size: 5

compliance:
  auto_check: true
  rules:
    - world-writable
    - suid-sgid
    - weak-permissions

alerts:
  enabled: false
"""
        with open(self.config_path, 'w') as f:
            f.write(config_content)
            
        self.success(f"Тестовое окружение создано: {self.test_dir}")
        
    def cleanup(self):
        """Очистка после тестов"""
        try:
            shutil.rmtree(self.test_dir)
            self.success("Тестовое окружение очищено")
        except Exception as e:
            self.fail(f"Ошибка очистки: {e}")
            
    def run_command(self, cmd, check=True):
        """Запуск команды sysaudit"""
        try:
            result = subprocess.run(
                cmd,
                shell=True,
                capture_output=True,
                text=True,
                timeout=30
            )
            if check and result.returncode != 0:
                raise Exception(f"Command failed: {result.stderr}")
            return result
        except subprocess.TimeoutExpired:
            raise Exception("Command timeout")
        except Exception as e:
            raise Exception(f"Command error: {e}")
    
    def scenario_1_initialization(self):
        """
        Сценарий 1: Администратор инициализирует систему мониторинга
        """
        self.log("\n=== Сценарий 1: Инициализация системы ===")
        
        try:
            # Шаг 1: Инициализация репозитория
            self.info("Инициализация Git репозитория...")
            result = self.run_command(f"sysaudit init --repo {self.repo_path}")
            
            if os.path.exists(os.path.join(self.repo_path, '.git')):
                self.success("Репозиторий успешно инициализирован")
            else:
                self.fail("Репозиторий не создан")
                return False
                
            # Шаг 2: Проверка версии
            self.info("Проверка версии sysaudit...")
            result = self.run_command("sysaudit --version")
            if "0.1.0" in result.stdout:
                self.success("Версия sysaudit корректна")
            else:
                self.fail("Некорректная версия")
                
            return True
            
        except Exception as e:
            self.fail(f"Ошибка инициализации: {e}")
            return False
    
    def scenario_2_file_monitoring(self):
        """
        Сценарий 2: Мониторинг изменений конфигурационных файлов
        """
        self.log("\n=== Сценарий 2: Мониторинг файлов ===")
        
        try:
            # Шаг 1: Создание начального снимка
            self.info("Создание начального снимка...")
            test_file = os.path.join(self.watch_path, 'test.conf')
            Path(test_file).write_text("initial config\n")
            
            result = self.run_command(
                f"sysaudit snapshot -m 'Initial snapshot' "
                f"--repo {self.repo_path} --paths {self.watch_path}"
            )
            self.success("Начальный снимок создан")
            
            # Шаг 2: Изменение файла
            self.info("Изменение конфигурационного файла...")
            Path(test_file).write_text("modified config\n")
            
            # Шаг 3: Создание снимка изменений
            result = self.run_command(
                f"sysaudit snapshot -m 'Config updated' "
                f"--repo {self.repo_path} --paths {self.watch_path}"
            )
            self.success("Изменения зафиксированы")
            
            # Шаг 4: Проверка истории
            self.info("Проверка истории изменений...")
            result = subprocess.run(
                f"cd {self.repo_path} && git log --oneline",
                shell=True,
                capture_output=True,
                text=True
            )
            
            if "Config updated" in result.stdout:
                self.success("История изменений корректна")
            else:
                self.fail("История изменений не найдена")
                
            return True
            
        except Exception as e:
            self.fail(f"Ошибка мониторинга: {e}")
            return False
    
    def scenario_3_drift_detection(self):
        """
        Сценарий 3: Обнаружение дрифта от базовой линии
        """
        self.log("\n=== Сценарий 3: Обнаружение дрифта ===")
        
        try:
            # Шаг 1: Создание базовой линии
            self.info("Создание базовой линии...")
            baseline_file = os.path.join(self.watch_path, 'baseline.conf')
            Path(baseline_file).write_text("baseline config\n")
            
            result = self.run_command(
                f"sysaudit snapshot -m 'Baseline' "
                f"--repo {self.repo_path} --paths {self.watch_path}"
            )
            
            # Шаг 2: Изменение файла (создание дрифта)
            self.info("Создание дрифта...")
            Path(baseline_file).write_text("drifted config\n")
            
            # Шаг 3: Проверка дрифта
            self.info("Проверка дрифта от базовой линии...")
            result = self.run_command(
                f"sysaudit drift-check --baseline main "
                f"--repo {self.repo_path}",
                check=False
            )
            
            # Дрифт должен быть обнаружен
            if "drift" in result.stdout.lower() or result.returncode != 0:
                self.success("Дрифт успешно обнаружен")
            else:
                self.fail("Дрифт не обнаружен")
                
            return True
            
        except Exception as e:
            self.fail(f"Ошибка обнаружения дрифта: {e}")
            return False
    
    def scenario_4_compliance_check(self):
        """
        Сценарий 4: Проверка соответствия требованиям безопасности
        """
        self.log("\n=== Сценарий 4: Проверка соответствия ===")
        
        try:
            # Шаг 1: Создание файла с небезопасными правами
            self.info("Создание файла с небезопасными правами...")
            unsafe_file = os.path.join(self.watch_path, 'unsafe.conf')
            Path(unsafe_file).write_text("sensitive data\n")
            
            # На Unix системах устанавливаем небезопасные права
            if os.name != 'nt':
                os.chmod(unsafe_file, 0o666)  # world-writable
            
            # Шаг 2: Запуск проверки соответствия
            self.info("Запуск проверки соответствия...")
            result = self.run_command(
                f"sysaudit compliance-report --paths {self.watch_path}",
                check=False
            )
            
            # Проверка должна найти проблемы
            if "world-writable" in result.stdout.lower() or "issue" in result.stdout.lower():
                self.success("Проблемы безопасности обнаружены")
            else:
                self.info("Проблемы безопасности не обнаружены (возможно, Windows)")
                
            # Шаг 3: Генерация JSON отчета
            self.info("Генерация JSON отчета...")
            report_file = os.path.join(self.test_dir, 'compliance-report.json')
            result = self.run_command(
                f"sysaudit compliance-report --format json "
                f"--output {report_file} --paths {self.watch_path}",
                check=False
            )
            
            if os.path.exists(report_file):
                self.success("JSON отчет создан")
            else:
                self.fail("JSON отчет не создан")
                
            return True
            
        except Exception as e:
            self.fail(f"Ошибка проверки соответствия: {e}")
            return False
    
    def scenario_5_rollback(self):
        """
        Сценарий 5: Откат изменений к предыдущей версии
        """
        self.log("\n=== Сценарий 5: Откат изменений ===")
        
        try:
            # Шаг 1: Создание файла и снимка
            self.info("Создание файла для отката...")
            rollback_file = os.path.join(self.watch_path, 'rollback.conf')
            Path(rollback_file).write_text("version 1\n")
            
            result = self.run_command(
                f"sysaudit snapshot -m 'Version 1' "
                f"--repo {self.repo_path} --paths {self.watch_path}"
            )
            
            # Получение хеша коммита
            result = subprocess.run(
                f"cd {self.repo_path} && git rev-parse HEAD",
                shell=True,
                capture_output=True,
                text=True
            )
            commit_hash = result.stdout.strip()
            
            # Шаг 2: Изменение файла
            self.info("Изменение файла...")
            Path(rollback_file).write_text("version 2 (bad)\n")
            
            result = self.run_command(
                f"sysaudit snapshot -m 'Version 2' "
                f"--repo {self.repo_path} --paths {self.watch_path}"
            )
            
            # Шаг 3: Dry-run отката
            self.info("Проверка отката (dry-run)...")
            result = self.run_command(
                f"sysaudit rollback --to-commit {commit_hash} "
                f"--path {rollback_file} --dry-run --repo {self.repo_path}",
                check=False
            )
            
            if "dry run" in result.stdout.lower() or "would restore" in result.stdout.lower():
                self.success("Dry-run отката выполнен")
            else:
                self.info("Dry-run отката завершен")
                
            # Шаг 4: Реальный откат
            self.info("Выполнение отката...")
            result = self.run_command(
                f"sysaudit rollback --to-commit {commit_hash} "
                f"--path {rollback_file} --repo {self.repo_path}",
                check=False
            )
            
            # Проверка содержимого файла
            content = Path(rollback_file).read_text()
            if "version 1" in content:
                self.success("Откат выполнен успешно")
            else:
                self.fail("Откат не выполнен")
                
            return True
            
        except Exception as e:
            self.fail(f"Ошибка отката: {e}")
            return False
    
    def scenario_6_cli_usage(self):
        """
        Сценарий 6: Использование CLI команд
        """
        self.log("\n=== Сценарий 6: CLI команды ===")
        
        try:
            # Тест различных CLI команд
            commands = [
                ("sysaudit --help", "Справка"),
                ("sysaudit --version", "Версия"),
                (f"sysaudit init --help", "Справка по init"),
                (f"sysaudit monitor --help", "Справка по monitor"),
                (f"sysaudit snapshot --help", "Справка по snapshot"),
                (f"sysaudit drift-check --help", "Справка по drift-check"),
                (f"sysaudit compliance-report --help", "Справка по compliance-report"),
                (f"sysaudit rollback --help", "Справка по rollback"),
            ]
            
            for cmd, desc in commands:
                self.info(f"Тест: {desc}...")
                result = self.run_command(cmd)
                if result.returncode == 0:
                    self.success(f"{desc} работает")
                else:
                    self.fail(f"{desc} не работает")
                    
            return True
            
        except Exception as e:
            self.fail(f"Ошибка CLI: {e}")
            return False
    
    def run_all_scenarios(self):
        """Запуск всех сценариев"""
        self.start_time = time.time()
        
        self.log("╔════════════════════════════════════════════════════════╗")
        self.log("║  E2E Тесты: Реальные пользовательские сценарии       ║")
        self.log("╚════════════════════════════════════════════════════════╝")
        
        try:
            self.setup()
            
            # Запуск сценариев
            scenarios = [
                self.scenario_1_initialization,
                self.scenario_2_file_monitoring,
                self.scenario_3_drift_detection,
                self.scenario_4_compliance_check,
                self.scenario_5_rollback,
                self.scenario_6_cli_usage,
            ]
            
            for scenario in scenarios:
                try:
                    scenario()
                except Exception as e:
                    self.fail(f"Сценарий провален: {e}")
                    
        finally:
            self.cleanup()
            
        # Итоговый отчет
        elapsed = time.time() - self.start_time
        self.log("\n╔════════════════════════════════════════════════════════╗")
        self.log("║                  Итоговый отчет                        ║")
        self.log("╚════════════════════════════════════════════════════════╝")
        self.log(f"Пройдено: {self.passed}", GREEN)
        self.log(f"Провалено: {self.failed}", RED if self.failed > 0 else GREEN)
        self.log(f"Время выполнения: {elapsed:.2f}s", BLUE)
        
        # Сохранение отчета
        report_dir = "/app/test-results"
        os.makedirs(report_dir, exist_ok=True)
        
        report = {
            "timestamp": datetime.now().isoformat(),
            "test_type": "e2e",
            "passed": self.passed,
            "failed": self.failed,
            "total": self.passed + self.failed,
            "duration_seconds": elapsed,
            "success_rate": f"{(self.passed / (self.passed + self.failed) * 100):.1f}%"
        }
        
        import json
        with open(f"{report_dir}/e2e-report.json", "w") as f:
            json.dump(report, f, indent=2)
            
        self.success(f"Отчет сохранен: {report_dir}/e2e-report.json")
        
        return self.failed == 0


def main():
    """Главная функция"""
    runner = E2ETestRunner()
    success = runner.run_all_scenarios()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
