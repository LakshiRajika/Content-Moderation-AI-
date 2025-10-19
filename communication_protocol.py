# communication_protocol.py
"""
Simple Message Bus for Agent-to-Agent communication (in-process).
Very small, synchronous implementation — suitable for demo/prototype.
"""
from typing import Any, Dict

class MessageBus:
    def __init__(self):
        # messages keyed by receiver id (latest wins)
        self._messages: Dict[str, Dict[str, Any]] = {}

    def send(self, sender: str, receiver: str, data: Any) -> None:
        """Send a message from sender -> receiver."""
        self._messages[receiver] = {"from": sender, "data": data}

    def receive(self, receiver: str) -> Any:
        """Retrieve the latest message for `receiver`. Returns the `data` or None."""
        msg = self._messages.get(receiver)
        return msg["data"] if msg else None

    def clear(self, receiver: str) -> None:
        """Optional: clear stored message for a receiver."""
        if receiver in self._messages:
            del self._messages[receiver]
