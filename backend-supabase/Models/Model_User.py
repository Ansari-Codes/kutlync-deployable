from Db import TableModel


class _ModelUser(TableModel):
    def __init__(self):
        super().__init__("authenticated")


Model_User = _ModelUser()
