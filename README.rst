botocore
========

**My Apologies**

I had intended to keep this up-to-date through version 1 of boto/botocore.   Unfortunately, I seem to
have overcommitted myself.   There is a lot of development effort and feature changes in the 250+ commits
in boto/botocore not merged here, and I do not expect to find the time to catchup.

The time I do find to commit to asyncio stuff, and the yieldfrom project, will go to the lower-level libraries 
such as yieldfromHttplib, yieldfromUrllib3, and yieldfromRequests.  Requests is much more widely used than 
Botocore, and should get more time. I should note that yieldfromBotocore does depend on all of these, and 
development there will, thus, indirectly support yieldfromBotocore.  


If any of you need this updated, feel free to fork and run with it.


-------------------

This is an asyncio port of botocore.  The content below is from boto/botocore.

-------------------



A low-level interface to a growing number of Amazon Web Services. The
botocore package is the foundation for
`AWS-CLI <https://github.com/aws/aws-cli>`__.

`Documentation <https://botocore.readthedocs.org/en/latest/>`__

**WARNING**

Botocore is currently under a developer preview, and its API is subject
to change prior to a GA (1.0) release.  Until botocore reaches a 1.0 release,
backwards compatibility is not guaranteed. The plan for GA is as follows:

1. **DONE** Add client interface to botocore.
2. **DONE** Add pending deprecation warnings to the use of ``Service`` and ``Operation``
   objects (added in version 0.96.0).
3. **DONE** Change the pending deprecation warnings to deprecation warnings
   (added in version 0.99.0).
4. **DONE** Create a
   `clients-only <https://github.com/boto/botocore/tree/clients-only>`_
   branch that completely removes ``Service`` and ``Operation`` objects.
5. **DONE** Changing the deprecation warnings to ImminentRemovalWarning.  These will
   now print to stderr by default so the warnings are more visible
   (added in version 0.104.0).
6. **DONE** Merge ``clients-only`` branch to develop branch, and make an alpha
   release of botocore (v 1.0.0a1 released on 5/21/15).
7. Make a beta release of botocore.
8. Make GA (1.0.0) release of botocore.

The project is currently at step **7**.
