from ninja import NinjaAPI
from common.package.jwt import JWTAuth
#from account.api import router as account_router
#from company.api import router as company_router
from common.api import router as common_router


api = NinjaAPI(auth=JWTAuth())


#api.add_router("/account/", account_router)
#api.add_router("/company/", company_router)
api.add_router("/common/", common_router)
#api.add_router("/cs/", cs_router)
#api.add_router("/notification/", notification_router)

@api.get("/hc", auth=None)
def health_check(request):
    return 200
