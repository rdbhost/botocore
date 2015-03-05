
__author__ = 'David'

import yieldfrom.requests.sessions
def null_method(self, prep_req=None, resp=None): return
setattr(yieldfrom.requests.sessions.SessionRedirectMixin, 'rebuild_auth', null_method)
