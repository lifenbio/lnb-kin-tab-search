from ninja import Schema


class LoginSchema(Schema):
    username: str
    password: str
    persist: bool = None
    page: str = 'base'


class FindIdSchema(Schema):
    name: str
    phone_number: str


class FindPWDSchema(Schema):
    username: str
    name: str
    phone_number: str
