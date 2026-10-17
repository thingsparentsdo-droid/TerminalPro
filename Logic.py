import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
import os
import sys
import Gui as gui
import random
import json
import requests
from pathlib import Path
import hashlib
import hmac
import re
import time

MAX_PING_WORKERS = 32

SUGGESTION_GROUPS = ("terminal", "cmd", "powershell")
SUGGESTION_FILE = "command_suggestions.json"


def _load_suggestions() -> dict[str, list[dict[str, str]]]:
    app_directory = Path(getattr(sys, "_MEIPASS", Path(__file__).parent))
    suggestion_path = app_directory / SUGGESTION_FILE
    with suggestion_path.open(encoding="utf-8") as suggestion_file:
        suggestions = json.load(suggestion_file)

    if not isinstance(suggestions, dict) or any(
        not isinstance(suggestions.get(group), list) for group in SUGGESTION_GROUPS
    ):
        raise ValueError(f"Invalid command suggestion data in {suggestion_path}")

    for group in SUGGESTION_GROUPS:
        for item in suggestions[group]:
            if not isinstance(item, dict) or any(
                not isinstance(item.get(field), str)
                for field in ("insertion", "description", "syntax")
            ):
                raise ValueError(f"Invalid command suggestion data in {suggestion_path}")
    return suggestions


_SUGGESTION_GROUPS = _load_suggestions()
COMMAND_SUGGESTIONS = tuple(
    (item["insertion"], item["description"], item["syntax"])
    for group in SUGGESTION_GROUPS
    for item in _SUGGESTION_GROUPS[group]
)
POWERSHELL_COMMAND_NAMES = frozenset(
    item["insertion"].strip().casefold()
    for item in _SUGGESTION_GROUPS["powershell"]
)
POWERSHELL_COMMAND_NAMES |= frozenset({"gl", "pwd"})


def _uses_powershell(command: str) -> bool:
    match = re.match(r"\s*([^\s|;&]+)", command)
    return match is not None and match.group(1).casefold() in POWERSHELL_COMMAND_NAMES


def _identity_path() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve()
    return Path(__file__).resolve()


def user_data_path() -> Path:
    app_data = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "TerminalPro"
    app_data.mkdir(parents=True, exist_ok=True)
    return app_data / "userData.json"


class Email:
    def __init__(self, email: str):
        if email.count('@') != 1 or email.startswith('@') or email.endswith('@'):
            raise ValueError("Invalid email format")
        if '.' not in email.split('@')[1]:
            raise ValueError("Invalid email format")
        self.email = email
    

class User:
    def __init__(self, username: str, password: str, email: str, firstName: str, lastName: str,):
        self.username = username
        self.__password = hashlib.sha256(password.encode()).hexdigest()
        self.email = Email(email)
        self.first_name = firstName
        self.last_name = lastName
        self.__OSSID = hashlib.sha256(self.extractOSSID(_identity_path()).encode()).hexdigest()

    def extractOSSID(self, path: Path) -> str:
        parts = str(path).replace("\\", "/").split("/")
        for index, part in enumerate(parts[:-1]):
            if part.casefold() == "users":
                return parts[index + 1]
        raise ValueError("Path does not contain a Windows Users directory")
    
    def logIn(self, password: str) -> bool:
        password_hash = hashlib.sha256(password.encode()).hexdigest()
        identity_hash = hashlib.sha256(self.extractOSSID(_identity_path()).encode()).hexdigest()
        return hmac.compare_digest(self.__password, password_hash) and hmac.compare_digest(
            self.__OSSID, identity_hash
        )
    
    def raiseUserLockDown(self,password: str,OSSID: str) -> None:
        self.__password = hashlib.sha256(self.__password.encode()).hexdigest()
        raise PermissionError("User is locked out due to invalid login attempts.")
    
    def _userDataRecord(self) -> dict[str, str]:
        return {
            "username": self.username,
            "password": self.__password,
            "email": self.email.email,
            "first_name": self.first_name,
            "last_name": self.last_name,
            "OSSID": self.__OSSID
        }

    def saveUserData(self, file_path: str | Path) -> None:
        path = Path(file_path)
        if path.exists():
            with path.open(encoding="utf-8") as f:
                existing_data = json.load(f)
            if isinstance(existing_data, dict):
                users = [existing_data]
            elif isinstance(existing_data, list) and all(
                isinstance(record, dict) for record in existing_data
            ):
                users = existing_data
            else:
                raise ValueError("Stored user data is invalid.")
        else:
            users = []

        user_data = self._userDataRecord()
        for index, existing_user in enumerate(users):
            if existing_user.get("username") == self.username:
                users[index] = user_data
                break
        else:
            users.append(user_data)

        with path.open("w", encoding="utf-8") as f:
            json.dump(users, f)

    @classmethod
    def loadUserData(cls, file_path: str | Path, username: str | None = None) -> "User":
        with open(file_path, encoding="utf-8") as f:
            stored_data = json.load(f)

        required_fields = ("username", "password", "email", "first_name", "last_name", "OSSID")
        if isinstance(stored_data, dict):
            users = [stored_data]
        elif isinstance(stored_data, list) and all(isinstance(record, dict) for record in stored_data):
            users = stored_data
        else:
            raise ValueError("Stored user data is invalid.")

        if any(
            any(not isinstance(user_data.get(field), str) for field in required_fields)
            for user_data in users
        ):
            raise ValueError("Stored user data is invalid.")

        if username is None:
            if len(users) != 1:
                raise ValueError("A username is required when multiple accounts exist.")
            user_data = users[0]
        else:
            user_data = next(
                (record for record in users if record["username"] == username),
                None,
            )
            if user_data is None:
                raise KeyError(username)

        user = cls.__new__(cls)
        user.username = user_data["username"]
        user.__password = user_data["password"]
        user.email = Email(user_data["email"])
        user.first_name = user_data["first_name"]
        user.last_name = user_data["last_name"]
        user.__OSSID = user_data["OSSID"]
        return user

class TermainalSession:
    def __init__(self, user: User,password: str):
        self.user = user
        if not self.user.logIn(password):
            raise PermissionError("Invalid username or password.")

    def _ping_target(self, target: str) -> tuple[str, float | None, bool, bool]:
        try:
            result = subprocess.run(["ping", target], capture_output=True, text=True)
            output = result.stdout
            windows_average = re.search(
                r"Average\s*=\s*(\d+(?:\.\d+)?)\s*ms", output, re.IGNORECASE
            )
            average = float(windows_average.group(1)) if windows_average else None
            packet_loss = re.search(
                r"Lost\s*=\s*\d+\s*\((\d+(?:\.\d+)?)%\s*loss\)",
                output,
                re.IGNORECASE,
            )
            degraded = result.returncode != 0 or (
                packet_loss is not None and float(packet_loss.group(1)) > 0
            )
            return output, average, degraded, False
        except Exception as error:
            return f"Error pinging {target}: {error}", None, True, True

    def ping(self, targets: str | list[str]) -> str:
        if isinstance(targets, str):
            target = targets
            output, _, _, errored = self._ping_target(target)
            if errored:
                return output.removeprefix(f"Error pinging {target}: ")
            return output

        if not targets:
            return "Error: No targets specified for ping."

        results = [""] * len(targets)
        average_times = []
        cpu_count = os.cpu_count() or 1
        concurrency = min(len(targets), max(1, min(MAX_PING_WORKERS, cpu_count * 4)))
        next_target = 0

        with ThreadPoolExecutor(max_workers=MAX_PING_WORKERS) as executor:
            while next_target < len(targets):
                batch_end = min(next_target + concurrency, len(targets))
                futures = {
                    executor.submit(self._ping_target, targets[index]): index
                    for index in range(next_target, batch_end)
                }
                degraded_batch = False

                for future in as_completed(futures):
                    index = futures[future]
                    output, average, degraded, errored = future.result()
                    results[index] = (
                        output
                        if errored
                        else f"Results for {targets[index]}:\n{output}"
                    )
                    if average is not None:
                        average_times.append(average)
                    degraded_batch = degraded_batch or degraded

                next_target = batch_end
                if degraded_batch:
                    concurrency = max(1, concurrency // 2)
                else:
                    concurrency = min(MAX_PING_WORKERS, concurrency + 1)

        if average_times:
            overall_average = sum(average_times) / len(average_times)
            results.append(
                f"Average ping time across {len(average_times)} target(s): "
                f"{overall_average:.2f} ms"
            )


        else:
            results.append("No ping statistics were available to average.")
        return "\n".join(results)

    def runCommand(self, command: str) -> str:
        if command == "clear" or command == "cls":
            gui.clear()
            return ""
        elif command == "/exit":
            self.killSession()
            return ""
        elif command.startswith("cd "):
            target_dir = command[3:].strip()
            if (target_dir.startswith('"') and target_dir.endswith('"')) or \
               (target_dir.startswith("'") and target_dir.endswith("'")):
                target_dir = target_dir[1:-1]
            
            try:
                os.chdir(target_dir)
                return f"Current directory: {os.getcwd()}"
            except Exception as e:
                return str(e)

        elif command.startswith("/ping "):
            target = command[5:].strip()
            if not target:
                return "Error: No target specified for ping."
            return self.ping(target)

        elif command.startswith("/ping: "):
            targets = []
            command = command[7:].strip()
            for target in command.split(","):
                target = target.strip()
                if target:
                    targets.append(target)
            return self.ping(targets)

        elif command.startswith("hash:"):
            target = command[5:].strip()
            if not target:
                return "Error: No target specified for hashing."
            try:
                with open(target, "rb") as f:
                    file_data = f.read()
                    sha256_hash = hashlib.sha256(file_data).hexdigest()
                    return f"SHA-256 hash of {target}: {sha256_hash}"
            except Exception as e:
                return str(e)

        elif command.startswith("hashtext:"):
            text = command[9:].strip()
            if not text:
                return "Error: No text specified for hashing."
            sha256_hash = hashlib.sha256(text.encode()).hexdigest()
            return f"SHA-256 hash of the provided text: {sha256_hash}"

        elif command.startswith("httpget:"):
            url = command[8:].strip()
            if not url:
                return "Error: No URL specified for HTTP GET request."
            try:
                response = requests.get(url)
                response.raise_for_status()
                return f"HTTP GET request to {url} succeeded with status code {response.status_code}.\nResponse content:\n{response.text}"
            except requests.exceptions.RequestException as e:
                return f"HTTP GET request to {url} failed: {e}"

        elif command.startswith("/download"):
            url = command[9:].strip()
            if not url:
                return "Error: No URL specified for download."
            try:
                response = requests.get(url, stream=True)
                response.raise_for_status()
                filename = url.split("/")[-1] or "downloaded_file"
                with open(filename, "wb") as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        f.write(chunk)
                return f"Downloaded {filename} from {url} successfully."
            except requests.exceptions.RequestException as e:
                return f"Download from {url} failed: {e}"

        elif command.startswith("randint: "):
            numbers = command[9:].strip().split(",")
            if len(numbers) != 2:
                return "Error: Provide exactly two integers, for example: randint: 1,10"
            try:
                num1, num2 = (int(number.strip()) for number in numbers)
                return str(random.randint(num1, num2))
            except ValueError:
                return "Error: Both randint bounds must be integers."

        elif command.startswith("randnum:"):
            numbers = command[8:].strip().split(",")
            if len(numbers) != 2:
                return "Error: Provide exactly two numbers, for example: randnum: 1,10"
            try:
                num1, num2 = (float(number.strip()) for number in numbers)
                return str(random.uniform(num1, num2))
            except ValueError:
                return "Error: Both randnum bounds must be numbers."

        elif command.startswith("randrange:"):
            numbers = command[10:].strip().split(",")
            if not 1 <= len(numbers) <= 3:
                return "Error: Provide one to three integers, for example: randrange: 1,10,2"
            try:
                bounds = [int(number.strip()) for number in numbers]
                return str(random.randrange(*bounds))
            except ValueError:
                return "Error: Randrange bounds must be integers."
            except (TypeError, OverflowError):
                return "Error: Invalid randrange bounds."

        elif command.startswith("choice:"):
            choices = [choice.strip() for choice in command[7:].split(",") if choice.strip()]
            if not choices:
                return "Error: Provide at least one choice, for example: choice: red,blue,green"
            return random.choice(choices)

        elif command.startswith("#folder "):
            parts = command[6:].strip().split("@", 1)
            if len(parts) != 2:
                return "Error: Provide a folder name and path separated by @."
            file, path = (part.strip() for part in parts)
            if (path.startswith('"') and path.endswith('"')) or \
                           (path.startswith("'") and path.endswith("'")):
                            path = path[1:-1]
                        
            try:
                os.chdir(path)
                self.runCommand(f"mkdir {file}")
            except Exception as e:
                return str(e)

        elif command.startswith("/sleep") or command.startswith("/wait"):
            try:
                parts = command.split(maxsplit=1)
                if len(parts) != 2:
                    return "Please specify an amount of time to delay."
                seconds = int(parts[1].strip())
                time.sleep(seconds)
                return f"Delayed {seconds} seconds."
            except ValueError:
                return "Please specify an amount of time to delay."
            
        elif _uses_powershell(command):
            try:
                result = subprocess.run(
                    [
                        "powershell.exe",
                        "-NoLogo",
                        "-NoProfile",
                        "-NonInteractive",
                        "-Command",
                        "$ErrorActionPreference = 'Stop'; " + command,
                    ],
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                )
                output = result.stdout
                if result.stderr:
                    output += ("\n" if output else "") + result.stderr
                if result.returncode and not output:
                    return f"PowerShell command failed with exit code {result.returncode}."
                return output
            except OSError as error:
                return f"Unable to run PowerShell command: {error}"
        else:
            try:
                result = subprocess.run(command, shell=True, capture_output=True, text=True)
                return result.stdout
            except Exception as e:
                return str(e)
    def killSession(self) -> None:
        gui.printOutput("Session terminated.")
        self.user.saveUserData(user_data_path())
        sys.exit(0)
