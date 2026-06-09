from __future__ import annotations


class ContentAssetPublishError(ValueError):
    def __init__(self, reason_code: str, message: str) -> None:
        super().__init__(message)
        self.reason_code = reason_code


class ContentAssetNotEditableError(ValueError):
    pass


class ContentAssetAlreadyDraftError(ValueError):
    pass


class ContentAssetReferencedByTemplatesError(ValueError):
    def __init__(self, templates: list[dict[str, str]]) -> None:
        self.referencing_templates = templates
        super().__init__("Content asset is referenced by published templates.")
