from typing import List
from ninja import Router
from django.contrib.auth.hashers import make_password
from django.core.paginator import Paginator
from common.package.pagination import get_current_page_data
from common.package.schema import (
    NotFoundSchema,
    Message
)
from account.models import (
    Account
)
from account.schema.base import (
    AccountSchema,
    AccountResponseSchema,
    AccountPaginationResponseSchema
)


base_router = Router()

 
@base_router.post(
    "",
    auth=None,
    response={
        201: AccountSchema,
        404: NotFoundSchema
    }
)
def create_account(
    request,
    obj: AccountSchema):
    try:
        payload_dict = obj.dict()
        payload_dict['type'] = 'manager'
        payload_dict['password'] = make_password(obj.dict().get('password'))
        Account.objects.create(**payload_dict)
        return 201, obj
    except:
        return 404, {'message': '이미 존재하는 아이디 입니다.'}


@base_router.get(
    "",
    auth=None,
    response={
        200: AccountPaginationResponseSchema
    }
)
def get_accounts(
    request,
    page: int = 1
):
    qs = Account.objects.filter(type='manager')

    paginator = Paginator(qs, 10)
    current_page = get_current_page_data(page, paginator)

    return {
        'results': list(current_page),
        'current_page': current_page.number,
        'total_pages': paginator.num_pages,
        'per_page': paginator.per_page,
        'total_items': paginator.count,
        'has_previous': current_page.has_previous(),
        'has_next': current_page.has_next()
    }


@base_router.get(
    "{account_id}",
    auth=None,
    response={
        200: AccountResponseSchema,
        404: NotFoundSchema
    }
)
def get_account(request, account_id):
    try:
        account = Account.objects.get(pk=account_id)
        return 200, account
    except Account.DoesNotExist as e:
        return 404, {"message": "Could not find account"}


@base_router.delete(
    "{account_id}",
    auth=None,
    response={
        200: None,
        404: NotFoundSchema
    }
)
def delete_account(request, account_id: int):
    try:
        account = Account.objects.get(pk=account_id)
        account.delete()
        return 200
    except Account.DoesNotExist as e:
        return 404, {"message": "Could not find account"}
