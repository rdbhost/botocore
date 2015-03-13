
__author__ = 'David'
"""
requests will check for authenticated connections being redirected to a different domain, and strip the
authentication.

This makes sense, generally, but makes aws requests break, as amazon does this on authenticated requests.

So, this little module, imported after yieldfrom.requests wherever it is imported, will patch the relevant
methods to allow authenticated requests to be redirected.


This could be improved to only allow redirection to 'similar' domains.

"""

import yieldfrom.requests.sessions
def null_method(self, prep_req=None, resp=None): return
setattr(yieldfrom.requests.sessions.SessionRedirectMixin, 'rebuild_auth', null_method)
