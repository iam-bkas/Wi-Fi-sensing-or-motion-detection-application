import subprocess
import re
import time
from typing import Iterator, Optional


class WindowsWlanSignalSource:
    def __init__(self, interface: Optional[str] = None):
        self.interface = interface

    def read(self) -> int:
        p = subprocess.run(["netsh", "wlan", "show", "interfaces"], capture_output=True, text=True)
        out = p.stdout
        if self.interface:
            blocks = re.split(r"\n\s*\n", out)
            target = None
            for b in blocks:
                mname = re.search(r"^\s*Name\s*:\s*(.+)$", b, re.M)
                if mname and mname.group(1).strip() == self.interface:
                    target = b
                    break
            if target is None:
                raise RuntimeError("interface not found")
            m = re.search(r"Signal\s*:\s*(\d+)\s*%", target)
        else:
            m = re.search(r"Signal\s*:\s*(\d+)\s*%", out)
        if not m:
            # Check if connected
            if "State" in out and "disconnected" in out:
                 raise RuntimeError("WiFi is disconnected. Please connect to a network.")
            raise RuntimeError("signal not found in netsh output")
        return int(m.group(1))

    def stream(self, interval_s: float) -> Iterator[int]:
        while True:
            yield self.read()
            time.sleep(interval_s)

