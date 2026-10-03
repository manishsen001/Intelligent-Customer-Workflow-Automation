"""Task Automation Workflow Module."""

import json
import shutil
import subprocess
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd
import requests

from src.config.logging_config import logger
from src.config.settings import settings


@dataclass
class TaskResult:
    """Result of a task execution."""

    success: bool
    output: Any
    error: str | None = None
    execution_time: float = 0.0


class TaskAutomation:
    """Handles general task automation operations."""

    def __init__(self, working_dir: Path | None = None):
        self.working_dir = working_dir or settings.DATA_DIR
        self.working_dir.mkdir(parents=True, exist_ok=True)

    def run_script(self, script_path: str, args: list[str] | None = None) -> TaskResult:
        """Execute a Python script or shell command."""
        import time

        start = time.time()

        try:
            if script_path.endswith(".py"):
                cmd = ["python", script_path] + (args or [])
            else:
                cmd = script_path.split() + (args or [])

            result = subprocess.run(
                cmd, cwd=self.working_dir, capture_output=True, text=True, timeout=300
            )

            execution_time = time.time() - start

            if result.returncode == 0:
                return TaskResult(
                    success=True, output=result.stdout, execution_time=execution_time
                )
            else:
                return TaskResult(
                    success=False,
                    output=result.stderr,
                    error=f"Script exited with code {result.returncode}",
                    execution_time=execution_time,
                )

        except subprocess.TimeoutExpired:
            return TaskResult(
                success=False,
                output="",
                error="Script execution timed out (5 minutes)",
                execution_time=time.time() - start,
            )
        except Exception as e:
            logger.error(f"Script execution error: {e}")
            return TaskResult(
                success=False,
                output="",
                error=str(e),
                execution_time=time.time() - start,
            )

    def file_operation(self, operation: str, **kwargs) -> TaskResult:
        """Perform file operations: read, write, copy, move, delete, list."""
        import time

        start = time.time()

        try:
            if operation == "read":
                path = self.working_dir / kwargs.get("path", "")
                if not path.exists():
                    return TaskResult(
                        success=False, output="", error=f"File not found: {path}"
                    )
                content = path.read_text(encoding=kwargs.get("encoding", "utf-8"))
                return TaskResult(
                    success=True, output=content, execution_time=time.time() - start
                )

            elif operation == "write":
                path = self.working_dir / kwargs.get("path", "")
                content = kwargs.get("content", "")
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(content, encoding=kwargs.get("encoding", "utf-8"))
                return TaskResult(
                    success=True,
                    output=f"Written to {path}",
                    execution_time=time.time() - start,
                )

            elif operation == "copy":
                src = self.working_dir / kwargs.get("src", "")
                dst = self.working_dir / kwargs.get("dst", "")
                if not src.exists():
                    return TaskResult(
                        success=False, output="", error=f"Source not found: {src}"
                    )
                shutil.copy2(src, dst)
                return TaskResult(
                    success=True,
                    output=f"Copied {src} to {dst}",
                    execution_time=time.time() - start,
                )

            elif operation == "move":
                src = self.working_dir / kwargs.get("src", "")
                dst = self.working_dir / kwargs.get("dst", "")
                if not src.exists():
                    return TaskResult(
                        success=False, output="", error=f"Source not found: {src}"
                    )
                shutil.move(str(src), str(dst))
                return TaskResult(
                    success=True,
                    output=f"Moved {src} to {dst}",
                    execution_time=time.time() - start,
                )

            elif operation == "delete":
                path = self.working_dir / kwargs.get("path", "")
                if not path.exists():
                    return TaskResult(
                        success=False, output="", error=f"File not found: {path}"
                    )
                if path.is_dir():
                    shutil.rmtree(path)
                else:
                    path.unlink()
                return TaskResult(
                    success=True,
                    output=f"Deleted {path}",
                    execution_time=time.time() - start,
                )

            elif operation == "list":
                path = self.working_dir / kwargs.get("path", ".")
                pattern = kwargs.get("pattern", "*")
                files = list(path.glob(pattern))
                output = [
                    {
                        "name": f.name,
                        "type": "dir" if f.is_dir() else "file",
                        "size": f.stat().st_size,
                    }
                    for f in files
                ]
                return TaskResult(
                    success=True, output=output, execution_time=time.time() - start
                )

            else:
                return TaskResult(
                    success=False, output="", error=f"Unknown operation: {operation}"
                )

        except Exception as e:
            logger.error(f"File operation error: {e}")
            return TaskResult(
                success=False,
                output="",
                error=str(e),
                execution_time=time.time() - start,
            )

    def data_processing(self, operation: str, **kwargs) -> TaskResult:
        """Process data files: CSV, JSON, Excel."""
        import time

        start = time.time()

        try:
            if operation == "read_csv":
                path = self.working_dir / kwargs.get("path", "")
                df = pd.read_csv(path)
                return TaskResult(
                    success=True,
                    output=df.to_dict("records"),
                    execution_time=time.time() - start,
                )

            elif operation == "write_csv":
                path = self.working_dir / kwargs.get("path", "")
                data = kwargs.get("data", [])
                df = pd.DataFrame(data)
                df.to_csv(path, index=False)
                return TaskResult(
                    success=True,
                    output=f"Written {len(data)} rows to {path}",
                    execution_time=time.time() - start,
                )

            elif operation == "read_json":
                path = self.working_dir / kwargs.get("path", "")
                with open(path) as f:
                    data = json.load(f)
                return TaskResult(
                    success=True, output=data, execution_time=time.time() - start
                )

            elif operation == "write_json":
                path = self.working_dir / kwargs.get("path", "")
                data = kwargs.get("data", {})
                path.parent.mkdir(parents=True, exist_ok=True)
                with open(path, "w") as f:
                    json.dump(data, f, indent=2)
                return TaskResult(
                    success=True,
                    output=f"Written JSON to {path}",
                    execution_time=time.time() - start,
                )

            elif operation == "read_excel":
                path = self.working_dir / kwargs.get("path", "")
                sheet = kwargs.get("sheet", 0)
                df = pd.read_excel(path, sheet_name=sheet)
                return TaskResult(
                    success=True,
                    output=df.to_dict("records"),
                    execution_time=time.time() - start,
                )

            elif operation == "write_excel":
                path = self.working_dir / kwargs.get("path", "")
                data = kwargs.get("data", [])
                df = pd.DataFrame(data)
                df.to_excel(path, index=False)
                return TaskResult(
                    success=True,
                    output=f"Written {len(data)} rows to {path}",
                    execution_time=time.time() - start,
                )

            elif operation == "transform":
                data = kwargs.get("data", [])
                df = pd.DataFrame(data)

                # Apply transformations
                if "filter" in kwargs:
                    for col, val in kwargs["filter"].items():
                        df = df[df[col] == val]

                if "select" in kwargs:
                    df = df[kwargs["select"]]

                if "groupby" in kwargs:
                    agg = kwargs.get("agg", "sum")
                    df = df.groupby(kwargs["groupby"]).agg(agg).reset_index()

                return TaskResult(
                    success=True,
                    output=df.to_dict("records"),
                    execution_time=time.time() - start,
                )

            else:
                return TaskResult(
                    success=False, output="", error=f"Unknown operation: {operation}"
                )

        except Exception as e:
            logger.error(f"Data processing error: {e}")
            return TaskResult(
                success=False,
                output="",
                error=str(e),
                execution_time=time.time() - start,
            )

    def web_scraping(
        self, url: str, selector: str | None = None, **kwargs
    ) -> TaskResult:
        """Scrape data from a website."""
        import time

        start = time.time()

        try:
            headers = kwargs.get(
                "headers",
                {
                    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
                },
            )

            response = requests.get(url, headers=headers, timeout=30)
            response.raise_for_status()

            if selector:
                from bs4 import BeautifulSoup

                soup = BeautifulSoup(response.text, "html.parser")
                elements = soup.select(selector)
                output: Any = [el.get_text(strip=True) for el in elements]
            else:
                output = response.text

            return TaskResult(
                success=True, output=output, execution_time=time.time() - start
            )

        except Exception as e:
            logger.error(f"Web scraping error: {e}")
            return TaskResult(
                success=False,
                output="",
                error=str(e),
                execution_time=time.time() - start,
            )

    def api_call(self, method: str, url: str, **kwargs) -> TaskResult:
        """Make HTTP API requests."""
        import time

        start = time.time()

        try:
            headers = kwargs.get("headers", {})
            params = kwargs.get("params", {})
            data = kwargs.get("data", None)
            json_data = kwargs.get("json", None)
            timeout = kwargs.get("timeout", 30)

            response = requests.request(
                method=method.upper(),
                url=url,
                headers=headers,
                params=params,
                data=data,
                json=json_data,
                timeout=timeout,
            )

            try:
                output = response.json()
            except ValueError:
                output = response.text

            if response.status_code < 400:
                return TaskResult(
                    success=True, output=output, execution_time=time.time() - start
                )
            else:
                return TaskResult(
                    success=False,
                    output=output,
                    error=f"HTTP {response.status_code}",
                    execution_time=time.time() - start,
                )

        except Exception as e:
            logger.error(f"API call error: {e}")
            return TaskResult(
                success=False,
                output="",
                error=str(e),
                execution_time=time.time() - start,
            )

    def schedule_task(
        self, task_name: str, schedule: str, action: str, **kwargs
    ) -> TaskResult:
        """Schedule a recurring task (using cron-like syntax)."""
        import time

        start = time.time()

        try:
            # Store scheduled task in a JSON file
            schedule_file = self.working_dir / "scheduled_tasks.json"

            if schedule_file.exists():
                with open(schedule_file) as f:
                    tasks = json.load(f)
            else:
                tasks = []

            task = {
                "name": task_name,
                "schedule": schedule,  # cron expression
                "action": action,
                "params": kwargs,
                "created_at": datetime.now().isoformat(),
                "enabled": True,
            }

            tasks.append(task)

            with open(schedule_file, "w") as f:
                json.dump(tasks, f, indent=2)

            return TaskResult(
                success=True,
                output=f"Task '{task_name}' scheduled with cron: {schedule}",
                execution_time=time.time() - start,
            )

        except Exception as e:
            logger.error(f"Schedule task error: {e}")
            return TaskResult(
                success=False,
                output="",
                error=str(e),
                execution_time=time.time() - start,
            )


def create_task_automation() -> TaskAutomation:
    """Factory function to create task automation instance."""
    return TaskAutomation()
