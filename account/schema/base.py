from ninja import Schema
from typing import List
from common.package.schema import PaginationSchema


class AccountSchema(Schema):
    name: str
    email: str
    phone_number: str
    username: str
    password: str


class AccountResponseSchema(Schema):
    id: int
    name: str
    email: str
    phone_number: str
    username: str


class AccountPaginationResponseSchema(PaginationSchema):
    results: List[AccountResponseSchema]