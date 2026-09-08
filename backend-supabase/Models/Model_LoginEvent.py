from Db import TableModel


class _ModelLoginEvent(TableModel):
    def __init__(self):
        super().__init__("login_events")


Model_LoginEvent = _ModelLoginEvent()
