from proper.concerns import Authentication as ProperAuthentication

from [[app_name]].models import Session


class Authentication(ProperAuthentication):
    Session = Session
