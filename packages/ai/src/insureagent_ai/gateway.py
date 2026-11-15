class ModelUnavailable(RuntimeError):
    """No approved model and privacy pipeline configured."""


class DisabledModelGateway:
    """Fail closed; never sends prompts to an external provider or logs their contents."""

    async def generate(self, text: str) -> str:
        raise ModelUnavailable("Model calls disabled until privacy and provider validation")
