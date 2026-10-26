"""One error type for the whole API. It always becomes a JSON body like
{"error": {"code": "out_of_range", "message": "...", "field": "latitude"}}.
The frontend uses the code (not the message) to show the right text in the farmer's language.
"""


class ApiError(Exception):
    def __init__(self, status, code, message, field=None, retry_after=None):
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message
        self.field = field
        self.retry_after = retry_after

    def body(self):
        err = {"code": self.code, "message": self.message}
        if self.field:
            err["field"] = self.field
        if self.retry_after is not None:
            err["retry_after"] = self.retry_after
        return {"error": err}
