from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


class AIProviderError(RuntimeError):
    """Errore generato durante una chiamata al provider AI."""


@dataclass(slots=True, frozen=True)
class AIResponse:
    content: str
    model: str
    input_tokens: int | None = None
    output_tokens: int | None = None
    raw_response: Any | None = None


class AIProvider(ABC):
    """
    Interfaccia comune per tutti i provider AI.

    Claude, OpenAI o altri provider dovranno implementare
    esclusivamente il metodo generate().
    """

    @abstractmethod
    def generate(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int = 4096,
        temperature: float = 0.0,
    ) -> AIResponse:
        """
        Invia una richiesta al modello e restituisce il testo generato.

        Raises:
            AIProviderError: se la chiamata al provider fallisce.
        """
        raise NotImplementedError